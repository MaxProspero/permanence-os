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
START_RE = re.compile(r"=== Briefing Run Started:\s*(.+)\s+===")


@dataclass
class RunSummary:
    path: Path
    started_at: datetime | None
    briefing_status: int | None
    digest_status: int | None
    notebooklm_status: int | None

    @property
    def success(self) -> bool:
        return (
            self.briefing_status == 0
            and self.digest_status == 0
            and (self.notebooklm_status in (0, None))
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


def _collect_runs(log_dir: Path) -> list[RunSummary]:
    runs: list[RunSummary] = []
    for path in sorted(log_dir.glob("run_*.log"), reverse=True):
        text = path.read_text(errors="ignore")
        status_match = STATUS_RE.search(text)
        start_match = START_RE.search(text)
        started_at = _parse_started_at(start_match.group(1).strip()) if start_match else None
        if status_match:
            runs.append(
                RunSummary(
                    path=path,
                    started_at=started_at,
                    briefing_status=int(status_match.group(1)),
                    digest_status=int(status_match.group(2)),
                    notebooklm_status=int(status_match.group(3)),
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
                )
            )
    return runs


def _check_launchd(label: str) -> bool:
    proc = subprocess.run(
        ["launchctl", "list"],
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.returncode == 0 and label in proc.stdout


def _latest_name(path: Path, pattern: str) -> str:
    candidates = sorted(path.glob(pattern), reverse=True)
    return candidates[0].name if candidates else "none"


def _build_report(runs: list[RunSummary], days: int, label: str) -> str:
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=days)
    in_window = [r for r in runs if (r.started_at and r.started_at >= cutoff) or not r.started_at]
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
                f"- Briefing status: {latest.briefing_status}",
                f"- Digest status: {latest.digest_status}",
                f"- NotebookLM status: {latest.notebooklm_status}",
            ]
        )
    else:
        lines.append("- No run logs found.")

    if failed:
        lines.extend(["", "## Failures"])
        for run in failed[:10]:
            lines.append(
                f"- {run.path.name}: briefing={run.briefing_status}, digest={run.digest_status}, notebooklm={run.notebooklm_status}"
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
