#!/usr/bin/env python3
"""Tests for approval execution board."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import scripts.approval_execution_board as board_mod  # noqa: E402


def test_approval_execution_board_builds_tasks_and_marks_queue() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        output = root / "outputs"
        tool = root / "tool"
        working = root / "working"
        approvals = root / "approvals.json"
        output.mkdir(parents=True, exist_ok=True)
        tool.mkdir(parents=True, exist_ok=True)
        working.mkdir(parents=True, exist_ok=True)

        approvals.write_text(
            json.dumps(
                [
                    {
                        "id": "OPP-PORTFOLIO-111",
                        "title": "Scale clipping studio",
                        "priority": "HIGH",
                        "risk_tier": "MEDIUM",
                        "implementation_scope": "business_execution",
                        "draft_codex_task": "Run 5 outreach tests and track conversion.",
                        "status": "APPROVED",
                        "source": "phase3_opportunity_queue",
                    },
                    {
                        "id": "OPP-GITHUB-222",
                        "title": "Fix stale PR backlog",
                        "priority": "MEDIUM",
                        "implementation_scope": "system_improvement",
                        "proposed_change": "Triage stale PRs and assign owners.",
                        "status": "APPROVED",
                        "source": "phase3_opportunity_queue",
                    },
                    {
                        "id": "OPP-SOCIAL-333",
                        "title": "Pending item",
                        "priority": "LOW",
                        "status": "PENDING_HUMAN_REVIEW",
                    },
                ]
            ),
            encoding="utf-8",
        )

        original = {
            "OUTPUT_DIR": board_mod.OUTPUT_DIR,
            "TOOL_DIR": board_mod.TOOL_DIR,
            "WORKING_DIR": board_mod.WORKING_DIR,
            "APPROVALS_PATH": board_mod.APPROVALS_PATH,
            "TASKS_PATH": board_mod.TASKS_PATH,
        }
        try:
            board_mod.OUTPUT_DIR = output
            board_mod.TOOL_DIR = tool
            board_mod.WORKING_DIR = working
            board_mod.APPROVALS_PATH = approvals
            board_mod.TASKS_PATH = working / "approved_execution_tasks.json"
            rc = board_mod.main([])
        finally:
            board_mod.OUTPUT_DIR = original["OUTPUT_DIR"]
            board_mod.TOOL_DIR = original["TOOL_DIR"]
            board_mod.WORKING_DIR = original["WORKING_DIR"]
            board_mod.APPROVALS_PATH = original["APPROVALS_PATH"]
            board_mod.TASKS_PATH = original["TASKS_PATH"]

        assert rc == 0
        assert (output / "approval_execution_board_latest.md").exists()
        assert (working / "approved_execution_tasks.json").exists()
        payload_files = sorted(tool.glob("approval_execution_board_*.json"))
        assert payload_files
        payload = json.loads(payload_files[-1].read_text(encoding="utf-8"))
        assert int(payload.get("approved_count", 0)) == 2
        assert int(payload.get("task_count", 0)) == 2

        approvals_rows = json.loads(approvals.read_text(encoding="utf-8"))
        approved_rows = [row for row in approvals_rows if str(row.get("status")) == "APPROVED"]
        assert all(str(row.get("execution_status")) == "QUEUED_FOR_EXECUTION" for row in approved_rows)


if __name__ == "__main__":
    test_approval_execution_board_builds_tasks_and_marks_queue()
    print("✓ Approval execution board tests passed")
