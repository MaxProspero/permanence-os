#!/usr/bin/env python3
"""Regression tests for chronicle-execution-board CLI forwarding."""

from __future__ import annotations

import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import cli as cli_mod  # noqa: E402


def test_cli_chronicle_execution_board_forwards_flags() -> None:
    captured: dict[str, list[str]] = {}
    original_run = cli_mod._run
    original_argv = list(sys.argv)
    try:
        cli_mod._run = lambda cmd: captured.setdefault("cmd", cmd) and 0  # type: ignore[assignment]
        sys.argv = [
            "cli.py",
            "chronicle-execution-board",
            "--limit",
            "6",
            "--source",
            "chronicle_refinement_queue",
            "--source",
            "manual_queue",
            "--no-canon",
            "--no-mark-queued",
        ]
        rc = cli_mod.main()
    finally:
        cli_mod._run = original_run
        sys.argv = original_argv

    assert rc == 0
    cmd = captured.get("cmd") or []
    assert "chronicle_execution_board.py" in " ".join(cmd)
    assert "--limit" in cmd and "6" in cmd
    assert cmd.count("--source") == 2
    assert "chronicle_refinement_queue" in cmd
    assert "manual_queue" in cmd
    assert "--no-canon" in cmd
    assert "--no-mark-queued" in cmd


if __name__ == "__main__":
    test_cli_chronicle_execution_board_forwards_flags()
    print("✓ CLI chronicle-execution-board forwarding tests passed")
