#!/usr/bin/env python3
"""Tests for ophtxn_ops_pack orchestrator."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import scripts.ophtxn_ops_pack as mod  # noqa: E402


def test_ops_pack_status_writes_plan_without_running_steps() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        output = root / "outputs"
        tool = root / "tool"
        output.mkdir(parents=True, exist_ok=True)
        tool.mkdir(parents=True, exist_ok=True)

        original = {"OUTPUT_DIR": mod.OUTPUT_DIR, "TOOL_DIR": mod.TOOL_DIR}
        try:
            mod.OUTPUT_DIR = output
            mod.TOOL_DIR = tool
            with patch("scripts.ophtxn_ops_pack.subprocess.run") as mocked:
                rc = mod.main(
                    [
                        "--action",
                        "status",
                        "--approval-source",
                        "phase3_opportunity_queue",
                    ]
                )
                assert mocked.call_count == 0
        finally:
            mod.OUTPUT_DIR = original["OUTPUT_DIR"]
            mod.TOOL_DIR = original["TOOL_DIR"]

        assert rc == 0
        latest = output / "ophtxn_ops_pack_latest.md"
        assert latest.exists()
        text = latest.read_text(encoding="utf-8")
        assert "Action: status" in text
        assert "approval-triage --action top" in text


def test_ops_pack_run_executes_steps_and_optional_safe_batch() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        output = root / "outputs"
        tool = root / "tool"
        output.mkdir(parents=True, exist_ok=True)
        tool.mkdir(parents=True, exist_ok=True)

        original = {"OUTPUT_DIR": mod.OUTPUT_DIR, "TOOL_DIR": mod.TOOL_DIR}
        try:
            mod.OUTPUT_DIR = output
            mod.TOOL_DIR = tool

            def fake_run(cmd, cwd, env, capture_output, text, timeout):  # type: ignore[no-untyped-def]
                return __import__("subprocess").CompletedProcess(
                    args=cmd,
                    returncode=0,
                    stdout=f"ok {' '.join(str(x) for x in cmd)}",
                    stderr="",
                )

            with patch("scripts.ophtxn_ops_pack.subprocess.run", side_effect=fake_run) as mocked:
                rc = mod.main(
                    [
                        "--action",
                        "run",
                        "--approval-source",
                        "phase3_opportunity_queue",
                        "--approval-decision",
                        "approve",
                        "--approval-batch-size",
                        "2",
                    ]
                )
                assert mocked.call_count == 4
        finally:
            mod.OUTPUT_DIR = original["OUTPUT_DIR"]
            mod.TOOL_DIR = original["TOOL_DIR"]

        assert rc == 0
        payload_files = sorted(tool.glob("ophtxn_ops_pack_*.json"))
        assert payload_files
        payload = json.loads(payload_files[-1].read_text(encoding="utf-8"))
        assert payload.get("overall_status") == "PASS"
        assert int(payload.get("step_count") or 0) == 4
        assert str(payload.get("approval_decision") or "") == "approve"


if __name__ == "__main__":
    test_ops_pack_status_writes_plan_without_running_steps()
    test_ops_pack_run_executes_steps_and_optional_safe_batch()
    print("✓ Ophtxn ops-pack tests passed")
