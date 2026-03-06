#!/usr/bin/env python3
"""Regression tests for chronicle-approve CLI forwarding."""

from __future__ import annotations

import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import cli as cli_mod  # noqa: E402


def test_cli_chronicle_approve_forwards_flags() -> None:
    captured: dict[str, list[str]] = {}
    original_run = cli_mod._run
    original_argv = list(sys.argv)
    try:
        cli_mod._run = lambda cmd: captured.setdefault("cmd", cmd) and 0  # type: ignore[assignment]
        sys.argv = [
            "cli.py",
            "chronicle-approve",
            "--action",
            "decide",
            "--approvals-path",
            "/tmp/approvals.json",
            "--source",
            "chronicle_refinement_queue",
            "--source",
            "manual_queue",
            "--limit",
            "9",
            "--decision",
            "approve",
            "--proposal-id",
            "CHR-CRB-xyz",
            "--decided-by",
            "payton",
            "--note",
            "approved for execution board",
        ]
        rc = cli_mod.main()
    finally:
        cli_mod._run = original_run
        sys.argv = original_argv

    assert rc == 0
    cmd = captured.get("cmd") or []
    assert "chronicle_approve.py" in " ".join(cmd)
    assert "--action" in cmd and "decide" in cmd
    assert "--approvals-path" in cmd and "/tmp/approvals.json" in cmd
    assert cmd.count("--source") == 2
    assert "chronicle_refinement_queue" in cmd
    assert "manual_queue" in cmd
    assert "--limit" in cmd and "9" in cmd
    assert "--decision" in cmd and "approve" in cmd
    assert "--proposal-id" in cmd and "CHR-CRB-xyz" in cmd
    assert "--decided-by" in cmd and "payton" in cmd
    assert "--note" in cmd and "approved for execution board" in cmd


if __name__ == "__main__":
    test_cli_chronicle_approve_forwards_flags()
    print("✓ CLI chronicle-approve forwarding tests passed")
