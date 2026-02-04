#!/usr/bin/env python3
"""Tests for Health Agent summary."""

import os
import sys
import json
import tempfile
from pathlib import Path

os.environ.setdefault("PERMANENCE_LOG_DIR", "/tmp/permanence-os-test-logs")

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from agents.departments.health_agent import HealthAgent


def test_health_summary_generates_report():
    with tempfile.TemporaryDirectory() as temp:
        data_dir = Path(temp) / "health"
        data_dir.mkdir(parents=True, exist_ok=True)
        output_dir = Path(temp) / "outputs"
        tool_dir = Path(temp) / "tool"
        os.environ["PERMANENCE_OUTPUT_DIR"] = str(output_dir)
        os.environ["PERMANENCE_TOOL_DIR"] = str(tool_dir)

        entries = [
            {
                "date": "2026-02-01",
                "sleep_hours": 7.2,
                "hrv": 55,
                "recovery_score": 78,
                "strain": 12,
            },
            {
                "date": "2026-02-02",
                "sleep_hours": 6.8,
                "hrv": 52,
                "recovery_score": 70,
                "strain": 10,
            },
        ]
        (data_dir / "health.json").write_text(json.dumps(entries))

        agent = HealthAgent()
        result = agent.execute({"data_dir": str(data_dir)})

        assert result.status == "SUMMARIZED"
        assert result.artifact is not None
        assert output_dir.exists()
        assert tool_dir.exists()
        assert any(p.name.startswith("health_summary_") for p in output_dir.iterdir())


if __name__ == "__main__":
    test_health_summary_generates_report()
    print("✓ Health agent tests passed")
