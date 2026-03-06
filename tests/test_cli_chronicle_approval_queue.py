#!/usr/bin/env python3
"""Regression tests for chronicle-approval-queue CLI forwarding."""

from __future__ import annotations

import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import cli as cli_mod  # noqa: E402


def test_cli_chronicle_approval_queue_forwards_flags() -> None:
    captured: dict[str, list[str]] = {}
    original_run = cli_mod._run
    original_argv = list(sys.argv)
    try:
        cli_mod._run = lambda cmd: captured.setdefault("cmd", cmd) and 0  # type: ignore[assignment]
        sys.argv = [
            "cli.py",
            "chronicle-approval-queue",
            "--force-policy",
            "--max-items",
            "7",
            "--no-canon-checks",
        ]
        rc = cli_mod.main()
    finally:
        cli_mod._run = original_run
        sys.argv = original_argv

    assert rc == 0
    cmd = captured.get("cmd") or []
    assert "chronicle_approval_queue.py" in " ".join(cmd)
    assert "--force-policy" in cmd
    assert "--max-items" in cmd and "7" in cmd
    assert "--no-canon-checks" in cmd


if __name__ == "__main__":
    test_cli_chronicle_approval_queue_forwards_flags()
    print("✓ CLI chronicle-approval-queue forwarding tests passed")
