#!/usr/bin/env python3
"""Tests for weekly revenue summary report generation."""

import json
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import scripts.revenue_weekly_summary as summary_mod  # noqa: E402


def test_revenue_weekly_summary_writes_outputs():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        outputs_dir = root / "outputs"
        tool_dir = root / "tool"
        working_dir = root / "working"
        outputs_dir.mkdir(parents=True, exist_ok=True)
        tool_dir.mkdir(parents=True, exist_ok=True)
        working_dir.mkdir(parents=True, exist_ok=True)

        now = datetime.now(timezone.utc)
        this_week = now.isoformat()
        yesterday = (now - timedelta(days=1)).isoformat()

        pipeline_path = working_dir / "sales_pipeline.json"
        pipeline_path.write_text(
            json.dumps(
                [
                    {
                        "lead_id": "L-OPEN-1",
                        "name": "Open Lead",
                        "stage": "qualified",
                        "est_value": 1500,
                        "next_action": "Run discovery call",
                        "next_action_due": (now.date() + timedelta(days=1)).isoformat(),
                        "created_at": this_week,
                        "updated_at": this_week,
                        "closed_at": None,
                    },
                    {
                        "lead_id": "L-WON-1",
                        "name": "Won Lead",
                        "stage": "won",
                        "est_value": 1500,
                        "actual_value": 1500,
                        "next_action": "",
                        "next_action_due": "",
                        "created_at": yesterday,
                        "updated_at": this_week,
                        "closed_at": this_week,
                    },
                ]
            ),
            encoding="utf-8",
        )

        intake_path = working_dir / "revenue_intake.jsonl"
        intake_path.write_text(
            json.dumps(
                {
                    "name": "Intake Person",
                    "email": "intake@example.com",
                    "workflow": "Operations",
                    "package": "Core",
                    "created_at": this_week,
                }
            )
            + "\n",
            encoding="utf-8",
        )

        (outputs_dir / "revenue_action_queue_20260225-120000.md").write_text(
            "\n".join(
                [
                    "# Revenue Action Queue",
                    "",
                    "## Next 7 Actions",
                    "1. [today] Follow up with Open Lead",
                    "2. [today] Publish offer update",
                ]
            ),
            encoding="utf-8",
        )

        original = {
            "OUTPUT_DIR": summary_mod.OUTPUT_DIR,
            "TOOL_DIR": summary_mod.TOOL_DIR,
            "PIPELINE_PATH": summary_mod.PIPELINE_PATH,
            "INTAKE_PATH": summary_mod.INTAKE_PATH,
        }
        try:
            summary_mod.OUTPUT_DIR = outputs_dir
            summary_mod.TOOL_DIR = tool_dir
            summary_mod.PIPELINE_PATH = pipeline_path
            summary_mod.INTAKE_PATH = intake_path
            rc = summary_mod.main()
        finally:
            summary_mod.OUTPUT_DIR = original["OUTPUT_DIR"]
            summary_mod.TOOL_DIR = original["TOOL_DIR"]
            summary_mod.PIPELINE_PATH = original["PIPELINE_PATH"]
            summary_mod.INTAKE_PATH = original["INTAKE_PATH"]

        assert rc == 0
        latest_md = outputs_dir / "revenue_weekly_summary_latest.md"
        assert latest_md.exists()
        content = latest_md.read_text(encoding="utf-8")
        assert "Revenue Weekly Summary" in content
        assert "Intake submissions (week): 1" in content
        assert "Wins closed (week): 1" in content
        assert "Open leads now: 1" in content
        assert "Follow up with Open Lead" in content

        json_payloads = list(tool_dir.glob("revenue_weekly_summary_*.json"))
        assert json_payloads


if __name__ == "__main__":
    test_revenue_weekly_summary_writes_outputs()
    print("✓ Revenue weekly summary tests passed")
