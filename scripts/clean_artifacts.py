#!/usr/bin/env python3
"""
Clean generated artifacts (logs, outputs, and volatile memory payloads).

This script is intentionally conservative:
- It removes only known generated file patterns.
- It keeps sentinel files such as `.gitkeep`.
"""

from __future__ import annotations

import argparse
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]

PATTERNS = {
    "logs": [
        "logs/*.log",
        "logs/*.json",
        "logs/*.jsonl",
        "logs/automation/*.log",
        "logs/automation/*.txt",
    ],
    "episodic": [
        "memory/episodic/*.json",
        "memory/episodic/*.jsonl",
    ],
    "tool": [
        "memory/tool/*.json",
        "memory/tool/*.txt",
    ],
    "working": [
        "memory/working/*.json",
        "memory/working/*.jsonl",
        "memory/working/*.md",
        "memory/working/*.txt",
    ],
    "inbox": [
        "memory/inbox/*.json",
        "memory/inbox/*.jsonl",
        "memory/inbox/*.md",
        "memory/inbox/*.txt",
    ],
    "outputs": [
        "outputs/*.md",
        "outputs/*.txt",
        "outputs/*.json",
        "outputs/horizon/*.json",
        "outputs/chronicle/*.md",
        "outputs/chronicle/*.json",
    ],
}


def _matches(targets: list[str]) -> list[Path]:
    rows: list[Path] = []
    for key in targets:
        for pattern in PATTERNS.get(key, []):
            rows.extend(BASE_DIR.glob(pattern))
    seen: set[Path] = set()
    out: list[Path] = []
    for path in sorted(rows):
        if path.name == ".gitkeep":
            continue
        if path.is_file() and path not in seen:
            out.append(path)
            seen.add(path)
    return out


def _delete(paths: list[Path], dry_run: bool) -> int:
    count = 0
    for path in paths:
        if dry_run:
            print(f"[dry-run] {path}")
            count += 1
            continue
        try:
            path.unlink()
            print(f"[deleted] {path}")
            count += 1
        except OSError as exc:
            print(f"[skip] {path} ({exc})")
    return count


def main() -> int:
    parser = argparse.ArgumentParser(description="Clean generated artifacts from local runtime.")
    parser.add_argument("--logs", action="store_true", help="Remove log files")
    parser.add_argument("--episodic", action="store_true", help="Remove episodic memory files")
    parser.add_argument("--tool", action="store_true", help="Remove memory/tool payload files")
    parser.add_argument("--working", action="store_true", help="Remove memory/working generated files")
    parser.add_argument("--inbox", action="store_true", help="Remove memory/inbox generated files")
    parser.add_argument("--outputs", action="store_true", help="Remove generated output reports")
    parser.add_argument("--all", action="store_true", help="Clean all supported artifact groups (default)")
    parser.add_argument("--dry-run", action="store_true", help="Print targets without deleting")
    args = parser.parse_args()

    selected = []
    if args.all or not any([args.logs, args.episodic, args.tool, args.working, args.inbox, args.outputs]):
        selected = list(PATTERNS.keys())
    else:
        if args.logs:
            selected.append("logs")
        if args.episodic:
            selected.append("episodic")
        if args.tool:
            selected.append("tool")
        if args.working:
            selected.append("working")
        if args.inbox:
            selected.append("inbox")
        if args.outputs:
            selected.append("outputs")

    targets = _matches(selected)
    print(f"Selected groups: {', '.join(selected)}")
    print(f"Matched files: {len(targets)}")
    removed = _delete(targets, dry_run=bool(args.dry_run))
    print(f"Removed files: {removed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
