#!/usr/bin/env python3
"""
PERMANENCE OS -- Document Ingestion System

Accepts multiple file types (text, URLs, PDF, Markdown, DOCX) and creates
Entity Graph nodes with full-text searchable storage.

Pipeline:
  1. Accept input (text, URL, or file path)
  2. Detect type automatically (by extension, URL pattern, or explicit param)
  3. Extract text content
  4. Extract metadata (title, word count, source, creation date)
  5. Chunk long documents into sections (max 2000 chars, paragraph boundaries)
  6. Create Entity Graph node (type: DOCUMENT)
  7. Store full text + chunks in SQLite (permanence_storage/documents.db)
  8. Return document ID + metadata

Design:
  - 60/30/10 rule: 60% deterministic SQLite ops, 30% rule-based routing,
    10% reserved for future AI-powered extraction
  - Graceful degradation: if pdftotext/python-docx unavailable, return error
  - try/except on all file reads and network calls
  - No emojis

Usage:
  python3 core/document_ingest.py --action ingest --source "https://example.com/article"
  python3 core/document_ingest.py --action ingest --source ./report.pdf
  python3 core/document_ingest.py --action list
  python3 core/document_ingest.py --action search --query "machine learning"
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sqlite3
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parents[1]
STORAGE_DIR = Path(
    os.getenv("PERMANENCE_STORAGE_DIR", str(BASE_DIR / "permanence_storage"))
)
DEFAULT_DB_PATH = str(STORAGE_DIR / "documents.db")

# Max chunk size in characters
MAX_CHUNK_SIZE = 2000


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    """Current UTC time as ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


def _gen_id() -> str:
    """Generate a 12-character hex ID."""
    return uuid.uuid4().hex[:12]


