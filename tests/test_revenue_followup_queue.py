#!/usr/bin/env python3
"""Tests for revenue follow-up queue generation."""

import json
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import scripts.revenue_followup_queue as follow_mod  # noqa: E402


def test_revenue_followup_queue_writes_due_followups():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        outputs_dir = root / "outputs"
        tool_dir = root / "tool"
        working_dir = root / "working"
        outputs_dir.mkdir(parents=True, exist_ok=True)
        tool_dir.mkdir(parents=True, exist_ok=True)
        working_dir.mkdir(parents=True, exist_ok=True)

        outreach_tool = tool_dir / "revenue_outreach_pack_20260226-120000.json"
        outreach_tool.write_text(
            json.dumps(
                {
                    "messages": [
                        {
                            "lead_id": "L-1",
                            "lead_name": "Alpha",
                            "stage": "proposal_sent",
                            "channel": "email",
                            "subject": "Alpha follow-up",
                            "body": "Body",
                        },
                        {
                            "lead_id": "L-2",
                            "lead_name": "Beta",
                            "stage": "qualified",
                            "channel": "dm",
                            "subject": "Beta follow-up",
                            "body": "Body",
                        },
                    ]
                }
            ),
            encoding="utf-8",
        )

        sent_old = (datetime.now(timezone.utc) - timedelta(hours=72)).isoformat()
        status_path = working_dir / "revenue_outreach_status.jsonl"
        status_path.write_text(
            json.dumps(
                {
                    "event_id": "RO-1",
                    "timestamp": sent_old,
                    "message_key": "L-1",
                    "lead_id": "L-1",
                    "status": "sent",
                }
            )
            + "\n",
            encoding="utf-8",
        )

        original = {
            "OUTPUT_DIR": follow_mod.OUTPUT_DIR,
            "TOOL_DIR": follow_mod.TOOL_DIR,
            "WORKING_DIR": follow_mod.WORKING_DIR,
            "OUTREACH_STATUS_PATH": follow_mod.OUTREACH_STATUS_PATH,
            "FOLLOWUP_HOURS": follow_mod.FOLLOWUP_HOURS,
        }
        try:
            follow_mod.OUTPUT_DIR = outputs_dir
            follow_mod.TOOL_DIR = tool_dir
            follow_mod.WORKING_DIR = working_dir
            follow_mod.OUTREACH_STATUS_PATH = status_path
            follow_mod.FOLLOWUP_HOURS = 48
            rc = follow_mod.main()
        finally:
            follow_mod.OUTPUT_DIR = original["OUTPUT_DIR"]
            follow_mod.TOOL_DIR = original["TOOL_DIR"]
            follow_mod.WORKING_DIR = original["WORKING_DIR"]
            follow_mod.OUTREACH_STATUS_PATH = original["OUTREACH_STATUS_PATH"]
            follow_mod.FOLLOWUP_HOURS = original["FOLLOWUP_HOURS"]

        assert rc == 0
        latest_md = outputs_dir / "revenue_followup_queue_latest.md"
        assert latest_md.exists()
        content = latest_md.read_text(encoding="utf-8")
        assert "Revenue Follow-up Queue" in content
        assert "Alpha" in content
        assert "No follow-ups due right now." not in content

        payloads = sorted(tool_dir.glob("revenue_followup_queue_*.json"))
        assert payloads
        payload = json.loads(payloads[-1].read_text(encoding="utf-8"))
        assert payload.get("count") >= 1
        assert payload.get("followups", [])[0]["lead_id"] == "L-1"


if __name__ == "__main__":
    test_revenue_followup_queue_writes_due_followups()
    print("✓ Revenue follow-up queue tests passed")
