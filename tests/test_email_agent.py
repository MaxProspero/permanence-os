#!/usr/bin/env python3
"""Tests for Email Agent triage."""

import os
import sys
import json
import tempfile
from pathlib import Path

os.environ.setdefault("PERMANENCE_LOG_DIR", "/tmp/permanence-os-test-logs")

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from agents.departments.email_agent import EmailAgent


def test_email_triage_generates_report():
    with tempfile.TemporaryDirectory() as temp:
        inbox_dir = Path(temp) / "email"
        inbox_dir.mkdir(parents=True, exist_ok=True)
        output_dir = Path(temp) / "outputs"
        tool_dir = Path(temp) / "tool"
        os.environ["PERMANENCE_OUTPUT_DIR"] = str(output_dir)
        os.environ["PERMANENCE_TOOL_DIR"] = str(tool_dir)

        messages = [
            {
                "id": "1",
                "from": "vip@example.com",
                "subject": "Urgent: approve contract",
                "body": "Please approve today.",
                "date": "2026-02-03",
            },
            {
                "id": "2",
                "from": "news@example.com",
                "subject": "Newsletter",
                "body": "Weekly update",
                "labels": ["newsletter"],
                "date": "2026-02-02",
            },
        ]
        (inbox_dir / "inbox.json").write_text(json.dumps(messages))

        agent = EmailAgent()
        result = agent.execute(
            {
                "inbox_dir": str(inbox_dir),
                "vip_senders": ["vip@example.com"],
            }
        )

        assert result.status == "TRIAGED"
        assert result.artifact is not None
        assert output_dir.exists()
        assert tool_dir.exists()
        assert any(p.name.startswith("email_triage_") for p in output_dir.iterdir())


if __name__ == "__main__":
    test_email_triage_generates_report()
    print("✓ Email agent tests passed")
