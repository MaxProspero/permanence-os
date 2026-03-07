#!/usr/bin/env python3
"""
PERMANENCE OS — THE LEDGER (Notion Integration)
A-KWJ-0368 // BUILD DATE 26.03.07 // STATUS ACTIVE

THE LEDGER is the governed project intelligence layer backed by Notion.
It syncs Ophtxn agent status, task queues, and key milestones to a
shared Notion database so the owner has a live, auditable record.

USAGE:
  python scripts/ledger_sync.py --check      # verify connection
  python scripts/ledger_sync.py --sync       # push current ops state
  python scripts/ledger_sync.py --list       # list LEDGER pages
  python scripts/ledger_sync.py --create-db  # scaffold LEDGER database

SETUP:
  1. Create a Notion integration at https://www.notion.so/my-integrations
  2. Copy the "Internal Integration Secret" → set NOTION_API_KEY in .env
  3. Share your target page/database with the integration
  4. Copy the database ID → set NOTION_LEDGER_DB_ID in .env
  5. Run: python scripts/ledger_sync.py --check
"""

import os
import sys
import json
import argparse
import logging
from datetime import datetime, timezone
from typing import Any, Optional

try:
    import requests as _requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

# ── Config ─────────────────────────────────────────────────────────────────
NOTION_API_KEY   = os.getenv("NOTION_API_KEY", "").strip()
NOTION_LEDGER_DB = os.getenv("NOTION_LEDGER_DB_ID", "").strip()
NOTION_VERSION   = "2022-06-28"
NOTION_BASE      = "https://api.notion.com/v1"
TIMEOUT          = 10

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s  %(message)s",
)
log = logging.getLogger("ledger")


# ── HTTP helpers ────────────────────────────────────────────────────────────

def _headers() -> dict:
    return {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }


