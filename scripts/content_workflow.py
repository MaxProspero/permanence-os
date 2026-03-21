#!/usr/bin/env python3
"""
PERMANENCE OS -- Content Workflow Pipeline

Central pipeline connecting capture -> process -> create -> publish -> analyze.
Inspired by the Obsidian second-brain pattern: every idea starts as a raw
capture and flows through structured stages before reaching an audience.

Pipeline stages:
  1. CAPTURE  -- Ingest from bookmarks, notes, URLs, voice memos, files
  2. PROCESS  -- Auto-tag, summarize, extract insights, create Entity Graph nodes
  3. CREATE   -- Generate threads, newsletters, LinkedIn posts, scripts
  4. PUBLISH  -- Submit to social_draft_queue for human approval
  5. ANALYZE  -- Track performance and publishing frequency

Storage: SQLite at permanence_storage/content_workflow.db

Usage:
  python scripts/content_workflow.py --action capture --type note --body "My idea"
  python scripts/content_workflow.py --action capture --type url --url "https://example.com"
  python scripts/content_workflow.py --action process --id abc123def012
  python scripts/content_workflow.py --action list --stage capture
  python scripts/content_workflow.py --action move --id abc123def012 --to create
  python scripts/content_workflow.py --action stats
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sqlite3
from dataclasses import asdict, dataclass, field
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
DEFAULT_DB_PATH = str(STORAGE_DIR / "content_workflow.db")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_STAGES = ["capture", "process", "create", "publish", "analyze"]
VALID_SOURCE_TYPES = ["bookmark", "note", "voice", "url", "file"]

# Allowed stage transitions: current_stage -> set of valid next stages
STAGE_TRANSITIONS: dict[str, set[str]] = {
    "capture": {"process"},
    "process": {"create"},
    "create": {"publish"},
    "publish": {"analyze"},
    "analyze": set(),  # terminal stage
}

# Theme map imported from content_generator.py for consistency
THEME_MAP = {
    "ai_governance": {
        "keywords": ["governance", "safety", "alignment", "compliance", "audit", "trust", "regulation"],
        "label": "AI Governance",
    },
    "agent_systems": {
        "keywords": ["agent", "swarm", "orchestration", "multi-agent", "autonomous", "agentic"],
        "label": "Agent Systems",
    },
    "trading_intelligence": {
        "keywords": ["trading", "market", "backtest", "smc", "ict", "order block", "liquidity"],
        "label": "Trading Intelligence",
    },
    "open_source_infra": {
        "keywords": ["open source", "github", "framework", "infrastructure", "stack", "deploy"],
        "label": "Open Source Infrastructure",
    },
    "personal_intelligence": {
        "keywords": ["personal", "memory", "knowledge graph", "life os", "second brain", "productivity"],
        "label": "Personal Intelligence",
    },
    "data_sovereignty": {
        "keywords": ["local", "privacy", "self-hosted", "sovereignty", "own your data", "on-device"],
        "label": "Data Sovereignty",
    },
}


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class ContentItem:
    id: str               # 12-char hex
    stage: str            # capture, process, create, publish, analyze
    source_type: str      # bookmark, note, voice, url, file
    title: str
    body: str
    tags: list[str] = field(default_factory=list)
    theme: str = ""       # from THEME_MAP
    created_at: str = ""  # ISO 8601
    updated_at: str = ""  # ISO 8601
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict with JSON-safe fields."""
        d = asdict(self)
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ContentItem":
        """Reconstruct from dict, handling JSON string fields."""
        tags = d.get("tags", [])
        if isinstance(tags, str):
            try:
                tags = json.loads(tags)
            except (json.JSONDecodeError, TypeError):
                tags = [t.strip() for t in tags.split(",") if t.strip()] if tags else []
        metadata = d.get("metadata", {})
        if isinstance(metadata, str):
            try:
                metadata = json.loads(metadata)
            except (json.JSONDecodeError, TypeError):
                metadata = {}
        return cls(
            id=d.get("id", ""),
            stage=d.get("stage", "capture"),
            source_type=d.get("source_type", "note"),
            title=d.get("title", ""),
            body=d.get("body", ""),
            tags=tags if isinstance(tags, list) else [],
            theme=d.get("theme", ""),
            created_at=d.get("created_at", ""),
            updated_at=d.get("updated_at", ""),
            metadata=metadata if isinstance(metadata, dict) else {},
        )


