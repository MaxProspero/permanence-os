#!/usr/bin/env python3
"""
Tests for promotion queue script.
"""

import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SCRIPT = os.path.join(BASE_DIR, "scripts", "promotion_queue.py")


def test_promotion_queue_add_list_clear():
    with tempfile.TemporaryDirectory() as tmp:
        mem_dir = os.path.join(tmp, "memory")
        epi_dir = os.path.join(mem_dir, "episodic")
        work_dir = os.path.join(mem_dir, "working")
        os.makedirs(epi_dir, exist_ok=True)
        os.makedirs(work_dir, exist_ok=True)

        episode = {
            "task_id": "T-QUEUE",
            "task_goal": "Test queue",
            "stage": "DONE",
            "status": "DONE",
            "risk_tier": "LOW",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        with open(os.path.join(epi_dir, "T-QUEUE.json"), "w") as f:
            json.dump(episode, f)

        env = os.environ.copy()
        env["PERMANENCE_MEMORY_DIR"] = mem_dir
        env["PERMANENCE_LOG_DIR"] = os.path.join(tmp, "logs")

        subprocess.check_call(
            [sys.executable, SCRIPT, "add", "--task-id", "T-QUEUE", "--reason", "test"],
            env=env,
        )

        output = subprocess.check_output([sys.executable, SCRIPT, "list"], env=env, text=True)
        assert "T-QUEUE" in output

        subprocess.check_call([sys.executable, SCRIPT, "clear"], env=env)
        output = subprocess.check_output([sys.executable, SCRIPT, "list"], env=env, text=True)
        assert "empty" in output.lower()


if __name__ == "__main__":
    test_promotion_queue_add_list_clear()
    print("✓ Promotion queue tests passed")
