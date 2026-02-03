#!/usr/bin/env python3
"""
Weekly cleanup: rotate outputs, tool memory, and logs with retention.
"""

from __future__ import annotations

import argparse
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _prune(dir_path: str, patterns: list[str], days: int) -> int:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    removed = 0
    base = Path(dir_path)
    if not base.exists():
        return 0
    for pattern in patterns:
        for path in base.glob(pattern):
            try:
                mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
                if mtime < cutoff:
                    path.unlink()
                    removed += 1
            except OSError:
                continue
    return removed


def main() -> int:
    parser = argparse.ArgumentParser(description="Weekly cleanup with retention")
    parser.add_argument("--outputs-days", type=int, default=14, help="Retain outputs for N days")
    parser.add_argument("--tool-days", type=int, default=14, help="Retain tool memory for N days")
    parser.add_argument("--log-days", type=int, default=30, help="Retain logs for N days")
    args = parser.parse_args()

    output_dir = os.getenv("PERMANENCE_OUTPUT_DIR", os.path.join(BASE_DIR, "outputs"))
    tool_dir = os.getenv("PERMANENCE_TOOL_DIR", os.path.join(BASE_DIR, "memory", "tool"))
    log_dir = os.getenv("PERMANENCE_LOG_DIR", os.path.join(BASE_DIR, "logs"))

    outputs_removed = _prune(output_dir, ["*.md", "*.txt", "*.json"], args.outputs_days)
    tool_removed = _prune(tool_dir, ["*.txt", "*.json"], args.tool_days)
    logs_removed = _prune(log_dir, ["*.log", "*.json", "*.jsonl"], args.log_days)

    print(
        "Cleanup complete: "
        f"outputs={outputs_removed}, tool={tool_removed}, logs={logs_removed}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
