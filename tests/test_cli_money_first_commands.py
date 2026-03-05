#!/usr/bin/env python3
"""Regression tests for money-first/low-cost CLI forwarding."""

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


def test_cli_low_cost_mode_forwards_flags() -> None:
    cmd = _run_cli(
        [
            "cli.py",
            "low-cost-mode",
            "--action",
            "enable",
            "--monthly-budget",
            "9",
            "--milestone-usd",
            "650",
            "--chat-agent",
        ]
    )
    assert "low_cost_mode.py" in " ".join(cmd)
    assert "--action" in cmd and "enable" in cmd
    assert "--monthly-budget" in cmd and "9.0" in cmd
    assert "--milestone-usd" in cmd and "650" in cmd
    assert "--chat-agent" in cmd


def test_cli_money_first_gate_forwards_flags() -> None:
    cmd = _run_cli(
        [
            "cli.py",
            "money-first-gate",
            "--pipeline-path",
            "/tmp/sales_pipeline.json",
            "--milestone-usd",
            "700",
            "--min-won-deals",
            "2",
            "--strict",
        ]
    )
    assert "money_first_gate.py" in " ".join(cmd)
    assert "--pipeline-path" in cmd and "/tmp/sales_pipeline.json" in cmd
    assert "--milestone-usd" in cmd and "700.0" in cmd
    assert "--min-won-deals" in cmd and "2" in cmd
    assert "--strict" in cmd


def test_cli_money_first_lane_forwards_flags() -> None:
    cmd = _run_cli(["cli.py", "money-first-lane", "--strict", "--timeout", "120", "--skip-init"])
    assert "money_first_lane.py" in " ".join(cmd)
    assert "--strict" in cmd
    assert "--timeout" in cmd and "120" in cmd
    assert "--skip-init" in cmd


if __name__ == "__main__":
    test_cli_low_cost_mode_forwards_flags()
    test_cli_money_first_gate_forwards_flags()
    test_cli_money_first_lane_forwards_flags()
    print("✓ CLI money-first command tests passed")
