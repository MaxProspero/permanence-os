#!/usr/bin/env python3
"""Regression tests for chronicle-refinement CLI forwarding."""

from __future__ import annotations

import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import cli as cli_mod  # noqa: E402


def test_cli_chronicle_refinement_forwards_flags() -> None:
    captured: dict[str, list[str]] = {}
    original_run = cli_mod._run
    original_argv = list(sys.argv)
    try:
        cli_mod._run = lambda cmd: captured.setdefault("cmd", cmd) and 0  # type: ignore[assignment]
        sys.argv = [
            "cli.py",
            "chronicle-refinement",
            "--report-json",
            "/tmp/chronicle.json",
            "--max-backlog-items",
            "5",
            "--max-canon-checks",
            "2",
            "--backlog-path",
            "/tmp/refinement.json",
            "--output",
            "/tmp/refinement.md",
            "--no-sync-backlog",
            "--strict",
        ]
        rc = cli_mod.main()
    finally:
        cli_mod._run = original_run
        sys.argv = original_argv

    assert rc == 0
    cmd = captured.get("cmd") or []
    assert "chronicle_refinement.py" in " ".join(cmd)
    assert "--report-json" in cmd and "/tmp/chronicle.json" in cmd
    assert "--max-backlog-items" in cmd and "5" in cmd
    assert "--max-canon-checks" in cmd and "2" in cmd
    assert "--backlog-path" in cmd and "/tmp/refinement.json" in cmd
    assert "--output" in cmd and "/tmp/refinement.md" in cmd
    assert "--no-sync-backlog" in cmd
    assert "--strict" in cmd


if __name__ == "__main__":
    test_cli_chronicle_refinement_forwards_flags()
    print("✓ CLI chronicle-refinement forwarding tests passed")
