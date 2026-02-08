#!/usr/bin/env python3
"""Tests for Ari receptionist intake/summary flow."""

import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("PERMANENCE_LOG_DIR", "/tmp/permanence-os-test-logs")

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from agents.departments.reception_agent import ReceptionAgent  # noqa: E402


def test_ari_intake_and_summary():
    with tempfile.TemporaryDirectory() as temp:
        queue_dir = Path(temp) / "queue"
        output_dir = Path(temp) / "outputs"
        tool_dir = Path(temp) / "tool"
        queue_dir.mkdir(parents=True, exist_ok=True)
        os.environ["PERMANENCE_OUTPUT_DIR"] = str(output_dir)
        os.environ["PERMANENCE_TOOL_DIR"] = str(tool_dir)

        agent = ReceptionAgent()
        intake = agent.execute(
            {
                "action": "intake",
                "queue_dir": str(queue_dir),
                "sender": "payton",
                "message": "Need urgent review of weekly gate",
                "channel": "discord",
                "source": "manual",
            }
        )
        assert intake.status == "INTAKE_SAVED"

        summary = agent.execute(
            {
                "action": "summary",
                "queue_dir": str(queue_dir),
                "max_items": 10,
            }
        )
        assert summary.status == "SUMMARY"
        assert output_dir.exists()
        assert tool_dir.exists()
        assert any(p.name.startswith("ari_reception_") for p in output_dir.iterdir())
        assert any(p.name.startswith("ari_reception_") for p in tool_dir.iterdir())


if __name__ == "__main__":
    test_ari_intake_and_summary()
    print("ok")
