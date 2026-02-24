#!/usr/bin/env python3
"""
Backfill project chronicle from local files and write timestamped reports.
"""

from __future__ import annotations

import argparse
import json
import os
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from scripts.chronicle_common import (
    BASE_DIR,
    CHRONICLE_EVENTS,
    CHRONICLE_OUTPUT_DIR,
    append_jsonl,
    categorize_path,
    detect_signals,
    ensure_chronicle_dirs,
    fingerprint_file,
    load_backfill_index,
    normalize_path,
    safe_read_excerpt,
    save_backfill_index,
    to_utc_iso,
    utc_iso,
)

ALLOWED_EXTENSIONS = {
    ".md",
    ".txt",
    ".py",
    ".json",
    ".yaml",
    ".yml",
    ".csv",
    ".tsv",
    ".docx",
    ".pdf",
    ".ipynb",
    ".png",
    ".jpg",
    ".jpeg",
    ".heic",
}

SKIP_DIRS = {
    ".git",
    "__pycache__",
    ".venv",
    "node_modules",
    ".mypy_cache",
    ".pytest_cache",
}


def _default_roots() -> list[Path]:
    home = Path.home()
    candidates = [
        BASE_DIR,
        home / "Local_Archive" / "Documents - Payton’s MacBook Air/UARK MSF/Quantum + Future + Study",
        home / "Library" / "CloudStorage" / "GoogleDrive-hello@permanencesystems.com" / "My Drive" / "Permanence OS Ops",
        home / "Library" / "CloudStorage" / "GoogleDrive-hello@permanencesystems.com" / "My Drive" / "Permanence Research",
    ]
    return [p for p in candidates if p.exists()]


def _iter_candidates(roots: list[Path], since_days: int | None) -> list[tuple[float, int, Path]]:
    cutoff_ts: float | None = None
    if since_days is not None:
        cutoff = datetime.now(timezone.utc) - timedelta(days=since_days)
        cutoff_ts = cutoff.timestamp()

    found: list[tuple[float, int, Path]] = []
    for root in roots:
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
            for name in filenames:
                path = Path(dirpath) / name
                if path.suffix.lower() not in ALLOWED_EXTENSIONS:
                    continue
                try:
                    st = path.stat()
                except OSError:
                    continue
                if cutoff_ts is not None and st.st_mtime < cutoff_ts:
                    continue
                found.append((st.st_mtime, st.st_size, path))
    return found


