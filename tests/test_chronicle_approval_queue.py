#!/usr/bin/env python3
"""Tests for chronicle approval queue."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import scripts.chronicle_approval_queue as queue_mod  # noqa: E402


def test_chronicle_approval_queue_adds_backlog_and_canon_items() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        working = root / "working"
        output = root / "outputs"
        tool = root / "tool"
        approvals_path = root / "approvals.json"
        working.mkdir(parents=True, exist_ok=True)
        output.mkdir(parents=True, exist_ok=True)
        tool.mkdir(parents=True, exist_ok=True)

        refinement_payload = {
            "backlog_updates": [
                {
                    "id": "CRB-dup-001",
                    "title": "Queue hygiene and backlog compression",
                    "category": "issue",
                    "priority": "HIGH",
                    "score": 90,
                    "next_action": "Close queue backlog.",
                    "why_now": "Queue backlog is still open.",
                    "evidence": ["2026-03-05T00:40:00Z | queue backlog"],
                },
                {
                    "id": "CRB-new-002",
                    "title": "Failure-path hardening and regression coverage",
                    "category": "issue",
                    "priority": "HIGH",
                    "score": 88,
                    "next_action": "Patch retry timeout path and add test.",
                    "why_now": "Relay timeout recurred in chronicle.",
                    "evidence": ["2026-03-05T00:42:00Z | timeout error"],
                },
                {
                    "id": "CRB-low-003",
                    "title": "Low-score direction update",
                    "category": "direction",
                    "priority": "LOW",
                    "score": 45,
                    "next_action": "Review later.",
                    "why_now": "Not urgent.",
                    "evidence": [],
                },
            ],
            "canon_checks": [
                {
                    "check_id": "CANON-abc123",
                    "title": "Canon alignment review before backlog execution",
                    "trigger": "direction_shift_detected",
                    "question": "Does this preserve human-final authority?",
                    "trigger_note": "Chronicle reports 2 direction-shift events.",
                }
            ],
        }
        (tool / "chronicle_refinement_20260305-064459.json").write_text(
            json.dumps(refinement_payload),
            encoding="utf-8",
        )

        approvals_path.write_text(
            json.dumps(
                [
                    {
                        "id": "CHR-CRB-dup-001",
                        "proposal_id": "CHR-CRB-dup-001",
                        "approval_id": "CHR-CRB-dup-001",
                        "source_opportunity_id": "CRB-dup-001",
                        "status": "PENDING_HUMAN_REVIEW",
                    }
                ]
            ),
            encoding="utf-8",
        )

        original = {
            "WORKING_DIR": queue_mod.WORKING_DIR,
            "OUTPUT_DIR": queue_mod.OUTPUT_DIR,
            "TOOL_DIR": queue_mod.TOOL_DIR,
            "APPROVALS_PATH": queue_mod.APPROVALS_PATH,
            "POLICY_PATH": queue_mod.POLICY_PATH,
        }
        try:
            queue_mod.WORKING_DIR = working
            queue_mod.OUTPUT_DIR = output
            queue_mod.TOOL_DIR = tool
            queue_mod.APPROVALS_PATH = approvals_path
            queue_mod.POLICY_PATH = working / "chronicle_queue_policy.json"
            rc = queue_mod.main([])
        finally:
            queue_mod.WORKING_DIR = original["WORKING_DIR"]
            queue_mod.OUTPUT_DIR = original["OUTPUT_DIR"]
            queue_mod.TOOL_DIR = original["TOOL_DIR"]
            queue_mod.APPROVALS_PATH = original["APPROVALS_PATH"]
            queue_mod.POLICY_PATH = original["POLICY_PATH"]

        assert rc == 0
        assert (output / "chronicle_approval_queue_latest.md").exists()
        rows = json.loads(approvals_path.read_text(encoding="utf-8"))
        assert isinstance(rows, list)
        assert len(rows) == 3
        assert any(str(row.get("source_opportunity_id")) == "CRB-new-002" for row in rows)
        assert any(str(row.get("implementation_scope")) == "canon_amendment" for row in rows)

        payload_files = sorted(tool.glob("chronicle_approval_queue_*.json"))
        assert payload_files
        payload = json.loads(payload_files[-1].read_text(encoding="utf-8"))
        assert int(payload.get("queued_count", 0)) == 2
        assert int(payload.get("skipped_existing", 0)) == 1
        assert int(payload.get("skipped_filtered", 0)) == 1
        assert int(payload.get("pending_total", 0)) == 3


def test_chronicle_approval_queue_no_canon_checks_flag() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        working = root / "working"
        output = root / "outputs"
        tool = root / "tool"
        approvals_path = root / "approvals.json"
        working.mkdir(parents=True, exist_ok=True)
        output.mkdir(parents=True, exist_ok=True)
        tool.mkdir(parents=True, exist_ok=True)

        refinement_payload = {
            "backlog_updates": [
                {
                    "id": "CRB-new-100",
                    "title": "Stability sprint from chronicle friction totals",
                    "category": "meta",
                    "priority": "HIGH",
                    "score": 92,
                    "next_action": "Run bounded stability sprint.",
                    "why_now": "Issue totals remain elevated.",
                    "evidence": [],
                }
            ],
            "canon_checks": [
                {
                    "check_id": "CANON-def456",
                    "title": "Canon alignment review before backlog execution",
                    "trigger": "routine_review",
                    "question": "Review canon alignment.",
                    "trigger_note": "Routine check.",
                }
            ],
        }
        (tool / "chronicle_refinement_20260305-070000.json").write_text(
            json.dumps(refinement_payload),
            encoding="utf-8",
        )
        approvals_path.write_text("[]", encoding="utf-8")

        original = {
            "WORKING_DIR": queue_mod.WORKING_DIR,
            "OUTPUT_DIR": queue_mod.OUTPUT_DIR,
            "TOOL_DIR": queue_mod.TOOL_DIR,
            "APPROVALS_PATH": queue_mod.APPROVALS_PATH,
            "POLICY_PATH": queue_mod.POLICY_PATH,
        }
        try:
            queue_mod.WORKING_DIR = working
            queue_mod.OUTPUT_DIR = output
            queue_mod.TOOL_DIR = tool
            queue_mod.APPROVALS_PATH = approvals_path
            queue_mod.POLICY_PATH = working / "chronicle_queue_policy.json"
            rc = queue_mod.main(["--no-canon-checks"])
        finally:
            queue_mod.WORKING_DIR = original["WORKING_DIR"]
            queue_mod.OUTPUT_DIR = original["OUTPUT_DIR"]
            queue_mod.TOOL_DIR = original["TOOL_DIR"]
            queue_mod.APPROVALS_PATH = original["APPROVALS_PATH"]
            queue_mod.POLICY_PATH = original["POLICY_PATH"]

        assert rc == 0
        rows = json.loads(approvals_path.read_text(encoding="utf-8"))
        assert len(rows) == 1
        assert str(rows[0].get("implementation_scope")) == "system_improvement"


if __name__ == "__main__":
    test_chronicle_approval_queue_adds_backlog_and_canon_items()
    test_chronicle_approval_queue_no_canon_checks_flag()
    print("✓ Chronicle approval queue tests passed")
