#!/usr/bin/env python3
"""
Run receptionist intake/summary actions.
"""

from __future__ import annotations

import argparse
import os
import sys

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(BASE_DIR)

from agents.departments.reception_agent import ReceptionAgent  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Run receptionist workflow")
    parser.add_argument("--action", choices=["intake", "summary"], default="summary", help="Reception action")
    parser.add_argument("--queue-dir", help="Queue directory override")
    parser.add_argument("--sender", help="Sender name/identifier (intake)")
    parser.add_argument("--message", help="Message body (intake)")
    parser.add_argument("--channel", help="Channel/source channel (intake)")
    parser.add_argument("--source", help="Source system (intake)")
    parser.add_argument("--priority", choices=["urgent", "high", "normal", "low"], help="Priority override")
    parser.add_argument("--max-items", type=int, default=20, help="Max open items in summary")
    parser.add_argument(
        "--name",
        default=os.getenv("PERMANENCE_RECEPTIONIST_NAME", "Ari"),
        help="Receptionist display name",
    )
    args = parser.parse_args()

    task = {
        "action": args.action,
        "queue_dir": args.queue_dir,
        "sender": args.sender,
        "message": args.message,
        "channel": args.channel,
        "source": args.source,
        "priority": args.priority,
        "max_items": args.max_items,
        "name": args.name,
    }

    agent = ReceptionAgent()
    result = agent.execute(task)
    for note in result.notes:
        print(note)
    return 0 if result.status in {"INTAKE_SAVED", "SUMMARY", "NO_ENTRIES"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
