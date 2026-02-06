#!/usr/bin/env python3
"""
Verify system health and recent briefing generation.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import os
import sys

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(BASE_DIR)

from core.storage import storage  # noqa: E402

REPO_ROOT = Path(__file__).parent.parent
SOURCES_FILE = REPO_ROOT / "memory" / "working" / "sources.json"
MAX_AGE_HOURS = 8


def check_recent_briefing() -> bool:
    briefings = sorted(storage.paths.outputs_briefings.glob("briefing_*.md"), reverse=True)
    if not briefings:
        print("ERROR: no briefing files found")
        return False
    latest = briefings[0]
    file_time = datetime.fromtimestamp(latest.stat().st_mtime, tz=timezone.utc)
    age = datetime.now(timezone.utc) - file_time
    if age > timedelta(hours=MAX_AGE_HOURS):
        print(f"WARNING: latest briefing is {age.total_seconds()/3600:.1f}h old")
        print(f"File: {latest.name}")
        return False
    print(f"OK: latest briefing {latest.name} ({age.total_seconds()/3600:.1f}h ago)")
    return True


def check_sources() -> bool:
    if not SOURCES_FILE.exists():
        print("ERROR: sources.json not found")
        return False
    try:
        with open(SOURCES_FILE, "r") as f:
            sources = json.load(f)
    except json.JSONDecodeError:
        print("ERROR: sources.json invalid JSON")
        return False
    count = len(sources) if isinstance(sources, list) else 0
    print(f"OK: sources loaded {count}")
    return count >= 10


def main() -> int:
    ok = check_recent_briefing() and check_sources()
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
