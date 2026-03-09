#!/usr/bin/env python3
"""
Permanence OS — Social Media Draft Queue

SQLite-backed draft queue for multi-platform social content.
Agents submit drafts; humans approve/reject via dashboard API.
Canon-compliant: no auto-publishing, all posts require human approval.

Usage:
  python scripts/social_draft_queue.py --action list
  python scripts/social_draft_queue.py --action submit --platform x --content "Thread about AI agents..."
  python scripts/social_draft_queue.py --action approve --id 1 --notes "Looks good"
  python scripts/social_draft_queue.py --action reject --id 1 --notes "Too long, trim to 280 chars"
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
from datetime import datetime, timezone
from typing import Any, Optional

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DEFAULT_DB_PATH = os.path.join(BASE_DIR, "permanence_storage", "permanence.db")

VALID_PLATFORMS = ["x", "tiktok", "youtube", "linkedin", "instagram", "threads"]
VALID_CONTENT_TYPES = ["tweet", "thread", "tiktok_script", "youtube_description", "youtube_title", "post", "story", "reel_script"]
VALID_STATUSES = ["pending", "approved", "rejected", "published", "archived"]


def _get_db(db_path: str | None = None) -> sqlite3.Connection:
    """Get or create the social_drafts table."""
    path = db_path or os.environ.get("PERMANENCE_DB_PATH", DEFAULT_DB_PATH)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS social_drafts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            platform TEXT NOT NULL,
            content_type TEXT NOT NULL DEFAULT 'post',
            content TEXT NOT NULL,
            media_notes TEXT DEFAULT '',
            hashtags TEXT DEFAULT '',
            suggested_time TEXT DEFAULT '',
            status TEXT NOT NULL DEFAULT 'pending',
            agent_id TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            reviewed_at TEXT DEFAULT '',
            reviewer_notes TEXT DEFAULT '',
            published_at TEXT DEFAULT '',
            metadata TEXT DEFAULT '{}'
        )
    """)
    conn.commit()
    return conn


def submit_draft(
    platform: str,
    content: str,
    content_type: str = "post",
    media_notes: str = "",
    hashtags: str = "",
    suggested_time: str = "",
    agent_id: str = "",
    metadata: dict | None = None,
    db_path: str | None = None,
) -> dict[str, Any]:
    """Agent submits a new draft. Returns draft dict."""
    if platform not in VALID_PLATFORMS:
        return {"ok": False, "error": f"Invalid platform: {platform}. Valid: {VALID_PLATFORMS}"}

    conn = _get_db(db_path)
    now = datetime.now(timezone.utc).isoformat()
    meta_json = json.dumps(metadata or {})

    cursor = conn.execute(
        """INSERT INTO social_drafts
           (platform, content_type, content, media_notes, hashtags, suggested_time,
            status, agent_id, created_at, metadata)
           VALUES (?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?)""",
        (platform, content_type, content, media_notes, hashtags, suggested_time, agent_id, now, meta_json),
    )
    conn.commit()
    draft_id = cursor.lastrowid

    return {
        "ok": True,
        "id": draft_id,
        "platform": platform,
        "content_type": content_type,
        "status": "pending",
        "created_at": now,
    }


def list_drafts(
    platform: str | None = None,
    status: str | None = None,
    limit: int = 50,
    db_path: str | None = None,
) -> list[dict[str, Any]]:
    """List drafts with optional filters."""
    conn = _get_db(db_path)
    query = "SELECT * FROM social_drafts WHERE 1=1"
    params: list[Any] = []

    if platform:
        query += " AND platform = ?"
        params.append(platform)
    if status:
        query += " AND status = ?"
        params.append(status)

    query += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)

    rows = conn.execute(query, params).fetchall()
    return [dict(row) for row in rows]


def get_draft(draft_id: int, db_path: str | None = None) -> dict[str, Any] | None:
    """Get a single draft by ID."""
    conn = _get_db(db_path)
    row = conn.execute("SELECT * FROM social_drafts WHERE id = ?", (draft_id,)).fetchone()
    return dict(row) if row else None


def approve_draft(
    draft_id: int,
    reviewer_notes: str = "",
    db_path: str | None = None,
) -> dict[str, Any]:
    """Human approves a draft."""
    conn = _get_db(db_path)
    draft = get_draft(draft_id, db_path)
    if not draft:
        return {"ok": False, "error": f"Draft {draft_id} not found"}
    if draft["status"] != "pending":
        return {"ok": False, "error": f"Draft {draft_id} is not pending (status: {draft['status']})"}

    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "UPDATE social_drafts SET status = 'approved', reviewed_at = ?, reviewer_notes = ? WHERE id = ?",
        (now, reviewer_notes, draft_id),
    )
    conn.commit()
    return {"ok": True, "id": draft_id, "status": "approved", "reviewed_at": now}


