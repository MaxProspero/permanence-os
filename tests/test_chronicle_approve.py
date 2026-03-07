#!/usr/bin/env python3
"""Tests for chronicle approval decision CLI script."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import scripts.chronicle_approve as approve_mod  # noqa: E402


def test_chronicle_approve_decide_oldest_pending_in_scope() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        output = root / "outputs"
        tool = root / "tool"
        approvals = root / "approvals.json"
        output.mkdir(parents=True, exist_ok=True)
        tool.mkdir(parents=True, exist_ok=True)

        approvals.write_text(
            json.dumps(
                [
                    {
                        "id": "CHR-CRB-oldest",
                        "title": "Oldest pending",
                        "status": "PENDING_HUMAN_REVIEW",
                        "queued_at": "2026-03-05T00:01:00Z",
                        "source": "chronicle_refinement_queue",
                    },
                    {
                        "id": "CHR-CRB-newer",
                        "title": "Newer pending",
                        "status": "PENDING_HUMAN_REVIEW",
                        "queued_at": "2026-03-05T00:05:00Z",
                        "source": "chronicle_refinement_queue",
                    },
                    {
                        "id": "OPP-123",
                        "title": "Non chronicle pending",
                        "status": "PENDING_HUMAN_REVIEW",
                        "queued_at": "2026-03-05T00:00:00Z",
                        "source": "phase3_opportunity_queue",
                    },
                ]
            ),
            encoding="utf-8",
        )

        original = {
            "OUTPUT_DIR": approve_mod.OUTPUT_DIR,
            "TOOL_DIR": approve_mod.TOOL_DIR,
            "APPROVALS_PATH": approve_mod.APPROVALS_PATH,
        }
        try:
            approve_mod.OUTPUT_DIR = output
            approve_mod.TOOL_DIR = tool
            approve_mod.APPROVALS_PATH = approvals
            rc = approve_mod.main(
                [
                    "--action",
                    "decide",
                    "--decision",
                    "approve",
                    "--decided-by",
                    "payton",
                    "--note",
                    "approved for scoped execution",
                ]
            )
        finally:
            approve_mod.OUTPUT_DIR = original["OUTPUT_DIR"]
            approve_mod.TOOL_DIR = original["TOOL_DIR"]
            approve_mod.APPROVALS_PATH = original["APPROVALS_PATH"]

        assert rc == 0
        rows = json.loads(approvals.read_text(encoding="utf-8"))
        oldest = next(row for row in rows if str(row.get("id")) == "CHR-CRB-oldest")
        newer = next(row for row in rows if str(row.get("id")) == "CHR-CRB-newer")
        non_chronicle = next(row for row in rows if str(row.get("id")) == "OPP-123")
        assert str(oldest.get("status")) == "APPROVED"
        assert str(oldest.get("decided_by")) == "payton"
        assert str(oldest.get("decision")) == "approve"
        assert str(newer.get("status")) == "PENDING_HUMAN_REVIEW"
        assert str(non_chronicle.get("status")) == "PENDING_HUMAN_REVIEW"

        latest = output / "chronicle_approve_latest.md"
        assert latest.exists()
        payload_files = sorted(tool.glob("chronicle_approve_*.json"))
        assert payload_files
        payload = json.loads(payload_files[-1].read_text(encoding="utf-8"))
        assert str(payload.get("decision_target_id")) == "CHR-CRB-oldest"
        assert int((payload.get("counts") or {}).get("APPROVED", 0)) == 1


def test_chronicle_approve_decide_missing_target_returns_error() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        output = root / "outputs"
        tool = root / "tool"
        approvals = root / "approvals.json"
        output.mkdir(parents=True, exist_ok=True)
        tool.mkdir(parents=True, exist_ok=True)
        approvals.write_text("[]", encoding="utf-8")

        original = {
            "OUTPUT_DIR": approve_mod.OUTPUT_DIR,
            "TOOL_DIR": approve_mod.TOOL_DIR,
            "APPROVALS_PATH": approve_mod.APPROVALS_PATH,
        }
        try:
            approve_mod.OUTPUT_DIR = output
            approve_mod.TOOL_DIR = tool
            approve_mod.APPROVALS_PATH = approvals
            rc = approve_mod.main(["--action", "decide", "--decision", "reject"])
        finally:
            approve_mod.OUTPUT_DIR = original["OUTPUT_DIR"]
            approve_mod.TOOL_DIR = original["TOOL_DIR"]
            approve_mod.APPROVALS_PATH = original["APPROVALS_PATH"]

        assert rc == 1
        latest = output / "chronicle_approve_latest.md"
        assert latest.exists()
        text = latest.read_text(encoding="utf-8")
        assert "no pending chronicle approvals found" in text.lower()


if __name__ == "__main__":
    test_chronicle_approve_decide_oldest_pending_in_scope()
    test_chronicle_approve_decide_missing_target_returns_error()
    print("✓ Chronicle approve tests passed")
