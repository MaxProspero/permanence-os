#!/usr/bin/env python3
"""
Run the Social Agent summary and draft queue.
"""

import argparse
import os
import sys

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(BASE_DIR)

from agents.departments.social_agent import SocialAgent  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Social Agent summary")
    parser.add_argument("--queue-dir", help="Social queue directory")
    parser.add_argument("--max-items", type=int, default=20, help="Max items to include")
    parser.add_argument("--draft-title", help="Draft title")
    parser.add_argument("--draft-body", help="Draft body")
    parser.add_argument("--draft-platform", help="Draft platform")
    parser.add_argument("--draft-tag", action="append", default=[], help="Draft tags (repeatable)")
    args = parser.parse_args()

    agent = SocialAgent()
    if args.draft_title or args.draft_body:
        draft = {
            "title": args.draft_title,
            "body": args.draft_body,
            "platform": args.draft_platform,
            "tags": args.draft_tag,
        }
        result = agent.execute({"queue_dir": args.queue_dir, "action": "draft", "draft": draft})
    else:
        result = agent.execute({"queue_dir": args.queue_dir, "max_items": args.max_items})
    for note in result.notes:
        print(note)
    return 0 if result.status in {"SUMMARY", "DRAFT_SAVED", "NO_DRAFTS"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
