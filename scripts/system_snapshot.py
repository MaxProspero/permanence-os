#!/usr/bin/env python3
"""
Generate an aggregated system snapshot report:
- Permanence status
- Latest OpenClaw status
- Latest Briefing
- Latest HR report
"""

from __future__ import annotations

import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _latest_path(dir_path: str, pattern: str) -> str:
    if not os.path.isdir(dir_path):
        return ""
    candidates = sorted(
        Path(dir_path).glob(pattern),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return str(candidates[0]) if candidates else ""


def _read_tail(path: str, max_lines: int = 50) -> str:
    if not path or not os.path.exists(path):
        return ""
    with open(path, "r") as f:
        lines = f.readlines()
    return "".join(lines[-max_lines:])


def main() -> int:
    output_dir = os.getenv("PERMANENCE_OUTPUT_DIR", os.path.join(BASE_DIR, "outputs"))
    memory_dir = os.getenv("PERMANENCE_MEMORY_DIR", os.path.join(BASE_DIR, "memory"))
    os.makedirs(output_dir, exist_ok=True)

    status_output = subprocess.check_output(
        ["python", os.path.join(BASE_DIR, "scripts", "status.py")],
        text=True,
    )
    openclaw_status = _latest_path(output_dir, "openclaw_status_*.txt")
    briefing = _latest_path(output_dir, "briefing_*.md")
    hr_report = os.path.join(output_dir, "weekly_system_health_report.md")
    episodic_jsonl = _latest_path(os.path.join(memory_dir, "episodic"), "episodic_*.jsonl")

    lines = [
        "# System Snapshot",
        f"- Time (UTC): {datetime.now(timezone.utc).isoformat()}",
        "",
        "## Status",
        "```",
        status_output.strip(),
        "```",
        "",
        "## OpenClaw Status (latest)",
        openclaw_status or "none",
        "",
        "## Briefing (latest)",
        briefing or "none",
        "",
        "## HR Report",
        hr_report if os.path.exists(hr_report) else "none",
        "",
        "## Episodic JSONL (latest)",
        episodic_jsonl or "none",
        "",
        "## OpenClaw Status Excerpt",
        "```",
        _read_tail(openclaw_status, max_lines=20).strip(),
        "```",
    ]

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    output_path = os.path.join(output_dir, f"system_snapshot_{stamp}.md")
    with open(output_path, "w") as f:
        f.write("\n".join(lines) + "\n")

    print(f"Snapshot written to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
