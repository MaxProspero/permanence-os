#!/usr/bin/env python3
"""Tests for HR Agent (The Shepherd)."""

import json
import os
import sys
import tempfile
from datetime import datetime, timezone

os.environ.setdefault("PERMANENCE_LOG_DIR", "/tmp/permanence-os-test-logs")

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from agents.departments.hr_agent import HRAgent


def _write_episode(path: str, task_id: str, logs: list[str], status: str = "DONE", stage: str = "DONE") -> None:
    episode = {
        "task_id": task_id,
        "task_goal": "Test goal",
        "stage": stage,
        "status": status,
        "risk_tier": "LOW",
        "step_count": 3,
        "max_steps": 12,
        "tool_calls_used": 0,
        "max_tool_calls": 5,
        "artifacts": {},
        "sources": [
            {
                "source": "s1",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "confidence": 0.9,
            }
        ],
        "escalation": None,
        "logs": logs,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    with open(path, "w") as f:
        json.dump(episode, f)


def test_hr_agent_collect_metrics_and_report():
    with tempfile.TemporaryDirectory() as tmp:
        memory_dir = os.path.join(tmp, "memory")
        episodic_dir = os.path.join(memory_dir, "episodic")
        os.makedirs(episodic_dir, exist_ok=True)

        logs = [
            "[2026-02-03T00:00:00+00:00] [INFO] Validating task against Canon...",
            "[2026-02-03T00:00:00+00:00] [INFO] Routing to agent: planner",
            "[2026-02-03T00:00:00+00:00] [INFO] Routing to agent: researcher",
            "[2026-02-03T00:00:00+00:00] [INFO] Routing to agent: executor",
            "[2026-02-03T00:00:00+00:00] [INFO] Routing to agent: reviewer",
            "[2026-02-03T00:00:00+00:00] [INFO] Conciliator decision: ACCEPT",
        ]
        _write_episode(os.path.join(episodic_dir, "T-1.json"), "T-1", logs)

        agent = HRAgent(memory_dir=memory_dir, logs_dir=os.environ["PERMANENCE_LOG_DIR"])
        metrics = agent.collect_metrics()

        assert metrics["planner"].tasks_processed == 1
        assert metrics["researcher"].tasks_processed == 1
        assert metrics["executor"].tasks_processed == 1
        assert metrics["reviewer"].total_reviews == 1
        assert metrics["polemarch"].canon_consultations == 1

        report = agent.generate_weekly_report()
        formatted = agent.format_report(report)
        assert "WEEKLY SYSTEM HEALTH REPORT" in formatted
        assert report.overall_score >= 0


if __name__ == "__main__":
    test_hr_agent_collect_metrics_and_report()
    print("✓ HR agent tests passed")
