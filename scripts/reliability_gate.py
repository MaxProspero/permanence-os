#!/usr/bin/env python3
"""
Evaluate automation reliability over the last N full days.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(BASE_DIR)

from core.storage import storage  # noqa: E402


RUN_FILE_RE = re.compile(r"run_(\d{8}-\d{6})\.log$")
STATUS_RE = re.compile(
    r"Briefing Status:\s*(\d+)\s*\|\s*Digest Status:\s*(\d+)\s*\|\s*NotebookLM Status:\s*(\d+)"
)


@dataclass
class RunStatus:
    path: Path
    started_local: datetime
    briefing_status: int | None
    digest_status: int | None
    notebooklm_status: int | None

    def success(self, require_notebooklm: bool) -> bool:
        if self.briefing_status != 0 or self.digest_status != 0:
            return False
        if require_notebooklm and self.notebooklm_status != 0:
            return False
        return True


def _parse_run(path: Path) -> RunStatus | None:
    m = RUN_FILE_RE.search(path.name)
    if not m:
        return None
    try:
        started_local = datetime.strptime(m.group(1), "%Y%m%d-%H%M%S")
    except ValueError:
        return None
    text = path.read_text(errors="ignore")
    status_match = STATUS_RE.search(text)
    if status_match:
        b = int(status_match.group(1))
        d = int(status_match.group(2))
        n = int(status_match.group(3))
    else:
        b = d = n = None
    return RunStatus(
        path=path,
        started_local=started_local,
        briefing_status=b,
        digest_status=d,
        notebooklm_status=n,
    )


def _window_dates(days: int, include_today: bool, today_local: date | None = None) -> list[date]:
    today = today_local or datetime.now().date()
    end = today if include_today else (today - timedelta(days=1))
    start = end - timedelta(days=days - 1)
    return [start + timedelta(days=i) for i in range(days)]


def evaluate_reliability(
    log_dir: Path,
    days: int,
    slots: list[int],
    tolerance_minutes: int,
    require_notebooklm: bool,
    include_today: bool,
    now_local: datetime | None = None,
) -> tuple[bool, str]:
    all_runs = []
    for path in sorted(log_dir.glob("run_*.log")):
        run = _parse_run(path)
        if run:
            all_runs.append(run)

    today_local = (now_local or datetime.now()).date()
    dates = _window_dates(days, include_today, today_local=today_local)
    expected = [(d, h) for d in dates for h in slots]
    total_expected = len(expected)

    passed = 0
    failed = 0
    missing = 0
    detail_lines: list[str] = []

    for d, h in expected:
        slot_dt = datetime(d.year, d.month, d.day, h, 0, 0)
        same_day = [r for r in all_runs if r.started_local.date() == d]
        if not same_day:
            missing += 1
            detail_lines.append(f"- {d} {h:02d}:00 -> MISSING")
            continue

        in_window = [
            r
            for r in same_day
            if abs((r.started_local - slot_dt).total_seconds()) / 60.0 <= tolerance_minutes
        ]
        if not in_window:
            nearest = min(
                same_day,
                key=lambda r: abs((r.started_local - slot_dt).total_seconds()),
            )
            delta_min = abs((nearest.started_local - slot_dt).total_seconds()) / 60.0
            missing += 1
            detail_lines.append(
                f"- {d} {h:02d}:00 -> MISSING (nearest {nearest.started_local.strftime('%H:%M:%S')}, delta {delta_min:.1f}m)"
            )
            continue

        successful = [r for r in in_window if r.success(require_notebooklm=require_notebooklm)]
        if successful:
            chosen = min(
                successful,
                key=lambda r: abs((r.started_local - slot_dt).total_seconds()),
            )
            passed += 1
            detail_lines.append(
                f"- {d} {h:02d}:00 -> PASS ({chosen.path.name}; b={chosen.briefing_status}, d={chosen.digest_status}, n={chosen.notebooklm_status})"
            )
        else:
            chosen = min(
                in_window,
                key=lambda r: abs((r.started_local - slot_dt).total_seconds()),
            )
            failed += 1
            detail_lines.append(
                f"- {d} {h:02d}:00 -> FAIL ({chosen.path.name}; b={chosen.briefing_status}, d={chosen.digest_status}, n={chosen.notebooklm_status})"
            )

    ok = (passed == total_expected) and failed == 0 and missing == 0
    mode = "STRICT+NOTEBOOKLM" if require_notebooklm else "STRICT"
    now_utc = datetime.now(timezone.utc).isoformat()

    report_lines = [
        f"# Reliability Gate — {mode}",
        "",
        f"- Generated (UTC): {now_utc}",
        f"- Days: {days}",
        f"- Include today: {'yes' if include_today else 'no'}",
        f"- Slots: {', '.join(str(s) for s in slots)}",
        f"- Tolerance minutes: {tolerance_minutes}",
        f"- Require NotebookLM status=0: {'yes' if require_notebooklm else 'no'}",
        "",
        "## Summary",
        f"- Expected slots: {total_expected}",
        f"- Passed: {passed}",
        f"- Failed: {failed}",
        f"- Missing: {missing}",
        f"- Gate result: {'PASS' if ok else 'FAIL'}",
        "",
        "## Slot Detail",
        *detail_lines,
        "",
    ]
    return ok, "\n".join(report_lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Enforce reliability gate for scheduled automation runs.")
    parser.add_argument(
        "--days",
        type=int,
        default=7,
        help="Number of days to evaluate",
    )
    parser.add_argument(
        "--slots",
        default="7,12,19",
        help="Comma-separated slot hours (local time)",
    )
    parser.add_argument(
        "--tolerance-minutes",
        type=int,
        default=90,
        help="Allowed minutes away from slot to count",
    )
    parser.add_argument(
        "--require-notebooklm",
        action="store_true",
        help="Require NotebookLM status 0 for slot pass",
    )
    parser.add_argument(
        "--include-today",
        action="store_true",
        help="Include current day in window",
    )
    parser.add_argument(
        "--log-dir",
        default=str(Path(BASE_DIR) / "logs" / "automation"),
        help="Automation log directory",
    )
    parser.add_argument("--output", help="Output markdown path")
    args = parser.parse_args()

    slots = [int(x.strip()) for x in args.slots.split(",") if x.strip()]
    log_dir = Path(os.path.expanduser(args.log_dir))
    ok, report = evaluate_reliability(
        log_dir=log_dir,
        days=args.days,
        slots=slots,
        tolerance_minutes=args.tolerance_minutes,
        require_notebooklm=args.require_notebooklm,
        include_today=args.include_today,
    )

    if args.output:
        output_path = Path(os.path.expanduser(args.output))
        output_path.parent.mkdir(parents=True, exist_ok=True)
    else:
        output_path = storage.paths.logs / f"reliability_gate_{datetime.now().date().isoformat()}.md"
    output_path.write_text(report)
    print(f"Reliability gate report written to {output_path}")
    print("Reliability gate: PASS" if ok else "Reliability gate: FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
