#!/usr/bin/env python3
"""
Permanence OS — Agent GitHub Operations

Governed GitHub write operations for autonomous agents.
Safety-first: protected branches, daily write limits, secret scanning,
branch naming conventions, and full audit logging.

Usage:
  python scripts/agent_github_ops.py --action list-branches
  python scripts/agent_github_ops.py --action push --agent researcher --branch agent/researcher/feature-x --message "feat: add feature x"
  python scripts/agent_github_ops.py --action create-pr --agent researcher --branch agent/researcher/feature-x --title "Add feature x"
  python scripts/agent_github_ops.py --action cleanup --days 30 --dry-run
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Optional

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
WRITE_LOG_PATH = os.path.join(BASE_DIR, "logs", "agent_github_writes.jsonl")

# ── Safety Constants ──────────────────────────────────────────────────────

PROTECTED_BRANCHES = [
    "main",
    "master",
    "claude/vibrant-merkle",
]

MAX_DAILY_WRITES_DEFAULT = 10

BRANCH_PREFIX_PATTERN = re.compile(r"^agent/[a-z0-9_-]+/[a-z0-9_-]+.*$")

FORBIDDEN_BRANCH_PATTERNS = [
    r"^main$",
    r"^master$",
    r"^release/",
    r"^hotfix/",
]


# ── Helpers ───────────────────────────────────────────────────────────────

def _run(cmd: list[str], cwd: str = BASE_DIR, capture: bool = False) -> subprocess.CompletedProcess:
    if capture:
        return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    return subprocess.run(cmd, cwd=cwd)


def _out(cmd: list[str], cwd: str = BASE_DIR) -> str:
    try:
        return subprocess.check_output(cmd, cwd=cwd, stderr=subprocess.DEVNULL).decode().strip()
    except subprocess.CalledProcessError:
        return ""


def _log_write(agent_id: str, action: str, details: dict[str, Any]) -> None:
    """Append to agent GitHub writes log."""
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "agent_id": agent_id,
        "action": action,
        **details,
    }
    os.makedirs(os.path.dirname(WRITE_LOG_PATH), exist_ok=True)
    with open(WRITE_LOG_PATH, "a") as f:
        f.write(json.dumps(entry) + "\n")


def _load_daily_writes(agent_id: str) -> int:
    """Count writes by this agent today."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    count = 0
    if not os.path.exists(WRITE_LOG_PATH):
        return 0
    try:
        with open(WRITE_LOG_PATH) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if entry.get("agent_id") == agent_id and entry.get("timestamp", "").startswith(today):
                    count += 1
    except OSError:
        pass
    return count


def _check_daily_limit(agent_id: str, max_writes: int = MAX_DAILY_WRITES_DEFAULT) -> bool:
    """Return True if agent is within daily write limit."""
    count = _load_daily_writes(agent_id)
    return count < max_writes


def _is_protected(branch: str) -> bool:
    """Check if a branch is protected."""
    clean = branch.strip()
    for pb in PROTECTED_BRANCHES:
        if clean == pb or clean == f"origin/{pb}":
            return True
    return False


def _validate_branch_name(branch: str, agent_id: str) -> str | None:
    """Validate branch name follows convention. Returns error message or None."""
    if _is_protected(branch):
        return f"Cannot operate on protected branch: {branch}"
    for pattern in FORBIDDEN_BRANCH_PATTERNS:
        if re.match(pattern, branch):
            return f"Branch name matches forbidden pattern: {branch}"
    expected_prefix = f"agent/{agent_id}/"
    if not branch.startswith(expected_prefix):
        return f"Branch must start with '{expected_prefix}' (got: {branch})"
    return None


def _run_secret_scan() -> bool:
    """Run secret scan on staged files. Returns True if clean."""
    scan_script = os.path.join(BASE_DIR, "scripts", "secret_scan.py")
    if not os.path.exists(scan_script):
        print("⚠  Secret scan script not found — skipping")
        return True
    result = _run(
        [sys.executable, scan_script, "--staged"],
        cwd=BASE_DIR,
        capture=True,
    )
    if result.returncode != 0:
        print("⛔ Secret scan FAILED — aborting push")
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(result.stderr)
        return False
    return True


# ── Actions ───────────────────────────────────────────────────────────────

def list_branches() -> list[dict[str, str]]:
    """List all agent branches."""
    raw = _out(["git", "branch", "-a", "--format=%(refname:short) %(committerdate:iso8601)"], cwd=BASE_DIR)
    branches = []
    for line in raw.splitlines():
        parts = line.strip().split(" ", 1)
        if len(parts) < 1:
            continue
        name = parts[0]
        date = parts[1] if len(parts) > 1 else ""
        if name.startswith("agent/") or name.startswith("origin/agent/"):
            branches.append({"name": name, "date": date})
    return branches


