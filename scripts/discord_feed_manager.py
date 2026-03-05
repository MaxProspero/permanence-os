#!/usr/bin/env python3
"""
Manage Discord feed rows in social_research_feeds.json.

This script prepares channel ingest config so Discord pull can be enabled as
soon as PERMANENCE_DISCORD_BOT_TOKEN is installed.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parents[1]
WORKING_DIR = Path(os.getenv("PERMANENCE_WORKING_DIR", str(BASE_DIR / "memory" / "working")))
FEEDS_PATH = Path(
    os.getenv("PERMANENCE_SOCIAL_RESEARCH_FEEDS_PATH", str(WORKING_DIR / "social_research_feeds.json"))
)
OUTPUT_DIR = Path(os.getenv("PERMANENCE_OUTPUT_DIR", str(BASE_DIR / "outputs")))
TOOL_DIR = Path(os.getenv("PERMANENCE_TOOL_DIR", str(BASE_DIR / "memory" / "tool")))
CHANNEL_LINK_RE = re.compile(r"discord(?:app)?\.com/channels/\d+/(\d+)")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now().isoformat()


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _read_feeds(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(payload, list):
        return []
    return [row for row in payload if isinstance(row, dict)]


def _write_feeds(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")


def _discord_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [row for row in rows if str(row.get("platform") or "").lower() == "discord"]


def _find_discord_row(rows: list[dict[str, Any]], name: str, channel_id: str) -> dict[str, Any] | None:
    for row in _discord_rows(rows):
        if channel_id and str(row.get("channel_id") or "").strip() == channel_id.strip():
            return row
        if name and str(row.get("name") or "").strip().lower() == name.strip().lower():
            return row
    return None


def _channel_id_from_link(link: str) -> str:
    text = str(link or "").strip()
    if not text:
        return ""
    match = CHANNEL_LINK_RE.search(text)
    if not match:
        return ""
    return str(match.group(1) or "").strip()


def _normalize_keywords(items: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        for token in str(item or "").split(","):
            value = token.strip()
            if not value or value.lower() in seen:
                continue
            seen.add(value.lower())
            out.append(value)
    return out


def _normalize_priority(value: Any) -> str:
    token = str(value or "").strip().lower()
    if token in {"urgent", "high", "normal", "low"}:
        return token
    return "normal"


def _write_report(
    *,
    action: str,
    feeds_path: Path,
    discord_rows: list[dict[str, Any]],
    changed: bool,
    notes: list[str],
) -> tuple[Path, Path]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    TOOL_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _now().strftime("%Y%m%d-%H%M%S")
    md_path = OUTPUT_DIR / f"discord_feed_manager_{stamp}.md"
    latest_md = OUTPUT_DIR / "discord_feed_manager_latest.md"
    json_path = TOOL_DIR / f"discord_feed_manager_{stamp}.json"

    lines = [
        "# Discord Feed Manager",
        "",
        f"Generated (UTC): {_now_iso()}",
        f"Action: {action}",
        f"Feeds path: {feeds_path}",
        f"Changed: {changed}",
        "",
        "## Discord Feeds",
        f"- Total Discord rows: {len(discord_rows)}",
    ]
    for row in discord_rows:
        include_keywords = row.get("include_keywords") if isinstance(row.get("include_keywords"), list) else []
        exclude_keywords = row.get("exclude_keywords") if isinstance(row.get("exclude_keywords"), list) else []
        lines.append(
            f"- {row.get('name','(unnamed)')} | enabled={bool(row.get('enabled', False))} | "
            f"channel_id={row.get('channel_id','')} | max_messages={_safe_int(row.get('max_messages'), 50)} | "
            f"priority={_normalize_priority(row.get('priority'))} | "
            f"min_chars={_safe_int(row.get('min_chars'), 0)} | include={','.join(include_keywords) or '-'} | "
            f"exclude={','.join(exclude_keywords) or '-'}"
        )
    if notes:
        lines.extend(["", "## Notes"])
        for note in notes:
            lines.append(f"- {note}")
    lines.append("")

    report = "\n".join(lines)
    md_path.write_text(report, encoding="utf-8")
    latest_md.write_text(report, encoding="utf-8")
    payload = {
        "generated_at": _now_iso(),
        "action": action,
        "feeds_path": str(feeds_path),
        "changed": changed,
        "discord_feeds": discord_rows,
        "notes": notes,
        "latest_markdown": str(latest_md),
    }
    json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return md_path, json_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Manage Discord rows in social_research_feeds.json")
    parser.add_argument("--action", choices=["list", "add", "enable", "disable", "remove"], default="list")
    parser.add_argument("--name", default="", help="Discord feed display name")
    parser.add_argument("--channel-id", default="", help="Discord channel ID")
    parser.add_argument("--channel-link", default="", help="Discord channel URL (extracts channel ID)")
    parser.add_argument("--invite-url", default="", help="Optional invite URL")
    parser.add_argument("--max-messages", type=int, default=50, help="Discord message pull limit")
    parser.add_argument("--include-keyword", action="append", default=[], help="Include keyword filter (repeatable)")
    parser.add_argument("--exclude-keyword", action="append", default=[], help="Exclude keyword filter (repeatable)")
    parser.add_argument("--priority", choices=["urgent", "high", "normal", "low"], help="Feed priority level")
    parser.add_argument("--min-chars", type=int, help="Minimum message length filter")
    parser.add_argument("--clear-filters", action="store_true", help="Clear include/exclude/min-chars filters")
    parser.add_argument("--feeds-path", help="Feeds JSON path")
    parser.add_argument("--disabled", action="store_true", help="For add: create disabled row")
    args = parser.parse_args(argv)

    feeds_path = Path(args.feeds_path).expanduser() if args.feeds_path else FEEDS_PATH
    rows = _read_feeds(feeds_path)
    changed = False
    notes: list[str] = []
    name = args.name.strip()
    link_channel_id = _channel_id_from_link(args.channel_link)
    channel_id = args.channel_id.strip() or link_channel_id
    include_keywords = _normalize_keywords(args.include_keyword or [])
    exclude_keywords = _normalize_keywords(args.exclude_keyword or [])
    if args.channel_link.strip() and not link_channel_id:
        print("channel-link did not match expected Discord channel URL format.")
        return 2

    if args.action == "add":
        if not name and not channel_id:
            print("add requires --name and/or --channel-id/--channel-link")
            return 2
        existing = _find_discord_row(rows, name=name, channel_id=channel_id)
        if existing is None:
            row = {
                "name": name or f"Discord {channel_id}",
                "platform": "discord",
                "enabled": not args.disabled,
                "channel_id": channel_id,
                "max_messages": max(1, int(args.max_messages)),
                "priority": _normalize_priority(args.priority),
            }
            if args.invite_url.strip():
                row["invite_url"] = args.invite_url.strip()
            if include_keywords:
                row["include_keywords"] = include_keywords
            if exclude_keywords:
                row["exclude_keywords"] = exclude_keywords
            if args.min_chars is not None:
                row["min_chars"] = max(0, int(args.min_chars))
            row["notes"] = "Managed by discord-feed-manager."
            rows.append(row)
            changed = True
            notes.append(f"added discord feed: {row['name']}")
        else:
            existing["name"] = name or str(existing.get("name") or "Discord feed")
            if channel_id:
                existing["channel_id"] = channel_id
            existing["max_messages"] = max(1, int(args.max_messages))
            if args.priority:
                existing["priority"] = _normalize_priority(args.priority)
            if args.invite_url.strip():
                existing["invite_url"] = args.invite_url.strip()
            if args.clear_filters:
                existing.pop("include_keywords", None)
                existing.pop("exclude_keywords", None)
                existing.pop("min_chars", None)
            if include_keywords:
                existing["include_keywords"] = include_keywords
            if exclude_keywords:
                existing["exclude_keywords"] = exclude_keywords
            if args.min_chars is not None:
                existing["min_chars"] = max(0, int(args.min_chars))
            changed = True
            notes.append(f"updated discord feed: {existing.get('name')}")

    elif args.action in {"enable", "disable", "remove"}:
        target = _find_discord_row(rows, name=name, channel_id=channel_id)
        if target is None:
            print("No matching Discord feed found; pass --name and/or --channel-id.")
            return 1
        if args.action == "enable":
            target["enabled"] = True
            changed = True
            notes.append(f"enabled: {target.get('name')}")
        elif args.action == "disable":
            target["enabled"] = False
            changed = True
            notes.append(f"disabled: {target.get('name')}")
        elif args.action == "remove":
            rows = [row for row in rows if row is not target]
            changed = True
            notes.append(f"removed: {target.get('name')}")

    if changed:
        _write_feeds(feeds_path, rows)

    discord_rows = _discord_rows(rows)
    md_path, json_path = _write_report(
        action=args.action,
        feeds_path=feeds_path,
        discord_rows=discord_rows,
        changed=changed,
        notes=notes,
    )
    print(f"Discord feed manager written: {md_path}")
    print(f"Discord feed manager latest: {OUTPUT_DIR / 'discord_feed_manager_latest.md'}")
    print(f"Tool payload written: {json_path}")
    print(f"Discord feeds: {len(discord_rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