def reject_draft(
    draft_id: int,
    reviewer_notes: str = "",
    db_path: str | None = None,
) -> dict[str, Any]:
    """Human rejects a draft with feedback."""
    conn = _get_db(db_path)
    draft = get_draft(draft_id, db_path)
    if not draft:
        return {"ok": False, "error": f"Draft {draft_id} not found"}
    if draft["status"] != "pending":
        return {"ok": False, "error": f"Draft {draft_id} is not pending (status: {draft['status']})"}

    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "UPDATE social_drafts SET status = 'rejected', reviewed_at = ?, reviewer_notes = ? WHERE id = ?",
        (now, reviewer_notes, draft_id),
    )
    conn.commit()
    return {"ok": True, "id": draft_id, "status": "rejected", "reviewed_at": now}


def mark_published(
    draft_id: int,
    db_path: str | None = None,
) -> dict[str, Any]:
    """Mark an approved draft as published (after human posts it)."""
    conn = _get_db(db_path)
    draft = get_draft(draft_id, db_path)
    if not draft:
        return {"ok": False, "error": f"Draft {draft_id} not found"}
    if draft["status"] != "approved":
        return {"ok": False, "error": f"Draft {draft_id} is not approved (status: {draft['status']})"}

    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "UPDATE social_drafts SET status = 'published', published_at = ? WHERE id = ?",
        (now, draft_id),
    )
    conn.commit()
    return {"ok": True, "id": draft_id, "status": "published", "published_at": now}


def get_stats(db_path: str | None = None) -> dict[str, Any]:
    """Get draft queue statistics."""
    conn = _get_db(db_path)
    stats = {}
    for status in VALID_STATUSES:
        row = conn.execute("SELECT COUNT(*) as cnt FROM social_drafts WHERE status = ?", (status,)).fetchone()
        stats[status] = row["cnt"] if row else 0

    platform_counts = {}
    rows = conn.execute("SELECT platform, COUNT(*) as cnt FROM social_drafts GROUP BY platform").fetchall()
    for row in rows:
        platform_counts[row["platform"]] = row["cnt"]
    stats["by_platform"] = platform_counts

    return stats


# ── CLI ───────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(description="Permanence OS — Social Draft Queue")
    parser.add_argument(
        "--action",
        choices=["list", "submit", "approve", "reject", "publish", "stats", "get"],
        required=True,
    )
    parser.add_argument("--platform", help="Platform (x, tiktok, youtube, linkedin, instagram, threads)")
    parser.add_argument("--content", help="Draft content text")
    parser.add_argument("--content-type", default="post", help="Content type (tweet, thread, tiktok_script, etc.)")
    parser.add_argument("--media-notes", default="", help="Notes about media/images to include")
    parser.add_argument("--hashtags", default="", help="Hashtags (comma-separated)")
    parser.add_argument("--suggested-time", default="", help="Suggested publish time (ISO format)")
    parser.add_argument("--agent-id", default="", help="Agent that created the draft")
    parser.add_argument("--status", help="Filter by status")
    parser.add_argument("--id", type=int, help="Draft ID (for approve/reject/publish/get)")
    parser.add_argument("--notes", default="", help="Reviewer notes (for approve/reject)")
    parser.add_argument("--limit", type=int, default=50, help="Max items to list")
    parser.add_argument("--db-path", help="Override database path")
    args = parser.parse_args()

    if args.action == "list":
        drafts = list_drafts(platform=args.platform, status=args.status, limit=args.limit, db_path=args.db_path)
        if not drafts:
            print("No drafts found.")
        else:
            for d in drafts:
                print(f"  [{d['id']}] {d['platform']}/{d['content_type']} — {d['status']} — {d['content'][:80]}...")
        return 0

    if args.action == "submit":
        if not args.platform or not args.content:
            print("--platform and --content required for submit")
            return 2
        result = submit_draft(
            platform=args.platform,
            content=args.content,
            content_type=args.content_type,
            media_notes=args.media_notes,
            hashtags=args.hashtags,
            suggested_time=args.suggested_time,
            agent_id=args.agent_id,
            db_path=args.db_path,
        )
        print(json.dumps(result, indent=2))
        return 0 if result.get("ok") else 1

    if args.action == "approve":
        if not args.id:
            print("--id required for approve")
            return 2
        result = approve_draft(args.id, reviewer_notes=args.notes, db_path=args.db_path)
        print(json.dumps(result, indent=2))
        return 0 if result.get("ok") else 1

    if args.action == "reject":
        if not args.id:
            print("--id required for reject")
            return 2
        result = reject_draft(args.id, reviewer_notes=args.notes, db_path=args.db_path)
        print(json.dumps(result, indent=2))
        return 0 if result.get("ok") else 1

    if args.action == "publish":
        if not args.id:
            print("--id required for publish")
            return 2
        result = mark_published(args.id, db_path=args.db_path)
        print(json.dumps(result, indent=2))
        return 0 if result.get("ok") else 1

    if args.action == "get":
        if not args.id:
            print("--id required for get")
            return 2
        draft = get_draft(args.id, db_path=args.db_path)
        if draft:
            print(json.dumps(draft, indent=2))
        else:
            print(f"Draft {args.id} not found")
            return 1
        return 0

    if args.action == "stats":
        stats = get_stats(db_path=args.db_path)
        print(json.dumps(stats, indent=2))
        return 0

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
