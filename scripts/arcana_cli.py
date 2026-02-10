#!/usr/bin/env python3
"""
Arcana CLI actions: scan and looking-glass.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(BASE_DIR)

from memory.zero_point import ZeroPoint  # noqa: E402
from special.arcana_engine import ArcanaEngine  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Arcana Engine actions")
    parser.add_argument("--mode", choices=["scan", "looking-glass"], default="scan")
    parser.add_argument("--query", help="Query/context string for looking-glass")
    parser.add_argument("--branches", type=int, default=3, help="Branch count for looking-glass")
    parser.add_argument("--last", type=int, default=50, help="Entry count for scan window")
    args = parser.parse_args()

    zp = ZeroPoint()
    arcana = ArcanaEngine(zero_point=zp)

    if args.mode == "scan":
        entries = list(zp.entries.values())[-max(1, args.last) :]
        payload = [e.content for e in entries]
        report = arcana.scan_for_patterns(payload)
    else:
        context = {"query": args.query or "", "last_entries": args.last}
        report = arcana.project_looking_glass(context, branches=args.branches)

    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
