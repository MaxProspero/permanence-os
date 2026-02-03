#!/usr/bin/env python3
"""
Tests for episodic memory promotion draft generation.
"""

import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SCRIPT = os.path.join(BASE_DIR, "scripts", "promote_memory.py")


def test_promote_memory_creates_output():
    with tempfile.TemporaryDirectory() as tmp:
        mem_dir = os.path.join(tmp, "memory")
        epi_dir = os.path.join(mem_dir, "episodic")
        os.makedirs(epi_dir, exist_ok=True)

        episode = {
            "task_id": "T-TEST",
            "task_goal": "Test episodic promotion",
            "stage": "DONE",
            "status": "DONE",
            "risk_tier": "LOW",
            "step_count": 1,
            "max_steps": 12,
            "tool_calls_used": 0,
            "max_tool_calls": 5,
            "artifacts": {"output": "outputs/test.md"},
            "sources": [],
            "escalation": None,
            "logs": [],
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        episode_path = os.path.join(epi_dir, "T-TEST.json")
        with open(episode_path, "w") as f:
            json.dump(episode, f)

        output_dir = os.path.join(tmp, "outputs")
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, "proposal.md")

        env = os.environ.copy()
        env["PERMANENCE_MEMORY_DIR"] = mem_dir
        env["PERMANENCE_OUTPUT_DIR"] = output_dir
        env["PERMANENCE_LOG_DIR"] = os.path.join(tmp, "logs")

        cmd = [sys.executable, SCRIPT, "--count", "1", "--output", output_path]
        subprocess.check_call(cmd, env=env)

        assert os.path.exists(output_path)
        with open(output_path, "r") as f:
            content = f.read()

        assert "Candidate Episodes" in content
        assert "T-TEST" in content


if __name__ == "__main__":
    test_promote_memory_creates_output()
    print("✓ Memory promotion tests passed")
