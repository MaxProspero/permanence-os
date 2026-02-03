#!/usr/bin/env python3
"""
Weekly auto-commit for tracked changes.
Skips if no changes or commit fails.
"""

from __future__ import annotations

import argparse
import os
import subprocess
from datetime import datetime, timezone


def _run(cmd: list[str], cwd: str) -> int:
    return subprocess.call(cmd, cwd=cwd)


def main() -> int:
    parser = argparse.ArgumentParser(description="Auto-commit tracked changes")
    parser.add_argument("--repo", default=".", help="Repo path")
    parser.add_argument("--message", help="Commit message")
    args = parser.parse_args()

    repo = os.path.abspath(args.repo)
    message = args.message or f"Weekly upkeep: {datetime.now(timezone.utc).strftime('%Y-%m-%d')}"

    _run(["git", "add", "-A"], cwd=repo)

    status = subprocess.check_output(["git", "status", "--porcelain"], cwd=repo).decode().strip()
    if not status:
        print("No changes to commit.")
        return 0

    code = _run(["git", "commit", "-m", message], cwd=repo)
    if code != 0:
        print("Commit failed.")
        return code
    print("Commit created.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
