#!/usr/bin/env python3
"""Tests for money-first lane orchestrator."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import scripts.money_first_lane as lane_mod  # noqa: E402


def test_money_first_lane_runs_steps_and_writes_outputs() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        output = root / "outputs"
        tool = root / "tool"
        output.mkdir(parents=True, exist_ok=True)
        tool.mkdir(parents=True, exist_ok=True)

        original = {
            "OUTPUT_DIR": lane_mod.OUTPUT_DIR,
            "TOOL_DIR": lane_mod.TOOL_DIR,
        }
        try:
            lane_mod.OUTPUT_DIR = output
            lane_mod.TOOL_DIR = tool

            def fake_run(cmd, cwd, env, capture_output, text, timeout):  # type: ignore[no-untyped-def]
                return __import__("subprocess").CompletedProcess(
                    args=cmd,
                    returncode=0,
                    stdout=f"ok {' '.join(str(x) for x in cmd)}",
                    stderr="",
                )

            with patch("scripts.money_first_lane.subprocess.run", side_effect=fake_run) as mocked:
                rc = lane_mod.main(["--strict"])
                assert mocked.call_count == 10
        finally:
            lane_mod.OUTPUT_DIR = original["OUTPUT_DIR"]
            lane_mod.TOOL_DIR = original["TOOL_DIR"]

        assert rc == 0
        assert (output / "money_first_lane_latest.md").exists()
        payload_files = sorted(tool.glob("money_first_lane_*.json"))
        assert payload_files
        payload = json.loads(payload_files[-1].read_text(encoding="utf-8"))
        assert payload.get("overall_status") == "PASS"
        assert int(payload.get("step_count", 0)) == 10


if __name__ == "__main__":
    test_money_first_lane_runs_steps_and_writes_outputs()
    print("✓ Money-first lane tests passed")
