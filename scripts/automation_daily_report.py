#!/usr/bin/env python3
"""
Generate an automation status report from recent run logs.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(BASE_DIR)

from core.storage import storage  # noqa: E402


STATUS_RE = re.compile(
    r"Briefing Status:\s*(\d+)\s*\|\s*Digest Status:\s*(\d+)\s*\|\s*NotebookLM Status:\s*(\d+)"
)
HEALTH_REPORT_RE = re.compile(r"Health Status:\s*(\d+)\s*\|\s*Report Status:\s*(\d+)")
CHRONICLE_RE = re.compile(
    r"Chronicle Capture:\s*(\d+)\s*\|\s*Chronicle Report:\s*(\d+)\s*\|\s*Chronicle Publish:\s*(\d+)"
)
DAILY_GATE_RE = re.compile(r"Daily Gate Status:\s*(\d+)\s*\|\s*Streak Status:\s*(\d+)")
WEEKLY_PHASE_RE = re.compile(r"Weekly Phase Gate Status:\s*(\d+)")
PROMOTION_DAILY_RE = re.compile(r"Promotion Daily Status:\s*(\d+)")
GLANCE_RE = re.compile(r"Glance Status:\s*(\d+)")
V04_SNAPSHOT_RE = re.compile(r"V04 Snapshot Status:\s*(\d+)")
START_RE = re.compile(r"=== Briefing Run Started:\s*(.+)\s+===")
RECEPTION_RE = re.compile(r"\n([A-Za-z][A-Za-z0-9 _-]*) Status:\s*(\d+)\nHealth Status:")


@dataclass
class RunSummary:
    path: Path
    started_at: datetime | None
    briefing_status: int | None
    digest_status: int | None
    notebooklm_status: int | None
    receptionist_name: str | None
    receptionist_status: int | None
    health_status: int | None
    report_status: int | None
    chronicle_capture_status: int | None
    chronicle_report_status: int | None
    chronicle_publish_status: int | None
    daily_gate_status: int | None
    streak_status: int | None
    weekly_phase_gate_status: int | None
    promotion_daily_status: int | None
    glance_status: int | None
    v04_snapshot_status: int | None

    @property
    def success(self) -> bool:
        return (
            self.briefing_status == 0
            and self.digest_status == 0
            and (self.notebooklm_status in (0, None))
            and (self.health_status in (0, None))
            and (self.report_status in (0, None))
            and (self.chronicle_capture_status in (0, None))
            and (self.chronicle_report_status in (0, None))
            and (self.chronicle_publish_status in (0, None))
            and (self.promotion_daily_status in (0, 2, None))
            and (self.glance_status in (0, None))
            and (self.v04_snapshot_status in (0, None))
        )


def _parse_started_at(text: str) -> datetime | None:
    # Example: Fri Feb  6 20:37:45 CST 2026
    for fmt in ("%a %b %d %H:%M:%S %Z %Y", "%a %b %d %H:%M:%S %Y"):
        try:
            dt = datetime.strptime(text, fmt)
            return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)
        except ValueError:
            continue
    return None


def _extract_status(match: re.Match[str] | None, idx: int) -> int | None:
    if not match:
        return None
    return int(match.group(idx))


def _collect_runs(log_dir: Path) -> list[RunSummary]:
    runs: list[RunSummary] = []
    for path in sorted(log_dir.glob("run_*.log"), reverse=True):
        text = path.read_text(errors="ignore")
        status_match = STATUS_RE.search(text)
        health_report_match = HEALTH_REPORT_RE.search(text)
        chronicle_match = CHRONICLE_RE.search(text)
        daily_gate_match = DAILY_GATE_RE.search(text)
        weekly_phase_match = WEEKLY_PHASE_RE.search(text)
        promotion_daily_match = PROMOTION_DAILY_RE.search(text)
        glance_match = GLANCE_RE.search(text)
        v04_match = V04_SNAPSHOT_RE.search(text)
        reception_match = RECEPTION_RE.search(text)
        start_match = START_RE.search(text)
        started_at = _parse_started_at(start_match.group(1).strip()) if start_match else None
        v04_status = int(v04_match.group(1)) if v04_match else None
        receptionist_name = reception_match.group(1) if reception_match else None
        receptionist_status = _extract_status(reception_match, 2)
        if status_match:
            runs.append(
                RunSummary(
                    path=path,
                    started_at=started_at,
                    briefing_status=int(status_match.group(1)),
                    digest_status=int(status_match.group(2)),
                    notebooklm_status=int(status_match.group(3)),
                    receptionist_name=receptionist_name,
                    receptionist_status=receptionist_status,
                    health_status=_extract_status(health_report_match, 1),
                    report_status=_extract_status(health_report_match, 2),
                    chronicle_capture_status=_extract_status(chronicle_match, 1),
                    chronicle_report_status=_extract_status(chronicle_match, 2),
                    chronicle_publish_status=_extract_status(chronicle_match, 3),
                    daily_gate_status=_extract_status(daily_gate_match, 1),
                    streak_status=_extract_status(daily_gate_match, 2),
                    weekly_phase_gate_status=_extract_status(weekly_phase_match, 1),
                    promotion_daily_status=_extract_status(promotion_daily_match, 1),
                    glance_status=_extract_status(glance_match, 1),
                    v04_snapshot_status=v04_status,
                )
            )
        else:
            runs.append(
                RunSummary(
                    path=path,
                    started_at=started_at,
                    briefing_status=None,
                    digest_status=None,
                    notebooklm_status=None,
                    receptionist_name=receptionist_name,
                    receptionist_status=receptionist_status,
                    health_status=_extract_status(health_report_match, 1),
                    report_status=_extract_status(health_report_match, 2),
                    chronicle_capture_status=_extract_status(chronicle_match, 1),
                    chronicle_report_status=_extract_status(chronicle_match, 2),
                    chronicle_publish_status=_extract_status(chronicle_match, 3),
                    daily_gate_status=_extract_status(daily_gate_match, 1),
                    streak_status=_extract_status(daily_gate_match, 2),
                    weekly_phase_gate_status=_extract_status(weekly_phase_match, 1),
                    promotion_daily_status=_extract_status(promotion_daily_match, 1),
                    glance_status=_extract_status(glance_match, 1),
                    v04_snapshot_status=v04_status,
                )
            )
    return runs


def _check_launchd(label: str) -> bool:
    try:
        proc = subprocess.run(
            ["launchctl", "list"],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        # Non-macOS environments (e.g., Linux cron on Dell) won't have launchctl.
        return False
    return proc.returncode == 0 and label in proc.stdout


def _latest_name(path: Path, pattern: str) -> str:
    candidates = sorted(path.glob(pattern), reverse=True)
    return candidates[0].name if candidates else "none"


def _fmt(status: int | None) -> str:
    return "n/a" if status is None else str(status)


def _build_report(runs: list[RunSummary], days: int, label: str) -> str:
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=days)
    in_window = [r for r in runs if (r.started_at and r.started_at >= cutoff) or not r.started_at]
    # Keep the report informative even when there are no runs in the lookback window yet.
    if not in_window and runs:
        in_window = [runs[0]]
    successful = [r for r in in_window if r.success]
    failed = [r for r in in_window if not r.success]
    launchd_loaded = _check_launchd(label)
    latest_briefing = _latest_name(storage.paths.outputs_briefings, "briefing_*.md")
    latest_digest = _latest_name(storage.paths.outputs_digests, "sources_digest_*.md")

    lines = [
        f"# Automation Daily Report — {now.date()}",
        "",
        f"- Generated (UTC): {now.isoformat()}",
        f"- Launchd label: `{label}`",
        f"- Launchd loaded: {'yes' if launchd_loaded else 'no'}",
        f"- Runs checked (last {days} day(s)): {len(in_window)}",
        f"- Successful runs: {len(successful)}",
        f"- Failed/incomplete runs: {len(failed)}",
        f"- Latest briefing: {latest_briefing}",
        f"- Latest digest: {latest_digest}",
        "",
        "## Latest Run",
    ]

    if runs:
        latest = runs[0]
        lines.extend(
            [
                f"- Log: {latest.path.name}",
                f"- Started: {latest.started_at.isoformat() if latest.started_at else 'unknown'}",
                f"- Briefing status: {_fmt(latest.briefing_status)}",
                f"- Digest status: {_fmt(latest.digest_status)}",
                f"- NotebookLM status: {_fmt(latest.notebooklm_status)}",
                f"- Receptionist ({latest.receptionist_name or 'n/a'}) status: {_fmt(latest.receptionist_status)}",
                f"- Health status: {_fmt(latest.health_status)}",
                f"- Report status: {_fmt(latest.report_status)}",
                f"- Chronicle capture/report/publish: {_fmt(latest.chronicle_capture_status)}/{_fmt(latest.chronicle_report_status)}/{_fmt(latest.chronicle_publish_status)}",
                f"- Daily gate/streak: {_fmt(latest.daily_gate_status)}/{_fmt(latest.streak_status)}",
                f"- Weekly phase gate status: {_fmt(latest.weekly_phase_gate_status)}",
                f"- Promotion daily status: {_fmt(latest.promotion_daily_status)}",
                f"- Glance status: {_fmt(latest.glance_status)}",
                f"- V04 snapshot status: {_fmt(latest.v04_snapshot_status)}",
            ]
        )
    else:
        lines.append("- No run logs found.")

    if failed:
        lines.extend(["", "## Failures"])
        for run in failed[:10]:
            lines.append(
                f"- {run.path.name}: briefing={_fmt(run.briefing_status)}, digest={_fmt(run.digest_status)}, "
                f"notebooklm={_fmt(run.notebooklm_status)}, health={_fmt(run.health_status)}, "
                f"report={_fmt(run.report_status)}, chronicle_publish={_fmt(run.chronicle_publish_status)}, "
                f"promotion_daily={_fmt(run.promotion_daily_status)}, glance={_fmt(run.glance_status)}, "
                f"v04_snapshot={_fmt(run.v04_snapshot_status)}"
            )

    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate daily automation status report.")
    parser.add_argument(
        "--log-dir",
        default=str(Path(BASE_DIR) / "logs" / "automation"),
        help="Automation log directory",
    )
    parser.add_argument("--days", type=int, default=1, help="Lookback window in days")
    parser.add_argument(
        "--label",
        default="com.permanence.briefing",
        help="Launchd label for status check",
    )
    parser.add_argument("--output", help="Optional explicit output path")
    args = parser.parse_args()

    log_dir = Path(os.path.expanduser(args.log_dir))
    runs = _collect_runs(log_dir) if log_dir.exists() else []
    report = _build_report(runs, args.days, args.label)

    if args.output:
        output_path = Path(os.path.expanduser(args.output))
        output_path.parent.mkdir(parents=True, exist_ok=True)
    else:
        output_path = storage.paths.logs / f"automation_report_{datetime.now(timezone.utc).date().isoformat()}.md"
    output_path.write_text(report)

    print(f"Automation report written to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
