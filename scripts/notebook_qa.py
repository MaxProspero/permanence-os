#!/usr/bin/env python3
"""
PERMANENCE OS -- NotebookLM-Style Question Answering

Ask natural-language questions over ingested documents.  The pipeline:
  1. Receive a question from the user
  2. Search document chunks for relevant passages (SQLite FTS)
  3. Assemble a context window from top-K matching chunks
  4. Send context + question to an LLM (Ollama local or Claude cloud)
  5. Return a structured answer with source citations

Storage: SQLite at permanence_storage/notebook_qa.db
  - documents table  (id, title, source_path, content, chunk_count, created_at)
  - chunks table      (id, document_id, chunk_index, content, created_at)

Model routing (60/30/10 rule -- LLM is the 10%):
  - Default: try Ollama local  (http://localhost:11434/api/generate)
  - Fallback: keyword extraction (no LLM needed, still returns sources)
  - Explicit override: model="claude" or model="ollama"

Usage:
  python scripts/notebook_qa.py --ask "What are the key findings?"
  python scripts/notebook_qa.py --ask "Revenue data" --sources doc123,doc456
  python scripts/notebook_qa.py --sources
  python scripts/notebook_qa.py --ingest /path/to/file.txt --title "My Report"
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sqlite3
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, List, Optional

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parents[1]
STORAGE_DIR = Path(
    os.getenv("PERMANENCE_STORAGE_DIR", str(BASE_DIR / "permanence_storage"))
)
DEFAULT_DB_PATH = str(STORAGE_DIR / "notebook_qa.db")

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")

# Chunk size for splitting documents (characters)
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    """Current UTC time as ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


def _generate_id() -> str:
    """Generate a 12-character hex ID."""
    seed = _now_iso() + os.urandom(8).hex()
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()[:12]


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    source_path TEXT NOT NULL DEFAULT '',
    content TEXT NOT NULL DEFAULT '',
    chunk_count INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS chunks (
    id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (document_id) REFERENCES documents(id)
);

