#!/usr/bin/env python3
"""
Generate a consolidated dashboard report.
Includes status, latest OpenClaw files, HR report, and briefing output paths.
"""

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(BASE_DIR)


def _latest_path(dir_path: str, pattern: str) -> str:
    if not os.path.isdir(dir_path):
        return ""
    candidates = sorted(
        Path(dir_path).glob(pattern),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return str(candidates[0]) if candidates else ""


def _default_output_path() -> str:
    output_dir = os.getenv("PERMANENCE_OUTPUT_DIR", os.path.join(BASE_DIR, "outputs"))
    os.makedirs(output_dir, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return os.path.join(output_dir, f"dashboard_{stamp}.md")


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate dashboard report")
    parser.add_argument("--output", help="Output path")
    args = parser.parse_args()

    output_dir = os.getenv("PERMANENCE_OUTPUT_DIR", os.path.join(BASE_DIR, "outputs"))
    memory_dir = os.getenv("PERMANENCE_MEMORY_DIR", os.path.join(BASE_DIR, "memory"))

    latest_status = _latest_path(output_dir, "openclaw_status_*.txt")
    latest_health = _latest_path(output_dir, "openclaw_health_*.txt")
    latest_briefing = _latest_path(output_dir, "briefing_*.md")
    latest_hr = os.path.join(output_dir, "weekly_system_health_report.md")
    latest_ep_jsonl = _latest_path(os.path.join(memory_dir, "episodic"), "episodic_*.jsonl")
    latest_ep_json = _latest_path(os.path.join(memory_dir, "episodic"), "T-*.json")

    lines = [
        "# Permanence OS Dashboard",
        f"- Time (UTC): {datetime.now(timezone.utc).isoformat()}",
        "",
        "## OpenClaw",
        f"- Status file: {latest_status or 'none'}",
        f"- Health file: {latest_health or 'none'}",
        "",
        "## Reports",
        f"- Briefing: {latest_briefing or 'none'}",
        f"- HR report: {latest_hr if os.path.exists(latest_hr) else 'none'}",
        "",
        "## Episodic Memory",
        f"- Latest JSONL: {latest_ep_jsonl or 'none'}",
        f"- Latest per-task JSON: {latest_ep_json or 'none'}",
    ]

    output_path = args.output or _default_output_path()
    with open(output_path, "w") as f:
        f.write("\n".join(lines) + "\n")

    print(f"Dashboard written to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