def _content_hash(text: str) -> str:
    """SHA-256 hash of text content for deduplication."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:32]


def _detect_source_type(source: str) -> str:
    """Detect source type from the source string."""
    if not source or not source.strip():
        return "text"

    source = source.strip()

    # URL detection
    parsed = urlparse(source)
    if parsed.scheme in ("http", "https"):
        return "url"

    # File extension detection
    lower = source.lower()
    if lower.endswith(".pdf"):
        return "pdf"
    elif lower.endswith(".md") or lower.endswith(".markdown"):
        return "markdown"
    elif lower.endswith(".docx"):
        return "docx"
    elif lower.endswith(".txt"):
        return "text_file"
    elif os.path.isfile(source):
        return "text_file"

    return "text"


# ---------------------------------------------------------------------------
# Text extraction
# ---------------------------------------------------------------------------

def _extract_from_url(url: str) -> dict[str, Any]:
    """Fetch and extract text from a URL."""
    try:
        import urllib.request
        import urllib.error

        req = urllib.request.Request(
            url,
            headers={"User-Agent": "PermanenceOS/1.0 DocumentIngest"},
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except urllib.error.URLError as exc:
        return {"ok": False, "error": f"Failed to fetch URL: {exc}"}
    except Exception as exc:
        return {"ok": False, "error": f"URL fetch error: {exc}"}

    # Strip HTML tags (simple heuristic, no AI)
    text = re.sub(r"<script[^>]*>.*?</script>", "", raw, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()

    # Extract title from original HTML
    title_match = re.search(r"<title[^>]*>(.*?)</title>", raw, re.IGNORECASE | re.DOTALL)
    title = title_match.group(1).strip() if title_match else ""

    return {"ok": True, "text": text, "title": title}


def _extract_from_pdf(path: str) -> dict[str, Any]:
    """Extract text from a PDF file using pdftotext or fallback."""
    if not os.path.isfile(path):
        return {"ok": False, "error": f"PDF file not found: {path}"}

    # Try pdftotext (poppler-utils)
    try:
        result = subprocess.run(
            ["pdftotext", "-layout", path, "-"],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode == 0 and result.stdout.strip():
            return {"ok": True, "text": result.stdout.strip()}
    except FileNotFoundError:
        pass  # pdftotext not installed, try fallback
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "PDF extraction timed out"}
    except Exception:
        pass

    # Fallback: try PyPDF2 or pypdf
    for module_name in ("pypdf", "PyPDF2"):
        try:
            mod = __import__(module_name)
            reader = mod.PdfReader(path)
            pages_text = []
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    pages_text.append(page_text)
            if pages_text:
                return {"ok": True, "text": "\n\n".join(pages_text)}
        except ImportError:
            continue
        except Exception as exc:
            return {"ok": False, "error": f"PDF read error ({module_name}): {exc}"}

    return {
        "ok": False,
        "error": (
            "PDF extraction requires pdftotext (poppler-utils) or pypdf. "
            "Install with: brew install poppler  OR  pip install pypdf"
        ),
    }


def _extract_from_markdown(path: str) -> dict[str, Any]:
    """Read a Markdown file as-is."""
    if not os.path.isfile(path):
        return {"ok": False, "error": f"Markdown file not found: {path}"}
    try:
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
        # Extract title from first heading
        title = ""
        for line in text.split("\n"):
            line = line.strip()
            if line.startswith("# "):
                title = line.lstrip("# ").strip()
                break
        return {"ok": True, "text": text, "title": title}
    except IOError as exc:
        return {"ok": False, "error": f"Failed to read markdown: {exc}"}


def _extract_from_docx(path: str) -> dict[str, Any]:
    """Extract text from a DOCX file."""
    if not os.path.isfile(path):
        return {"ok": False, "error": f"DOCX file not found: {path}"}
    try:
        import docx
        doc = docx.Document(path)
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        text = "\n\n".join(paragraphs)
        title = paragraphs[0] if paragraphs else ""
        return {"ok": True, "text": text, "title": title}
    except ImportError:
        return {
            "ok": False,
            "error": (
                "DOCX extraction requires python-docx. "
                "Install with: pip install python-docx"
            ),
        }
    except Exception as exc:
        return {"ok": False, "error": f"DOCX read error: {exc}"}


def _extract_from_text_file(path: str) -> dict[str, Any]:
    """Read a plain text file."""
    if not os.path.isfile(path):
        return {"ok": False, "error": f"Text file not found: {path}"}
    try:
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
        return {"ok": True, "text": text}
    except IOError as exc:
        return {"ok": False, "error": f"Failed to read file: {exc}"}


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------

def chunk_text(text: str, max_size: int = MAX_CHUNK_SIZE) -> list[str]:
    """
    Split text into chunks at paragraph boundaries.
    Each chunk is at most max_size characters.
    """
    if not text or not text.strip():
        return []

    if len(text) <= max_size:
        return [text.strip()]

    # Split on double newlines (paragraph boundaries)
    paragraphs = re.split(r"\n\s*\n", text)
    chunks = []
    current = ""

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        # If adding this paragraph would exceed max_size
        if current and len(current) + len(para) + 2 > max_size:
            chunks.append(current.strip())
            current = para
        elif not current and len(para) > max_size:
            # Single paragraph exceeds max_size -- split on sentences
            sentences = re.split(r"(?<=[.!?])\s+", para)
            for sent in sentences:
                if current and len(current) + len(sent) + 1 > max_size:
                    chunks.append(current.strip())
                    current = sent
                else:
                    current = (current + " " + sent).strip() if current else sent
        else:
            current = (current + "\n\n" + para).strip() if current else para

    if current.strip():
        chunks.append(current.strip())

    return chunks


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL DEFAULT '',
    source TEXT NOT NULL DEFAULT '',
    source_type TEXT NOT NULL DEFAULT 'text',
    content_hash TEXT NOT NULL DEFAULT '',
    word_count INTEGER NOT NULL DEFAULT 0,
    chunk_count INTEGER NOT NULL DEFAULT 0,
    full_text TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS chunks (
    id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL,
    chunk_index INTEGER NOT NULL,
    text TEXT NOT NULL DEFAULT '',
    word_count INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (document_id) REFERENCES documents(id)
);

CREATE INDEX IF NOT EXISTS idx_documents_hash ON documents(content_hash);
CREATE INDEX IF NOT EXISTS idx_documents_source_type ON documents(source_type);
CREATE INDEX IF NOT EXISTS idx_chunks_document ON chunks(document_id);
CREATE INDEX IF NOT EXISTS idx_chunks_index ON chunks(document_id, chunk_index);
"""