def push_branch(
    agent_id: str,
    branch: str,
    commit_msg: str,
    files: list[str] | None = None,
    max_writes: int = MAX_DAILY_WRITES_DEFAULT,
) -> dict[str, Any]:
    """Stage, commit, and push to a branch. Returns result dict."""
    # Safety checks
    error = _validate_branch_name(branch, agent_id)
    if error:
        return {"ok": False, "error": error}

    if not _check_daily_limit(agent_id, max_writes):
        return {"ok": False, "error": f"Daily write limit ({max_writes}) reached for agent {agent_id}"}

    # Create/checkout branch
    current = _out(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=BASE_DIR)
    if current != branch:
        # Check if branch exists remotely
        remote_exists = _out(["git", "ls-remote", "--heads", "origin", branch], cwd=BASE_DIR)
        if remote_exists:
            _run(["git", "checkout", branch], cwd=BASE_DIR)
            _run(["git", "pull", "--ff-only", "origin", branch], cwd=BASE_DIR)
        else:
            _run(["git", "checkout", "-b", branch], cwd=BASE_DIR)

    # Stage files
    if files:
        for f in files:
            _run(["git", "add", f], cwd=BASE_DIR)
    else:
        _run(["git", "add", "-A"], cwd=BASE_DIR)

    # Check if there are changes to commit
    status = _out(["git", "status", "--porcelain"], cwd=BASE_DIR)
    if not status:
        return {"ok": True, "message": "No changes to commit"}

    # Secret scan
    if not _run_secret_scan():
        return {"ok": False, "error": "Secret scan failed — secrets detected in staged files"}

    # Commit
    result = _run(
        ["git", "commit", "-m", commit_msg],
        cwd=BASE_DIR,
        capture=True,
    )
    if result.returncode != 0:
        return {"ok": False, "error": f"Commit failed: {result.stderr}"}

    # Push
    result = _run(
        ["git", "push", "-u", "origin", branch],
        cwd=BASE_DIR,
        capture=True,
    )
    if result.returncode != 0:
        return {"ok": False, "error": f"Push failed: {result.stderr}"}

    # Log the write
    _log_write(agent_id, "push", {"branch": branch, "message": commit_msg})

    return {"ok": True, "branch": branch, "message": commit_msg}


def create_pr(
    agent_id: str,
    branch: str,
    title: str,
    body: str = "",
    base: str = "main",
    max_writes: int = MAX_DAILY_WRITES_DEFAULT,
) -> dict[str, Any]:
    """Create a pull request. Returns result dict."""
    error = _validate_branch_name(branch, agent_id)
    if error:
        return {"ok": False, "error": error}

    if not _check_daily_limit(agent_id, max_writes):
        return {"ok": False, "error": f"Daily write limit ({max_writes}) reached for agent {agent_id}"}

    # Check gh is available
    if not _out(["which", "gh"]):
        # Fallback: use git to create a PR URL
        remote_url = _out(["git", "remote", "get-url", "origin"], cwd=BASE_DIR)
        if "github.com" in remote_url:
            # Parse org/repo
            match = re.search(r"github\.com[:/](.+?)(?:\.git)?$", remote_url)
            if match:
                repo_path = match.group(1)
                pr_url = f"https://github.com/{repo_path}/compare/{base}...{branch}?expand=1"
                _log_write(agent_id, "pr_url", {"branch": branch, "base": base, "url": pr_url})
                return {"ok": True, "message": f"gh CLI not available. Create PR manually: {pr_url}"}
        return {"ok": False, "error": "gh CLI not available and couldn't generate PR URL"}

    cmd = ["gh", "pr", "create", "--head", branch, "--base", base, "--title", title]
    if body:
        cmd += ["--body", body]
    else:
        cmd += ["--body", f"Automated PR by agent `{agent_id}`"]

    result = _run(cmd, cwd=BASE_DIR, capture=True)
    if result.returncode != 0:
        return {"ok": False, "error": f"PR creation failed: {result.stderr}"}

    pr_url = result.stdout.strip()
    _log_write(agent_id, "create_pr", {"branch": branch, "base": base, "title": title, "url": pr_url})

    return {"ok": True, "url": pr_url, "branch": branch, "title": title}


