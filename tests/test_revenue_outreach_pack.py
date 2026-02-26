#!/usr/bin/env python3
"""Tests for revenue outreach pack generation."""

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import scripts.revenue_outreach_pack as outreach_mod  # noqa: E402


def test_revenue_outreach_pack_writes_outputs():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        outputs_dir = root / "outputs"
        tool_dir = root / "tool"
        working_dir = root / "working"
        outputs_dir.mkdir(parents=True, exist_ok=True)
        tool_dir.mkdir(parents=True, exist_ok=True)
        working_dir.mkdir(parents=True, exist_ok=True)

        pipeline_path = working_dir / "sales_pipeline.json"
        pipeline_path.write_text(
            json.dumps(
                [
                    {
                        "lead_id": "L-1",
                        "name": "Alpha Co",
                        "source": "X DM",
                        "stage": "qualified",
                        "est_value": 1500,
                        "next_action": "Book discovery call",
                        "next_action_due": "2026-02-27",
                        "updated_at": "2026-02-26T10:00:00Z",
                    },
                    {
                        "lead_id": "L-2",
                        "name": "Beta Co",
                        "source": "website intake",
                        "stage": "proposal_sent",
                        "est_value": 3000,
                        "next_action": "Follow up on proposal",
                        "next_action_due": "2026-02-26",
                        "updated_at": "2026-02-26T11:00:00Z",
                    },
                    {
                        "lead_id": "L-3",
                        "name": "Closed Lead",
                        "source": "email",
                        "stage": "won",
                        "est_value": 1200,
                        "next_action": "",
                        "next_action_due": "",
                    },
                ]
            ),
            encoding="utf-8",
        )
        playbook_path = working_dir / "revenue_playbook.json"
        playbook_path.write_text(
            json.dumps(
                {
                    "offer_name": "Operator System Install",
                    "cta_keyword": "OPERATOR",
                    "cta_public": 'DM me "OPERATOR".',
                    "cta_direct": 'If this is a fit, DM "OPERATOR" and I will send intake + calendar link.',
                    "pricing_tier": "Pilot",
                    "price_usd": 900,
                }
            ),
            encoding="utf-8",
        )

        original = {
            "OUTPUT_DIR": outreach_mod.OUTPUT_DIR,
            "TOOL_DIR": outreach_mod.TOOL_DIR,
            "WORKING_DIR": outreach_mod.WORKING_DIR,
            "PIPELINE_PATH": outreach_mod.PIPELINE_PATH,
            "PLAYBOOK_PATH": outreach_mod.PLAYBOOK_PATH,
        }
        try:
            outreach_mod.OUTPUT_DIR = outputs_dir
            outreach_mod.TOOL_DIR = tool_dir
            outreach_mod.WORKING_DIR = working_dir
            outreach_mod.PIPELINE_PATH = pipeline_path
            outreach_mod.PLAYBOOK_PATH = playbook_path
            rc = outreach_mod.main()
        finally:
            outreach_mod.OUTPUT_DIR = original["OUTPUT_DIR"]
            outreach_mod.TOOL_DIR = original["TOOL_DIR"]
            outreach_mod.WORKING_DIR = original["WORKING_DIR"]
            outreach_mod.PIPELINE_PATH = original["PIPELINE_PATH"]
            outreach_mod.PLAYBOOK_PATH = original["PLAYBOOK_PATH"]

        assert rc == 0
        latest_md = outputs_dir / "revenue_outreach_pack_latest.md"
        assert latest_md.exists()
        content = latest_md.read_text(encoding="utf-8")
        assert "Revenue Outreach Pack" in content
        assert "Operator System Install" in content
        assert "Alpha Co" in content
        assert "Beta Co" in content
        assert "Governance Notes" in content
        assert "Closed Lead" not in content

        payloads = sorted(tool_dir.glob("revenue_outreach_pack_*.json"))
        assert payloads
        payload = json.loads(payloads[-1].read_text(encoding="utf-8"))
        assert len(payload.get("messages") or []) == 2
        assert payload.get("playbook", {}).get("cta_keyword") == "OPERATOR"
        assert any(msg.get("channel") == "dm" for msg in payload["messages"])
        assert any(msg.get("channel") == "email" for msg in payload["messages"])


if __name__ == "__main__":
    test_revenue_outreach_pack_writes_outputs()
    print("✓ Revenue outreach pack tests passed")