# FTS5 virtual table for full-text search
_FTS_SQL = """
CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
    document_id,
    text,
    content='chunks',
    content_rowid='rowid'
);
"""

_FTS_TRIGGERS = """
CREATE TRIGGER IF NOT EXISTS chunks_ai AFTER INSERT ON chunks BEGIN
    INSERT INTO chunks_fts(rowid, document_id, text)
    VALUES (new.rowid, new.document_id, new.text);
END;

CREATE TRIGGER IF NOT EXISTS chunks_ad AFTER DELETE ON chunks BEGIN
    INSERT INTO chunks_fts(chunks_fts, rowid, document_id, text)
    VALUES('delete', old.rowid, old.document_id, old.text);
END;

CREATE TRIGGER IF NOT EXISTS chunks_au AFTER UPDATE ON chunks BEGIN
    INSERT INTO chunks_fts(chunks_fts, rowid, document_id, text)
    VALUES('delete', old.rowid, old.document_id, old.text);
    INSERT INTO chunks_fts(rowid, document_id, text)
    VALUES (new.rowid, new.document_id, new.text);
END;
"""


def _get_db(db_path: Optional[str] = None) -> sqlite3.Connection:
    """Initialize and return database connection."""
    path = db_path or os.environ.get("PERMANENCE_DOCUMENTS_DB", DEFAULT_DB_PATH)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(_SCHEMA_SQL)
    # FTS5 setup -- separate try/except because some SQLite builds lack FTS5
    try:
        conn.executescript(_FTS_SQL)
        conn.executescript(_FTS_TRIGGERS)
    except sqlite3.OperationalError:
        # FTS5 not available; search will fall back to LIKE queries
        pass
    conn.commit()
    return conn


# ---------------------------------------------------------------------------
# Entity Graph integration
# ---------------------------------------------------------------------------

def _create_entity_graph_node(
    doc_id: str,
    title: str,
    source: str,
    source_type: str,
    word_count: int,
    chunk_count: int,
    content_hash: str,
) -> Optional[dict]:
    """Create an Entity Graph DOCUMENT node. Returns None if graph unavailable."""
    try:
        from core.entity_graph import EntityGraph
        graph = EntityGraph()
        entity = graph.create_entity(
            entity_type="DOCUMENT",
            title=title or f"Document {doc_id}",
            properties={
                "document_id": doc_id,
                "source": source,
                "source_type": source_type,
                "word_count": word_count,
                "chunk_count": chunk_count,
                "content_hash": content_hash,
            },
            created_by="document_ingest",
        )
        return entity
    except Exception:
        # Entity Graph not available or failed -- non-fatal
        return None


# ---------------------------------------------------------------------------
# Core API
# ---------------------------------------------------------------------------

def ingest(
    source: str,
    source_type: str = "auto",
    title: str = "",
    db_path: Optional[str] = None,
) -> dict[str, Any]:
    """
    Ingest a document from any source.

    Args:
        source: Text content, URL, or file path
        source_type: auto, text, url, pdf, markdown, docx, text_file
        title: Optional title (auto-detected if empty)

    Returns:
        Dict with ok, id, and metadata fields.
    """
    if not source or not source.strip():
        return {"ok": False, "error": "Source cannot be empty"}

    source = source.strip()

    # Auto-detect type
    if source_type == "auto":
        source_type = _detect_source_type(source)

    # Route to appropriate extractor
    if source_type == "url":
        return ingest_url(source, title=title, db_path=db_path)
    elif source_type == "pdf":
        return ingest_file(source, title=title, db_path=db_path)
    elif source_type == "markdown":
        return ingest_file(source, title=title, db_path=db_path)
    elif source_type == "docx":
        return ingest_file(source, title=title, db_path=db_path)
    elif source_type == "text_file":
        return ingest_file(source, title=title, db_path=db_path)
    else:
        # Treat as plain text
        return ingest_text(source, title=title, db_path=db_path)