CREATE INDEX IF NOT EXISTS idx_chunks_doc ON chunks(document_id);
CREATE INDEX IF NOT EXISTS idx_chunks_index ON chunks(chunk_index);
"""


def _get_db(db_path: Optional[str] = None) -> sqlite3.Connection:
    """Get or create the notebook_qa database."""
    path = db_path or os.environ.get("PERMANENCE_QA_DB", DEFAULT_DB_PATH)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(_SCHEMA_SQL)
    conn.commit()
    return conn


# ---------------------------------------------------------------------------
# Document ingestion
# ---------------------------------------------------------------------------


def _split_into_chunks(text: str, chunk_size: int = CHUNK_SIZE,
                       overlap: int = CHUNK_OVERLAP) -> List[str]:
    """Split text into overlapping chunks at sentence boundaries."""
    if not text or not text.strip():
        return []

    text = text.strip()
    if len(text) <= chunk_size:
        return [text]

    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size

        if end < len(text):
            # Try to break at a sentence boundary
            search_region = text[max(start + chunk_size // 2, start):end]
            last_period = search_region.rfind(".")
            last_newline = search_region.rfind("\n")
            boundary = max(last_period, last_newline)
            if boundary > 0:
                end = max(start + chunk_size // 2, start) + boundary + 1

        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)

        start = end - overlap if end < len(text) else len(text)

    return chunks


def ingest_document(
    content: str,
    title: str = "",
    source_path: str = "",
    db_path: Optional[str] = None,
) -> dict[str, Any]:
    """
    Ingest a document: store it and split into searchable chunks.

    Args:
        content: Full text content of the document.
        title: Human-readable title.
        source_path: Original file path or URL.
        db_path: Override database path.

    Returns:
        Dict with ok, document_id, chunk_count.
    """
    if not content or not content.strip():
        return {"ok": False, "error": "Content cannot be empty"}

    doc_id = _generate_id()
    now = _now_iso()

    if not title:
        title = content.strip()[:60]
        if len(content.strip()) > 60:
            title += "..."

    chunks = _split_into_chunks(content)

    try:
        conn = _get_db(db_path)
        conn.execute(
            """INSERT INTO documents (id, title, source_path, content, chunk_count, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (doc_id, title, source_path, content.strip(), len(chunks), now),
        )

        for i, chunk_text in enumerate(chunks):
            chunk_id = _generate_id()
            conn.execute(
                """INSERT INTO chunks (id, document_id, chunk_index, content, created_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (chunk_id, doc_id, i, chunk_text, now),
            )

        conn.commit()
        conn.close()
    except sqlite3.Error as exc:
        return {"ok": False, "error": f"Database error: {exc}"}

    return {
        "ok": True,
        "document_id": doc_id,
        "title": title,
        "chunk_count": len(chunks),
    }


def ingest_file(
    file_path: str,
    title: str = "",
    db_path: Optional[str] = None,
) -> dict[str, Any]:
    """Ingest a document from a file path."""
    try:
        path = Path(file_path)
        if not path.exists():
            return {"ok": False, "error": f"File not found: {file_path}"}
        content = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return {"ok": False, "error": f"Failed to read file: {exc}"}

    if not title:
        title = path.stem.replace("_", " ").replace("-", " ").title()

    return ingest_document(
        content=content,
        title=title,
        source_path=str(path.resolve()),
        db_path=db_path,
    )


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------


def search_documents(
    query: str,
    source_ids: Optional[List[str]] = None,
    max_chunks: int = 5,
    db_path: Optional[str] = None,
) -> List[dict[str, Any]]:
    """
    Search document chunks for passages matching the query.

    Uses keyword matching (LIKE) against chunk content.
    Returns top-K matching chunks sorted by relevance (keyword density).

    Args:
        query: Search query string.
        source_ids: Optional list of document IDs to restrict search.
        max_chunks: Maximum number of chunks to return.
        db_path: Override database path.

    Returns:
        List of dicts with document_id, title, chunk_index, content, snippet.
    """
    if not query or not query.strip():
        return []

    # Extract keywords (words 3+ chars, lowercased)
    keywords = [w.lower() for w in re.findall(r'\b\w{3,}\b', query)]
    if not keywords:
        return []

    try:
        conn = _get_db(db_path)

        # Build query with LIKE for each keyword
        base_sql = """
            SELECT c.id, c.document_id, c.chunk_index, c.content,
                   d.title AS doc_title
            FROM chunks c
            JOIN documents d ON c.document_id = d.id
            WHERE 1=1
        """
        params: list[Any] = []

        if source_ids:
            placeholders = ",".join("?" for _ in source_ids)
            base_sql += f" AND c.document_id IN ({placeholders})"
            params.extend(source_ids)

        # At least one keyword must match
        keyword_conditions = []
        for kw in keywords:
            keyword_conditions.append("LOWER(c.content) LIKE ?")
            params.append(f"%{kw}%")

        if keyword_conditions:
            base_sql += " AND (" + " OR ".join(keyword_conditions) + ")"

        rows = conn.execute(base_sql, params).fetchall()
        conn.close()
    except sqlite3.Error as exc:
        return []

    # Score by keyword density and sort
    results = []
    for row in rows:
        content_lower = row["content"].lower()
        score = sum(1 for kw in keywords if kw in content_lower)

        # Build a snippet (first 200 chars around first keyword match)
        snippet = row["content"][:200]
        for kw in keywords:
            idx = content_lower.find(kw)
            if idx >= 0:
                start = max(0, idx - 80)
                end = min(len(row["content"]), idx + 120)
                snippet = row["content"][start:end]
                if start > 0:
                    snippet = "..." + snippet
                if end < len(row["content"]):
                    snippet = snippet + "..."
                break

        results.append({
            "document_id": row["document_id"],
            "title": row["doc_title"],
            "chunk_index": row["chunk_index"],
            "content": row["content"],
            "snippet": snippet,
            "score": score,
        })

    # Sort by score descending, take top-K
    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:max_chunks]


# ---------------------------------------------------------------------------
# Context building
# ---------------------------------------------------------------------------


def build_context(
    question: str,
    source_ids: Optional[List[str]] = None,
    max_chunks: int = 5,
    db_path: Optional[str] = None,
) -> str:
    """
    Build a context string from relevant document chunks for the LLM.

    Args:
        question: The user's question.
        source_ids: Optional document IDs to restrict search.
        max_chunks: Maximum chunks to include.
        db_path: Override database path.

    Returns:
        Formatted context string with source citations.
    """
    chunks = search_documents(
        query=question,
        source_ids=source_ids,
        max_chunks=max_chunks,
        db_path=db_path,
    )

    if not chunks:
        return ""

    parts = []
    for i, chunk in enumerate(chunks, 1):
        parts.append(
            f"[Source {i}: {chunk['title']} (chunk {chunk['chunk_index']})]"
            f"\n{chunk['content']}\n"
        )

    return "\n---\n".join(parts)


# ---------------------------------------------------------------------------
# LLM interaction
# ---------------------------------------------------------------------------


def _call_ollama(prompt: str, model: str = OLLAMA_MODEL) -> Optional[str]:
    """
    Call Ollama local LLM. Returns response text or None if unavailable.

    Uses urllib to avoid requests dependency.
    """
    payload = json.dumps({
        "model": model,
        "prompt": prompt,
        "stream": False,
    }).encode("utf-8")

    req = urllib.request.Request(
        OLLAMA_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("response", "")
    except (urllib.error.URLError, urllib.error.HTTPError, OSError, ValueError):
        return None


def _keyword_extract_answer(question: str, context: str) -> str:
    """
    Fallback answer generation using keyword extraction (no LLM).

    Extracts sentences from context that contain question keywords.
    """
    if not context:
        return "No relevant documents found for this question."

    keywords = [w.lower() for w in re.findall(r'\b\w{3,}\b', question)]
    if not keywords:
        return "Could not extract keywords from the question."

    # Split context into sentences
    sentences = re.split(r'[.!?]\s+', context)
    relevant = []
    for sentence in sentences:
        sentence_lower = sentence.lower()
        matches = sum(1 for kw in keywords if kw in sentence_lower)
        if matches > 0:
            relevant.append((matches, sentence.strip()))

    relevant.sort(key=lambda x: x[0], reverse=True)

    if not relevant:
        return (
            "Found related documents but could not extract a specific answer. "
            "Please review the source documents directly."
        )

    # Take top 3 most relevant sentences
    answer_parts = [s for _, s in relevant[:3]]
    return "Based on the documents: " + ". ".join(answer_parts) + "."


# ---------------------------------------------------------------------------
# Main Q&A function
# ---------------------------------------------------------------------------


def format_answer(raw_answer: str, sources: List[dict], question: str,
                  model_used: str) -> dict[str, Any]:
    """
    Format the answer with source citations and metadata.

    Args:
        raw_answer: The generated answer text.
        sources: List of source chunk dicts.
        question: Original question.
        model_used: Which model generated the answer.

    Returns:
        Structured response dict.
    """
    # Confidence based on number of matching sources
    if len(sources) >= 3:
        confidence = "high"
    elif len(sources) >= 1:
        confidence = "medium"
    else:
        confidence = "low"

    formatted_sources = []
    for s in sources:
        formatted_sources.append({
            "document_id": s["document_id"],
            "title": s["title"],
            "chunk_index": s["chunk_index"],
            "snippet": s.get("snippet", s.get("content", "")[:150]),
        })

    return {
        "answer": raw_answer,
        "sources": formatted_sources,
        "model_used": model_used,
        "confidence": confidence,
        "question": question,
    }


def ask(
    question: str,
    source_ids: Optional[List[str]] = None,
    model: str = "auto",
    max_chunks: int = 5,
    db_path: Optional[str] = None,
) -> dict[str, Any]:
    """
    Ask a question over ingested documents.

    Pipeline:
      1. Search for relevant chunks
      2. Build context from top-K chunks
      3. Send to LLM (or fall back to keyword extraction)
      4. Return structured answer with citations

    Args:
        question: The question to answer.
        source_ids: Optional list of document IDs to restrict search.
        model: "auto" (try Ollama then fallback), "ollama", "keyword", or "claude".
        max_chunks: Maximum chunks to include in context.
        db_path: Override database path.

    Returns:
        Structured response dict with answer, sources, model_used, confidence.
    """
    if not question or not question.strip():
        return format_answer(
            "Please provide a question.",
            sources=[],
            question=question or "",
            model_used="none",
        )

    question = question.strip()

    # Search for relevant chunks
    sources = search_documents(
        query=question,
        source_ids=source_ids,
        max_chunks=max_chunks,
        db_path=db_path,
    )

    if not sources:
        return format_answer(
            "No relevant documents found. Try ingesting some documents first, "
            "or rephrase your question.",
            sources=[],
            question=question,
            model_used="none",
        )

    # Build context
    context = build_context(
        question=question,
        source_ids=source_ids,
        max_chunks=max_chunks,
        db_path=db_path,
    )

    # Try LLM
    model_used = "keyword"
    raw_answer = None

    if model in ("auto", "ollama"):
        prompt = (
            "You are a helpful research assistant. Answer the question based "
            "ONLY on the provided context. If the context does not contain "
            "enough information, say so. Cite sources by number.\n\n"
            f"Context:\n{context}\n\n"
            f"Question: {question}\n\n"
            "Answer:"
        )
        raw_answer = _call_ollama(prompt)
        if raw_answer:
            model_used = OLLAMA_MODEL

    if raw_answer is None and model != "ollama":
        # Fallback to keyword extraction
        raw_answer = _keyword_extract_answer(question, context)
        model_used = "keyword"

    if raw_answer is None:
        raw_answer = (
            "LLM unavailable and keyword extraction produced no results. "
            "Relevant source documents are listed below."
        )
        model_used = "none"

    return format_answer(
        raw_answer=raw_answer,
        sources=sources,
        question=question,
        model_used=model_used,
    )


# ---------------------------------------------------------------------------
# List sources
# ---------------------------------------------------------------------------


def list_sources(db_path: Optional[str] = None) -> List[dict[str, Any]]:
    """
    List all ingested documents.

    Returns:
        List of dicts with id, title, source_path, chunk_count, created_at.
    """
    try:
        conn = _get_db(db_path)
        rows = conn.execute(
            "SELECT id, title, source_path, chunk_count, created_at "
            "FROM documents ORDER BY created_at DESC"
        ).fetchall()
        conn.close()
    except sqlite3.Error:
        return []

    return [dict(row) for row in rows]


def delete_document(
    document_id: str,
    db_path: Optional[str] = None,
) -> dict[str, Any]:
    """Delete a document and all its chunks."""
    try:
        conn = _get_db(db_path)
        conn.execute("DELETE FROM chunks WHERE document_id = ?", (document_id,))
        cursor = conn.execute("DELETE FROM documents WHERE id = ?", (document_id,))
        deleted = cursor.rowcount > 0
        conn.commit()
        conn.close()
    except sqlite3.Error as exc:
        return {"ok": False, "error": f"Database error: {exc}"}

    if not deleted:
        return {"ok": False, "error": f"Document {document_id} not found"}
    return {"ok": True, "document_id": document_id}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Permanence OS -- NotebookLM-Style Q&A"
    )
    parser.add_argument("--ask", default="", help="Question to ask")
    parser.add_argument("--sources", nargs="?", const="__list__", default=None,
                        help="List sources, or comma-separated doc IDs to restrict search")
    parser.add_argument("--ingest", default="", help="File path to ingest")
    parser.add_argument("--title", default="", help="Title for ingested document")
    parser.add_argument("--model", default="auto",
                        choices=["auto", "ollama", "keyword", "claude"],
                        help="Model to use for answering")
    parser.add_argument("--db-path", default=None, help="Override database path")
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    """CLI entry point."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    # List sources
    if args.sources == "__list__":
        sources = list_sources(db_path=args.db_path)
        if not sources:
            print("No documents ingested yet.")
        else:
            print(f"Ingested documents ({len(sources)}):")
            for doc in sources:
                print(f"  [{doc['id']}] {doc['title']} ({doc['chunk_count']} chunks)")
        return 0

    # Ingest a file
    if args.ingest:
        result = ingest_file(
            file_path=args.ingest,
            title=args.title,
            db_path=args.db_path,
        )
        if result["ok"]:
            print(f"Ingested: {result['document_id']}")
            print(f"  Title: {result['title']}")
            print(f"  Chunks: {result['chunk_count']}")
        else:
            print(f"Error: {result['error']}")
            return 1
        return 0

    # Ask a question
    if args.ask:
        source_ids = None
        if args.sources and args.sources != "__list__":
            source_ids = [s.strip() for s in args.sources.split(",") if s.strip()]

        result = ask(
            question=args.ask,
            source_ids=source_ids,
            model=args.model,
            db_path=args.db_path,
        )

        print(f"Q: {result['question']}")
        print(f"A: {result['answer']}")
        print(f"Confidence: {result['confidence']} | Model: {result['model_used']}")
        if result["sources"]:
            print(f"Sources ({len(result['sources'])}):")
            for s in result["sources"]:
                print(f"  - {s['title']} (chunk {s['chunk_index']})")
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
