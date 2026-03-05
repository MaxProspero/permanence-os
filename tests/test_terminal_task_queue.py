#!/usr/bin/env python3
"""Tests for terminal task queue manager."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import scripts.terminal_task_queue as queue_mod  # noqa: E402


def test_terminal_task_queue_add_list_complete() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        outputs = root / "outputs"
        tool = root / "tool"
        working = root / "working"
        outputs.mkdir(parents=True, exist_ok=True)
        tool.mkdir(parents=True, exist_ok=True)
        working.mkdir(parents=True, exist_ok=True)
        queue_path = working / "telegram_terminal_tasks.jsonl"

        original = {
            "OUTPUT_DIR": queue_mod.OUTPUT_DIR,
            "TOOL_DIR": queue_mod.TOOL_DIR,
            "WORKING_DIR": queue_mod.WORKING_DIR,
            "QUEUE_PATH": queue_mod.QUEUE_PATH,
        }
        try:
            queue_mod.OUTPUT_DIR = outputs
            queue_mod.TOOL_DIR = tool
            queue_mod.WORKING_DIR = working
            queue_mod.QUEUE_PATH = queue_path

            rc_add = queue_mod.main(
                [
                    "--action",
                    "add",
                    "--text",
                    "harden telegram terminal command flow",
                    "--source",
                    "telegram",
                    "--sender",
                    "payton",
                    "--sender-user-id",
                    "123",
                    "--chat-id",
                    "-1001",
                ]
            )
            assert rc_add == 0
            assert queue_path.exists()

            rows = queue_mod._load_rows(queue_path)
            assert rows
            task_id = str(rows[-1].get("task_id") or "").strip()
            assert task_id.startswith("TERM-")

            rc_list = queue_mod.main(["--action", "list"])
            assert rc_list == 0

            rc_complete = queue_mod.main(["--action", "complete", "--task-id", task_id])
            assert rc_complete == 0
        finally:
            queue_mod.OUTPUT_DIR = original["OUTPUT_DIR"]
            queue_mod.TOOL_DIR = original["TOOL_DIR"]
            queue_mod.WORKING_DIR = original["WORKING_DIR"]
            queue_mod.QUEUE_PATH = original["QUEUE_PATH"]

        rows = queue_mod._load_rows(queue_path)
        assert any(
            str(row.get("task_id") or "") == task_id and str(row.get("status") or "").upper() == "DONE"
            for row in rows
        )
        latest = outputs / "terminal_task_queue_latest.md"
        assert latest.exists()
        text = latest.read_text(encoding="utf-8")
        assert "Terminal Task Queue" in text
        payload_files = list(tool.glob("terminal_task_queue_*.json"))
        assert payload_files
        payload = json.loads(payload_files[-1].read_text(encoding="utf-8"))
        assert payload.get("task_count") == len(rows)


if __name__ == "__main__":
    test_terminal_task_queue_add_list_complete()
    print("✓ terminal task queue tests passed")