def ingest_url(
    url: str,
    title: str = "",
    db_path: Optional[str] = None,
) -> dict[str, Any]:
    """Ingest a document from a URL."""
    if not url or not url.strip():
        return {"ok": False, "error": "URL cannot be empty"}

    result = _extract_from_url(url.strip())
    if not result["ok"]:
        return result

    text = result["text"]
    if not text.strip():
        return {"ok": False, "error": "No text content extracted from URL"}

    extracted_title = title or result.get("title", "") or url[:60]
    return _store_document(
        text=text,
        title=extracted_title,
        source=url.strip(),
        source_type="url",
        db_path=db_path,
    )


def ingest_file(
    path: str,
    title: str = "",
    db_path: Optional[str] = None,
) -> dict[str, Any]:
    """Ingest a document from a file path."""
    if not path or not path.strip():
        return {"ok": False, "error": "File path cannot be empty"}

    path = path.strip()
    file_type = _detect_source_type(path)

    if file_type == "pdf":
        result = _extract_from_pdf(path)
    elif file_type == "markdown":
        result = _extract_from_markdown(path)
    elif file_type == "docx":
        result = _extract_from_docx(path)
    else:
        result = _extract_from_text_file(path)

    if not result["ok"]:
        return result

    text = result["text"]
    if not text.strip():
        return {"ok": False, "error": "No text content extracted from file"}

    extracted_title = title or result.get("title", "") or os.path.basename(path)
    return _store_document(
        text=text,
        title=extracted_title,
        source=os.path.abspath(path),
        source_type=file_type,
        db_path=db_path,
    )


def ingest_text(
    text: str,
    title: str = "",
    db_path: Optional[str] = None,
) -> dict[str, Any]:
    """Ingest plain text directly."""
    if not text or not text.strip():
        return {"ok": False, "error": "Text cannot be empty"}

    if not title:
        title = text.strip()[:60]
        if len(text.strip()) > 60:
            title += "..."

    return _store_document(
        text=text.strip(),
        title=title,
        source="direct_input",
        source_type="text",
        db_path=db_path,
    )


