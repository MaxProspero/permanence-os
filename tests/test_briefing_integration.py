#!/usr/bin/env python3
"""Integration tests for BriefingAgent summaries."""

import os
import json
import tempfile
from datetime import datetime, timezone


def _write_json(path, payload):
    with open(path, "w") as f:
        json.dump(payload, f, indent=2)


def test_briefing_includes_email_health_social_and_focus():
    with tempfile.TemporaryDirectory() as tmp:
        output_dir = os.path.join(tmp, "outputs")
        tool_dir = os.path.join(tmp, "memory", "tool")
        episodic_dir = os.path.join(tmp, "memory", "episodic")
        os.makedirs(output_dir, exist_ok=True)
        os.makedirs(tool_dir, exist_ok=True)
        os.makedirs(episodic_dir, exist_ok=True)

        os.environ["PERMANENCE_OUTPUT_DIR"] = output_dir
        os.environ["PERMANENCE_TOOL_DIR"] = tool_dir
        os.environ["PERMANENCE_MEMORY_DIR"] = os.path.join(tmp, "memory")

        _write_json(
            os.path.join(tool_dir, "email_triage_20260204-000000.json"),
            {
                "P0": [],
                "P1": [],
                "P2": [{"summary": "GitHub 2FA reminder"}, {"summary": "Sign-in review"}],
                "P3": [{}],
            },
        )
        _write_json(
            os.path.join(tool_dir, "health_summary_20260204-000000.json"),
            {
                "avg_sleep_hours": 6.2,
                "avg_hrv": 45,
                "avg_recovery": 62,
                "avg_strain": 8.2,
                "latest": {"date": "2026-02-04", "sleep_hours": 6.1},
            },
        )
        _write_json(
            os.path.join(tool_dir, "social_summary_20260204-000000.json"),
            {
                "count": 2,
                "drafts": [{"title": "Draft A"}, {"title": "Draft B"}],
            },
        )
        with open(os.path.join(output_dir, "weekly_system_health_report.md"), "w") as f:
            f.write("PATTERNS DETECTED\n  1. [LOW] test\nLOGOS PRAKTIKOS STATUS\nReady: NO\n")

        episodic_path = os.path.join(episodic_dir, "episodic_2026-02-04.jsonl")
        with open(episodic_path, "w") as f:
            f.write(json.dumps({"timestamp": datetime.now(timezone.utc).isoformat()}) + "\n")

        from agents.departments.briefing_agent import BriefingAgent  # noqa: E402

        notes = BriefingAgent().execute({}).notes
        content = "\n".join(notes)

        assert "## Email" in content
        assert "P2: 2 items needing action" in content
        assert "GitHub 2FA reminder" in content
        assert "## Health" in content
        assert "avg" in content
        assert "## Social" in content
        assert "Draft queue" in content
        assert "## Today's Focus" in content
        assert "## System Health" in content

