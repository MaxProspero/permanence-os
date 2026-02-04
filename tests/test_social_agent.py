#!/usr/bin/env python3
"""Tests for Social Agent summary and draft save."""

import os
import sys
import tempfile
import json
from pathlib import Path

os.environ.setdefault("PERMANENCE_LOG_DIR", "/tmp/permanence-os-test-logs")

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from agents.departments.social_agent import SocialAgent


def test_social_summary_generates_report():
    with tempfile.TemporaryDirectory() as temp:
        queue_dir = Path(temp) / "social"
        queue_dir.mkdir(parents=True, exist_ok=True)
        output_dir = Path(temp) / "outputs"
        tool_dir = Path(temp) / "tool"
        os.environ["PERMANENCE_OUTPUT_DIR"] = str(output_dir)
        os.environ["PERMANENCE_TOOL_DIR"] = str(tool_dir)

        drafts = [
            {
                "title": "Draft 1",
                "body": "Body",
                "platform": "x",
                "created_at": "2026-02-03T00:00:00+00:00",
            }
        ]
        (queue_dir / "drafts.json").write_text(json.dumps(drafts))

        agent = SocialAgent()
        result = agent.execute({"queue_dir": str(queue_dir)})

        assert result.status == "SUMMARY"
        assert result.artifact is not None
        assert output_dir.exists()
        assert tool_dir.exists()
        assert any(p.name.startswith("social_summary_") for p in output_dir.iterdir())


def test_social_draft_append():
    with tempfile.TemporaryDirectory() as temp:
        queue_dir = Path(temp) / "social"
        queue_dir.mkdir(parents=True, exist_ok=True)

        agent = SocialAgent()
        result = agent.execute(
            {
                "queue_dir": str(queue_dir),
                "action": "draft",
                "draft": {"title": "Test Draft", "body": "Hello", "platform": "x"},
            }
        )
        assert result.status == "DRAFT_SAVED"
        assert Path(result.artifact).exists()


if __name__ == "__main__":
    test_social_summary_generates_report()
    test_social_draft_append()
    print("✓ Social agent tests passed")
