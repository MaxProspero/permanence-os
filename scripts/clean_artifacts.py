#!/usr/bin/env python3
"""
Clean generated artifacts (logs, episodic state, outputs).
"""

import argparse
import os

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
LOG_DIR = os.path.join(BASE_DIR, "logs")
EPISODIC_DIR = os.path.join(BASE_DIR, "memory", "episodic")
OUTPUT_DIR = os.path.join(BASE_DIR, "outputs")


def _delete_ext(root: str, ext: str) -> int:
    count = 0
    if not os.path.isdir(root):
        return count
    for name in os.listdir(root):
        if name.endswith(ext):
            path = os.path.join(root, name)
            os.remove(path)
            count += 1
    return count


def main() -> int:
    parser = argparse.ArgumentParser(description="Clean generated artifacts.")
    parser.add_argument("--logs", action="store_true", help="Remove log files")
    parser.add_argument("--episodic", action="store_true", help="Remove episodic JSON files")
    parser.add_argument("--outputs", action="store_true", help="Remove output markdown files")
    parser.add_argument("--all", action="store_true", help="Remove all artifacts (default)")

    args = parser.parse_args()
    if not (args.logs or args.episodic or args.outputs or args.all):
        args.all = True

    total = 0
    if args.all or args.logs:
        total += _delete_ext(LOG_DIR, ".log")
    if args.all or args.episodic:
        total += _delete_ext(EPISODIC_DIR, ".json")
    if args.all or args.outputs:
        total += _delete_ext(OUTPUT_DIR, ".md")

    print(f"Removed {total} artifact files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