def cleanup_stale_branches(
    days_old: int = 30,
    dry_run: bool = True,
) -> list[dict[str, str]]:
    """Find and optionally delete stale agent branches."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days_old)
    branches = list_branches()
    stale: list[dict[str, str]] = []

    for b in branches:
        name = b["name"]
        date_str = b.get("date", "")

        # Never delete protected branches
        clean_name = name.replace("origin/", "")
        if _is_protected(clean_name):
            continue

        # Parse date
        try:
            # ISO format from git: 2026-03-01 12:00:00 -0600
            branch_date = datetime.fromisoformat(date_str.strip()) if date_str else None
        except (ValueError, TypeError):
            branch_date = None

        if branch_date and branch_date.replace(tzinfo=timezone.utc if branch_date.tzinfo is None else branch_date.tzinfo) < cutoff:
            action = "would delete" if dry_run else "deleted"
            stale.append({"name": clean_name, "date": date_str, "action": action})

            if not dry_run:
                # Delete remote
                _run(["git", "push", "origin", "--delete", clean_name], cwd=BASE_DIR, capture=True)
                # Delete local
                _run(["git", "branch", "-d", clean_name], cwd=BASE_DIR, capture=True)

    return stale


def get_daily_write_count(agent_id: str) -> dict[str, Any]:
    """Get current daily write count for an agent."""
    count = _load_daily_writes(agent_id)
    return {
        "agent_id": agent_id,
        "writes_today": count,
        "limit": MAX_DAILY_WRITES_DEFAULT,
        "remaining": max(0, MAX_DAILY_WRITES_DEFAULT - count),
    }


# ── CLI ───────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Permanence OS — Agent GitHub Operations",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--action",
        choices=["list-branches", "push", "create-pr", "cleanup", "write-count"],
        required=True,
        help="Operation to perform",
    )
    parser.add_argument("--agent", help="Agent ID (required for push/create-pr)")
    parser.add_argument("--branch", help="Branch name (required for push/create-pr)")
    parser.add_argument("--message", help="Commit message (for push)")
    parser.add_argument("--title", help="PR title (for create-pr)")
    parser.add_argument("--body", default="", help="PR body (for create-pr)")
    parser.add_argument("--base", default="main", help="Base branch for PR (default: main)")
    parser.add_argument("--files", nargs="*", help="Specific files to stage (for push)")
    parser.add_argument("--days", type=int, default=30, help="Days threshold for cleanup")
    parser.add_argument("--dry-run", action="store_true", help="Dry run for cleanup (default)")
    parser.add_argument("--execute", action="store_true", help="Actually delete stale branches")
    parser.add_argument("--max-writes", type=int, default=MAX_DAILY_WRITES_DEFAULT, help="Daily write limit")
    args = parser.parse_args()

    if args.action == "list-branches":
        branches = list_branches()
        if not branches:
            print("No agent branches found.")
        else:
            print(f"Agent branches ({len(branches)}):")
            for b in branches:
                print(f"  {b['name']}  ({b.get('date', 'unknown date')})")
        return 0

    if args.action == "push":
        if not args.agent or not args.branch or not args.message:
            print("--agent, --branch, and --message are required for push")
            return 2
        result = push_branch(
            agent_id=args.agent,
            branch=args.branch,
            commit_msg=args.message,
            files=args.files,
            max_writes=args.max_writes,
        )
        print(json.dumps(result, indent=2))
        return 0 if result.get("ok") else 1

    if args.action == "create-pr":
        if not args.agent or not args.branch or not args.title:
            print("--agent, --branch, and --title are required for create-pr")
            return 2
        result = create_pr(
            agent_id=args.agent,
            branch=args.branch,
            title=args.title,
            body=args.body,
            base=args.base,
            max_writes=args.max_writes,
        )
        print(json.dumps(result, indent=2))
        return 0 if result.get("ok") else 1

    if args.action == "cleanup":
        stale = cleanup_stale_branches(
            days_old=args.days,
            dry_run=not args.execute,
        )
        mode = "DRY RUN" if not args.execute else "EXECUTING"
        print(f"Stale branch cleanup ({mode}, >{args.days} days):")
        if not stale:
            print("  No stale agent branches found.")
        else:
            for b in stale:
                print(f"  {b['action']}: {b['name']} (last commit: {b.get('date', '?')})")
            print(f"\n  Total: {len(stale)} branches")
            if not args.execute:
                print("  Run with --execute to actually delete.")
        return 0

    if args.action == "write-count":
        if not args.agent:
            print("--agent is required for write-count")
            return 2
        result = get_daily_write_count(args.agent)
        print(json.dumps(result, indent=2))
        return 0

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
