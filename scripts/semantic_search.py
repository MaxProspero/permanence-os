#!/usr/bin/env python3
"""
PERMANENCE OS -- Semantic Search (Cross-System)

Unified search across Entity Graph, Document store, and Content Workflow.
Merges results from all three sources, deduplicates, and returns ranked hits.

Design:
  - 60/30/10 rule: all search is deterministic SQLite queries and keyword
    matching; no AI calls in v1
  - Graceful degradation: if a search source is unavailable, skip it
  - try/except on all database operations
  - No emojis

Search sources:
  1. Entity Graph nodes (all types) -- title + property search
  2. Document chunks -- FTS5 full-text search (with LIKE fallback)
  3. Content Workflow items -- title + body search

Usage:
  python3 scripts/semantic_search.py --query "machine learning" --limit 20
  python3 scripts/semantic_search.py --query "governance" --types document,note
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parents[1]
STORAGE_DIR = Path(
    os.getenv("PERMANENCE_STORAGE_DIR", str(BASE_DIR / "permanence_storage"))
)

# Database paths (can be overridden via env or constructor)
ENTITY_GRAPH_DB = str(STORAGE_DIR / "entity_graph.db")
DOCUMENTS_DB = str(STORAGE_DIR / "documents.db")
CONTENT_WORKFLOW_DB = str(STORAGE_DIR / "content_workflow.db")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_connect(db_path: str) -> Optional[sqlite3.Connection]:
    """Safely connect to a database. Returns None if unavailable."""
    if not os.path.isfile(db_path):
        return None
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.Error:
        return None


def _snippet(text: str, max_len: int = 200) -> str:
    """Generate a snippet from text."""
    if not text:
        return ""
    text = text.strip()
    if len(text) <= max_len:
        return text
    return text[:max_len].rstrip() + "..."


# ---------------------------------------------------------------------------
# Entity Graph search
# ---------------------------------------------------------------------------

def search_entities(
    query: str,
    limit: int = 10,
    entity_type: Optional[str] = None,
    db_path: Optional[str] = None,
) -> list[dict[str, Any]]:
    """
    Search Entity Graph nodes by title and properties.

    Returns list of result dicts with: id, type, title, snippet, source,
    relevance_score, created_at.
    """
    if not query or not query.strip():
        return []

    path = db_path or ENTITY_GRAPH_DB
    conn = _safe_connect(path)
    if conn is None:
        return []

    search_term = f"%{query.strip()}%"
    results = []

    try:
        sql = """
            SELECT id, entity_type, title, properties, status,
                   created_at, updated_at
            FROM entities
            WHERE (title LIKE ? OR properties LIKE ?)
            AND status != 'deleted'
        """
        params: list[Any] = [search_term, search_term]

        if entity_type:
            sql += " AND entity_type = ?"
            params.append(entity_type.upper())

        sql += " ORDER BY updated_at DESC LIMIT ?"
        params.append(limit)

        rows = conn.execute(sql, params).fetchall()

        for row in rows:
            props = {}
            try:
                props = json.loads(row["properties"] or "{}")
            except (json.JSONDecodeError, TypeError):
                pass

            # Simple relevance: title match scores higher than property match
            title_lower = (row["title"] or "").lower()
            query_lower = query.strip().lower()
            score = 0.8 if query_lower in title_lower else 0.5

            results.append({
                "id": row["id"],
                "type": row["entity_type"].lower(),
                "title": row["title"],
                "snippet": _snippet(row["title"]),
                "source": "entity_graph",
                "relevance_score": score,
                "created_at": row["created_at"],
            })
    except sqlite3.Error:
        pass
    finally:
        conn.close()

    return results


# ---------------------------------------------------------------------------
# Document search
# ---------------------------------------------------------------------------

def search_documents(
    query: str,
    limit: int = 10,
    db_path: Optional[str] = None,
) -> list[dict[str, Any]]:
    """
    Search documents using FTS5 or LIKE fallback.

    Returns list of result dicts with: id, type, title, snippet, source,
    relevance_score, created_at.
    """
    if not query or not query.strip():
        return []

    path = db_path or DOCUMENTS_DB
    conn = _safe_connect(path)
    if conn is None:
        return []

    results = []
    seen_docs: set[str] = set()

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
            (query.strip(), limit * 3),  # Over-fetch to handle dedup
        ).fetchall()

        for row in rows:
            doc_id = row["document_id"]
            if doc_id in seen_docs:
                continue
            seen_docs.add(doc_id)
            results.append({
                "id": doc_id,
                "type": "document",
                "title": row["title"],
                "snippet": _snippet(row["text"]),
                "source": "documents",
                "relevance_score": 0.9,  # FTS match is high quality
                "created_at": row["created_at"],
            })
            if len(results) >= limit:
                break

        conn.close()
        return results
    except sqlite3.OperationalError:
        # FTS5 not available
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
            (search_term, search_term, limit * 3),
        ).fetchall()

        for row in rows:
            doc_id = row["document_id"]
            if doc_id in seen_docs:
                continue
            seen_docs.add(doc_id)

            title_lower = (row["title"] or "").lower()
            query_lower = query.strip().lower()
            score = 0.7 if query_lower in title_lower else 0.5

            results.append({
                "id": doc_id,
                "type": "document",
                "title": row["title"],
                "snippet": _snippet(row["text"]),
                "source": "documents",
                "relevance_score": score,
                "created_at": row["created_at"],
            })
            if len(results) >= limit:
                break
    except sqlite3.Error:
        pass
    finally:
        conn.close()

    return results


# ---------------------------------------------------------------------------
# Content Workflow search
# ---------------------------------------------------------------------------

def search_content(
    query: str,
    limit: int = 10,
    db_path: Optional[str] = None,
) -> list[dict[str, Any]]:
    """
    Search Content Workflow items by title and body.

    Returns list of result dicts with: id, type, title, snippet, source,
    relevance_score, created_at.
    """
    if not query or not query.strip():
        return []

    path = db_path or CONTENT_WORKFLOW_DB
    conn = _safe_connect(path)
    if conn is None:
        return []

    search_term = f"%{query.strip()}%"
    results = []

    try:
        rows = conn.execute(
            """SELECT id, stage, source_type, title, body, created_at
               FROM content_items
               WHERE title LIKE ? OR body LIKE ?
               ORDER BY updated_at DESC
               LIMIT ?""",
            (search_term, search_term, limit),
        ).fetchall()

        for row in rows:
            title_lower = (row["title"] or "").lower()
            query_lower = query.strip().lower()
            score = 0.7 if query_lower in title_lower else 0.4

            results.append({
                "id": row["id"],
                "type": f"content_{row['stage']}",
                "title": row["title"],
                "snippet": _snippet(row["body"]),
                "source": "content_workflow",
                "relevance_score": score,
                "created_at": row["created_at"],
            })
    except sqlite3.Error:
        pass
    finally:
        conn.close()

    return results


# ---------------------------------------------------------------------------
# Unified search
# ---------------------------------------------------------------------------

def search(
    query: str,
    limit: int = 20,
    types: Optional[list[str]] = None,
    entity_graph_db: Optional[str] = None,
    documents_db: Optional[str] = None,
    content_db: Optional[str] = None,
) -> list[dict[str, Any]]:
    """
    Cross-system search across Entity Graph, Documents, and Content Workflow.

    Args:
        query: Search query string
        limit: Maximum total results
        types: Filter by result types (e.g., ["document", "note", "task"])
               None means search all sources

    Returns:
        List of result dicts sorted by relevance_score descending.
    """
    if not query or not query.strip():
        return []

    all_results: list[dict[str, Any]] = []

    # Determine which sources to search based on type filters
    search_entities_flag = True
    search_documents_flag = True
    search_content_flag = True

    if types:
        types_lower = [t.lower() for t in types]
        # Entity types map to entity graph
        entity_types = {
            "note", "task", "ticker", "strategy", "user", "agent",
            "contact", "company", "reminder", "approval", "decision",
            "mission", "position", "portfolio", "memory", "canon",
        }
        search_entities_flag = bool(entity_types & set(types_lower))
        search_documents_flag = "document" in types_lower
        search_content_flag = any(t.startswith("content") for t in types_lower)

        # If none of the specific flags were set but we have types,
        # search everything anyway and filter after
        if not (search_entities_flag or search_documents_flag or search_content_flag):
            search_entities_flag = True
            search_documents_flag = True
            search_content_flag = True

    per_source = max(limit, 10)

    if search_entities_flag:
        entity_type_filter = None
        if types:
            # If a single entity type is specified, pass it to narrow the search
            entity_types_in = [t.upper() for t in types if t.upper() in {
                "NOTE", "TASK", "TICKER", "STRATEGY", "USER", "AGENT",
                "CONTACT", "COMPANY", "DOCUMENT", "REMINDER", "APPROVAL",
                "DECISION", "MISSION", "POSITION", "PORTFOLIO", "MEMORY", "CANON",
            }]
            if len(entity_types_in) == 1:
                entity_type_filter = entity_types_in[0]

        all_results.extend(
            search_entities(
                query, limit=per_source,
                entity_type=entity_type_filter,
                db_path=entity_graph_db,
            )
        )

    if search_documents_flag:
        all_results.extend(
            search_documents(query, limit=per_source, db_path=documents_db)
        )

    if search_content_flag:
        all_results.extend(
            search_content(query, limit=per_source, db_path=content_db)
        )

    # Apply type filter if specified
    if types:
        types_lower = [t.lower() for t in types]
        all_results = [
            r for r in all_results if r["type"].lower() in types_lower
        ]

    # Sort by relevance_score descending, then by created_at descending
    all_results.sort(
        key=lambda r: (r.get("relevance_score", 0), r.get("created_at", "")),
        reverse=True,
    )

    return all_results[:limit]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Permanence OS -- Cross-System Semantic Search"
    )
    parser.add_argument("--query", required=True, help="Search query")
    parser.add_argument("--limit", type=int, default=20, help="Max results")
    parser.add_argument(
        "--types",
        default="",
        help="Comma-separated type filters (e.g., document,note,task)",
    )
    parser.add_argument("--source", default="all",
                        choices=["all", "entities", "documents", "content"],
                        help="Search source")
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    types_list = [t.strip() for t in args.types.split(",") if t.strip()] if args.types else None

    if args.source == "entities":
        results = search_entities(args.query, limit=args.limit)
    elif args.source == "documents":
        results = search_documents(args.query, limit=args.limit)
    elif args.source == "content":
        results = search_content(args.query, limit=args.limit)
    else:
        results = search(args.query, limit=args.limit, types=types_list)

    if not results:
        print("No results found.")
        return 0

    print(f"Search results ({len(results)}):")
    for r in results:
        score_str = f"{r['relevance_score']:.1f}"
        print(
            f"  [{r['id']}] {r['type']:12s} | "
            f"score={score_str} | {r['title'][:50]}"
        )
        if r.get("snippet"):
            print(f"    {r['snippet'][:80]}...")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
