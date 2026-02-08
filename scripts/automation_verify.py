#!/usr/bin/env python3
"""
Verify local automation scheduling and runtime state.
"""

from __future__ import annotations

import argparse
import os
import plistlib
import subprocess
import sys
from pathlib import Path

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(BASE_DIR)


EXPECTED_SLOTS = {(7, 0), (12, 0), (19, 0)}


def _read_plist(plist_path: Path) -> dict:
    if not plist_path.exists():
        return {}
    with plist_path.open("rb") as f:
        return plistlib.load(f)


def _extract_slots(plist_data: dict) -> set[tuple[int, int]]:
    raw = plist_data.get("StartCalendarInterval", [])
    slots: set[tuple[int, int]] = set()
    for item in raw:
        if not isinstance(item, dict):
            continue
        hour = item.get("Hour")
        minute = item.get("Minute")
        if isinstance(hour, int) and isinstance(minute, int):
            slots.add((hour, minute))
    return slots


def _launchctl_loaded(label: str) -> bool:
    proc = subprocess.run(
        ["launchctl", "list"],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        return False
    return label in proc.stdout


def _launchctl_details(label: str) -> tuple[int, str]:
    uid = os.getuid()
    proc = subprocess.run(
        ["launchctl", "print", f"gui/{uid}/{label}"],
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.returncode, (proc.stdout or proc.stderr or "").strip()


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify Permanence launchd automation.")
    parser.add_argument(
        "--label",
        default="com.permanence.briefing",
        help="LaunchAgent label",
    )
    parser.add_argument(
        "--plist",
        default=str(Path.home() / "Library" / "LaunchAgents" / "com.permanence.briefing.plist"),
        help="Path to LaunchAgent plist",
    )
    args = parser.parse_args()

    plist_path = Path(os.path.expanduser(args.plist))
    plist_data = _read_plist(plist_path)
    configured_slots = _extract_slots(plist_data)
    schedule_ok = configured_slots == EXPECTED_SLOTS
    loaded = _launchctl_loaded(args.label)
    details_code, details = _launchctl_details(args.label)

    print(f"label: {args.label}")
    print(f"plist: {plist_path}")
    print(f"loaded: {'yes' if loaded else 'no'}")
    print(f"schedule_slots: {sorted(configured_slots)}")
    print(f"schedule_expected: {sorted(EXPECTED_SLOTS)}")
    print(f"schedule_ok: {'yes' if schedule_ok else 'no'}")
    if details_code == 0:
        print("launchctl_print: ok")
    else:
        print("launchctl_print: failed")
        if details:
            print(details.splitlines()[-1])

    return 0 if loaded and schedule_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
