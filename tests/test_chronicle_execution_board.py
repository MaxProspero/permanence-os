#!/usr/bin/env python3
"""Tests for chronicle execution board."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import scripts.chronicle_execution_board as board_mod  # noqa: E402


def test_chronicle_execution_board_builds_tasks_and_marks_only_chronicle_rows() -> None:
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
                        "id": "CHR-CRB-new-002",
                        "title": "Failure-path hardening and regression coverage",
                        "priority": "HIGH",
                        "risk_tier": "MEDIUM",
                        "implementation_scope": "system_improvement",
                        "draft_codex_task": "Patch timeout retry path and add regression test.",
                        "status": "APPROVED",
                        "source": "chronicle_refinement_queue",
                    },
                    {
                        "id": "CHR-CANON-abc123",
                        "title": "Canon alignment review before backlog execution",
                        "priority": "HIGH",
                        "implementation_scope": "canon_amendment",
                        "proposed_change": "Review canon alignment and decide approve/reject.",
                        "status": "APPROVED",
                        "source": "chronicle_refinement_queue",
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
                        "id": "CHR-CRB-pending-999",
                        "title": "Pending chronicle item",
                        "priority": "LOW",
                        "status": "PENDING_HUMAN_REVIEW",
                        "source": "chronicle_refinement_queue",
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
            board_mod.TASKS_PATH = working / "chronicle_execution_tasks.json"
            rc = board_mod.main([])
        finally:
            board_mod.OUTPUT_DIR = original["OUTPUT_DIR"]
            board_mod.TOOL_DIR = original["TOOL_DIR"]
            board_mod.WORKING_DIR = original["WORKING_DIR"]
            board_mod.APPROVALS_PATH = original["APPROVALS_PATH"]
            board_mod.TASKS_PATH = original["TASKS_PATH"]

        assert rc == 0
        assert (output / "chronicle_execution_board_latest.md").exists()
        assert (working / "chronicle_execution_tasks.json").exists()
        payload_files = sorted(tool.glob("chronicle_execution_board_*.json"))
        assert payload_files
        payload = json.loads(payload_files[-1].read_text(encoding="utf-8"))
        assert int(payload.get("approved_count", 0)) == 2
        assert int(payload.get("task_count", 0)) == 2
        tasks = payload.get("tasks") or []
        assert any(str(row.get("scope_package")) == "reliability_patch" for row in tasks)
        assert any(str(row.get("scope_package")) == "governance_patch" for row in tasks)

        approval_rows = json.loads(approvals.read_text(encoding="utf-8"))
        chronicle_approved = [
            row
            for row in approval_rows
            if str(row.get("status")) == "APPROVED" and str(row.get("source")) == "chronicle_refinement_queue"
        ]
        assert all(str(row.get("execution_status")) == "QUEUED_FOR_EXECUTION" for row in chronicle_approved)

        non_chronicle_approved = [
            row
            for row in approval_rows
            if str(row.get("status")) == "APPROVED" and str(row.get("source")) != "chronicle_refinement_queue"
        ]
        assert all(str(row.get("execution_status") or "") == "" for row in non_chronicle_approved)


def test_chronicle_execution_board_no_canon_and_no_mark_queue() -> None:
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
                        "id": "CHR-CRB-new-100",
                        "title": "Queue hygiene and backlog compression",
                        "priority": "HIGH",
                        "implementation_scope": "system_improvement",
                        "draft_codex_task": "Reduce queue to <=1 pending.",
                        "status": "APPROVED",
                        "source": "chronicle_refinement_queue",
                    },
                    {
                        "id": "CHR-CANON-def456",
                        "title": "Canon alignment review before backlog execution",
                        "priority": "HIGH",
                        "implementation_scope": "canon_amendment",
                        "proposed_change": "Review canon alignment.",
                        "status": "APPROVED",
                        "source": "chronicle_refinement_queue",
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
            board_mod.TASKS_PATH = working / "chronicle_execution_tasks.json"
            rc = board_mod.main(["--no-canon", "--no-mark-queued"])
        finally:
            board_mod.OUTPUT_DIR = original["OUTPUT_DIR"]
            board_mod.TOOL_DIR = original["TOOL_DIR"]
            board_mod.WORKING_DIR = original["WORKING_DIR"]
            board_mod.APPROVALS_PATH = original["APPROVALS_PATH"]
            board_mod.TASKS_PATH = original["TASKS_PATH"]

        assert rc == 0
        payload_files = sorted(tool.glob("chronicle_execution_board_*.json"))
        assert payload_files
        payload = json.loads(payload_files[-1].read_text(encoding="utf-8"))
        assert int(payload.get("approved_count", 0)) == 1
        assert int(payload.get("task_count", 0)) == 1

        approval_rows = json.loads(approvals.read_text(encoding="utf-8"))
        assert all(str(row.get("execution_status") or "") == "" for row in approval_rows)


if __name__ == "__main__":
    test_chronicle_execution_board_builds_tasks_and_marks_only_chronicle_rows()
    test_chronicle_execution_board_no_canon_and_no_mark_queue()
    print("✓ Chronicle execution board tests passed")