# ---------------------------------------------------------------------------
# ID generation
# ---------------------------------------------------------------------------

def _generate_id() -> str:
    """Generate a 12-character hex ID from timestamp + random bytes."""
    now = datetime.now(timezone.utc).isoformat()
    seed = now + os.urandom(8).hex()
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()[:12]


def _now_iso() -> str:
    """Current UTC time as ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

def _get_db(db_path: Optional[str] = None) -> sqlite3.Connection:
    """Get or create the content_workflow table."""
    path = db_path or os.environ.get("PERMANENCE_WORKFLOW_DB", DEFAULT_DB_PATH)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS content_items (
            id TEXT PRIMARY KEY,
            stage TEXT NOT NULL DEFAULT 'capture',
            source_type TEXT NOT NULL DEFAULT 'note',
            title TEXT NOT NULL DEFAULT '',
            body TEXT NOT NULL DEFAULT '',
            tags TEXT NOT NULL DEFAULT '[]',
            theme TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            metadata TEXT NOT NULL DEFAULT '{}'
        )
    """)
    conn.commit()
    return conn


def _row_to_item(row: sqlite3.Row) -> ContentItem:
    """Convert a database row to a ContentItem."""
    return ContentItem.from_dict(dict(row))


# ---------------------------------------------------------------------------
# Stage 1: CAPTURE
# ---------------------------------------------------------------------------

