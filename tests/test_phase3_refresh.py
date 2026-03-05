#!/usr/bin/env python3
"""Tests for phase3 refresh orchestrator."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import scripts.phase3_refresh as phase3_mod  # noqa: E402


def test_phase3_refresh_runs_steps_and_writes_outputs() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        output = root / "outputs"
        tool = root / "tool"
        output.mkdir(parents=True, exist_ok=True)
        tool.mkdir(parents=True, exist_ok=True)

        original = {
            "OUTPUT_DIR": phase3_mod.OUTPUT_DIR,
            "TOOL_DIR": phase3_mod.TOOL_DIR,
            "FEATURE_GATE": os.environ.get("PERMANENCE_FEATURE_WORK_REQUIRE_REVENUE_MILESTONE"),
        }
        try:
            phase3_mod.OUTPUT_DIR = output
            phase3_mod.TOOL_DIR = tool
            os.environ["PERMANENCE_FEATURE_WORK_REQUIRE_REVENUE_MILESTONE"] = "0"

            def fake_run(cmd, cwd, env, capture_output, text, timeout):  # type: ignore[no-untyped-def]
                return __import__("subprocess").CompletedProcess(
                    args=cmd,
                    returncode=0,
                    stdout=f"ok {' '.join(str(x) for x in cmd)}",
                    stderr="",
                )

            with patch("scripts.phase3_refresh.subprocess.run", side_effect=fake_run) as mocked:
                rc = phase3_mod.main([])
                assert mocked.call_count == 14
        finally:
            phase3_mod.OUTPUT_DIR = original["OUTPUT_DIR"]
            phase3_mod.TOOL_DIR = original["TOOL_DIR"]
            if original["FEATURE_GATE"] is None:
                os.environ.pop("PERMANENCE_FEATURE_WORK_REQUIRE_REVENUE_MILESTONE", None)
            else:
                os.environ["PERMANENCE_FEATURE_WORK_REQUIRE_REVENUE_MILESTONE"] = original["FEATURE_GATE"]

        assert rc == 0
        assert (output / "phase3_refresh_latest.md").exists()
        payload_files = sorted(tool.glob("phase3_refresh_*.json"))
        assert payload_files
        payload = json.loads(payload_files[-1].read_text(encoding="utf-8"))
        assert payload.get("overall_status") == "PASS"
        assert int(payload.get("step_count", 0)) == 14
        assert int(payload.get("failed_count", 0)) == 0


def test_phase3_refresh_blocks_when_money_gate_fails() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        output = root / "outputs"
        tool = root / "tool"
        output.mkdir(parents=True, exist_ok=True)
        tool.mkdir(parents=True, exist_ok=True)

        original = {
            "OUTPUT_DIR": phase3_mod.OUTPUT_DIR,
            "TOOL_DIR": phase3_mod.TOOL_DIR,
            "FEATURE_GATE": os.environ.get("PERMANENCE_FEATURE_WORK_REQUIRE_REVENUE_MILESTONE"),
        }
        try:
            phase3_mod.OUTPUT_DIR = output
            phase3_mod.TOOL_DIR = tool
            os.environ["PERMANENCE_FEATURE_WORK_REQUIRE_REVENUE_MILESTONE"] = "1"

            def fake_run(cmd, cwd, env, capture_output, text, timeout):  # type: ignore[no-untyped-def]
                rc = 1 if "money-first-gate" in cmd else 0
                return __import__("subprocess").CompletedProcess(
                    args=cmd,
                    returncode=rc,
                    stdout=f"rc={rc} {' '.join(str(x) for x in cmd)}",
                    stderr="",
                )

            with patch("scripts.phase3_refresh.subprocess.run", side_effect=fake_run) as mocked:
                rc = phase3_mod.main([])
                assert mocked.call_count == 1
        finally:
            phase3_mod.OUTPUT_DIR = original["OUTPUT_DIR"]
            phase3_mod.TOOL_DIR = original["TOOL_DIR"]
            if original["FEATURE_GATE"] is None:
                os.environ.pop("PERMANENCE_FEATURE_WORK_REQUIRE_REVENUE_MILESTONE", None)
            else:
                os.environ["PERMANENCE_FEATURE_WORK_REQUIRE_REVENUE_MILESTONE"] = original["FEATURE_GATE"]

        assert rc == 1
        latest = output / "phase3_refresh_latest.md"
        assert latest.exists()
        text = latest.read_text(encoding="utf-8")
        assert "money-first-gate --strict" in text


if __name__ == "__main__":
    test_phase3_refresh_runs_steps_and_writes_outputs()
    test_phase3_refresh_blocks_when_money_gate_fails()
    print("✓ Phase3 refresh tests passed")
