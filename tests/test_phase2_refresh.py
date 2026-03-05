#!/usr/bin/env python3
"""Tests for phase2 refresh orchestrator."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import scripts.phase2_refresh as phase2_mod  # noqa: E402


def test_phase2_refresh_runs_steps_and_writes_outputs() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        output = root / "outputs"
        tool = root / "tool"
        inbox = root / "inbox"
        output.mkdir(parents=True, exist_ok=True)
        tool.mkdir(parents=True, exist_ok=True)
        inbox.mkdir(parents=True, exist_ok=True)

        original = {
            "OUTPUT_DIR": phase2_mod.OUTPUT_DIR,
            "TOOL_DIR": phase2_mod.TOOL_DIR,
            "ATTACHMENT_INBOX_DIR": phase2_mod.ATTACHMENT_INBOX_DIR,
        }
        try:
            phase2_mod.OUTPUT_DIR = output
            phase2_mod.TOOL_DIR = tool
            phase2_mod.ATTACHMENT_INBOX_DIR = inbox

            def fake_run(cmd, cwd, env, capture_output, text, timeout):  # type: ignore[no-untyped-def]
                return __import__("subprocess").CompletedProcess(
                    args=cmd,
                    returncode=0,
                    stdout=f"ok {' '.join(str(x) for x in cmd)}",
                    stderr="",
                )

            with patch("scripts.phase2_refresh.subprocess.run", side_effect=fake_run) as mocked:
                rc = phase2_mod.main([])
                assert mocked.call_count == 5
        finally:
            phase2_mod.OUTPUT_DIR = original["OUTPUT_DIR"]
            phase2_mod.TOOL_DIR = original["TOOL_DIR"]
            phase2_mod.ATTACHMENT_INBOX_DIR = original["ATTACHMENT_INBOX_DIR"]

        assert rc == 0
        assert (output / "phase2_refresh_latest.md").exists()
        payload_files = sorted(tool.glob("phase2_refresh_*.json"))
        assert payload_files
        payload = json.loads(payload_files[-1].read_text(encoding="utf-8"))
        assert payload.get("overall_status") == "PASS"
        assert int(payload.get("step_count", 0)) == 5
        assert int(payload.get("failed_count", 0)) == 0


if __name__ == "__main__":
    test_phase2_refresh_runs_steps_and_writes_outputs()
    print("✓ Phase2 refresh tests passed")