def capture(
    source_type: str,
    body: str,
    title: str = "",
    metadata: Optional[dict[str, Any]] = None,
    db_path: Optional[str] = None,
) -> dict[str, Any]:
    """
    Capture a new content item from any source.

    Args:
        source_type: One of bookmark, note, voice, url, file
        body: The raw content text
        title: Optional title (auto-generated if empty)
        metadata: Optional dict with source URL, file path, etc.

    Returns:
        Dict with ok, id, and item fields.
    """
    if source_type not in VALID_SOURCE_TYPES:
        return {
            "ok": False,
            "error": f"Invalid source_type: {source_type}. Valid: {VALID_SOURCE_TYPES}",
        }
    if not body or not body.strip():
        return {"ok": False, "error": "body is required and cannot be empty"}

    item_id = _generate_id()
    now = _now_iso()

    if not title:
        # Auto-generate title from first 60 chars of body
        title = body.strip()[:60]
        if len(body.strip()) > 60:
            title += "..."

    item = ContentItem(
        id=item_id,
        stage="capture",
        source_type=source_type,
        title=title,
        body=body.strip(),
        tags=[],
        theme="",
        created_at=now,
        updated_at=now,
        metadata=metadata or {},
    )

    conn = _get_db(db_path)
    try:
        conn.execute(
            """INSERT INTO content_items
               (id, stage, source_type, title, body, tags, theme,
                created_at, updated_at, metadata)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                item.id, item.stage, item.source_type,
                item.title, item.body,
                json.dumps(item.tags), item.theme,
                item.created_at, item.updated_at,
                json.dumps(item.metadata),
            ),
        )
        conn.commit()
    except sqlite3.Error as exc:
        return {"ok": False, "error": f"Database error: {exc}"}

    return {"ok": True, "id": item_id, "item": item.to_dict()}


def capture_bookmark(
    url: str,
    text: str = "",
    title: str = "",
    db_path: Optional[str] = None,
) -> dict[str, Any]:
    """Capture a bookmark with URL metadata."""
    body = text or url
    return capture(
        source_type="bookmark",
        body=body,
        title=title or url[:60],
        metadata={"source_url": url},
        db_path=db_path,
    )


def capture_url(
    url: str,
    title: str = "",
    body: str = "",
    db_path: Optional[str] = None,
) -> dict[str, Any]:
    """Capture a URL for later scraping/processing."""
    return capture(
        source_type="url",
        body=body or f"URL to process: {url}",
        title=title or url[:60],
        metadata={"source_url": url},
        db_path=db_path,
    )


# ---------------------------------------------------------------------------
# Stage 2: PROCESS
# ---------------------------------------------------------------------------

def _extract_tags(text: str) -> list[str]:
    """
    Extract topic tags from text using keyword matching against THEME_MAP.
    Deterministic, no AI calls.
    """
    tags = []
    lower = text.lower()
    for theme_id, theme_info in THEME_MAP.items():
        for kw in theme_info["keywords"]:
            if kw in lower:
                tag = theme_info["label"].lower().replace(" ", "_")
                if tag not in tags:
                    tags.append(tag)
                break
    return tags


def _detect_theme(text: str) -> str:
    """
    Detect the primary theme from text using keyword density.
    Returns the theme_id with the most keyword matches, or empty string.
    """
    lower = text.lower()
    best_theme = ""
    best_count = 0

    for theme_id, theme_info in THEME_MAP.items():
        count = sum(1 for kw in theme_info["keywords"] if kw in lower)
        if count > best_count:
            best_count = count
            best_theme = theme_id

    return best_theme


def _summarize_text(text: str, max_length: int = 200) -> str:
    """
    Simple extractive summary: take the first N characters at a sentence boundary.
    No AI calls -- deterministic heuristic.
    """
    if len(text) <= max_length:
        return text

    # Find the last sentence boundary before max_length
    truncated = text[:max_length]
    last_period = truncated.rfind(".")
    last_question = truncated.rfind("?")
    last_excl = truncated.rfind("!")
    boundary = max(last_period, last_question, last_excl)

    if boundary > max_length // 3:
        return text[: boundary + 1]
    return truncated.rstrip() + "..."


def process_item(
    item_id: str,
    db_path: Optional[str] = None,
) -> dict[str, Any]:
    """
    Process a captured item: auto-tag, detect theme, summarize.

    Moves the item from 'capture' to 'process' stage.
    """
    conn = _get_db(db_path)
    row = conn.execute(
        "SELECT * FROM content_items WHERE id = ?", (item_id,)
    ).fetchone()
    if not row:
        return {"ok": False, "error": f"Item {item_id} not found"}

    item = _row_to_item(row)
    if item.stage != "capture":
        return {
            "ok": False,
            "error": f"Item {item_id} is in stage '{item.stage}', expected 'capture'",
        }

    # Extract tags and theme
    full_text = f"{item.title} {item.body}"
    tags = _extract_tags(full_text)
    theme = _detect_theme(full_text)
    summary = _summarize_text(item.body)

    now = _now_iso()
    metadata = item.metadata.copy()
    metadata["summary"] = summary
    metadata["processed_at"] = now

    try:
        conn.execute(
            """UPDATE content_items
               SET stage = 'process', tags = ?, theme = ?,
                   updated_at = ?, metadata = ?
               WHERE id = ?""",
            (
                json.dumps(tags), theme, now,
                json.dumps(metadata), item_id,
            ),
        )
        conn.commit()
    except sqlite3.Error as exc:
        return {"ok": False, "error": f"Database error: {exc}"}

    return {
        "ok": True,
        "id": item_id,
        "stage": "process",
        "tags": tags,
        "theme": theme,
        "summary": summary,
    }


# ---------------------------------------------------------------------------
# Stage 3: CREATE (delegates to content_generator.py)
# ---------------------------------------------------------------------------

def _load_content_generator():
    """Lazy import of content_generator module."""
    try:
        import sys
        sys.path.insert(0, str(BASE_DIR / "scripts"))
        import content_generator as cgen
        return cgen
    except ImportError:
        return None


def create_from_item(
    item_id: str,
    output_type: str = "thread",
    db_path: Optional[str] = None,
) -> dict[str, Any]:
    """
    Generate publishable content from a processed item.

    output_type: thread, newsletter, linkedin, short_script
    """
    valid_output_types = ["thread", "newsletter", "linkedin", "short_script"]
    if output_type not in valid_output_types:
        return {
            "ok": False,
            "error": f"Invalid output_type: {output_type}. Valid: {valid_output_types}",
        }

    conn = _get_db(db_path)
    row = conn.execute(
        "SELECT * FROM content_items WHERE id = ?", (item_id,)
    ).fetchone()
    if not row:
        return {"ok": False, "error": f"Item {item_id} not found"}

    item = _row_to_item(row)
    if item.stage != "process":
        return {
            "ok": False,
            "error": f"Item {item_id} is in stage '{item.stage}', expected 'process'",
        }

    cgen = _load_content_generator()

    now = _now_iso()
    metadata = item.metadata.copy()
    metadata["output_type"] = output_type
    metadata["created_content_at"] = now

    generated_content = None

    if output_type == "thread" and cgen:
        # Split body into points for thread generation
        sentences = [s.strip() for s in item.body.split(".") if s.strip()]
        points = sentences[:5] if sentences else [item.body[:200]]
        result = cgen.generate_thread(
            topic=item.title,
            points=points,
            source_urls=[item.metadata.get("source_url", "")],
        )
        generated_content = result.get("full_text", "")
        metadata["thread_result"] = {
            "segment_count": result.get("segment_count", 0),
            "voice_compliant": result.get("voice_compliant", False),
        }

    elif output_type == "linkedin" and cgen:
        result = cgen.generate_linkedin_post(
            topic=item.title,
            body=item.body[:1200],
            hashtags=item.tags[:5],
        )
        generated_content = result.get("content", "")
        metadata["linkedin_result"] = {
            "char_count": result.get("char_count", 0),
            "voice_compliant": result.get("voice_compliant", False),
        }

    elif output_type == "short_script" and cgen:
        summary = item.metadata.get("summary", item.body[:300])
        result = cgen.generate_short_script(
            topic=item.title,
            hook=item.title,
            body=summary,
        )
        generated_content = result.get("full_script", "")
        metadata["script_result"] = {
            "word_count": result.get("word_count", 0),
            "est_duration_seconds": result.get("est_duration_seconds", 0),
            "voice_compliant": result.get("voice_compliant", False),
        }

    else:
        # Fallback: simple formatted output when content_generator unavailable
        generated_content = f"# {item.title}\n\n{item.body}"
        if item.tags:
            generated_content += "\n\nTags: " + ", ".join(item.tags)

    metadata["generated_content"] = generated_content

    try:
        conn.execute(
            """UPDATE content_items
               SET stage = 'create', updated_at = ?, metadata = ?
               WHERE id = ?""",
            (now, json.dumps(metadata), item_id),
        )
        conn.commit()
    except sqlite3.Error as exc:
        return {"ok": False, "error": f"Database error: {exc}"}

    return {
        "ok": True,
        "id": item_id,
        "stage": "create",
        "output_type": output_type,
        "content_preview": (generated_content or "")[:200],
    }


# ---------------------------------------------------------------------------
# Stage 4: PUBLISH (delegates to social_draft_queue.py)
# ---------------------------------------------------------------------------

def _load_draft_queue():
    """Lazy import of social_draft_queue module."""
    try:
        import sys
        sys.path.insert(0, str(BASE_DIR / "scripts"))
        import social_draft_queue as sdq
        return sdq
    except ImportError:
        return None


def publish_item(
    item_id: str,
    platform: str = "x",
    db_path: Optional[str] = None,
) -> dict[str, Any]:
    """
    Submit a created item to the social_draft_queue for human approval.

    This does NOT auto-publish. It queues the item for review.
    Human authority is final -- the approval gate is preserved.
    """
    conn = _get_db(db_path)
    row = conn.execute(
        "SELECT * FROM content_items WHERE id = ?", (item_id,)
    ).fetchone()
    if not row:
        return {"ok": False, "error": f"Item {item_id} not found"}

    item = _row_to_item(row)
    if item.stage != "create":
        return {
            "ok": False,
            "error": f"Item {item_id} is in stage '{item.stage}', expected 'create'",
        }

    content = item.metadata.get("generated_content", item.body)
    if not content:
        return {"ok": False, "error": "No generated content found on this item"}

    now = _now_iso()
    metadata = item.metadata.copy()
    metadata["published_to_queue_at"] = now
    metadata["target_platform"] = platform

    sdq = _load_draft_queue()
    draft_result = None
    if sdq:
        try:
            draft_result = sdq.submit_draft(
                platform=platform,
                content=content,
                content_type=item.metadata.get("output_type", "post"),
                agent_id="content_workflow",
                metadata={
                    "workflow_item_id": item_id,
                    "source_type": item.source_type,
                    "theme": item.theme,
                    "tags": item.tags,
                },
            )
            metadata["draft_queue_result"] = draft_result
        except Exception as exc:
            metadata["draft_queue_error"] = str(exc)

    try:
        conn.execute(
            """UPDATE content_items
               SET stage = 'publish', updated_at = ?, metadata = ?
               WHERE id = ?""",
            (now, json.dumps(metadata), item_id),
        )
        conn.commit()
    except sqlite3.Error as exc:
        return {"ok": False, "error": f"Database error: {exc}"}

    return {
        "ok": True,
        "id": item_id,
        "stage": "publish",
        "platform": platform,
        "draft_queue_result": draft_result,
    }


# ---------------------------------------------------------------------------
# Stage transition (generic move)
# ---------------------------------------------------------------------------

def move_item(
    item_id: str,
    to_stage: str,
    db_path: Optional[str] = None,
) -> dict[str, Any]:
    """
    Move an item to a new stage, validating the transition.

    Only forward transitions are allowed (capture->process->create->publish->analyze).
    """
    if to_stage not in VALID_STAGES:
        return {
            "ok": False,
            "error": f"Invalid stage: {to_stage}. Valid: {VALID_STAGES}",
        }

    conn = _get_db(db_path)
    row = conn.execute(
        "SELECT * FROM content_items WHERE id = ?", (item_id,)
    ).fetchone()
    if not row:
        return {"ok": False, "error": f"Item {item_id} not found"}

    item = _row_to_item(row)
    allowed = STAGE_TRANSITIONS.get(item.stage, set())
    if to_stage not in allowed:
        return {
            "ok": False,
            "error": (
                f"Cannot move from '{item.stage}' to '{to_stage}'. "
                f"Allowed transitions: {sorted(allowed) if allowed else 'none (terminal stage)'}"
            ),
        }

    now = _now_iso()
    try:
        conn.execute(
            "UPDATE content_items SET stage = ?, updated_at = ? WHERE id = ?",
            (to_stage, now, item_id),
        )
        conn.commit()
    except sqlite3.Error as exc:
        return {"ok": False, "error": f"Database error: {exc}"}

    return {
        "ok": True,
        "id": item_id,
        "from_stage": item.stage,
        "to_stage": to_stage,
    }


# ---------------------------------------------------------------------------
# Query
# ---------------------------------------------------------------------------

def get_item(
    item_id: str,
    db_path: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    """Get a single content item by ID."""
    conn = _get_db(db_path)
    row = conn.execute(
        "SELECT * FROM content_items WHERE id = ?", (item_id,)
    ).fetchone()
    if not row:
        return None
    return _row_to_item(row).to_dict()


def list_items(
    stage: Optional[str] = None,
    source_type: Optional[str] = None,
    theme: Optional[str] = None,
    limit: int = 50,
    db_path: Optional[str] = None,
) -> list[dict[str, Any]]:
    """List content items with optional filters."""
    conn = _get_db(db_path)
    query = "SELECT * FROM content_items WHERE 1=1"
    params: list[Any] = []

    if stage:
        query += " AND stage = ?"
        params.append(stage)
    if source_type:
        query += " AND source_type = ?"
        params.append(source_type)
    if theme:
        query += " AND theme = ?"
        params.append(theme)

    query += " ORDER BY updated_at DESC LIMIT ?"
    params.append(limit)

    rows = conn.execute(query, params).fetchall()
    return [_row_to_item(row).to_dict() for row in rows]


# ---------------------------------------------------------------------------
# Stage 5: ANALYZE (stats and metrics)
# ---------------------------------------------------------------------------

def get_stats(db_path: Optional[str] = None) -> dict[str, Any]:
    """Return workflow statistics across all stages."""
    conn = _get_db(db_path)
    stats: dict[str, Any] = {
        "total_items": 0,
        "by_stage": {},
        "by_source_type": {},
        "by_theme": {},
        "recent_items": [],
    }

    # Count by stage
    for stage in VALID_STAGES:
        row = conn.execute(
            "SELECT COUNT(*) as cnt FROM content_items WHERE stage = ?",
            (stage,),
        ).fetchone()
        count = row["cnt"] if row else 0
        stats["by_stage"][stage] = count
        stats["total_items"] += count

    # Count by source type
    rows = conn.execute(
        "SELECT source_type, COUNT(*) as cnt FROM content_items GROUP BY source_type"
    ).fetchall()
    for row in rows:
        stats["by_source_type"][row["source_type"]] = row["cnt"]

    # Count by theme (excluding empty)
    rows = conn.execute(
        "SELECT theme, COUNT(*) as cnt FROM content_items WHERE theme != '' GROUP BY theme"
    ).fetchall()
    for row in rows:
        stats["by_theme"][row["theme"]] = row["cnt"]

    # Recent items (last 5)
    rows = conn.execute(
        "SELECT id, stage, title, updated_at FROM content_items ORDER BY updated_at DESC LIMIT 5"
    ).fetchall()
    stats["recent_items"] = [dict(row) for row in rows]

    return stats


def get_publishing_frequency(
    days: int = 30,
    db_path: Optional[str] = None,
) -> dict[str, Any]:
    """Track publishing frequency over the last N days."""
    conn = _get_db(db_path)

    # Count items that reached publish stage
    rows = conn.execute(
        """SELECT DATE(updated_at) as pub_date, COUNT(*) as cnt
           FROM content_items
           WHERE stage IN ('publish', 'analyze')
           GROUP BY pub_date
           ORDER BY pub_date DESC
           LIMIT ?""",
        (days,),
    ).fetchall()

    daily_counts = {row["pub_date"]: row["cnt"] for row in rows}
    total_published = sum(daily_counts.values())

    return {
        "period_days": days,
        "total_published": total_published,
        "daily_counts": daily_counts,
        "avg_per_day": round(total_published / max(days, 1), 2),
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser."""
    parser = argparse.ArgumentParser(
        description="Permanence OS -- Content Workflow Pipeline"
    )
    parser.add_argument(
        "--action",
        required=True,
        choices=["capture", "process", "create", "list", "get", "move", "stats", "publish"],
        help="Action to perform",
    )
    parser.add_argument("--type", dest="source_type", default="note",
                        help="Source type for capture (bookmark, note, voice, url, file)")
    parser.add_argument("--body", default="", help="Content body text")
    parser.add_argument("--title", default="", help="Content title")
    parser.add_argument("--url", default="", help="URL for url/bookmark capture")
    parser.add_argument("--id", dest="item_id", default="", help="Item ID for process/move/get")
    parser.add_argument("--to", dest="to_stage", default="", help="Target stage for move action")
    parser.add_argument("--stage", default="", help="Filter by stage for list action")
    parser.add_argument("--output-type", default="thread",
                        help="Output type for create (thread, newsletter, linkedin, short_script)")
    parser.add_argument("--platform", default="x", help="Platform for publish action")
    parser.add_argument("--limit", type=int, default=50, help="Max items to list")
    parser.add_argument("--db-path", default=None, help="Override database path")
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    """CLI entry point."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.action == "capture":
        source_type = args.source_type
        body = args.body
        title = args.title
        metadata: dict[str, Any] = {}

        if source_type == "url" and args.url:
            body = body or f"URL to process: {args.url}"
            metadata["source_url"] = args.url
        elif source_type == "bookmark" and args.url:
            body = body or args.url
            metadata["source_url"] = args.url
            title = title or args.url[:60]

        if not body:
            print("Error: --body is required for capture (or --url for url/bookmark types)")
            return 1

        result = capture(
            source_type=source_type,
            body=body,
            title=title,
            metadata=metadata,
            db_path=args.db_path,
        )
        if result["ok"]:
            print(f"Captured: {result['id']}")
            print(f"  Stage: capture")
            print(f"  Type: {source_type}")
            print(f"  Title: {result['item']['title'][:80]}")
        else:
            print(f"Error: {result['error']}")
            return 1
        return 0

    if args.action == "process":
        if not args.item_id:
            print("Error: --id is required for process action")
            return 1
        result = process_item(args.item_id, db_path=args.db_path)
        if result["ok"]:
            print(f"Processed: {result['id']}")
            print(f"  Tags: {result['tags']}")
            print(f"  Theme: {result['theme']}")
            print(f"  Summary: {result['summary'][:100]}")
        else:
            print(f"Error: {result['error']}")
            return 1
        return 0

    if args.action == "create":
        if not args.item_id:
            print("Error: --id is required for create action")
            return 1
        result = create_from_item(
            args.item_id,
            output_type=args.output_type,
            db_path=args.db_path,
        )
        if result["ok"]:
            print(f"Created: {result['id']}")
            print(f"  Output type: {result['output_type']}")
            print(f"  Preview: {result['content_preview'][:100]}")
        else:
            print(f"Error: {result['error']}")
            return 1
        return 0

    if args.action == "publish":
        if not args.item_id:
            print("Error: --id is required for publish action")
            return 1
        result = publish_item(
            args.item_id,
            platform=args.platform,
            db_path=args.db_path,
        )
        if result["ok"]:
            print(f"Published to queue: {result['id']}")
            print(f"  Platform: {result['platform']}")
            if result.get("draft_queue_result"):
                print(f"  Draft ID: {result['draft_queue_result'].get('id', 'N/A')}")
        else:
            print(f"Error: {result['error']}")
            return 1
        return 0

    if args.action == "list":
        items = list_items(
            stage=args.stage or None,
            limit=args.limit,
            db_path=args.db_path,
        )
        if not items:
            print("No items found.")
        else:
            print(f"Content items ({len(items)}):")
            for item in items:
                print(f"  [{item['id']}] {item['stage']}/{item['source_type']} -- {item['title'][:60]}")
        return 0

    if args.action == "get":
        if not args.item_id:
            print("Error: --id is required for get action")
            return 1
        item = get_item(args.item_id, db_path=args.db_path)
        if item:
            print(json.dumps(item, indent=2))
        else:
            print(f"Item {args.item_id} not found")
            return 1
        return 0

    if args.action == "move":
        if not args.item_id:
            print("Error: --id is required for move action")
            return 1
        if not args.to_stage:
            print("Error: --to is required for move action")
            return 1
        result = move_item(
            args.item_id,
            to_stage=args.to_stage,
            db_path=args.db_path,
        )
        if result["ok"]:
            print(f"Moved: {result['id']} from '{result['from_stage']}' to '{result['to_stage']}'")
        else:
            print(f"Error: {result['error']}")
            return 1
        return 0

    if args.action == "stats":
        stats = get_stats(db_path=args.db_path)
        print("Content Workflow Stats:")
        print(f"  Total items: {stats['total_items']}")
        print(f"  By stage:")
        for stage, count in stats["by_stage"].items():
            print(f"    {stage}: {count}")
        if stats["by_source_type"]:
            print(f"  By source type:")
            for st, count in stats["by_source_type"].items():
                print(f"    {st}: {count}")
        if stats["by_theme"]:
            print(f"  By theme:")
            for theme, count in stats["by_theme"].items():
                print(f"    {theme}: {count}")
        return 0

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
