#!/usr/bin/env python3
"""Regression tests for ophtxn-daily-ops CLI forwarding."""

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


def test_cli_ophtxn_daily_ops_forwards_flags() -> None:
    cmd = _run_cli(
        [
            "cli.py",
            "ophtxn-daily-ops",
            "--action",
            "morning",
            "--queue-path",
            "/tmp/queue.jsonl",
            "--approvals-path",
            "/tmp/approvals.json",
            "--target-pending",
            "2",
            "--max-items",
            "8",
            "--freshness-minutes",
            "120",
            "--strict",
            "--output",
            "/tmp/report.md",
        ]
    )
    assert "ophtxn_daily_ops.py" in " ".join(cmd)
    assert "--action" in cmd and "morning" in cmd
    assert "--queue-path" in cmd and "/tmp/queue.jsonl" in cmd
    assert "--approvals-path" in cmd and "/tmp/approvals.json" in cmd
    assert "--target-pending" in cmd and "2" in cmd
    assert "--max-items" in cmd and "8" in cmd
    assert "--freshness-minutes" in cmd and "120" in cmd
    assert "--strict" in cmd
    assert "--output" in cmd and "/tmp/report.md" in cmd


def test_cli_ophtxn_daily_ops_cycle_action_forwards() -> None:
    cmd = _run_cli(["cli.py", "ophtxn-daily-ops", "--action", "cycle"])
    assert "ophtxn_daily_ops.py" in " ".join(cmd)
    assert "--action" in cmd and "cycle" in cmd


if __name__ == "__main__":
    test_cli_ophtxn_daily_ops_forwards_flags()
    test_cli_ophtxn_daily_ops_cycle_action_forwards()
    print("✓ CLI ophtxn-daily-ops forwarding tests passed")
