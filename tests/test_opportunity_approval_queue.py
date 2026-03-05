#!/usr/bin/env python3
"""Tests for opportunity approval queue."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import scripts.opportunity_approval_queue as queue_mod  # noqa: E402


def test_opportunity_approval_queue_adds_new_items_and_dedupes() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        working = root / "working"
        output = root / "outputs"
        tool = root / "tool"
        approvals_path = root / "approvals.json"
        working.mkdir(parents=True, exist_ok=True)
        output.mkdir(parents=True, exist_ok=True)
        tool.mkdir(parents=True, exist_ok=True)

        ranked_payload = {
            "item_count": 2,
            "top_items": [
                {
                    "opportunity_id": "dup-opp-001",
                    "source_type": "social",
                    "source_name": "x",
                    "title": "Duplicate opportunity",
                    "summary": "Will be skipped as existing.",
                    "priority_score": 77.0,
                    "priority": "HIGH",
                    "risk_tier": "MEDIUM",
                    "implementation_scope": "opportunity_execution",
                    "proposed_action": "Review and test",
                    "expected_benefit": "Benefit",
                    "risk_if_ignored": "Risk",
                    "draft_codex_task": "Draft task",
                },
                {
                    "opportunity_id": "new-opp-002",
                    "source_type": "github",
                    "source_name": "acme/repo",
                    "title": "New opportunity",
                    "summary": "Should be queued.",
                    "priority_score": 66.0,
                    "priority": "MEDIUM",
                    "risk_tier": "LOW",
                    "implementation_scope": "system_improvement",
                    "proposed_action": "Execute scoped backlog cleanup",
                    "expected_benefit": "Better velocity",
                    "risk_if_ignored": "Debt increases",
                    "draft_codex_task": "Plan + execute in safe branch",
                },
            ],
        }
        (tool / "opportunity_ranker_20260301-120000.json").write_text(
            json.dumps(ranked_payload),
            encoding="utf-8",
        )

        approvals_path.write_text(
            json.dumps(
                [
                    {
                        "id": "OPP-SOCIAL-dup-opp-001",
                        "proposal_id": "OPP-SOCIAL-dup-opp-001",
                        "approval_id": "OPP-SOCIAL-dup-opp-001",
                        "source_opportunity_id": "dup-opp-001",
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
            queue_mod.POLICY_PATH = working / "opportunity_queue_policy.json"
            rc = queue_mod.main([])
        finally:
            queue_mod.WORKING_DIR = original["WORKING_DIR"]
            queue_mod.OUTPUT_DIR = original["OUTPUT_DIR"]
            queue_mod.TOOL_DIR = original["TOOL_DIR"]
            queue_mod.APPROVALS_PATH = original["APPROVALS_PATH"]
            queue_mod.POLICY_PATH = original["POLICY_PATH"]

        assert rc == 0
        assert (output / "opportunity_approval_queue_latest.md").exists()
        rows = json.loads(approvals_path.read_text(encoding="utf-8"))
        assert isinstance(rows, list)
        assert len(rows) == 2
        assert any(str(row.get("source_opportunity_id")) == "new-opp-002" for row in rows)
        assert all(str(row.get("status")) in {"PENDING_HUMAN_REVIEW"} for row in rows)

        payload_files = sorted(tool.glob("opportunity_approval_queue_*.json"))
        assert payload_files
        payload = json.loads(payload_files[-1].read_text(encoding="utf-8"))
        assert int(payload.get("queued_count", 0)) == 1
        assert int(payload.get("skipped_existing", 0)) == 1
        assert int(payload.get("pending_total", 0)) == 2


if __name__ == "__main__":
    test_opportunity_approval_queue_adds_new_items_and_dedupes()
    print("✓ Opportunity approval queue tests passed")
