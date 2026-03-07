#!/usr/bin/env python3
"""Regression tests for ophtxn-launchpad CLI forwarding."""

from __future__ import annotations

import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import cli as cli_mod  # noqa: E402


def _run_cli(argv: list[str]) -> list[str]:
    captured: dict[str, list[str]] = {}
    original_run = cli_mod._run
    original_argv = list(sys.argv)
    try:
        cli_mod._run = lambda cmd: captured.setdefault("cmd", cmd) and 0  # type: ignore[assignment]
        sys.argv = argv
        rc = cli_mod.main()
    finally:
        cli_mod._run = original_run
        sys.argv = original_argv
    assert rc == 0
    return captured.get("cmd") or []


def test_cli_ophtxn_launchpad_forwards_flags() -> None:
    cmd = _run_cli(
        [
            "cli.py",
            "ophtxn-launchpad",
            "--action",
            "status",
            "--strict",
            "--min-score",
            "82",
            "--output",
            "/tmp/launch.md",
        ]
    )
    assert "ophtxn_launchpad.py" in " ".join(cmd)
    assert "--action" in cmd and "status" in cmd
    assert "--strict" in cmd
    assert "--min-score" in cmd and "82.0" in cmd
    assert "--output" in cmd and "/tmp/launch.md" in cmd


def test_cli_ophtxn_launchpad_plan_action_forwards() -> None:
    cmd = _run_cli(["cli.py", "ophtxn-launchpad", "--action", "plan"])
    assert "ophtxn_launchpad.py" in " ".join(cmd)
    assert "--action" in cmd and "plan" in cmd


if __name__ == "__main__":
    test_cli_ophtxn_launchpad_forwards_flags()
    test_cli_ophtxn_launchpad_plan_action_forwards()
    print("✓ CLI ophtxn-launchpad forwarding tests passed")
