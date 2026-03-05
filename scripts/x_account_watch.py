#!/usr/bin/env python3
"""
Manage read-only personal X account watch feeds for social-research ingest.
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parents[1]


def _load_local_env() -> None:
    env_path = BASE_DIR / ".env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key or key in os.environ:
            continue
        value = value.strip()
        if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
            value = value[1:-1]
        os.environ[key] = value


_load_local_env()

WORKING_DIR = Path(os.getenv("PERMANENCE_WORKING_DIR", str(BASE_DIR / "memory" / "working")))
OUTPUT_DIR = Path(os.getenv("PERMANENCE_OUTPUT_DIR", str(BASE_DIR / "outputs")))
TOOL_DIR = Path(os.getenv("PERMANENCE_TOOL_DIR", str(BASE_DIR / "memory" / "tool")))
FEEDS_PATH = Path(
    os.getenv("PERMANENCE_SOCIAL_RESEARCH_FEEDS_PATH", str(WORKING_DIR / "social_research_feeds.json"))
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now().isoformat()


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _normalize_handle(value: str) -> str:
    token = str(value or "").strip()
    if not token:
        return ""
    token = token.replace("https://x.com/", "").replace("http://x.com/", "")
    token = token.replace("https://twitter.com/", "").replace("http://twitter.com/", "")
    token = token.split("?", 1)[0].split("/", 1)[0].strip()
    token = token.lstrip("@").strip()
    cleaned = "".join(ch for ch in token if ch.isalnum() or ch == "_")
    if not cleaned:
        return ""
    if len(cleaned) > 15:
        cleaned = cleaned[:15]
    return cleaned.lower()


def _extract_handle_from_feed(feed: dict[str, Any]) -> str:
    handle = _normalize_handle(str(feed.get("x_handle") or ""))
    if handle:
        return handle
    query = str(feed.get("query") or "").lower()
    marker = "from:"
    idx = query.find(marker)
    if idx == -1:
        return ""
    tail = query[idx + len(marker) :].strip()
    parts = tail.split()
    if not parts:
        return ""
    return _normalize_handle(parts[0])


def _personal_x_feeds(feeds: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in feeds:
        if not isinstance(row, dict):
            continue
        platform = str(row.get("platform") or "").strip().lower()
        if platform not in {"x", "twitter"}:
            continue
        handle = _extract_handle_from_feed(row)
        if not handle:
            continue
        out.append(
            {
                "handle": handle,
                "name": str(row.get("name") or f"X Personal @{handle}"),
                "query": str(row.get("query") or ""),
                "max_results": int(row.get("max_results") or 25),
            }
        )
    out.sort(key=lambda item: item["handle"])
    return out


def _build_query(handle: str, include_replies: bool) -> str:
    clauses = [f"from:{handle}", "-is:retweet", "lang:en"]
    if not include_replies:
        clauses.insert(2, "-is:reply")
    return " ".join(clauses)


def _upsert_feed(
    feeds: list[dict[str, Any]],
    handle: str,
    max_results: int,
    include_replies: bool,
    label: str = "",
) -> tuple[list[dict[str, Any]], bool]:
    normalized = _normalize_handle(handle)
    if not normalized:
        return feeds, False

    query = _build_query(normalized, include_replies=include_replies)
    title = str(label or f"X Personal @{normalized}").strip()
    max_results = max(10, min(100, int(max_results)))
    updated = False
    out: list[dict[str, Any]] = []
    matched = False

    for row in feeds:
        if not isinstance(row, dict):
            continue
        platform = str(row.get("platform") or "").strip().lower()
        existing_handle = _extract_handle_from_feed(row)
        if platform in {"x", "twitter"} and existing_handle == normalized:
            patched = dict(row)
            patched["name"] = title
            patched["platform"] = "x"
            patched["query"] = query
            patched["max_results"] = max_results
            patched["x_handle"] = normalized
            patched["read_only"] = True
            patched["owner_scope"] = "personal"
            patched["updated_at"] = _now_iso()
            out.append(patched)
            matched = True
            updated = True
            continue
        out.append(row)

    if not matched:
        out.append(
            {
                "name": title,
                "platform": "x",
                "query": query,
                "max_results": max_results,
                "x_handle": normalized,
                "read_only": True,
                "owner_scope": "personal",
                "created_at": _now_iso(),
                "updated_at": _now_iso(),
                "notes": "Read-only personal account watch feed. No publishing endpoints.",
            }
        )
        updated = True
    return out, updated


def _remove_feed(feeds: list[dict[str, Any]], handle: str) -> tuple[list[dict[str, Any]], bool]:
    normalized = _normalize_handle(handle)
    if not normalized:
        return feeds, False
    out: list[dict[str, Any]] = []
    removed = False
    for row in feeds:
        if not isinstance(row, dict):
            continue
        platform = str(row.get("platform") or "").strip().lower()
        existing_handle = _extract_handle_from_feed(row)
        if platform in {"x", "twitter"} and existing_handle == normalized:
            removed = True
            continue
        out.append(row)
    return out, removed


def _write_report(
    *,
    action: str,
    feeds_path: Path,
    handles_input: list[str],
    list_rows: list[dict[str, Any]],
    changed: bool,
    warnings: list[str],
) -> tuple[Path, Path]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    TOOL_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _now().strftime("%Y%m%d-%H%M%S")
    md_path = OUTPUT_DIR / f"x_account_watch_{stamp}.md"
    latest_md = OUTPUT_DIR / "x_account_watch_latest.md"
    json_path = TOOL_DIR / f"x_account_watch_{stamp}.json"

    lines = [
        "# X Account Watch",
        "",
        f"Generated (UTC): {_now_iso()}",
        f"Action: {action}",
        f"Feeds path: {feeds_path}",
        f"Changed: {changed}",
        f"Handles input: {', '.join(handles_input) if handles_input else '-'}",
        "",
        "## Watched Accounts",
    ]
    if not list_rows:
        lines.append("- none")
    else:
        for row in list_rows:
            lines.append(
                f"- @{row.get('handle')}: max_results={row.get('max_results')} | query={row.get('query')}"
            )
    lines.extend(
        [
            "",
            "## Governance",
            "- Read-only feed setup only. This command does not post, like, follow, or send DMs.",
            "- Social publishing remains disabled unless explicitly enabled elsewhere.",
        ]
    )
    if warnings:
        lines.extend(["", "## Warnings"])
        for row in warnings:
            lines.append(f"- {row}")

    payload = {
        "generated_at": _now_iso(),
        "action": action,
        "feeds_path": str(feeds_path),
        "handles_input": handles_input,
        "changed": changed,
        "watch_count": len(list_rows),
        "watched_accounts": list_rows,
        "warnings": warnings,
        "latest_markdown": str(latest_md),
    }
    report = "\n".join(lines) + "\n"
    md_path.write_text(report, encoding="utf-8")
    latest_md.write_text(report, encoding="utf-8")
    _write_json(json_path, payload)
    return md_path, json_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Manage read-only personal X account watch feeds.")
    parser.add_argument("--action", choices=["list", "add", "remove"], default="list")
    parser.add_argument("--handle", action="append", default=[], help="X handle, @handle, or profile URL (repeatable)")
    parser.add_argument("--max-results", type=int, default=25, help="Max results for added watch feed")
    parser.add_argument("--include-replies", action="store_true", help="Keep replies in account query")
    parser.add_argument("--label", help="Optional feed display name for single add")
    parser.add_argument("--feeds-path", help="Override feeds JSON path")
    args = parser.parse_args(argv)

    feeds_path = Path(args.feeds_path).expanduser() if args.feeds_path else FEEDS_PATH
    payload = _read_json(feeds_path, [])
    feeds = [row for row in payload if isinstance(row, dict)] if isinstance(payload, list) else []
    warnings: list[str] = []
    changed = False

    handles = [_normalize_handle(row) for row in args.handle]
    handles = [row for row in handles if row]
    if args.action in {"add", "remove"} and not handles:
        warnings.append("No valid handle provided. Use --handle @your_account.")

    if args.action == "add":
        for idx, handle in enumerate(handles):
            label = str(args.label or "").strip() if (idx == 0 and len(handles) == 1) else ""
            feeds, row_changed = _upsert_feed(
                feeds,
                handle=handle,
                max_results=max(10, min(100, int(args.max_results))),
                include_replies=bool(args.include_replies),
                label=label,
            )
            changed = changed or row_changed
        if changed:
            _write_json(feeds_path, feeds)
    elif args.action == "remove":
        for handle in handles:
            feeds, row_removed = _remove_feed(feeds, handle=handle)
            changed = changed or row_removed
        if changed:
            _write_json(feeds_path, feeds)

    list_rows = _personal_x_feeds(feeds)
    md_path, json_path = _write_report(
        action=args.action,
        feeds_path=feeds_path,
        handles_input=handles,
        list_rows=list_rows,
        changed=changed,
        warnings=warnings,
    )
    print(f"X account watch report: {md_path}")
    print(f"X account watch latest: {OUTPUT_DIR / 'x_account_watch_latest.md'}")
    print(f"Tool payload: {json_path}")
    print(f"Watched accounts: {len(list_rows)}")
    if warnings:
        print(f"Warnings: {len(warnings)}")
    if warnings and args.action in {"add", "remove"}:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
