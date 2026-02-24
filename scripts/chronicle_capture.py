#!/usr/bin/env python3
"""
Capture a timestamped project session event into the chronicle log.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any

from scripts.chronicle_common import (
    BASE_DIR,
    CHRONICLE_EVENTS,
    append_jsonl,
    detect_signals,
    ensure_chronicle_dirs,
    normalize_path,
    safe_read_excerpt,
    utc_iso,
)


def _run_out(cmd: list[str]) -> str:
    try:
        return subprocess.check_output(cmd, cwd=BASE_DIR).decode("utf-8", errors="ignore").strip()
    except Exception:
        return ""


def _git_changed_files() -> list[str]:
    raw = _run_out(["git", "status", "--porcelain"])
    files: list[str] = []
    for line in raw.splitlines():
        if not line:
            continue
        path = line[3:].strip()
        if path:
            files.append(path)
    return files


def _collect_log_issue_counts(max_lines: int) -> dict[str, Any]:
    logs_dir = BASE_DIR / "logs"
    if not logs_dir.exists():
        return {"error_hits": 0, "warning_hits": 0, "files_checked": 0}

    files = sorted(logs_dir.glob("*.log"), key=lambda p: p.stat().st_mtime, reverse=True)[:6]
    error_hits = 0
    warning_hits = 0
    for path in files:
        try:
            lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()[-max_lines:]
        except Exception:
            continue
        text = "\n".join(lines).lower()
        error_hits += text.count("error")
        warning_hits += text.count("warning")
    return {"error_hits": error_hits, "warning_hits": warning_hits, "files_checked": len(files)}


def _extract_chat_info(chat_file: Path | None, sample_chars: int) -> dict[str, Any]:
    if not chat_file:
        return {"chat_file": None, "chat_signals": {"frustration_hits": 0, "direction_hits": 0, "issue_hits": 0}}
    if not chat_file.exists():
        return {"chat_file": normalize_path(chat_file), "chat_missing": True, "chat_signals": {"frustration_hits": 0, "direction_hits": 0, "issue_hits": 0}}

    excerpt = safe_read_excerpt(chat_file, max_chars=sample_chars)
    return {
        "chat_file": normalize_path(chat_file),
        "chat_missing": False,
        "chat_excerpt_preview": excerpt[:280].replace("\n", " ").strip(),
        "chat_signals": detect_signals(excerpt),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Capture chronicle session event.")
    parser.add_argument("--note", default="", help="Session note")
    parser.add_argument("--chat-file", help="Optional chat export/text file path")
    parser.add_argument("--tag", action="append", default=[], help="Tag (repeatable)")
    parser.add_argument("--max-log-lines", type=int, default=200, help="Recent lines per log file to analyze")
    parser.add_argument("--sample-chars", type=int, default=1200, help="Excerpt chars for chat signal scan")
    args = parser.parse_args()

    ensure_chronicle_dirs()

    branch = _run_out(["git", "rev-parse", "--abbrev-ref", "HEAD"])
    head = _run_out(["git", "rev-parse", "HEAD"])
    changed_files = _git_changed_files()
    log_counts = _collect_log_issue_counts(max_lines=args.max_log_lines)
    note_signals = detect_signals(args.note)

    chat_path = Path(args.chat_file).expanduser() if args.chat_file else None
    chat_info = _extract_chat_info(chat_path, sample_chars=args.sample_chars)

    event: dict[str, Any] = {
        "timestamp": utc_iso(),
        "type": "session_capture",
        "note": args.note,
        "tags": args.tag,
        "git_branch": branch,
        "git_head": head,
        "changed_files_count": len(changed_files),
        "changed_files": changed_files[:80],
        "log_issue_counts": log_counts,
        "note_signals": note_signals,
    }
    event.update(chat_info)

    append_jsonl(CHRONICLE_EVENTS, event)
    print(json.dumps(event, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
