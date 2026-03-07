#!/usr/bin/env python3
"""Tests for chronicle control plane."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import scripts.chronicle_control as control_mod  # noqa: E402


def test_chronicle_control_status_summarizes_pipeline_state() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        output = root / "outputs"
        tool = root / "tool"
        approvals = root / "approvals.json"
        output.mkdir(parents=True, exist_ok=True)
        tool.mkdir(parents=True, exist_ok=True)

        (tool / "chronicle_refinement_20260305-010000.json").write_text(
            json.dumps({"backlog_updates_count": 3, "canon_checks_count": 1}),
            encoding="utf-8",
        )
        (tool / "chronicle_approval_queue_20260305-010100.json").write_text(
            json.dumps({"queued_count": 2, "pending_total": 4}),
            encoding="utf-8",
        )
        (tool / "chronicle_execution_board_20260305-010200.json").write_text(
            json.dumps({"task_count": 2, "marked_queued_count": 1}),
            encoding="utf-8",
        )

        approvals.write_text(
            json.dumps(
                [
                    {"id": "A", "source": "chronicle_refinement_queue", "status": "PENDING_HUMAN_REVIEW"},
                    {"id": "B", "source": "chronicle_refinement_queue", "status": "APPROVED"},
                    {
                        "id": "C",
                        "source": "chronicle_refinement_queue",
                        "status": "APPROVED",
                        "execution_status": "QUEUED_FOR_EXECUTION",
                    },
                    {"id": "D", "source": "phase3_opportunity_queue", "status": "PENDING_HUMAN_REVIEW"},
                ]
            ),
            encoding="utf-8",
        )

        original = {
            "OUTPUT_DIR": control_mod.OUTPUT_DIR,
            "TOOL_DIR": control_mod.TOOL_DIR,
            "APPROVALS_PATH": control_mod.APPROVALS_PATH,
        }
        try:
            control_mod.OUTPUT_DIR = output
            control_mod.TOOL_DIR = tool
            control_mod.APPROVALS_PATH = approvals
            rc = control_mod.main(["--action", "status"])
        finally:
            control_mod.OUTPUT_DIR = original["OUTPUT_DIR"]
            control_mod.TOOL_DIR = original["TOOL_DIR"]
            control_mod.APPROVALS_PATH = original["APPROVALS_PATH"]

        assert rc == 0
        latest = output / "chronicle_control_latest.md"
        assert latest.exists()
        text = latest.read_text(encoding="utf-8")
        assert "Refinement backlog updates: 3" in text
        assert "Queue pending total: 4" in text
        assert "Execution tasks: 2" in text
        assert "Pending approvals remain." in text

        payload_files = sorted(tool.glob("chronicle_control_*.json"))
        assert payload_files
        payload = json.loads(payload_files[-1].read_text(encoding="utf-8"))
        assert str(payload.get("action")) == "status"
        snapshot = payload.get("status_snapshot") or {}
        assert int(((snapshot.get("approval_state") or {}).get("pending_count")) == 1)


def test_chronicle_control_run_executes_pipeline_steps() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        output = root / "outputs"
        tool = root / "tool"
        approvals = root / "approvals.json"
        output.mkdir(parents=True, exist_ok=True)
        tool.mkdir(parents=True, exist_ok=True)
        approvals.write_text("[]", encoding="utf-8")

        original = {
            "OUTPUT_DIR": control_mod.OUTPUT_DIR,
            "TOOL_DIR": control_mod.TOOL_DIR,
            "APPROVALS_PATH": control_mod.APPROVALS_PATH,
        }
        try:
            control_mod.OUTPUT_DIR = output
            control_mod.TOOL_DIR = tool
            control_mod.APPROVALS_PATH = approvals

            def fake_run(cmd, cwd, env, capture_output, text, timeout):  # type: ignore[no-untyped-def]
                return __import__("subprocess").CompletedProcess(
                    args=cmd,
                    returncode=0,
                    stdout=f"ok {' '.join(str(x) for x in cmd)}",
                    stderr="",
                )

            with patch("scripts.chronicle_control.subprocess.run", side_effect=fake_run) as mocked:
                rc = control_mod.main(["--action", "run", "--queue-max-items", "7", "--execution-limit", "5", "--no-canon"])
                assert mocked.call_count == 3
        finally:
            control_mod.OUTPUT_DIR = original["OUTPUT_DIR"]
            control_mod.TOOL_DIR = original["TOOL_DIR"]
            control_mod.APPROVALS_PATH = original["APPROVALS_PATH"]

        assert rc == 0
        payload_files = sorted(tool.glob("chronicle_control_*.json"))
        assert payload_files
        payload = json.loads(payload_files[-1].read_text(encoding="utf-8"))
        assert str(payload.get("action")) == "run"
        assert int(len(payload.get("run_steps") or [])) == 3
        commands = [" ".join(step.get("command") or []) for step in (payload.get("run_steps") or [])]
        assert any("chronicle-refinement" in cmd for cmd in commands)
        assert any("chronicle-approval-queue" in cmd and "--max-items 7" in cmd for cmd in commands)
        assert any("chronicle-execution-board" in cmd and "--limit 5" in cmd and "--no-canon" in cmd for cmd in commands)


if __name__ == "__main__":
    test_chronicle_control_status_summarizes_pipeline_state()
    test_chronicle_control_run_executes_pipeline_steps()
    print("✓ Chronicle control tests passed")
