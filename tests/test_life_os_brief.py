#!/usr/bin/env python3
"""Tests for Life OS brief generation."""

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import scripts.life_os_brief as life_mod  # noqa: E402


def test_life_os_brief_outputs_summary():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        outputs = root / "outputs"
        tool = root / "tool"
        working = root / "working"
        outputs.mkdir(parents=True, exist_ok=True)
        tool.mkdir(parents=True, exist_ok=True)
        working.mkdir(parents=True, exist_ok=True)

        profile_path = working / "life_profile.json"
        profile_path.write_text(
            json.dumps(
                {
                    "owner": "Payton",
                    "north_star": "Build a durable life+business operating system.",
                    "daily_non_negotiables": ["Sleep", "Language sprint"],
                }
            ),
            encoding="utf-8",
        )
        tasks_path = working / "life_tasks.json"
        tasks_path.write_text(
            json.dumps(
                [
                    {
                        "task_id": "LIFE-001",
                        "title": "Health block",
                        "domain": "health",
                        "priority": "high",
                        "status": "open",
                        "due": "today",
                        "next_action": "Walk and hydration.",
                    },
                    {
                        "task_id": "LIFE-002",
                        "title": "Closed item",
                        "domain": "health",
                        "priority": "normal",
                        "status": "done",
                    },
                ]
            ),
            encoding="utf-8",
        )

        original = {
            "OUTPUT_DIR": life_mod.OUTPUT_DIR,
            "TOOL_DIR": life_mod.TOOL_DIR,
            "PROFILE_PATH": life_mod.PROFILE_PATH,
            "TASKS_PATH": life_mod.TASKS_PATH,
        }
        try:
            life_mod.OUTPUT_DIR = outputs
            life_mod.TOOL_DIR = tool
            life_mod.PROFILE_PATH = profile_path
            life_mod.TASKS_PATH = tasks_path
            rc = life_mod.main()
        finally:
            life_mod.OUTPUT_DIR = original["OUTPUT_DIR"]
            life_mod.TOOL_DIR = original["TOOL_DIR"]
            life_mod.PROFILE_PATH = original["PROFILE_PATH"]
            life_mod.TASKS_PATH = original["TASKS_PATH"]

        assert rc == 0
        latest = outputs / "life_os_brief_latest.md"
        assert latest.exists()
        content = latest.read_text(encoding="utf-8")
        assert "Life OS Brief" in content
        assert "Health block" in content
        assert "Closed item" not in content

        tool_files = sorted(tool.glob("life_os_brief_*.json"))
        assert tool_files
        payload = json.loads(tool_files[-1].read_text(encoding="utf-8"))
        assert payload.get("open_task_count") == 1


if __name__ == "__main__":
    test_life_os_brief_outputs_summary()
    print("✓ Life OS brief tests passed")
