#!/usr/bin/env python3
"""
Research inbox:
- add text/link captures
- process unprocessed captures into sources.json
- view queue status
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from agents.researcher import ResearcherAgent, TOOL_DIR

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DEFAULT_INBOX_PATH = os.path.join(BASE_DIR, "memory", "working", "research", "inbox.jsonl")
DEFAULT_STATE_PATH = os.path.join(BASE_DIR, "memory", "working", "research", "state.json")
DEFAULT_SOURCES_PATH = os.path.join(BASE_DIR, "memory", "working", "sources.json")
DEFAULT_OUTPUT_DIR = os.getenv("PERMANENCE_OUTPUT_DIR", os.path.join(BASE_DIR, "outputs"))

URL_RE = re.compile(r"https?://[^\s<>\"]+")


def _extract_urls(text: str) -> list[str]:
    seen: set[str] = set()
    urls: list[str] = []
    for candidate in URL_RE.findall(text or ""):
        cleaned = candidate.rstrip(".,);]")
        if cleaned not in seen:
            seen.add(cleaned)
            urls.append(cleaned)
    return urls


def _entry_id(text: str, source: str, channel: str, ts: str) -> str:
    payload = f"{text}|{source}|{channel}|{ts}".encode("utf-8")
    return "rx_" + hashlib.sha256(payload).hexdigest()[:12]


def _load_json(path: str, fallback: object) -> object:
    if not os.path.exists(path):
        return fallback
    try:
        with open(path, "r") as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError):
        return fallback


def _save_json(path: str, payload: object) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as handle:
        json.dump(payload, handle, indent=2)


def _load_entries(inbox_path: str) -> list[dict]:
    entries: list[dict] = []
    if not os.path.exists(inbox_path):
        return entries
    try:
        with open(inbox_path, "r") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    parsed = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(parsed, dict):
                    entries.append(parsed)
    except OSError:
        return []
    return entries


def _merge_sources(existing: list[dict], new: list[dict]) -> list[dict]:
    merged: list[dict] = []
    seen: set[tuple[str, str, str]] = set()

    def _key(item: dict) -> tuple[str, str, str]:
        return (
            str(item.get("source") or ""),
            str(item.get("origin") or ""),
            str(item.get("hash") or ""),
        )

    for item in existing + new:
        key = _key(item)
        if key in seen:
            continue
        seen.add(key)
        merged.append(item)
    return merged


def add_entry(
    text: str,
    source: str = "manual",
    channel: str = "manual",
    inbox_path: str = DEFAULT_INBOX_PATH,
) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    payload = {
        "id": _entry_id(text, source, channel, now),
        "created_at": now,
        "source": source,
        "channel": channel,
        "text": text,
        "urls": _extract_urls(text),
    }
    os.makedirs(os.path.dirname(inbox_path), exist_ok=True)
    with open(inbox_path, "a") as handle:
        handle.write(json.dumps(payload) + "\n")
    return payload


def status(
    inbox_path: str = DEFAULT_INBOX_PATH,
    state_path: str = DEFAULT_STATE_PATH,
) -> dict:
    entries = _load_entries(inbox_path)
    state = _load_json(state_path, {"processed_ids": []})
    processed = set(state.get("processed_ids", [])) if isinstance(state, dict) else set()
    unprocessed = [e for e in entries if e.get("id") not in processed]
    urls = []
    for entry in unprocessed:
        for url in entry.get("urls", []):
            urls.append(url)
    return {
        "entries_total": len(entries),
        "entries_unprocessed": len(unprocessed),
        "urls_unprocessed": len(set(urls)),
        "state_path": os.path.abspath(state_path),
        "inbox_path": os.path.abspath(inbox_path),
    }


def _default_fetcher(
    urls: list[str],
    max_sources: int,
    excerpt: int,
    timeout: int,
    max_bytes: int,
    user_agent: str,
    tool_dir: str,
) -> list[dict]:
    agent = ResearcherAgent()
    return agent.compile_sources_from_urls(
        urls=urls,
        output_path=None,
        default_confidence=0.6,
        max_entries=max_sources,
        excerpt_chars=excerpt,
        timeout_sec=timeout,
        max_bytes=max_bytes,
        user_agent=user_agent,
        tool_dir=tool_dir,
    )


def process_entries(
    inbox_path: str = DEFAULT_INBOX_PATH,
    state_path: str = DEFAULT_STATE_PATH,
    sources_path: str = DEFAULT_SOURCES_PATH,
    output_dir: str = DEFAULT_OUTPUT_DIR,
    max_sources: int = 30,
    excerpt: int = 280,
    timeout: int = 15,
    max_bytes: int = 1_000_000,
    user_agent: str = "PermanenceOS-ResearchInbox/0.1",
    tool_dir: str = TOOL_DIR,
    fetcher: Callable[..., list[dict]] | None = None,
) -> dict:
    entries = _load_entries(inbox_path)
    state = _load_json(state_path, {"processed_ids": []})
    processed_ids = set(state.get("processed_ids", [])) if isinstance(state, dict) else set()

    pending = [e for e in entries if e.get("id") and e.get("id") not in processed_ids]
    urls: list[str] = []
    seen_urls: set[str] = set()
    for entry in pending:
        for url in entry.get("urls", []):
            if url not in seen_urls:
                seen_urls.add(url)
                urls.append(url)

    fetched_sources: list[dict] = []
    if urls:
        fetch = fetcher or _default_fetcher
        fetched_sources = fetch(
            urls=urls,
            max_sources=max_sources,
            excerpt=excerpt,
            timeout=timeout,
            max_bytes=max_bytes,
            user_agent=user_agent,
            tool_dir=tool_dir,
        )

    existing = _load_json(sources_path, [])
    if not isinstance(existing, list):
        existing = []
    merged = _merge_sources(existing, fetched_sources)
    _save_json(sources_path, merged)

    for entry in pending:
        entry_id = entry.get("id")
        if entry_id:
            processed_ids.add(entry_id)
    _save_json(
        state_path,
        {
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "processed_ids": sorted(processed_ids),
            "processed_count": len(processed_ids),
        },
    )

    os.makedirs(output_dir, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    report_path = os.path.join(output_dir, f"research_inbox_{stamp}.md")
    with open(report_path, "w") as handle:
        handle.write(
            "\n".join(
                [
                    "# Research Inbox Process Report",
                    "",
                    f"Pending entries processed: {len(pending)}",
                    f"Unique URLs discovered: {len(urls)}",
                    f"New source records fetched: {len(fetched_sources)}",
                    f"Total sources after merge: {len(merged)}",
                    f"Inbox: {os.path.abspath(inbox_path)}",
                    f"State: {os.path.abspath(state_path)}",
                    f"Sources: {os.path.abspath(sources_path)}",
                ]
            )
            + "\n"
        )

    return {
        "pending_entries": len(pending),
        "urls_found": len(urls),
        "sources_fetched": len(fetched_sources),
        "sources_total": len(merged),
        "report_path": report_path,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Research inbox capture + processing")
    parser.add_argument("--action", choices=["add", "process", "status"], default="process")
    parser.add_argument("--text", help="Text payload for --action add")
    parser.add_argument("--source", default="manual", help="Source identifier for add")
    parser.add_argument("--channel", default="manual", help="Channel identifier for add")
    parser.add_argument("--inbox-path", default=DEFAULT_INBOX_PATH, help="Inbox JSONL path")
    parser.add_argument("--state-path", default=DEFAULT_STATE_PATH, help="State JSON path")
    parser.add_argument("--sources-path", default=DEFAULT_SOURCES_PATH, help="sources.json path")
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR, help="Report output directory")
    parser.add_argument("--max-sources", type=int, default=30, help="Max URLs to fetch per process run")
    parser.add_argument("--excerpt", type=int, default=280, help="Excerpt length")
    parser.add_argument("--timeout", type=int, default=15, help="URL fetch timeout")
    parser.add_argument("--max-bytes", type=int, default=1_000_000, help="Max bytes per URL")
    parser.add_argument("--user-agent", default="PermanenceOS-ResearchInbox/0.1", help="Fetch user agent")
    parser.add_argument("--tool-dir", default=TOOL_DIR, help="Tool memory directory for fetched payloads")
    args = parser.parse_args()

    if args.action == "add":
        if not args.text or not args.text.strip():
            print("Missing --text for --action add")
            return 2
        entry = add_entry(
            text=args.text.strip(),
            source=args.source.strip(),
            channel=args.channel.strip(),
            inbox_path=args.inbox_path,
        )
        print(f"Saved research inbox entry: {entry['id']} (urls={len(entry['urls'])})")
        return 0

    if args.action == "status":
        s = status(inbox_path=args.inbox_path, state_path=args.state_path)
        print(
            "Research inbox status: "
            f"total={s['entries_total']} unprocessed={s['entries_unprocessed']} "
            f"urls_unprocessed={s['urls_unprocessed']}"
        )
        return 0

    result = process_entries(
        inbox_path=args.inbox_path,
        state_path=args.state_path,
        sources_path=args.sources_path,
        output_dir=args.output_dir,
        max_sources=max(1, args.max_sources),
        excerpt=max(80, args.excerpt),
        timeout=max(1, args.timeout),
        max_bytes=max(1000, args.max_bytes),
        user_agent=args.user_agent,
        tool_dir=args.tool_dir,
    )
    print(
        "Research inbox processed: "
        f"entries={result['pending_entries']} urls={result['urls_found']} "
        f"fetched={result['sources_fetched']} total={result['sources_total']}"
    )
    print(f"Report: {result['report_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
