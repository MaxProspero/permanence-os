#!/usr/bin/env python3
"""Tests for promotion review script."""

import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SCRIPT = os.path.join(BASE_DIR, "scripts", "promotion_review.py")


def test_promotion_review_creates_output():
    with tempfile.TemporaryDirectory() as tmp:
        memory_dir = os.path.join(tmp, "memory")
        episodic_dir = os.path.join(memory_dir, "episodic")
        working_dir = os.path.join(memory_dir, "working")
        os.makedirs(episodic_dir, exist_ok=True)
        os.makedirs(working_dir, exist_ok=True)

        episode = {
            "task_id": "T-REVIEW",
            "task_goal": "Test promotion review",
            "stage": "DONE",
            "status": "DONE",
            "risk_tier": "LOW",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        with open(os.path.join(episodic_dir, "T-REVIEW.json"), "w") as f:
            json.dump(episode, f)

        queue_path = os.path.join(working_dir, "promotion_queue.json")
        with open(queue_path, "w") as f:
            json.dump([{"task_id": "T-REVIEW", "reason": "test"}], f)

        output_path = os.path.join(tmp, "promotion_review.md")
        env = os.environ.copy()
        env["PERMANENCE_MEMORY_DIR"] = memory_dir
        env["PERMANENCE_PROMOTION_QUEUE"] = queue_path

        subprocess.check_call([sys.executable, SCRIPT, "--output", output_path], env=env)
        assert os.path.exists(output_path)


if __name__ == "__main__":
    test_promotion_review_creates_output()
    print("✓ Promotion review tests passed")
