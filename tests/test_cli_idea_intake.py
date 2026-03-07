#!/usr/bin/env python3
"""Regression tests for idea-intake CLI forwarding."""

from __future__ import annotations

import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import cli as cli_mod  # noqa: E402


def test_cli_idea_intake_forwards_flags() -> None:
    captured: dict[str, list[str]] = {}
    original_run = cli_mod._run
    original_argv = list(sys.argv)
    try:
        cli_mod._run = lambda cmd: captured.setdefault("cmd", cmd) and 0  # type: ignore[assignment]
        sys.argv = [
            "cli.py",
            "idea-intake",
            "--action",
            "process",
            "--intake-path",
            "/tmp/intake.jsonl",
            "--state-path",
            "/tmp/state.json",
            "--policy-path",
            "/tmp/policy.json",
            "--max-items",
            "25",
            "--min-score",
            "41",
            "--queue-approvals",
            "--queue-limit",
            "4",
            "--queue-min-score",
            "72",
            "--strict",
        ]
        rc = cli_mod.main()
    finally:
        cli_mod._run = original_run
        sys.argv = original_argv

    assert rc == 0
    cmd = captured.get("cmd") or []
    assert "idea_intake.py" in " ".join(cmd)
    assert "--action" in cmd and "process" in cmd
    assert "--intake-path" in cmd and "/tmp/intake.jsonl" in cmd
    assert "--state-path" in cmd and "/tmp/state.json" in cmd
    assert "--policy-path" in cmd and "/tmp/policy.json" in cmd
    assert "--max-items" in cmd and "25" in cmd
    assert "--min-score" in cmd and "41.0" in cmd
    assert "--queue-approvals" in cmd
    assert "--queue-limit" in cmd and "4" in cmd
    assert "--queue-min-score" in cmd and "72.0" in cmd
    assert "--strict" in cmd


if __name__ == "__main__":
    test_cli_idea_intake_forwards_flags()
    print("✓ CLI idea-intake forwarding tests passed")
