#!/usr/bin/env python3
"""Regression tests for no-spend-audit CLI forwarding."""

from __future__ import annotations

import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import cli as cli_mod  # noqa: E402


def test_cli_no_spend_audit_forwards_flags() -> None:
    captured: dict[str, list[str]] = {}
    original_run = cli_mod._run
    original_argv = list(sys.argv)
    try:
        cli_mod._run = lambda cmd: captured.setdefault("cmd", cmd) and 0  # type: ignore[assignment]
        sys.argv = [
            "cli.py",
            "no-spend-audit",
            "--env-path",
            "/tmp/.env",
            "--calls-log",
            "/tmp/model_calls.jsonl",
            "--lookback-hours",
            "36",
            "--max-recent-calls",
            "500",
            "--strict",
        ]
        rc = cli_mod.main()
    finally:
        cli_mod._run = original_run
        sys.argv = original_argv

    assert rc == 0
    cmd = captured.get("cmd") or []
    assert "no_spend_audit.py" in " ".join(cmd)
    assert "--env-path" in cmd and "/tmp/.env" in cmd
    assert "--calls-log" in cmd and "/tmp/model_calls.jsonl" in cmd
    assert "--lookback-hours" in cmd and "36" in cmd
    assert "--max-recent-calls" in cmd and "500" in cmd
    assert "--strict" in cmd


if __name__ == "__main__":
    test_cli_no_spend_audit_forwards_flags()
    print("✓ CLI no-spend-audit forwarding tests passed")