def _store_document(
    text: str,
    title: str,
    source: str,
    source_type: str,
    db_path: Optional[str] = None,
) -> dict[str, Any]:
    """Store a document with chunks in SQLite and create Entity Graph node."""
    doc_id = _gen_id()
    now = _now_iso()
    c_hash = _content_hash(text)
    words = text.split()
    word_count = len(words)

    # Check for duplicate content
    conn = _get_db(db_path)
    try:
        existing = conn.execute(
            "SELECT id, title FROM documents WHERE content_hash = ?",
            (c_hash,),
        ).fetchone()
        if existing:
            conn.close()
            return {
                "ok": True,
                "id": existing["id"],
                "duplicate": True,
                "message": f"Document already exists with ID {existing['id']}",
                "title": existing["title"],
            }
    except sqlite3.Error:
        pass

    # Chunk the text
    chunks = chunk_text(text)
    chunk_count = len(chunks)

    # Store document
    try:
        conn.execute(
            """INSERT INTO documents
               (id, title, source, source_type, content_hash, word_count,
                chunk_count, full_text, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (doc_id, title, source, source_type, c_hash, word_count,
             chunk_count, text, now),
        )

        # Store chunks
        for i, chunk in enumerate(chunks):
            chunk_id = _gen_id()
            chunk_words = len(chunk.split())
            conn.execute(
                """INSERT INTO chunks
                   (id, document_id, chunk_index, text, word_count)
                   VALUES (?, ?, ?, ?, ?)""",
                (chunk_id, doc_id, i, chunk, chunk_words),
            )

        conn.commit()
    except sqlite3.Error as exc:
        conn.close()
        return {"ok": False, "error": f"Database error: {exc}"}

    conn.close()

    # Create Entity Graph node (non-fatal if unavailable)
    entity = _create_entity_graph_node(
        doc_id=doc_id,
        title=title,
        source=source,
        source_type=source_type,
        word_count=word_count,
        chunk_count=chunk_count,
        content_hash=c_hash,
    )

    return {
        "ok": True,
        "id": doc_id,
        "title": title,
        "source": source,
        "source_type": source_type,
        "word_count": word_count,
        "chunk_count": chunk_count,
        "content_hash": c_hash,
        "created_at": now,
        "entity_id": entity["id"] if entity else None,
    }


# ---------------------------------------------------------------------------
# Query API
# ---------------------------------------------------------------------------

def get_document(doc_id: str, db_path: Optional[str] = None) -> Optional[dict[str, Any]]:
    """Get a document by ID. Returns None if not found."""
    conn = _get_db(db_path)
    try:
        row = conn.execute(
            "SELECT * FROM documents WHERE id = ?", (doc_id,)
        ).fetchone()
        conn.close()
    except sqlite3.Error as exc:
        conn.close()
        return None

    if not row:
        return None

    return {
        "id": row["id"],
        "title": row["title"],
        "source": row["source"],
        "source_type": row["source_type"],
        "content_hash": row["content_hash"],
        "word_count": row["word_count"],
        "chunk_count": row["chunk_count"],
        "full_text": row["full_text"],
        "created_at": row["created_at"],
    }


def get_chunks(doc_id: str, db_path: Optional[str] = None) -> list[dict[str, Any]]:
    """Get all chunks for a document."""
    conn = _get_db(db_path)
    try:
        rows = conn.execute(
            "SELECT * FROM chunks WHERE document_id = ? ORDER BY chunk_index",
            (doc_id,),
        ).fetchall()
        conn.close()
    except sqlite3.Error:
        conn.close()
        return []

    return [
        {
            "id": row["id"],
            "document_id": row["document_id"],
            "chunk_index": row["chunk_index"],
            "text": row["text"],
            "word_count": row["word_count"],
        }
        for row in rows
    ]


def list_documents(
    limit: int = 50,
    db_path: Optional[str] = None,
) -> list[dict[str, Any]]:
    """List all documents, most recent first."""
    conn = _get_db(db_path)
    try:
        rows = conn.execute(
            """SELECT id, title, source, source_type, word_count,
                      chunk_count, created_at
               FROM documents ORDER BY created_at DESC LIMIT ?""",
            (limit,),
        ).fetchall()
        conn.close()
    except sqlite3.Error:
        conn.close()
        return []

    return [dict(row) for row in rows]


def delete_document(doc_id: str, db_path: Optional[str] = None) -> bool:
    """Delete a document and its chunks. Returns True if deleted."""
    conn = _get_db(db_path)
    try:
        # Delete chunks first
        conn.execute(
            "DELETE FROM chunks WHERE document_id = ?", (doc_id,)
        )
        cursor = conn.execute(
            "DELETE FROM documents WHERE id = ?", (doc_id,)
        )
        deleted = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return deleted
    except sqlite3.Error:
        conn.close()
        return False


def search_documents(
    query: str,
    limit: int = 10,
    db_path: Optional[str] = None,
) -> list[dict[str, Any]]:
    """
    Search documents using FTS5 full-text search with LIKE fallback.
    Returns documents with matching chunks and relevance info.
    """
    if not query or not query.strip():
        return []

    conn = _get_db(db_path)
    results = []

    # Try FTS5 first
    try:
        rows = conn.execute(
            """SELECT c.document_id, c.text, c.chunk_index,
                      d.title, d.source, d.source_type, d.created_at
               FROM chunks_fts fts
               JOIN chunks c ON fts.rowid = c.rowid
               JOIN documents d ON c.document_id = d.id
               WHERE chunks_fts MATCH ?
               ORDER BY rank
               LIMIT ?""",
            (query.strip(), limit),
        ).fetchall()

        seen_docs = set()
        for row in rows:
            doc_id = row["document_id"]
            if doc_id not in seen_docs:
                seen_docs.add(doc_id)
                snippet = row["text"][:200]
                results.append({
                    "id": doc_id,
                    "title": row["title"],
                    "source": row["source"],
                    "source_type": row["source_type"],
                    "snippet": snippet,
                    "chunk_index": row["chunk_index"],
                    "created_at": row["created_at"],
                })

        conn.close()
        return results
    except sqlite3.OperationalError:
        # FTS5 not available, fall back to LIKE
        pass

    # LIKE fallback
    search_term = f"%{query.strip()}%"
    try:
        rows = conn.execute(
            """SELECT c.document_id, c.text, c.chunk_index,
                      d.title, d.source, d.source_type, d.created_at
               FROM chunks c
               JOIN documents d ON c.document_id = d.id
               WHERE c.text LIKE ? OR d.title LIKE ?
               ORDER BY d.created_at DESC
               LIMIT ?""",
            (search_term, search_term, limit),
        ).fetchall()

        seen_docs = set()
        for row in rows:
            doc_id = row["document_id"]
            if doc_id not in seen_docs:
                seen_docs.add(doc_id)
                snippet = row["text"][:200]
                results.append({
                    "id": doc_id,
                    "title": row["title"],
                    "source": row["source"],
                    "source_type": row["source_type"],
                    "snippet": snippet,
                    "chunk_index": row["chunk_index"],
                    "created_at": row["created_at"],
                })
    except sqlite3.Error:
        pass

    conn.close()
    return results


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Permanence OS -- Document Ingestion System"
    )
    parser.add_argument(
        "--action",
        required=True,
        choices=["ingest", "list", "get", "search", "delete", "chunks"],
        help="Action to perform",
    )
    parser.add_argument("--source", default="", help="Source text, URL, or file path")
    parser.add_argument("--source-type", default="auto", help="Source type override")
    parser.add_argument("--title", default="", help="Document title")
    parser.add_argument("--query", default="", help="Search query")
    parser.add_argument("--id", dest="doc_id", default="", help="Document ID")
    parser.add_argument("--limit", type=int, default=50, help="Max results")
    parser.add_argument("--db-path", default=None, help="Override database path")
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.action == "ingest":
        if not args.source:
            print("Error: --source is required for ingest")
            return 1
        result = ingest(
            source=args.source,
            source_type=args.source_type,
            title=args.title,
            db_path=args.db_path,
        )
        if result["ok"]:
            dup_msg = " (duplicate)" if result.get("duplicate") else ""
            print(f"Ingested{dup_msg}: {result['id']}")
            print(f"  Title: {result.get('title', 'N/A')}")
            if not result.get("duplicate"):
                print(f"  Words: {result.get('word_count', 0)}")
                print(f"  Chunks: {result.get('chunk_count', 0)}")
        else:
            print(f"Error: {result['error']}")
            return 1

    elif args.action == "list":
        docs = list_documents(limit=args.limit, db_path=args.db_path)
        if not docs:
            print("No documents found.")
        else:
            print(f"Documents ({len(docs)}):")
            for doc in docs:
                print(
                    f"  [{doc['id']}] {doc['source_type']} | "
                    f"{doc['word_count']}w | {doc['title'][:60]}"
                )

    elif args.action == "get":
        if not args.doc_id:
            print("Error: --id is required for get")
            return 1
        doc = get_document(args.doc_id, db_path=args.db_path)
        if doc:
            print(json.dumps(doc, indent=2))
        else:
            print(f"Document {args.doc_id} not found")
            return 1

    elif args.action == "chunks":
        if not args.doc_id:
            print("Error: --id is required for chunks")
            return 1
        chunks = get_chunks(args.doc_id, db_path=args.db_path)
        if not chunks:
            print(f"No chunks found for document {args.doc_id}")
        else:
            print(f"Chunks ({len(chunks)}):")
            for c in chunks:
                print(f"  [{c['chunk_index']}] {c['word_count']}w | {c['text'][:80]}...")

    elif args.action == "search":
        if not args.query:
            print("Error: --query is required for search")
            return 1
        results = search_documents(
            query=args.query, limit=args.limit, db_path=args.db_path
        )
        if not results:
            print("No results found.")
        else:
            print(f"Results ({len(results)}):")
            for r in results:
                print(f"  [{r['id']}] {r['title'][:50]} | {r['snippet'][:60]}...")

    elif args.action == "delete":
        if not args.doc_id:
            print("Error: --id is required for delete")
            return 1
        if delete_document(args.doc_id, db_path=args.db_path):
            print(f"Deleted: {args.doc_id}")
        else:
            print(f"Document {args.doc_id} not found or already deleted")
            return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
