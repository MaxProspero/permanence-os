#!/usr/bin/env python3
"""Regression tests for ophtxn-completion CLI forwarding."""

from __future__ import annotations

import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import cli as cli_mod  # noqa: E402


def test_cli_ophtxn_completion_forwards_target_and_strict() -> None:
    captured: dict[str, list[str]] = {}
    original_run = cli_mod._run
    original_argv = list(sys.argv)
    try:
        cli_mod._run = lambda cmd: captured.setdefault("cmd", cmd) and 0  # type: ignore[assignment]
        sys.argv = [
            "cli.py",
            "ophtxn-completion",
            "--target",
            "95",
            "--strict",
        ]
        rc = cli_mod.main()
    finally:
        cli_mod._run = original_run
        sys.argv = original_argv

    assert rc == 0
    cmd = captured.get("cmd") or []
    assert "scripts/ophtxn_completion.py" in " ".join(cmd)
    assert "--target" in cmd
    assert "95" in cmd
    assert "--strict" in cmd


if __name__ == "__main__":
    test_cli_ophtxn_completion_forwards_target_and_strict()
    print("✓ CLI ophtxn-completion forwarding tests passed")
