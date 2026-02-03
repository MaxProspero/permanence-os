#!/usr/bin/env python3
"""
Generate weekly system health report using HR Agent.
"""

import argparse
import os
import subprocess
import sys
from datetime import datetime, timezone

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(BASE_DIR)

from agents.departments.hr_agent import HRAgent  # noqa: E402

OUTPUT_DIR = os.getenv("PERMANENCE_OUTPUT_DIR", os.path.join(BASE_DIR, "outputs"))
DEFAULT_OUTPUT = os.getenv(
    "PERMANENCE_HR_REPORT_OUTPUT",
    os.path.join(OUTPUT_DIR, "weekly_system_health_report.md"),
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate weekly system health report")
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help="Output report path")
    args = parser.parse_args()

    _capture_openclaw_snapshot()
    agent = HRAgent()
    report = agent.generate_weekly_report()
    formatted = agent.format_report(report)

    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, "w") as f:
        f.write(formatted + "\n")

    print(f"HR report written to {args.output}")
    return 0


def _capture_openclaw_snapshot() -> None:
    script_path = os.path.join(BASE_DIR, "scripts", "openclaw_status.py")
    if not os.path.exists(script_path):
        return
    openclaw_cli = os.getenv("OPENCLAW_CLI", os.path.expanduser("~/.openclaw/bin/openclaw"))
    if not os.path.exists(openclaw_cli):
        return
    for args in ([], ["--health"]):
        cmd = [sys.executable, script_path, *args]
        try:
            subprocess.run(cmd, check=False, capture_output=True, text=True)
        except OSError:
            continue


if __name__ == "__main__":
    raise SystemExit(main())
