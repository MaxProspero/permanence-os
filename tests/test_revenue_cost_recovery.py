#!/usr/bin/env python3
"""Tests for revenue cost-recovery planner."""

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import scripts.revenue_cost_recovery as recovery_mod  # noqa: E402


def test_revenue_cost_recovery_writes_outputs():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        outputs_dir = root / "outputs"
        tool_dir = root / "tool"
        working_dir = root / "working"
        outputs_dir.mkdir(parents=True, exist_ok=True)
        tool_dir.mkdir(parents=True, exist_ok=True)
        working_dir.mkdir(parents=True, exist_ok=True)

        (outputs_dir / "revenue_action_queue_20260301-120000.md").write_text(
            "\n".join(
                [
                    "# Revenue Action Queue",
                    "",
                    "## Next 7 Actions",
                    "1. [today] Resolve high-priority email: Your receipt from X Developer Platform",
                    "2. [today] Follow up with warm lead",
                    "3. [today] Publish offer CTA post",
                ]
            ),
            encoding="utf-8",
        )
        (working_dir / "revenue_playbook.json").write_text(
            json.dumps({"offer_name": "Operator Install", "price_usd": 1000, "cta_public": 'DM "OPERATOR".'}),
            encoding="utf-8",
        )
        (working_dir / "revenue_targets.json").write_text(
            json.dumps({"daily_outreach_target": 5}),
            encoding="utf-8",
        )
        (working_dir / "sales_pipeline.json").write_text(
            json.dumps(
                [
                    {"lead_id": "L1", "name": "Open A", "stage": "qualified", "est_value": 1200},
                    {"lead_id": "L2", "name": "Open B", "stage": "proposal_sent", "est_value": 1800},
                    {"lead_id": "L3", "name": "Won A", "stage": "won", "actual_value": 1500},
                    {"lead_id": "L4", "name": "Lost A", "stage": "lost", "est_value": 1200},
                    {"lead_id": "L5", "name": "Lost B", "stage": "lost", "est_value": 900},
                ]
            ),
            encoding="utf-8",
        )

        original = {
            "OUTPUT_DIR": recovery_mod.OUTPUT_DIR,
            "TOOL_DIR": recovery_mod.TOOL_DIR,
            "WORKING_DIR": recovery_mod.WORKING_DIR,
            "PIPELINE_PATH": recovery_mod.PIPELINE_PATH,
            "TARGETS_PATH": recovery_mod.TARGETS_PATH,
            "PLAYBOOK_PATH": recovery_mod.PLAYBOOK_PATH,
            "COST_PLAN_PATH": recovery_mod.COST_PLAN_PATH,
        }
        try:
            recovery_mod.OUTPUT_DIR = outputs_dir
            recovery_mod.TOOL_DIR = tool_dir
            recovery_mod.WORKING_DIR = working_dir
            recovery_mod.PIPELINE_PATH = working_dir / "sales_pipeline.json"
            recovery_mod.TARGETS_PATH = working_dir / "revenue_targets.json"
            recovery_mod.PLAYBOOK_PATH = working_dir / "revenue_playbook.json"
            recovery_mod.COST_PLAN_PATH = working_dir / "api_cost_plan.json"
            rc = recovery_mod.main([])
        finally:
            recovery_mod.OUTPUT_DIR = original["OUTPUT_DIR"]
            recovery_mod.TOOL_DIR = original["TOOL_DIR"]
            recovery_mod.WORKING_DIR = original["WORKING_DIR"]
            recovery_mod.PIPELINE_PATH = original["PIPELINE_PATH"]
            recovery_mod.TARGETS_PATH = original["TARGETS_PATH"]
            recovery_mod.PLAYBOOK_PATH = original["PLAYBOOK_PATH"]
            recovery_mod.COST_PLAN_PATH = original["COST_PLAN_PATH"]

        assert rc == 0

        latest_md = outputs_dir / "revenue_cost_recovery_latest.md"
        assert latest_md.exists()
        content = latest_md.read_text(encoding="utf-8")
        assert "Revenue Cost Recovery Plan" in content
        assert "Target closes needed" in content
        assert "Follow up with warm lead" in content
        assert "Offer price used: $1,000" in content
        assert "receipt from X Developer Platform" not in content

        json_payloads = list(tool_dir.glob("revenue_cost_recovery_*.json"))
        assert json_payloads
        payload = json.loads(json_payloads[-1].read_text(encoding="utf-8"))
        recovery = payload.get("recovery_plan") or {}
        assert recovery.get("target_closes", 0) >= 1
        assert recovery.get("daily_outreach_needed", 0) >= 1
        assert (working_dir / "api_cost_plan.json").exists()


if __name__ == "__main__":
    test_revenue_cost_recovery_writes_outputs()
    print("✓ Revenue cost recovery tests passed")
