#!/usr/bin/env python3
"""Tests for generic approval triage command."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import scripts.approval_triage as triage_mod  # noqa: E402


def test_approval_triage_decides_oldest_pending_globally() -> None:
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
                        "approval_id": "APR-oldest",
                        "title": "Oldest pending",
                        "status": "PENDING_HUMAN_REVIEW",
                        "queued_at": "2026-03-05T00:01:00Z",
                        "source": "phase3_opportunity_queue",
                    },
                    {
                        "approval_id": "CHR-newer",
                        "title": "Newer pending",
                        "status": "PENDING_HUMAN_REVIEW",
                        "queued_at": "2026-03-05T00:05:00Z",
                        "source": "chronicle_refinement_queue",
                    },
                ]
            ),
            encoding="utf-8",
        )

        original = {
            "OUTPUT_DIR": triage_mod.OUTPUT_DIR,
            "TOOL_DIR": triage_mod.TOOL_DIR,
            "APPROVALS_PATH": triage_mod.APPROVALS_PATH,
        }
        try:
            triage_mod.OUTPUT_DIR = output
            triage_mod.TOOL_DIR = tool
            triage_mod.APPROVALS_PATH = approvals
            rc = triage_mod.main(
                [
                    "--action",
                    "decide",
                    "--decision",
                    "approve",
                    "--decided-by",
                    "payton",
                    "--note",
                    "approved via telegram next",
                ]
            )
        finally:
            triage_mod.OUTPUT_DIR = original["OUTPUT_DIR"]
            triage_mod.TOOL_DIR = original["TOOL_DIR"]
            triage_mod.APPROVALS_PATH = original["APPROVALS_PATH"]

        assert rc == 0
        rows = json.loads(approvals.read_text(encoding="utf-8"))
        oldest = next(row for row in rows if str(row.get("approval_id")) == "APR-oldest")
        newer = next(row for row in rows if str(row.get("approval_id")) == "CHR-newer")
        assert str(oldest.get("status")) == "APPROVED"
        assert str(oldest.get("decided_by")) == "payton"
        assert str(oldest.get("decision")) == "approve"
        assert str(newer.get("status")) == "PENDING_HUMAN_REVIEW"

        latest = output / "approval_triage_latest.md"
        assert latest.exists()
        payload_files = sorted(tool.glob("approval_triage_*.json"))
        assert payload_files
        payload = json.loads(payload_files[-1].read_text(encoding="utf-8"))
        assert str(payload.get("decision_target_id")) == "APR-oldest"


def test_approval_triage_can_scope_by_source() -> None:
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
                        "approval_id": "APR-op",
                        "title": "Opportunity pending",
                        "status": "PENDING_HUMAN_REVIEW",
                        "queued_at": "2026-03-05T00:01:00Z",
                        "source": "phase3_opportunity_queue",
                    },
                    {
                        "approval_id": "CHR-1",
                        "title": "Chronicle pending",
                        "status": "PENDING_HUMAN_REVIEW",
                        "queued_at": "2026-03-05T00:00:00Z",
                        "source": "chronicle_refinement_queue",
                    },
                ]
            ),
            encoding="utf-8",
        )

        original = {
            "OUTPUT_DIR": triage_mod.OUTPUT_DIR,
            "TOOL_DIR": triage_mod.TOOL_DIR,
            "APPROVALS_PATH": triage_mod.APPROVALS_PATH,
        }
        try:
            triage_mod.OUTPUT_DIR = output
            triage_mod.TOOL_DIR = tool
            triage_mod.APPROVALS_PATH = approvals
            rc = triage_mod.main(
                [
                    "--action",
                    "decide",
                    "--decision",
                    "reject",
                    "--source",
                    "chronicle_refinement_queue",
                ]
            )
        finally:
            triage_mod.OUTPUT_DIR = original["OUTPUT_DIR"]
            triage_mod.TOOL_DIR = original["TOOL_DIR"]
            triage_mod.APPROVALS_PATH = original["APPROVALS_PATH"]

        assert rc == 0
        rows = json.loads(approvals.read_text(encoding="utf-8"))
        op = next(row for row in rows if str(row.get("approval_id")) == "APR-op")
        ch = next(row for row in rows if str(row.get("approval_id")) == "CHR-1")
        assert str(op.get("status")) == "PENDING_HUMAN_REVIEW"
        assert str(ch.get("status")) == "REJECTED"


def test_approval_triage_decide_batch_applies_multiple() -> None:
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
                    {"approval_id": "APR-1", "status": "PENDING_HUMAN_REVIEW", "queued_at": "2026-03-05T00:01:00Z"},
                    {"approval_id": "APR-2", "status": "PENDING_HUMAN_REVIEW", "queued_at": "2026-03-05T00:02:00Z"},
                    {"approval_id": "APR-3", "status": "PENDING_HUMAN_REVIEW", "queued_at": "2026-03-05T00:03:00Z"},
                ]
            ),
            encoding="utf-8",
        )

        original = {
            "OUTPUT_DIR": triage_mod.OUTPUT_DIR,
            "TOOL_DIR": triage_mod.TOOL_DIR,
            "APPROVALS_PATH": triage_mod.APPROVALS_PATH,
        }
        try:
            triage_mod.OUTPUT_DIR = output
            triage_mod.TOOL_DIR = tool
            triage_mod.APPROVALS_PATH = approvals
            rc = triage_mod.main(
                [
                    "--action",
                    "decide-batch",
                    "--decision",
                    "defer",
                    "--batch-size",
                    "2",
                    "--decided-by",
                    "payton",
                ]
            )
        finally:
            triage_mod.OUTPUT_DIR = original["OUTPUT_DIR"]
            triage_mod.TOOL_DIR = original["TOOL_DIR"]
            triage_mod.APPROVALS_PATH = original["APPROVALS_PATH"]

        assert rc == 0
        rows = json.loads(approvals.read_text(encoding="utf-8"))
        statuses = {str(row.get("approval_id")): str(row.get("status")) for row in rows}
        assert statuses.get("APR-1") == "DEFERRED"
        assert statuses.get("APR-2") == "DEFERRED"
        assert statuses.get("APR-3") == "PENDING_HUMAN_REVIEW"

        payload_files = sorted(tool.glob("approval_triage_*.json"))
        assert payload_files
        payload = json.loads(payload_files[-1].read_text(encoding="utf-8"))
        assert payload.get("action") == "decide-batch"
        assert len(payload.get("decision_target_ids") or []) == 2


def test_approval_triage_safe_batch_requires_source_allowlist() -> None:
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
                        "approval_id": "APR-low",
                        "status": "PENDING_HUMAN_REVIEW",
                        "priority": "LOW",
                        "queued_at": "2026-03-05T00:01:00Z",
                        "source": "phase3_opportunity_queue",
                    }
                ]
            ),
            encoding="utf-8",
        )

        original = {
            "OUTPUT_DIR": triage_mod.OUTPUT_DIR,
            "TOOL_DIR": triage_mod.TOOL_DIR,
            "APPROVALS_PATH": triage_mod.APPROVALS_PATH,
        }
        try:
            triage_mod.OUTPUT_DIR = output
            triage_mod.TOOL_DIR = tool
            triage_mod.APPROVALS_PATH = approvals
            rc = triage_mod.main(
                [
                    "--action",
                    "decide-batch-safe",
                    "--decision",
                    "approve",
                    "--batch-size",
                    "1",
                    "--safe-max-priority",
                    "low",
                    "--safe-max-risk",
                    "low",
                ]
            )
        finally:
            triage_mod.OUTPUT_DIR = original["OUTPUT_DIR"]
            triage_mod.TOOL_DIR = original["TOOL_DIR"]
            triage_mod.APPROVALS_PATH = original["APPROVALS_PATH"]

        assert rc == 1
        rows = json.loads(approvals.read_text(encoding="utf-8"))
        assert str(rows[0].get("status")) == "PENDING_HUMAN_REVIEW"


def test_approval_triage_safe_batch_respects_priority_and_source() -> None:
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
                        "approval_id": "APR-low-1",
                        "status": "PENDING_HUMAN_REVIEW",
                        "priority": "LOW",
                        "queued_at": "2026-03-05T00:01:00Z",
                        "source": "phase3_opportunity_queue",
                    },
                    {
                        "approval_id": "APR-high-1",
                        "status": "PENDING_HUMAN_REVIEW",
                        "priority": "HIGH",
                        "queued_at": "2026-03-05T00:02:00Z",
                        "source": "phase3_opportunity_queue",
                    },
                    {
                        "approval_id": "CHR-low-1",
                        "status": "PENDING_HUMAN_REVIEW",
                        "priority": "LOW",
                        "queued_at": "2026-03-05T00:03:00Z",
                        "source": "chronicle_refinement_queue",
                    },
                ]
            ),
            encoding="utf-8",
        )

        original = {
            "OUTPUT_DIR": triage_mod.OUTPUT_DIR,
            "TOOL_DIR": triage_mod.TOOL_DIR,
            "APPROVALS_PATH": triage_mod.APPROVALS_PATH,
        }
        try:
            triage_mod.OUTPUT_DIR = output
            triage_mod.TOOL_DIR = tool
            triage_mod.APPROVALS_PATH = approvals
            rc = triage_mod.main(
                [
                    "--action",
                    "decide-batch-safe",
                    "--decision",
                    "approve",
                    "--batch-size",
                    "3",
                    "--source",
                    "phase3_opportunity_queue",
                    "--safe-max-priority",
                    "low",
                    "--safe-max-risk",
                    "low",
                    "--decided-by",
                    "telegram",
                ]
            )
        finally:
            triage_mod.OUTPUT_DIR = original["OUTPUT_DIR"]
            triage_mod.TOOL_DIR = original["TOOL_DIR"]
            triage_mod.APPROVALS_PATH = original["APPROVALS_PATH"]

        assert rc == 0
        rows = json.loads(approvals.read_text(encoding="utf-8"))
        statuses = {str(row.get("approval_id")): str(row.get("status")) for row in rows}
        assert statuses.get("APR-low-1") == "APPROVED"
        assert statuses.get("APR-high-1") == "PENDING_HUMAN_REVIEW"
        assert statuses.get("CHR-low-1") == "PENDING_HUMAN_REVIEW"

        payload_files = sorted(tool.glob("approval_triage_*.json"))
        assert payload_files
        payload = json.loads(payload_files[-1].read_text(encoding="utf-8"))
        assert payload.get("action") == "decide-batch-safe"
        assert payload.get("safe_max_priority") == "LOW"
        assert payload.get("safe_max_risk") == "LOW"


def test_approval_triage_top_sorts_high_before_low() -> None:
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
                        "approval_id": "APR-low",
                        "title": "low first",
                        "status": "PENDING_HUMAN_REVIEW",
                        "priority": "LOW",
                        "opportunity_score": 10,
                        "queued_at": "2026-03-05T00:01:00Z",
                        "source": "phase3_opportunity_queue",
                    },
                    {
                        "approval_id": "APR-high",
                        "title": "high later",
                        "status": "PENDING_HUMAN_REVIEW",
                        "priority": "HIGH",
                        "opportunity_score": 11,
                        "queued_at": "2026-03-05T00:02:00Z",
                        "source": "phase3_opportunity_queue",
                    },
                ]
            ),
            encoding="utf-8",
        )

        original = {
            "OUTPUT_DIR": triage_mod.OUTPUT_DIR,
            "TOOL_DIR": triage_mod.TOOL_DIR,
            "APPROVALS_PATH": triage_mod.APPROVALS_PATH,
        }
        try:
            triage_mod.OUTPUT_DIR = output
            triage_mod.TOOL_DIR = tool
            triage_mod.APPROVALS_PATH = approvals
            rc = triage_mod.main(["--action", "top", "--limit", "2"])
        finally:
            triage_mod.OUTPUT_DIR = original["OUTPUT_DIR"]
            triage_mod.TOOL_DIR = original["TOOL_DIR"]
            triage_mod.APPROVALS_PATH = original["APPROVALS_PATH"]

        assert rc == 0
        latest = output / "approval_triage_latest.md"
        text = latest.read_text(encoding="utf-8")
        assert "1. APR-high [HIGH]" in text
        assert "2. APR-low [LOW]" in text


def test_approval_triage_status_reports_stale_pending() -> None:
    """Verify stale pending items are counted and warned about in status output."""
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
                        "approval_id": "STALE-1",
                        "title": "Old pending item",
                        "status": "PENDING_HUMAN_REVIEW",
                        "queued_at": "2026-01-01T00:00:00Z",
                        "source": "phase3_opportunity_queue",
                    },
                    {
                        "approval_id": "FRESH-1",
                        "title": "Recent pending item",
                        "status": "PENDING_HUMAN_REVIEW",
                        "queued_at": "2099-12-31T23:59:59Z",
                        "source": "phase3_opportunity_queue",
                    },
                    {
                        "approval_id": "NO-TS",
                        "title": "No timestamp item",
                        "status": "PENDING_HUMAN_REVIEW",
                        "source": "phase3_opportunity_queue",
                    },
                ]
            ),
            encoding="utf-8",
        )

        original = {
            "OUTPUT_DIR": triage_mod.OUTPUT_DIR,
            "TOOL_DIR": triage_mod.TOOL_DIR,
            "APPROVALS_PATH": triage_mod.APPROVALS_PATH,
        }
        try:
            triage_mod.OUTPUT_DIR = output
            triage_mod.TOOL_DIR = tool
            triage_mod.APPROVALS_PATH = approvals
            rc = triage_mod.main(["--action", "status"])
        finally:
            triage_mod.OUTPUT_DIR = original["OUTPUT_DIR"]
            triage_mod.TOOL_DIR = original["TOOL_DIR"]
            triage_mod.APPROVALS_PATH = original["APPROVALS_PATH"]

        assert rc == 0
        latest = output / "approval_triage_latest.md"
        text = latest.read_text(encoding="utf-8")
        assert "Stale (>48h pending): 2" in text
        assert "have been pending for more than 48 hours" in text

        payload_files = sorted(tool.glob("approval_triage_*.json"))
        assert payload_files
        payload = json.loads(payload_files[-1].read_text(encoding="utf-8"))
        assert payload.get("stale_pending_count") == 2


if __name__ == "__main__":
    test_approval_triage_decides_oldest_pending_globally()
    test_approval_triage_can_scope_by_source()
    test_approval_triage_decide_batch_applies_multiple()
    test_approval_triage_safe_batch_requires_source_allowlist()
    test_approval_triage_safe_batch_respects_priority_and_source()
    test_approval_triage_top_sorts_high_before_low()
    test_approval_triage_status_reports_stale_pending()
    print("✓ Approval triage tests passed")
