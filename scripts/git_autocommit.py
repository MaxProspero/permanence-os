#!/usr/bin/env python3
"""
Auto-commit tracked changes with optional push.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from datetime import datetime, timezone


def _run(cmd: list[str], cwd: str) -> int:
    return subprocess.call(cmd, cwd=cwd)


def _out(cmd: list[str], cwd: str) -> str:
    return subprocess.check_output(cmd, cwd=cwd).decode().strip()


def _changed_files_from_status(porcelain: str) -> list[str]:
    files: list[str] = []
    for line in porcelain.splitlines():
        if not line:
            continue
        match = re.match(r"^[ MARCUD?!]{2}\s(.+)$", line)
        if not match:
            continue
        path = match.group(1).strip()
        if " -> " in path:
            path = path.split(" -> ", 1)[1].strip()
        if path:
            files.append(path)
    return files


def _append_chronicle_event(payload: dict) -> None:
    try:
        from scripts.chronicle_common import CHRONICLE_EVENTS, append_jsonl, ensure_chronicle_dirs, utc_iso
    except Exception:
        return
    ensure_chronicle_dirs()
    payload = dict(payload)
    payload.setdefault("timestamp", utc_iso())
    payload.setdefault("type", "git_sync")
    append_jsonl(CHRONICLE_EVENTS, payload)


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

    porcelain_before_add = _out(["git", "status", "--porcelain"], cwd=repo)
    changed_files = _changed_files_from_status(porcelain_before_add)

    _run(["git", "add", "-A"], cwd=repo)

    status = _out(["git", "status", "--porcelain"], cwd=repo)
    commit_created = False
    pushed = False
    if status:
        code = _run(["git", "commit", "-m", message], cwd=repo)
        if code != 0:
            print("Commit failed.")
            return code
        print("Commit created.")
        commit_created = True
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
        pushed = True

    head = _out(["git", "rev-parse", "HEAD"], cwd=repo)
    if commit_created or pushed:
        _append_chronicle_event(
            {
                "repo": repo,
                "git_branch": branch or _out(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=repo),
                "git_head": head,
                "message": message,
                "commit_created": commit_created,
                "push_requested": bool(args.push),
                "push_completed": pushed,
                "remote": args.remote,
                "changed_files_count": len(changed_files),
                "changed_files": changed_files[:120],
            }
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
