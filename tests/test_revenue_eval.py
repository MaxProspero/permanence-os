#!/usr/bin/env python3
"""Tests for revenue eval harness."""

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import scripts.revenue_eval as eval_mod  # noqa: E402


def test_revenue_eval_passes_with_minimum_artifacts():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        outputs = root / "outputs"
        tool = root / "tool"
        working = root / "working"
        outputs.mkdir(parents=True, exist_ok=True)
        tool.mkdir(parents=True, exist_ok=True)
        working.mkdir(parents=True, exist_ok=True)

        (outputs / "revenue_action_queue_latest.md").write_text("# queue\n", encoding="utf-8")
        (outputs / "revenue_execution_board_latest.md").write_text("# board\n", encoding="utf-8")
        (outputs / "revenue_outreach_pack_latest.md").write_text("# outreach\n", encoding="utf-8")
        (working / "sales_pipeline.json").write_text("[]\n", encoding="utf-8")
        (working / "revenue_playbook.json").write_text(
            json.dumps({"offer_name": "Offer", "cta_keyword": "FOUNDATION"}), encoding="utf-8"
        )
        (working / "revenue_targets.json").write_text(
            json.dumps({"weekly_revenue_target": 3000, "monthly_revenue_target": 12000}), encoding="utf-8"
        )
        (tool / "revenue_outreach_pack_20260226-120000.json").write_text(json.dumps({"messages": []}), encoding="utf-8")

        original = {
            "OUTPUT_DIR": eval_mod.OUTPUT_DIR,
            "TOOL_DIR": eval_mod.TOOL_DIR,
            "WORKING_DIR": eval_mod.WORKING_DIR,
            "PIPELINE_PATH": eval_mod.PIPELINE_PATH,
            "PLAYBOOK_PATH": eval_mod.PLAYBOOK_PATH,
            "TARGETS_PATH": eval_mod.TARGETS_PATH,
            "INTEGRATION_LATEST": eval_mod.INTEGRATION_LATEST,
        }
        try:
            eval_mod.OUTPUT_DIR = outputs
            eval_mod.TOOL_DIR = tool
            eval_mod.WORKING_DIR = working
            eval_mod.PIPELINE_PATH = working / "sales_pipeline.json"
            eval_mod.PLAYBOOK_PATH = working / "revenue_playbook.json"
            eval_mod.TARGETS_PATH = working / "revenue_targets.json"
            eval_mod.INTEGRATION_LATEST = outputs / "integration_readiness_latest.md"
            rc = eval_mod.main()
        finally:
            eval_mod.OUTPUT_DIR = original["OUTPUT_DIR"]
            eval_mod.TOOL_DIR = original["TOOL_DIR"]
            eval_mod.WORKING_DIR = original["WORKING_DIR"]
            eval_mod.PIPELINE_PATH = original["PIPELINE_PATH"]
            eval_mod.PLAYBOOK_PATH = original["PLAYBOOK_PATH"]
            eval_mod.TARGETS_PATH = original["TARGETS_PATH"]
            eval_mod.INTEGRATION_LATEST = original["INTEGRATION_LATEST"]

        assert rc == 0
        latest = outputs / "revenue_eval_latest.md"
        assert latest.exists()
        assert "Result: PASS" in latest.read_text(encoding="utf-8")


if __name__ == "__main__":
    test_revenue_eval_passes_with_minimum_artifacts()
    print("✓ Revenue eval tests passed")
