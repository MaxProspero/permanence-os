#!/usr/bin/env python3
"""
Track daily reliability streak from gate outcomes.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(BASE_DIR)

from core.storage import storage  # noqa: E402


TARGET_DAYS = 7
MAX_HISTORY_DAYS = 120


def _paths() -> tuple[Path, Path]:
    log_dir = storage.paths.logs
    return (
        log_dir / "reliability_streak.json",
        log_dir / "reliability_streak.md",
    )


def _load(path: Path) -> dict:
    if not path.exists():
        return {"history": {}}
    try:
        data = json.loads(path.read_text())
        if not isinstance(data, dict):
            return {"history": {}}
        history = data.get("history")
        if not isinstance(history, dict):
            data["history"] = {}
        return data
    except Exception:
        return {"history": {}}


def _keep_recent(history: dict[str, bool], max_days: int) -> dict[str, bool]:
    parsed = []
    for d, status in history.items():
        try:
            parsed.append((datetime.strptime(d, "%Y-%m-%d").date(), bool(status)))
        except ValueError:
            continue
    parsed.sort(reverse=True)
    return {d.isoformat(): s for d, s in parsed[:max_days]}


def _compute_streak(history: dict[str, bool]) -> tuple[int, str | None]:
    if not history:
        return 0, None
    dates = []
    for d in history:
        try:
            dates.append(datetime.strptime(d, "%Y-%m-%d").date())
        except ValueError:
            continue
    if not dates:
        return 0, None
    latest = max(dates)
    streak = 0
    current = latest
    while history.get(current.isoformat(), False):
        streak += 1
        current = current - timedelta(days=1)
    return streak, latest.isoformat()


def update_streak(status_code: int, for_date: str | None = None) -> dict:
    json_path, md_path = _paths()
    state = _load(json_path)
    history = state.get("history", {})
    day = for_date or datetime.now().date().isoformat()
    history[day] = status_code == 0
    history = _keep_recent(history, MAX_HISTORY_DAYS)
    streak, last_date = _compute_streak(history)

    last_status = "UNKNOWN"
    if last_date:
        last_status = "PASS" if history.get(last_date) else "FAIL"

    updated = {
        "target": TARGET_DAYS,
        "current_streak": streak,
        "remaining_to_target": max(TARGET_DAYS - streak, 0),
        "last_date": last_date,
        "last_status": last_status,
        "history": history,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    json_path.write_text(json.dumps(updated, indent=2))

    md = [
        "# Reliability Streak",
        "",
        f"- Current streak: {updated['current_streak']}/{TARGET_DAYS}",
        f"- Remaining: {updated['remaining_to_target']}",
        f"- Last date: {updated['last_date']}",
        f"- Last status: {updated['last_status']}",
        f"- Updated at: {updated['updated_at']}",
        "",
    ]
    md_path.write_text("\n".join(md))
    return updated


def show_streak() -> dict:
    json_path, _ = _paths()
    state = _load(json_path)
    history = _keep_recent(state.get("history", {}), MAX_HISTORY_DAYS)
    streak, last_date = _compute_streak(history)
    last_status = "UNKNOWN"
    if last_date:
        last_status = "PASS" if history.get(last_date) else "FAIL"
    return {
        "target": TARGET_DAYS,
        "current_streak": streak,
        "remaining_to_target": max(TARGET_DAYS - streak, 0),
        "last_date": last_date,
        "last_status": last_status,
        "history": history,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="View or update reliability streak.")
    parser.add_argument("--update", action="store_true", help="Update streak from a gate status code")
    parser.add_argument("--status", type=int, choices=[0, 1], help="Gate status code (0 pass, 1 fail)")
    parser.add_argument("--date", help="Date for streak entry (YYYY-MM-DD)")
    args = parser.parse_args()

    if args.update:
        if args.status is None:
            print("Missing --status for update mode")
            return 1
        state = update_streak(args.status, args.date)
    else:
        state = show_streak()

    print(
        f"Reliability streak: {state['current_streak']}/{state['target']} "
        f"(remaining {state['remaining_to_target']})"
    )
    if state.get("last_date"):
        print(f"Last: {state['last_date']} {state['last_status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