def _build_markdown(snapshot: dict[str, Any]) -> str:
    categories: dict[str, int] = snapshot["category_counts"]
    top_direction = snapshot["top_direction_files"]
    top_frustration = snapshot["top_frustration_files"]
    roots = snapshot["roots"]

    lines = [
        "# Chronicle Backfill Report",
        "",
        f"- Generated: {snapshot['generated_at']}",
        f"- Files scanned: {snapshot['files_scanned']}",
        f"- Files processed: {snapshot['files_processed']}",
        f"- New fingerprints: {snapshot['new_fingerprints']}",
        f"- Truncated by max-files: {snapshot['truncated_count']}",
        "",
        "## Roots",
    ]
    lines.extend([f"- {r}" for r in roots] or ["- none"])
    lines.extend(["", "## Category Counts"])
    for cat, count in sorted(categories.items(), key=lambda x: (-x[1], x[0])):
        lines.append(f"- {cat}: {count}")

    lines.extend(["", "## Direction Signals (Top 15)"])
    if top_direction:
        for item in top_direction:
            lines.append(
                f"- {item['direction_hits']} hits | {item['path']} | mtime {item['mtime_utc']}"
            )
    else:
        lines.append("- none")

    lines.extend(["", "## Frustration Signals (Top 15)"])
    if top_frustration:
        for item in top_frustration:
            lines.append(
                f"- {item['frustration_hits']} hits | {item['path']} | mtime {item['mtime_utc']}"
            )
    else:
        lines.append("- none")

    lines.extend(["", "## Notes", "- This report is file-driven; private chat services require exported local files for ingestion."])
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill chronicle from local files.")
    parser.add_argument("--roots", nargs="*", help="Roots to scan")
    parser.add_argument("--since-days", type=int, help="Only include files modified in last N days")
    parser.add_argument("--max-files", type=int, default=4000, help="Maximum files to process")
    parser.add_argument("--sample-chars", type=int, default=1200, help="Excerpt chars for signal detection")
    parser.add_argument("--output", help="Output markdown path")
    parser.add_argument("--no-events", action="store_true", help="Do not append summary event to chronicle")
    args = parser.parse_args()

    ensure_chronicle_dirs()

    roots = [Path(r).expanduser() for r in args.roots] if args.roots else _default_roots()
    roots = [r for r in roots if r.exists()]
    if not roots:
        print("No valid roots found.")
        return 1

    candidates = _iter_candidates(roots, args.since_days)
    candidates.sort(key=lambda x: x[0])  # old -> new
    files_scanned = len(candidates)
    truncated_count = max(0, files_scanned - args.max_files)
    if files_scanned > args.max_files:
        candidates = candidates[-args.max_files :]

    records: list[dict[str, Any]] = []
    category_counter: Counter[str] = Counter()
    indexed = load_backfill_index()
    new_fingerprints = 0
    seen_in_run: set[str] = set()

    for mtime, size, path in candidates:
        fp = fingerprint_file(path, size=size, mtime=mtime)
        excerpt = safe_read_excerpt(path, max_chars=args.sample_chars)
        signals = detect_signals(excerpt)
        category = categorize_path(path)
        category_counter[category] += 1

        if fp not in indexed and fp not in seen_in_run:
            new_fingerprints += 1
            seen_in_run.add(fp)

        records.append(
            {
                "fingerprint": fp,
                "path": normalize_path(path),
                "name": path.name,
                "category": category,
                "size_bytes": size,
                "mtime_utc": to_utc_iso(mtime),
                "signals": signals,
                "excerpt_preview": excerpt[:280].replace("\n", " ").strip(),
            }
        )

    indexed |= seen_in_run
    save_backfill_index(indexed)

    direction_sorted = sorted(
        [r for r in records if r["signals"]["direction_hits"] > 0],
        key=lambda r: r["signals"]["direction_hits"],
        reverse=True,
    )[:15]
    frustration_sorted = sorted(
        [r for r in records if r["signals"]["frustration_hits"] > 0],
        key=lambda r: r["signals"]["frustration_hits"],
        reverse=True,
    )[:15]

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    json_path = CHRONICLE_OUTPUT_DIR / f"chronicle_backfill_{stamp}.json"
    md_path = Path(args.output).expanduser() if args.output else CHRONICLE_OUTPUT_DIR / f"chronicle_backfill_{stamp}.md"

    snapshot = {
        "generated_at": utc_iso(),
        "roots": [normalize_path(r) for r in roots],
        "files_scanned": files_scanned,
        "files_processed": len(records),
        "truncated_count": truncated_count,
        "new_fingerprints": new_fingerprints,
        "since_days": args.since_days,
        "max_files": args.max_files,
        "category_counts": dict(category_counter),
        "top_direction_files": [
            {"path": x["path"], "mtime_utc": x["mtime_utc"], "direction_hits": x["signals"]["direction_hits"]}
            for x in direction_sorted
        ],
        "top_frustration_files": [
            {"path": x["path"], "mtime_utc": x["mtime_utc"], "frustration_hits": x["signals"]["frustration_hits"]}
            for x in frustration_sorted
        ],
        "records": records,
    }

    json_path.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
    md_path.write_text(_build_markdown(snapshot), encoding="utf-8")

    if not args.no_events:
        append_jsonl(
            CHRONICLE_EVENTS,
            {
                "timestamp": utc_iso(),
                "type": "backfill_scan",
                "roots": [normalize_path(r) for r in roots],
                "files_scanned": files_scanned,
                "files_processed": len(records),
                "new_fingerprints": new_fingerprints,
                "truncated_count": truncated_count,
                "snapshot_json": normalize_path(json_path),
                "report_md": normalize_path(md_path),
            },
        )

    print(f"Backfill JSON: {json_path}")
    print(f"Backfill report: {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
