#!/usr/bin/env python3
"""Tests for revenue execution board generation."""

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import scripts.revenue_execution_board as board_mod  # noqa: E402


def test_revenue_execution_board_writes_outputs():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        outputs_dir = root / "outputs"
        tool_dir = root / "tool"
        working_dir = root / "working"
        outputs_dir.mkdir(parents=True, exist_ok=True)
        tool_dir.mkdir(parents=True, exist_ok=True)
        working_dir.mkdir(parents=True, exist_ok=True)

        (outputs_dir / "revenue_action_queue_20260225-120000.md").write_text(
            "\n".join(
                [
                    "# Revenue Action Queue",
                    "",
                    "## Next 7 Actions",
                    "1. [today] Send DMs to 5 leads",
                    "2. [today] Publish FOUNDATION offer post",
                ]
            ),
            encoding="utf-8",
        )
        (outputs_dir / "email_triage_20260225-120000.md").write_text(
            "\n".join(
                [
                    "# Email Triage Report",
                    "",
                    "## P0 (1)",
                    "- [30] Critical email",
                    "",
                    "## P1 (2)",
                    "- [20] Follow-up email",
                    "",
                    "## P2 (3)",
                    "- [10] Normal email",
                    "",
                    "## P3 (4)",
                    "- [0] Newsletter",
                ]
            ),
            encoding="utf-8",
        )
        (outputs_dir / "social_summary_20260225-120000.md").write_text(
            "\n".join(
                [
                    "# Social Draft Summary",
                    "",
                    "- Foundation Launch [LinkedIn] (2026-02-25T12:00:00Z)",
                ]
            ),
            encoding="utf-8",
        )

        pipeline_path = working_dir / "sales_pipeline.json"
        pipeline_path.write_text(
            json.dumps(
                [
                    {
                        "lead_id": "L-1",
                        "name": "Lead One",
                        "stage": "qualified",
                        "est_value": 1500,
                        "next_action": "Run fit call",
                        "next_action_due": "2026-02-26",
                    }
                ]
            ),
            encoding="utf-8",
        )
        targets_path = working_dir / "revenue_targets.json"
        targets_path.write_text(json.dumps({"daily_outreach_target": 12}), encoding="utf-8")

        original = {
            "OUTPUT_DIR": board_mod.OUTPUT_DIR,
            "TOOL_DIR": board_mod.TOOL_DIR,
            "PIPELINE_PATH": board_mod.PIPELINE_PATH,
            "TARGETS_PATH": board_mod.TARGETS_PATH,
        }
        try:
            board_mod.OUTPUT_DIR = outputs_dir
            board_mod.TOOL_DIR = tool_dir
            board_mod.PIPELINE_PATH = pipeline_path
            board_mod.TARGETS_PATH = targets_path
            rc = board_mod.main()
        finally:
            board_mod.OUTPUT_DIR = original["OUTPUT_DIR"]
            board_mod.TOOL_DIR = original["TOOL_DIR"]
            board_mod.PIPELINE_PATH = original["PIPELINE_PATH"]
            board_mod.TARGETS_PATH = original["TARGETS_PATH"]

        assert rc == 0

        latest_md = outputs_dir / "revenue_execution_board_latest.md"
        assert latest_md.exists()
        content = latest_md.read_text(encoding="utf-8")
        assert "Revenue Execution Board" in content
        assert "Outreach target today: 12" in content
        assert "Lead One" in content
        assert "P0: 1 | P1: 2 | P2: 3 | P3: 4" in content

        json_payloads = list(tool_dir.glob("revenue_execution_board_*.json"))
        assert json_payloads


if __name__ == "__main__":
    test_revenue_execution_board_writes_outputs()
    print("✓ Revenue execution board tests passed")
