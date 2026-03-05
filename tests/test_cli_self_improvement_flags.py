#!/usr/bin/env python3
"""Regression tests for self-improvement CLI flag forwarding."""

from __future__ import annotations

import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import cli as cli_mod  # noqa: E402


def test_cli_self_improvement_forwards_set_decision_code() -> None:
    captured: dict[str, list[str]] = {}
    original_run = cli_mod._run
    original_argv = list(sys.argv)
    try:
        cli_mod._run = lambda cmd: captured.setdefault("cmd", cmd) and 0  # type: ignore[assignment]
        sys.argv = [
            "cli.py",
            "self-improvement",
            "--action",
            "status",
            "--set-decision-code",
            "114272",
        ]
        rc = cli_mod.main()
    finally:
        cli_mod._run = original_run
        sys.argv = original_argv

    assert rc == 0
    cmd = captured.get("cmd") or []
    assert "--set-decision-code" in cmd
    assert "114272" in cmd


def test_cli_self_improvement_forwards_decision_code_on_decide() -> None:
    captured: dict[str, list[str]] = {}
    original_run = cli_mod._run
    original_argv = list(sys.argv)
    try:
        cli_mod._run = lambda cmd: captured.setdefault("cmd", cmd) and 0  # type: ignore[assignment]
        sys.argv = [
            "cli.py",
            "self-improvement",
            "--action",
            "decide",
            "--decision",
            "approve",
            "--proposal-id",
            "IMP-ABCDE12345",
            "--decided-by",
            "payton",
            "--decision-code",
            "114272",
            "--clear-decision-code",
        ]
        rc = cli_mod.main()
    finally:
        cli_mod._run = original_run
        sys.argv = original_argv

    assert rc == 0
    cmd = captured.get("cmd") or []
    assert "--decision-code" in cmd
    assert "114272" in cmd
    assert "--clear-decision-code" in cmd


if __name__ == "__main__":
    test_cli_self_improvement_forwards_set_decision_code()
    test_cli_self_improvement_forwards_decision_code_on_decide()
    print("✓ CLI self-improvement flag forwarding tests passed")
