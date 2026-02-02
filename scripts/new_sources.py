#!/usr/bin/env python3
"""
Create or append to memory/working/sources.json with proper provenance.
"""

import json
import os
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
WORKING_DIR = os.path.join(BASE_DIR, "memory", "working")
SOURCES_PATH = os.getenv(
    "PERMANENCE_SOURCES_PATH", os.path.join(WORKING_DIR, "sources.json")
)


def _load_sources(path: str) -> List[Dict[str, Any]]:
    if not os.path.exists(path):
        return []
    with open(path, "r") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError("Sources file must contain a list")
    return data


def _save_sources(path: str, sources: List[Dict[str, Any]]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(sources, f, indent=2)


def main() -> int:
    if len(sys.argv) < 3:
        print("Usage: python scripts/new_sources.py <source> <confidence> [notes]")
        return 2

    source = sys.argv[1].strip()
    confidence = float(sys.argv[2])
    notes = " ".join(sys.argv[3:]).strip() if len(sys.argv) > 3 else ""

    entry = {
        "source": source,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "confidence": confidence,
    }
    if notes:
        entry["notes"] = notes

    sources = _load_sources(SOURCES_PATH)
    sources.append(entry)
    _save_sources(SOURCES_PATH, sources)

    print(f"Added source to {SOURCES_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