def _get(path: str, params: Optional[dict] = None) -> dict:
    try:
        r = _requests.get(
            f"{NOTION_BASE}{path}",
            headers=_headers(),
            params=params or {},
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        return r.json()
    except Exception as exc:
        return {"object": "error", "message": str(exc)}


def _post(path: str, payload: dict) -> dict:
    try:
        r = _requests.post(
            f"{NOTION_BASE}{path}",
            headers=_headers(),
            json=payload,
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        return r.json()
    except Exception as exc:
        return {"object": "error", "message": str(exc)}


def _patch(path: str, payload: dict) -> dict:
    try:
        r = _requests.patch(
            f"{NOTION_BASE}{path}",
            headers=_headers(),
            json=payload,
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        return r.json()
    except Exception as exc:
        return {"object": "error", "message": str(exc)}


# ── Rich-text builder ───────────────────────────────────────────────────────

def _rt(text: str) -> list:
    """Minimal rich-text array for Notion API."""
    return [{"type": "text", "text": {"content": text}}]


# ── Connection check ────────────────────────────────────────────────────────

def check_connection() -> bool:
    if not HAS_REQUESTS:
        log.error("requests library not installed — run: pip install requests")
        return False
    if not NOTION_API_KEY:
        log.error("NOTION_API_KEY not set in environment.")
        log.info("Add it to your .env: NOTION_API_KEY=secret_xxx")
        return False
    data = _get("/users/me")
    if data.get("object") == "error":
        log.error("Notion auth failed: %s", data.get("message", "unknown error"))
        return False
    bot_name = data.get("name") or data.get("bot", {}).get("workspace_name", "unknown")
    log.info("✓ Connected to Notion as: %s", bot_name)
    return True


# ── Database scaffold ───────────────────────────────────────────────────────

LEDGER_SCHEMA = {
    "Name": {"title": {}},
    "Status": {
        "select": {
            "options": [
                {"name": "PERMANENT", "color": "yellow"},
                {"name": "SEALED",    "color": "blue"},
                {"name": "ACTIVE",    "color": "green"},
                {"name": "PENDING",   "color": "gray"},
            ]
        }
    },
    "Category": {
        "select": {
            "options": [
                {"name": "Agent",    "color": "purple"},
                {"name": "Task",     "color": "orange"},
                {"name": "Revenue",  "color": "green"},
                {"name": "Comms",    "color": "blue"},
                {"name": "Infra",    "color": "red"},
                {"name": "Research", "color": "pink"},
            ]
        }
    },
    "Priority": {
        "select": {
            "options": [
                {"name": "P0 — Critical",  "color": "red"},
                {"name": "P1 — High",      "color": "orange"},
                {"name": "P2 — Normal",    "color": "yellow"},
                {"name": "P3 — Low",       "color": "gray"},
            ]
        }
    },
    "Agent": {"rich_text": {}},
    "Notes": {"rich_text": {}},
    "Synced At": {"date": {}},
}


def create_ledger_database(parent_page_id: str) -> Optional[str]:
    """
    Scaffold a LEDGER database on the given Notion parent page.
    Returns the new database ID, or None on failure.
    """
    if not check_connection():
        return None
    if not parent_page_id:
        log.error("parent_page_id required — pass the Notion page ID to host the database")
        return None

    payload = {
        "parent": {"type": "page_id", "page_id": parent_page_id},
        "title": _rt("THE LEDGER // A-KWJ-0368"),
        "properties": LEDGER_SCHEMA,
    }
    result = _post("/databases", payload)
    if result.get("object") == "error":
        log.error("Failed to create LEDGER database: %s", result.get("message"))
        return None

    db_id = result.get("id", "")
    log.info("✓ LEDGER database created: %s", db_id)
    log.info("  Set NOTION_LEDGER_DB_ID=%s in your .env", db_id)
    return db_id


# ── LEDGER read ─────────────────────────────────────────────────────────────

def list_ledger_pages(limit: int = 20) -> list[dict]:
    """Query LEDGER database and return page summaries."""
    if not check_connection():
        return []
    if not NOTION_LEDGER_DB:
        log.error("NOTION_LEDGER_DB_ID not set — run --create-db or set it in .env")
        return []

    result = _post(f"/databases/{NOTION_LEDGER_DB}/query", {"page_size": limit})
    if result.get("object") == "error":
        log.error("Query failed: %s", result.get("message"))
        return []

    pages = []
    for page in result.get("results", []):
        props = page.get("properties", {})
        name_prop = props.get("Name", {})
        title_arr = name_prop.get("title", [])
        name = title_arr[0]["text"]["content"] if title_arr else "(untitled)"
        status_prop = props.get("Status", {}).get("select") or {}
        category_prop = props.get("Category", {}).get("select") or {}
        pages.append({
            "id":       page.get("id"),
            "name":     name,
            "status":   status_prop.get("name", "—"),
            "category": category_prop.get("name", "—"),
            "url":      page.get("url", ""),
        })
    return pages


# ── LEDGER write ────────────────────────────────────────────────────────────

def upsert_ledger_entry(
    name: str,
    status: str = "ACTIVE",
    category: str = "Task",
    priority: str = "P2 — Normal",
    agent: str = "",
    notes: str = "",
) -> Optional[str]:
    """
    Create or update a LEDGER entry. Returns the page ID, or None on failure.
    Looks for an existing page with the same name and updates it; creates if absent.
    """
    if not check_connection():
        return None
    if not NOTION_LEDGER_DB:
        log.error("NOTION_LEDGER_DB_ID not set")
        return None

    # Search for existing entry by name
    result = _post(f"/databases/{NOTION_LEDGER_DB}/query", {
        "filter": {
            "property": "Name",
            "title": {"equals": name},
        },
        "page_size": 1,
    })
    existing = result.get("results", [])
    now_iso = datetime.now(timezone.utc).isoformat()

    props = {
        "Name":     {"title": _rt(name)},
        "Status":   {"select": {"name": status}},
        "Category": {"select": {"name": category}},
        "Priority": {"select": {"name": priority}},
        "Agent":    {"rich_text": _rt(agent)},
        "Notes":    {"rich_text": _rt(notes)},
        "Synced At": {"date": {"start": now_iso}},
    }

    if existing:
        page_id = existing[0]["id"]
        res = _patch(f"/pages/{page_id}", {"properties": props})
        if res.get("object") == "error":
            log.error("Update failed for '%s': %s", name, res.get("message"))
            return None
        log.info("✓ Updated: %s [%s]", name, status)
        return page_id
    else:
        payload = {
            "parent": {"database_id": NOTION_LEDGER_DB},
            "properties": props,
        }
        res = _post("/pages", payload)
        if res.get("object") == "error":
            log.error("Create failed for '%s': %s", name, res.get("message"))
            return None
        page_id = res.get("id", "")
        log.info("✓ Created: %s [%s]", name, status)
        return page_id


# ── Ops-state sync ──────────────────────────────────────────────────────────

AGENT_ROSTER = [
    {"name": "A-HZN-0001 HORIZON",   "category": "Agent", "agent": "HORIZON",   "priority": "P1 — High"},
    {"name": "A-NXS-0002 NEXUS",     "category": "Agent", "agent": "NEXUS",     "priority": "P1 — High"},
    {"name": "A-MDX-0003 MEDEX",     "category": "Agent", "agent": "MEDEX",     "priority": "P2 — Normal"},
    {"name": "A-FNX-0004 FINEX",     "category": "Agent", "agent": "FINEX",     "priority": "P2 — Normal"},
    {"name": "A-LXR-0005 LUXOR",     "category": "Agent", "agent": "LUXOR",     "priority": "P2 — Normal"},
    {"name": "A-SCT-0006 SCOUT",     "category": "Agent", "agent": "SCOUT",     "priority": "P2 — Normal"},
    {"name": "A-MXC-0007 MAXX CLAW", "category": "Agent", "agent": "MAXX CLAW", "priority": "P1 — High"},
]

OPEN_TASKS = [
    {"name": "Site overhaul — grain, reticle, archival system",       "category": "Infra",    "priority": "P1 — High",   "status": "SEALED",  "notes": "PR #16 + PR #17 merged"},
    {"name": "Notion MCP integration → THE LEDGER",                   "category": "Infra",    "priority": "P0 — Critical","status": "ACTIVE",  "notes": "NOTION_API_KEY required"},
    {"name": "Wire OpenClaw through NEXUS agent",                      "category": "Agent",    "priority": "P1 — High",   "status": "PENDING", "notes": "Pending OpenClaw v2 release"},
    {"name": "OrbStack + Docker sandbox for agents",                   "category": "Infra",    "priority": "P1 — High",   "status": "PENDING", "notes": "Sandboxing architecture phase 1"},
    {"name": "Inter-agent mesh protocol",                              "category": "Agent",    "priority": "P2 — Normal", "status": "PENDING", "notes": "Pending OpenClaw update"},
    {"name": "Telegram integration",                                   "category": "Comms",    "priority": "P1 — High",   "status": "SEALED",  "notes": "Connected — primary channel"},
    {"name": "Discord integration",                                    "category": "Comms",    "priority": "P2 — Normal", "status": "SEALED",  "notes": "Connected — secondary channel"},
    {"name": "Brave Search MCP",                                       "category": "Research", "priority": "P2 — Normal", "status": "PENDING", "notes": "BRAVE_API_KEY required"},
    {"name": "GitHub MCP",                                             "category": "Infra",    "priority": "P2 — Normal", "status": "PENDING", "notes": "GITHUB_TOKEN required"},
]


def sync_ops_state() -> dict:
    """Sync full ops state (agents + tasks) to THE LEDGER."""
    if not check_connection():
        return {"ok": False, "error": "connection failed"}
    if not NOTION_LEDGER_DB:
        log.error("NOTION_LEDGER_DB_ID not set — cannot sync")
        return {"ok": False, "error": "NOTION_LEDGER_DB_ID not set"}

    log.info("Syncing agent roster to THE LEDGER…")
    created = updated = failed = 0

    for agent in AGENT_ROSTER:
        pid = upsert_ledger_entry(
            name=agent["name"],
            status="ACTIVE",
            category=agent["category"],
            agent=agent["agent"],
            priority=agent["priority"],
            notes=f"Permanence OS agent — THE CONSTRUCT A-KWJ-0368",
        )
        if pid:
            created += 1
        else:
            failed += 1

    log.info("Syncing open tasks to THE LEDGER…")
    for task in OPEN_TASKS:
        pid = upsert_ledger_entry(
            name=task["name"],
            status=task["status"],
            category=task["category"],
            priority=task["priority"],
            notes=task["notes"],
        )
        if pid:
            updated += 1
        else:
            failed += 1

    now = datetime.now(timezone.utc).isoformat()
    log.info("Sync complete: %d entries pushed, %d failed — %s", created + updated, failed, now)
    return {"ok": failed == 0, "synced": created + updated, "failed": failed, "at": now}


# ── CLI ─────────────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(
        description="THE LEDGER — Notion sync for Permanence OS",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--check",      action="store_true", help="Verify Notion connection")
    ap.add_argument("--sync",       action="store_true", help="Push current ops state to THE LEDGER")
    ap.add_argument("--list",       action="store_true", help="List LEDGER pages")
    ap.add_argument("--create-db",  metavar="PAGE_ID",   help="Scaffold LEDGER database on given Notion page")
    args = ap.parse_args()

    if not HAS_REQUESTS:
        log.error("Missing dependency: pip install requests")
        sys.exit(1)

    if args.check:
        ok = check_connection()
        sys.exit(0 if ok else 1)

    elif args.create_db:
        db_id = create_ledger_database(args.create_db)
        sys.exit(0 if db_id else 1)

    elif args.list:
        pages = list_ledger_pages()
        if not pages:
            log.info("No LEDGER pages found (or database not set).")
        else:
            log.info("THE LEDGER — %d entries:", len(pages))
            for p in pages:
                print(f"  [{p['status']:8s}] {p['category']:10s}  {p['name']}")
                print(f"            {p['url']}")

    elif args.sync:
        result = sync_ops_state()
        if result.get("ok"):
            log.info("✓ THE LEDGER synced: %d entries", result.get("synced", 0))
        else:
            log.error("Sync failed: %s", result.get("error", "unknown"))
            sys.exit(1)

    else:
        ap.print_help()


if __name__ == "__main__":
    main()
