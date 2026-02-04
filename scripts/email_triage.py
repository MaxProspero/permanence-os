#!/usr/bin/env python3
"""
Run the Email Agent triage and write report to outputs.
"""

import argparse
import os
import sys

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(BASE_DIR)

from agents.departments.email_agent import EmailAgent  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Email Agent triage")
    parser.add_argument("--inbox-dir", help="Inbox directory (default: memory/working/email)")
    parser.add_argument("--vip", nargs="*", default=[], help="VIP sender emails")
    parser.add_argument("--ignore", nargs="*", default=[], help="Ignored sender emails")
    parser.add_argument("--max-items", type=int, default=25, help="Max items to include")
    args = parser.parse_args()

    agent = EmailAgent()
    task = {
        "inbox_dir": args.inbox_dir,
        "vip_senders": args.vip,
        "ignore_senders": args.ignore,
        "max_items": args.max_items,
    }
    result = agent.execute(task)
    for note in result.notes:
        print(note)
    return 0 if result.status in {"TRIAGED", "NO_MESSAGES"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
