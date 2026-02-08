#!/usr/bin/env python3
"""
Weekly phase gate: require strict reliability plus a minimum consecutive streak.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(BASE_DIR)

from core.storage import storage  # noqa: E402
from scripts.reliability_gate import evaluate_reliability  # noqa: E402


SUMMARY_RE = re.compile(
    r"- Expected slots:\s*(\d+)\n- Passed:\s*(\d+)\n- Failed:\s*(\d+)\n- Missing:\s*(\d+)\n- Gate result:\s*(PASS|FAIL)",
    re.MULTILINE,
)


def _read_streak(streak_path: Path) -> dict:
    if not streak_path.exists():
        return {
            "current_streak": 0,
            "target": 7,
            "last_date": None,
            "last_status": "UNKNOWN",
        }
    try:
        data = json.loads(streak_path.read_text())
    except Exception:
        return {
            "current_streak": 0,
            "target": 7,
            "last_date": None,
            "last_status": "UNKNOWN",
        }
    return {
        "current_streak": int(data.get("current_streak", 0)),
        "target": int(data.get("target", 7)),
        "last_date": data.get("last_date"),
        "last_status": data.get("last_status", "UNKNOWN"),
    }


def _extract_summary(report: str) -> dict:
    m = SUMMARY_RE.search(report)
    if not m:
        return {
            "expected_slots": 0,
            "passed": 0,
            "failed": 0,
            "missing": 0,
            "gate_result": "FAIL",
        }
    return {
        "expected_slots": int(m.group(1)),
        "passed": int(m.group(2)),
        "failed": int(m.group(3)),
        "missing": int(m.group(4)),
        "gate_result": m.group(5),
    }


def evaluate_phase_gate(
    *,
    log_dir: Path,
    streak_path: Path,
    days: int,
    slots: list[int],
    tolerance_minutes: int,
    require_notebooklm: bool,
    include_today: bool,
    target_streak: int,
) -> tuple[bool, str]:
    reliability_ok, reliability_report = evaluate_reliability(
        log_dir=log_dir,
        days=days,
        slots=slots,
        tolerance_minutes=tolerance_minutes,
        require_notebooklm=require_notebooklm,
        include_today=include_today,
    )
    streak = _read_streak(streak_path)
    streak_ok = streak["current_streak"] >= target_streak
    phase_ok = reliability_ok and streak_ok

    summary = _extract_summary(reliability_report)
    now_utc = datetime.now(timezone.utc).isoformat()

    lines = [
        "# Phase Gate",
        "",
        f"- Generated (UTC): {now_utc}",
        f"- Reliability window days: {days}",
        f"- Slots: {', '.join(str(s) for s in slots)}",
        f"- Tolerance minutes: {tolerance_minutes}",
        f"- Require NotebookLM status=0: {'yes' if require_notebooklm else 'no'}",
        f"- Include today: {'yes' if include_today else 'no'}",
        "",
        "## Reliability",
        f"- Expected slots: {summary['expected_slots']}",
        f"- Passed: {summary['passed']}",
        f"- Failed: {summary['failed']}",
        f"- Missing: {summary['missing']}",
        f"- Reliability gate: {'PASS' if reliability_ok else 'FAIL'}",
        "",
        "## Streak",
        f"- Current streak: {streak['current_streak']}",
        f"- Required streak: {target_streak}",
        f"- Last day: {streak.get('last_date')}",
        f"- Last status: {streak.get('last_status')}",
        f"- Streak gate: {'PASS' if streak_ok else 'FAIL'}",
        "",
        "## Result",
        f"- Phase gate: {'PASS' if phase_ok else 'FAIL'}",
        "",
        "## Reliability Detail",
        "",
        reliability_report,
    ]
    return phase_ok, "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Phase gate requiring strict reliability + consecutive streak."
    )
    parser.add_argument("--days", type=int, default=7, help="Reliability window days")
    parser.add_argument("--slots", default="7,12,19", help="Comma-separated scheduled hours")
    parser.add_argument(
        "--tolerance-minutes",
        type=int,
        default=90,
        help="Allowed drift from each slot",
    )
    parser.add_argument(
        "--require-notebooklm",
        action="store_true",
        help="Require NotebookLM status=0 for slot pass",
    )
    parser.add_argument(
        "--include-today",
        action="store_true",
        help="Include current day in the reliability window",
    )
    parser.add_argument(
        "--target-streak",
        type=int,
        default=7,
        help="Required consecutive-pass days",
    )
    parser.add_argument(
        "--log-dir",
        default=str(Path(BASE_DIR) / "logs" / "automation"),
        help="Automation log directory",
    )
    parser.add_argument(
        "--streak-file",
        default=str(storage.paths.logs / "reliability_streak.json"),
        help="Path to reliability streak json",
    )
    parser.add_argument("--output", help="Output markdown path")
    args = parser.parse_args()

    slots = [int(x.strip()) for x in args.slots.split(",") if x.strip()]
    log_dir = Path(os.path.expanduser(args.log_dir))
    streak_path = Path(os.path.expanduser(args.streak_file))

    ok, report = evaluate_phase_gate(
        log_dir=log_dir,
        streak_path=streak_path,
        days=args.days,
        slots=slots,
        tolerance_minutes=args.tolerance_minutes,
        require_notebooklm=args.require_notebooklm,
        include_today=args.include_today,
        target_streak=args.target_streak,
    )

    if args.output:
        output_path = Path(os.path.expanduser(args.output))
        output_path.parent.mkdir(parents=True, exist_ok=True)
    else:
        output_path = storage.paths.logs / f"phase_gate_{datetime.now().date().isoformat()}.md"
    output_path.write_text(report)
    print(f"Phase gate report written to {output_path}")
    print("Phase gate: PASS" if ok else "Phase gate: FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
