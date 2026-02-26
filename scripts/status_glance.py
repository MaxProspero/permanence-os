#!/usr/bin/env python3
"""
Write a one-line daily status file for quick glance surfaces (phone/iPad).
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
PHASE_RE = re.compile(r"- Phase gate:\s*(PASS|FAIL)")


def _extract_summary(report: str) -> dict:
    m = SUMMARY_RE.search(report)
    if not m:
        return {"expected_slots": 0, "passed": 0, "failed": 0, "missing": 0, "gate_result": "FAIL"}
    return {
        "expected_slots": int(m.group(1)),
        "passed": int(m.group(2)),
        "failed": int(m.group(3)),
        "missing": int(m.group(4)),
        "gate_result": m.group(5),
    }


def _read_streak(path: Path, default_target: int = 7) -> dict:
    if not path.exists():
        return {"current_streak": 0, "target": default_target, "last_date": None, "last_status": "UNKNOWN"}
    try:
        data = json.loads(path.read_text())
    except Exception:
        return {"current_streak": 0, "target": default_target, "last_date": None, "last_status": "UNKNOWN"}
    return {
        "current_streak": int(data.get("current_streak", 0)),
        "target": int(data.get("target", default_target)),
        "last_date": data.get("last_date"),
        "last_status": data.get("last_status", "UNKNOWN"),
    }


def _latest_phase_result(log_dir: Path) -> str:
    candidates = sorted(log_dir.glob("phase_gate_*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not candidates:
        return "PENDING"
    text = candidates[0].read_text(errors="ignore")
    m = PHASE_RE.search(text)
    return m.group(1) if m else "PENDING"


def compute_glance(
    *,
    log_dir: Path,
    streak_path: Path,
    slots: list[int],
    tolerance_minutes: int,
    now_local: datetime | None = None,
) -> dict:
    now_local = now_local or datetime.now()
    active_slots = [s for s in slots if now_local.hour >= s]
    if active_slots:
        ok, report = evaluate_reliability(
            log_dir=log_dir,
            days=1,
            slots=active_slots,
            tolerance_minutes=tolerance_minutes,
            require_notebooklm=False,
            include_today=True,
            now_local=now_local,
        )
        summary = _extract_summary(report)
        today_state = "PASS" if ok else "FAIL"
        slot_progress = f"{summary['passed']}/{summary['expected_slots']}"
    else:
        today_state = "PENDING"
        slot_progress = "0/0"
        summary = {"expected_slots": 0, "passed": 0, "failed": 0, "missing": 0}

    streak = _read_streak(streak_path)
    phase_result = _latest_phase_result(streak_path.parent)
    now_utc = datetime.now(timezone.utc).isoformat()

    payload = {
        "today_state": today_state,
        "slot_progress": slot_progress,
        "active_slots": active_slots,
        "slots": slots,
        "summary": summary,
        "streak": {
            "current": streak["current_streak"],
            "target": streak["target"],
            "last_date": streak["last_date"],
            "last_status": streak["last_status"],
        },
        "phase_gate": phase_result,
        "updated_at_utc": now_utc,
    }
    payload["line"] = (
        f"TODAY:{payload['today_state']} ({payload['slot_progress']}) | "
        f"STREAK:{payload['streak']['current']}/{payload['streak']['target']} | "
        f"PHASE:{payload['phase_gate']} | "
        f"UPDATED:{payload['updated_at_utc']}"
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate one-line glance status.")
    parser.add_argument("--log-dir", default=str(storage.paths.logs), help="Directory containing phase/reliability logs")
    parser.add_argument(
        "--automation-log-dir",
        default=str(Path(BASE_DIR) / "logs" / "automation"),
        help="Directory containing run_*.log files",
    )
    parser.add_argument(
        "--streak-file",
        default=str(storage.paths.logs / "reliability_streak.json"),
        help="Path to reliability_streak.json",
    )
    parser.add_argument("--slots", default="7,12,19", help="Comma-separated slot hours")
    parser.add_argument("--tolerance-minutes", type=int, default=90, help="Slot tolerance")
    parser.add_argument(
        "--output",
        default=str(storage.paths.logs / "status_today.txt"),
        help="One-line status output path",
    )
    parser.add_argument(
        "--json-output",
        default=str(storage.paths.logs / "status_today.json"),
        help="JSON status output path",
    )
    args = parser.parse_args()

    slots = [int(x.strip()) for x in args.slots.split(",") if x.strip()]
    automation_log_dir = Path(os.path.expanduser(args.automation_log_dir))
    streak_path = Path(os.path.expanduser(args.streak_file))
    out_path = Path(os.path.expanduser(args.output))
    json_out_path = Path(os.path.expanduser(args.json_output))

    payload = compute_glance(
        log_dir=automation_log_dir,
        streak_path=streak_path,
        slots=slots,
        tolerance_minutes=args.tolerance_minutes,
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    json_out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(payload["line"] + "\n")
    json_out_path.write_text(json.dumps(payload, indent=2) + "\n")

    print(f"Glance status written to {out_path}")
    print(payload["line"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
