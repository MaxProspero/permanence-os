#!/usr/bin/env python3
"""
Verify Dell cutover prerequisites and cron scheduling block.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(BASE_DIR)

MARKER_BEGIN = "# >>> permanence-automation >>>"
MARKER_END = "# <<< permanence-automation <<<"
EXPECTED_SLOTS = {"0 7 * * *", "0 12 * * *", "0 19 * * *"}
REQUIRED_ENV_KEYS = {"PERMANENCE_STORAGE_ROOT"}


def extract_managed_cron_block(text: str) -> list[str]:
    lines = text.splitlines()
    block: list[str] = []
    in_block = False
    for line in lines:
        if line.strip() == MARKER_BEGIN:
            in_block = True
            continue
        if line.strip() == MARKER_END:
            in_block = False
            continue
        if in_block:
            block.append(line.strip())
    return [line for line in block if line]


def cron_slots_present(block: list[str]) -> bool:
    prefixes = set()
    for line in block:
        parts = line.split()
        if len(parts) >= 5:
            prefixes.add(" ".join(parts[:5]))
    return EXPECTED_SLOTS.issubset(prefixes)


def load_env_keys(path: Path) -> set[str]:
    if not path.exists():
        return set()
    keys = set()
    for raw in path.read_text(errors="ignore").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key = line.split("=", 1)[0].strip()
        if key:
            keys.add(key)
    return keys


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify Dell automation cutover state.")
    parser.add_argument("--repo-path", default=BASE_DIR, help="Repo path to verify")
    parser.add_argument("--env-file", help="Path to .env (default: <repo>/.env)")
    args = parser.parse_args()

    repo_path = Path(os.path.expanduser(args.repo_path)).resolve()
    env_file = Path(os.path.expanduser(args.env_file)).resolve() if args.env_file else repo_path / ".env"

    run_script = repo_path / "automation" / "run_briefing.sh"
    setup_script = repo_path / "automation" / "setup_dell_automation.sh"
    disable_script = repo_path / "automation" / "disable_dell_automation.sh"

    cron_proc = subprocess.run(["crontab", "-l"], capture_output=True, text=True, check=False)
    cron_text = cron_proc.stdout if cron_proc.returncode == 0 else ""
    cron_block = extract_managed_cron_block(cron_text)
    slots_ok = cron_slots_present(cron_block)

    env_keys = load_env_keys(env_file)
    missing_env = sorted(REQUIRED_ENV_KEYS - env_keys)

    print(f"repo_path: {repo_path}")
    print(f"run_script_exists: {'yes' if run_script.exists() else 'no'}")
    print(f"setup_script_exists: {'yes' if setup_script.exists() else 'no'}")
    print(f"disable_script_exists: {'yes' if disable_script.exists() else 'no'}")
    print(f"managed_cron_block_found: {'yes' if bool(cron_block) else 'no'}")
    print(f"managed_slots_ok: {'yes' if slots_ok else 'no'}")
    print(f"env_file: {env_file}")
    print(f"required_env_missing: {', '.join(missing_env) if missing_env else 'none'}")

    ok = (
        run_script.exists()
        and setup_script.exists()
        and disable_script.exists()
        and bool(cron_block)
        and slots_ok
        and not missing_env
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
