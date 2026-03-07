#!/usr/bin/env python3
"""Regression tests for chronicle-control CLI forwarding."""

from __future__ import annotations

import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import cli as cli_mod  # noqa: E402


def test_cli_chronicle_control_forwards_flags() -> None:
    captured: dict[str, list[str]] = {}
    original_run = cli_mod._run
    original_argv = list(sys.argv)
    try:
        cli_mod._run = lambda cmd: captured.setdefault("cmd", cmd) and 0  # type: ignore[assignment]
        sys.argv = [
            "cli.py",
            "chronicle-control",
            "--action",
            "run",
            "--strict",
            "--timeout",
            "600",
            "--source-filter",
            "chronicle_refinement_queue",
            "--skip-queue",
            "--queue-max-items",
            "8",
            "--execution-limit",
            "4",
            "--no-canon",
        ]
        rc = cli_mod.main()
    finally:
        cli_mod._run = original_run
        sys.argv = original_argv

    assert rc == 0
    cmd = captured.get("cmd") or []
    assert "chronicle_control.py" in " ".join(cmd)
    assert "--action" in cmd and "run" in cmd
    assert "--strict" in cmd
    assert "--timeout" in cmd and "600" in cmd
    assert "--source-filter" in cmd and "chronicle_refinement_queue" in cmd
    assert "--skip-queue" in cmd
    assert "--queue-max-items" in cmd and "8" in cmd
    assert "--execution-limit" in cmd and "4" in cmd
    assert "--no-canon" in cmd


if __name__ == "__main__":
    test_cli_chronicle_control_forwards_flags()
    print("✓ CLI chronicle-control forwarding tests passed")
