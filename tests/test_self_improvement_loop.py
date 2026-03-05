#!/usr/bin/env python3
"""Tests for self-improvement loop."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import scripts.self_improvement_loop as improve_mod  # noqa: E402


def test_self_improvement_status_writes_template_and_report() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        outputs = root / "outputs"
        tool = root / "tool"
        working = root / "working"
        outputs.mkdir(parents=True, exist_ok=True)
        tool.mkdir(parents=True, exist_ok=True)
        working.mkdir(parents=True, exist_ok=True)

        original = {
            "OUTPUT_DIR": improve_mod.OUTPUT_DIR,
            "TOOL_DIR": improve_mod.TOOL_DIR,
            "WORKING_DIR": improve_mod.WORKING_DIR,
            "PROPOSALS_PATH": improve_mod.PROPOSALS_PATH,
            "POLICY_PATH": improve_mod.POLICY_PATH,
            "APPROVALS_PATH": improve_mod.APPROVALS_PATH,
            "PERSONAL_MEMORY_PATH": improve_mod.PERSONAL_MEMORY_PATH,
            "SIMULATION_LATEST_PATH": improve_mod.SIMULATION_LATEST_PATH,
        }
        try:
            improve_mod.OUTPUT_DIR = outputs
            improve_mod.TOOL_DIR = tool
            improve_mod.WORKING_DIR = working
            improve_mod.PROPOSALS_PATH = working / "self_improvement_proposals.json"
            improve_mod.POLICY_PATH = working / "self_improvement_policy.json"
            improve_mod.APPROVALS_PATH = working / "approvals.json"
            improve_mod.PERSONAL_MEMORY_PATH = working / "personal_memory.json"
            improve_mod.SIMULATION_LATEST_PATH = outputs / "ophtxn_simulation_latest.md"

            rc = improve_mod.main(["--action", "status"])
        finally:
            improve_mod.OUTPUT_DIR = original["OUTPUT_DIR"]
            improve_mod.TOOL_DIR = original["TOOL_DIR"]
            improve_mod.WORKING_DIR = original["WORKING_DIR"]
            improve_mod.PROPOSALS_PATH = original["PROPOSALS_PATH"]
            improve_mod.POLICY_PATH = original["POLICY_PATH"]
            improve_mod.APPROVALS_PATH = original["APPROVALS_PATH"]
            improve_mod.PERSONAL_MEMORY_PATH = original["PERSONAL_MEMORY_PATH"]
            improve_mod.SIMULATION_LATEST_PATH = original["SIMULATION_LATEST_PATH"]

        assert rc == 0
        assert (working / "self_improvement_policy.json").exists()
        latest = outputs / "self_improvement_latest.md"
        assert latest.exists()
        assert "Self Improvement" in latest.read_text(encoding="utf-8")


def test_self_improvement_pitch_generates_pending_items() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        outputs = root / "outputs"
        tool = root / "tool"
        working = root / "working"
        outputs.mkdir(parents=True, exist_ok=True)
        tool.mkdir(parents=True, exist_ok=True)
        working.mkdir(parents=True, exist_ok=True)

        (outputs / "ophtxn_simulation_latest.md").write_text(
            "\n".join(
                [
                    "# Ophtxn Simulation",
                    "## Memory Retrieval",
                    "- Top1 hit rate: 0.61",
                    "## Profile Consistency",
                    "- Open profile conflicts: 2",
                ]
            )
            + "\n",
            encoding="utf-8",
        )

        (tool / "telegram_control_20260101-000000.json").write_text(
            json.dumps({"chat_replies_failed": 3, "chat_replies_fallback_sent": 1}, indent=2) + "\n",
            encoding="utf-8",
        )
        (tool / "governed_learning_20260101-000000.json").write_text(
            json.dumps({"block_reasons": ["policy disabled"]}, indent=2) + "\n",
            encoding="utf-8",
        )
        (working / "personal_memory.json").write_text(
            json.dumps(
                {
                    "profiles": {
                        "user:1": {
                            "profile_conflicts": [
                                {"id": "PC-1", "status": "open"},
                                {"id": "PC-2", "status": "resolved"},
                            ]
                        }
                    }
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        original = {
            "OUTPUT_DIR": improve_mod.OUTPUT_DIR,
            "TOOL_DIR": improve_mod.TOOL_DIR,
            "WORKING_DIR": improve_mod.WORKING_DIR,
            "PROPOSALS_PATH": improve_mod.PROPOSALS_PATH,
            "POLICY_PATH": improve_mod.POLICY_PATH,
            "APPROVALS_PATH": improve_mod.APPROVALS_PATH,
            "PERSONAL_MEMORY_PATH": improve_mod.PERSONAL_MEMORY_PATH,
            "SIMULATION_LATEST_PATH": improve_mod.SIMULATION_LATEST_PATH,
        }
        try:
            improve_mod.OUTPUT_DIR = outputs
            improve_mod.TOOL_DIR = tool
            improve_mod.WORKING_DIR = working
            improve_mod.PROPOSALS_PATH = working / "self_improvement_proposals.json"
            improve_mod.POLICY_PATH = working / "self_improvement_policy.json"
            improve_mod.APPROVALS_PATH = working / "approvals.json"
            improve_mod.PERSONAL_MEMORY_PATH = working / "personal_memory.json"
            improve_mod.SIMULATION_LATEST_PATH = outputs / "ophtxn_simulation_latest.md"
            rc = improve_mod.main(["--action", "pitch"])
        finally:
            improve_mod.OUTPUT_DIR = original["OUTPUT_DIR"]
            improve_mod.TOOL_DIR = original["TOOL_DIR"]
            improve_mod.WORKING_DIR = original["WORKING_DIR"]
            improve_mod.PROPOSALS_PATH = original["PROPOSALS_PATH"]
            improve_mod.POLICY_PATH = original["POLICY_PATH"]
            improve_mod.APPROVALS_PATH = original["APPROVALS_PATH"]
            improve_mod.PERSONAL_MEMORY_PATH = original["PERSONAL_MEMORY_PATH"]
            improve_mod.SIMULATION_LATEST_PATH = original["SIMULATION_LATEST_PATH"]

        assert rc == 0
        proposals = json.loads((working / "self_improvement_proposals.json").read_text(encoding="utf-8"))
        pending = [row for row in proposals if str(row.get("status") or "") == "PENDING_HUMAN_REVIEW"]
        assert len(pending) >= 2


def test_self_improvement_decide_approve_queues_approval() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        outputs = root / "outputs"
        tool = root / "tool"
        working = root / "working"
        outputs.mkdir(parents=True, exist_ok=True)
        tool.mkdir(parents=True, exist_ok=True)
        working.mkdir(parents=True, exist_ok=True)

        proposal = {
            "proposal_id": "IMP-ABCDE12345",
            "fingerprint": "abcde12345abcde1",
            "title": "Improve memory retrieval precision",
            "priority": "HIGH",
            "finding_summary": "Top1 below target",
            "current_state": "Top1 below target",
            "proposed_change": "Add reranker",
            "expected_benefit": "Better recall",
            "risk_if_ignored": "Lower trust",
            "implementation_scope": "system_improvement",
            "source_findings": [],
            "status": "PENDING_HUMAN_REVIEW",
        }
        (working / "self_improvement_proposals.json").write_text(
            json.dumps([proposal], indent=2) + "\n", encoding="utf-8"
        )

        original = {
            "OUTPUT_DIR": improve_mod.OUTPUT_DIR,
            "TOOL_DIR": improve_mod.TOOL_DIR,
            "WORKING_DIR": improve_mod.WORKING_DIR,
            "PROPOSALS_PATH": improve_mod.PROPOSALS_PATH,
            "POLICY_PATH": improve_mod.POLICY_PATH,
            "APPROVALS_PATH": improve_mod.APPROVALS_PATH,
            "PERSONAL_MEMORY_PATH": improve_mod.PERSONAL_MEMORY_PATH,
            "SIMULATION_LATEST_PATH": improve_mod.SIMULATION_LATEST_PATH,
        }
        try:
            improve_mod.OUTPUT_DIR = outputs
            improve_mod.TOOL_DIR = tool
            improve_mod.WORKING_DIR = working
            improve_mod.PROPOSALS_PATH = working / "self_improvement_proposals.json"
            improve_mod.POLICY_PATH = working / "self_improvement_policy.json"
            improve_mod.APPROVALS_PATH = working / "approvals.json"
            improve_mod.PERSONAL_MEMORY_PATH = working / "personal_memory.json"
            improve_mod.SIMULATION_LATEST_PATH = outputs / "ophtxn_simulation_latest.md"
            rc = improve_mod.main(
                [
                    "--action",
                    "decide",
                    "--decision",
                    "approve",
                    "--decided-by",
                    "payton",
                ]
            )
        finally:
            improve_mod.OUTPUT_DIR = original["OUTPUT_DIR"]
            improve_mod.TOOL_DIR = original["TOOL_DIR"]
            improve_mod.WORKING_DIR = original["WORKING_DIR"]
            improve_mod.PROPOSALS_PATH = original["PROPOSALS_PATH"]
            improve_mod.POLICY_PATH = original["POLICY_PATH"]
            improve_mod.APPROVALS_PATH = original["APPROVALS_PATH"]
            improve_mod.PERSONAL_MEMORY_PATH = original["PERSONAL_MEMORY_PATH"]
            improve_mod.SIMULATION_LATEST_PATH = original["SIMULATION_LATEST_PATH"]

        assert rc == 0
        proposals = json.loads((working / "self_improvement_proposals.json").read_text(encoding="utf-8"))
        assert proposals[0]["status"] == "APPROVED"
        approvals = json.loads((working / "approvals.json").read_text(encoding="utf-8"))
        assert isinstance(approvals, list)
        assert any(str(row.get("id") or "") == "IMP-ABCDE12345" for row in approvals if isinstance(row, dict))


def test_self_improvement_decide_requires_decision_code_when_enabled() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        outputs = root / "outputs"
        tool = root / "tool"
        working = root / "working"
        outputs.mkdir(parents=True, exist_ok=True)
        tool.mkdir(parents=True, exist_ok=True)
        working.mkdir(parents=True, exist_ok=True)

        proposal = {
            "proposal_id": "IMP-ABCDE12345",
            "fingerprint": "abcde12345abcde1",
            "title": "Improve memory retrieval precision",
            "priority": "HIGH",
            "finding_summary": "Top1 below target",
            "current_state": "Top1 below target",
            "proposed_change": "Add reranker",
            "expected_benefit": "Better recall",
            "risk_if_ignored": "Lower trust",
            "implementation_scope": "system_improvement",
            "source_findings": [],
            "status": "PENDING_HUMAN_REVIEW",
        }
        (working / "self_improvement_proposals.json").write_text(
            json.dumps([proposal], indent=2) + "\n", encoding="utf-8"
        )
        policy = improve_mod._default_policy()
        policy["require_decision_code"] = True
        policy["decision_code_sha256"] = improve_mod._hash_decision_code("246810")
        (working / "self_improvement_policy.json").write_text(json.dumps(policy, indent=2) + "\n", encoding="utf-8")

        original = {
            "OUTPUT_DIR": improve_mod.OUTPUT_DIR,
            "TOOL_DIR": improve_mod.TOOL_DIR,
            "WORKING_DIR": improve_mod.WORKING_DIR,
            "PROPOSALS_PATH": improve_mod.PROPOSALS_PATH,
            "POLICY_PATH": improve_mod.POLICY_PATH,
            "APPROVALS_PATH": improve_mod.APPROVALS_PATH,
            "PERSONAL_MEMORY_PATH": improve_mod.PERSONAL_MEMORY_PATH,
            "SIMULATION_LATEST_PATH": improve_mod.SIMULATION_LATEST_PATH,
        }
        try:
            improve_mod.OUTPUT_DIR = outputs
            improve_mod.TOOL_DIR = tool
            improve_mod.WORKING_DIR = working
            improve_mod.PROPOSALS_PATH = working / "self_improvement_proposals.json"
            improve_mod.POLICY_PATH = working / "self_improvement_policy.json"
            improve_mod.APPROVALS_PATH = working / "approvals.json"
            improve_mod.PERSONAL_MEMORY_PATH = working / "personal_memory.json"
            improve_mod.SIMULATION_LATEST_PATH = outputs / "ophtxn_simulation_latest.md"
            rc_missing = improve_mod.main(
                [
                    "--action",
                    "decide",
                    "--decision",
                    "approve",
                    "--decided-by",
                    "payton",
                ]
            )
            rc_valid = improve_mod.main(
                [
                    "--action",
                    "decide",
                    "--decision",
                    "approve",
                    "--decided-by",
                    "payton",
                    "--decision-code",
                    "246810",
                ]
            )
        finally:
            improve_mod.OUTPUT_DIR = original["OUTPUT_DIR"]
            improve_mod.TOOL_DIR = original["TOOL_DIR"]
            improve_mod.WORKING_DIR = original["WORKING_DIR"]
            improve_mod.PROPOSALS_PATH = original["PROPOSALS_PATH"]
            improve_mod.POLICY_PATH = original["POLICY_PATH"]
            improve_mod.APPROVALS_PATH = original["APPROVALS_PATH"]
            improve_mod.PERSONAL_MEMORY_PATH = original["PERSONAL_MEMORY_PATH"]
            improve_mod.SIMULATION_LATEST_PATH = original["SIMULATION_LATEST_PATH"]

        assert rc_missing == 1
        assert rc_valid == 0
        proposals = json.loads((working / "self_improvement_proposals.json").read_text(encoding="utf-8"))
        assert proposals[0]["status"] == "APPROVED"


if __name__ == "__main__":
    test_self_improvement_status_writes_template_and_report()
    test_self_improvement_pitch_generates_pending_items()
    test_self_improvement_decide_approve_queues_approval()
    test_self_improvement_decide_requires_decision_code_when_enabled()
    print("✓ Self improvement loop tests passed")
