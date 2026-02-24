#!/usr/bin/env python3
"""
Auto-commit tracked changes with optional push.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from datetime import datetime, timezone


def _run(cmd: list[str], cwd: str) -> int:
    return subprocess.call(cmd, cwd=cwd)


def _out(cmd: list[str], cwd: str) -> str:
    return subprocess.check_output(cmd, cwd=cwd).decode().strip()


def main() -> int:
    parser = argparse.ArgumentParser(description="Auto-commit tracked changes")
    parser.add_argument("--repo", default=".", help="Repo path")
    parser.add_argument("--message", help="Commit message")
    parser.add_argument("--push", action="store_true", help="Push after commit")
    parser.add_argument("--remote", default="origin", help="Remote name for push")
    parser.add_argument("--branch", help="Branch name override for push target")
    args = parser.parse_args()

    repo = os.path.abspath(args.repo)
    message = args.message or f"Weekly upkeep: {datetime.now(timezone.utc).strftime('%Y-%m-%d')}"
    branch = args.branch

    _run(["git", "add", "-A"], cwd=repo)

    status = _out(["git", "status", "--porcelain"], cwd=repo)
    if status:
        code = _run(["git", "commit", "-m", message], cwd=repo)
        if code != 0:
            print("Commit failed.")
            return code
        print("Commit created.")
    else:
        print("No changes to commit.")

    if args.push:
        if not branch:
            branch = _out(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=repo)
        if branch == "HEAD":
            print("Cannot push from detached HEAD. Use --branch to set a target.", file=sys.stderr)
            return 2

        code = _run(["git", "push", args.remote, branch], cwd=repo)
        if code != 0:
            print("Push failed.")
            return code
        print(f"Pushed to {args.remote}/{branch}.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
