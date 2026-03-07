#!/usr/bin/env python3
"""Regression tests for ophtxn-ops-pack CLI forwarding."""

from __future__ import annotations

import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import cli as cli_mod  # noqa: E402


def test_cli_ophtxn_ops_pack_forwards_flags() -> None:
    captured: dict[str, list[str]] = {}
    original_run = cli_mod._run
    original_argv = list(sys.argv)
    try:
        cli_mod._run = lambda cmd: captured.setdefault("cmd", cmd) and 0  # type: ignore[assignment]
        sys.argv = [
            "cli.py",
            "ophtxn-ops-pack",
            "--action",
            "run",
            "--strict",
            "--timeout",
            "180",
            "--approval-source",
            "phase3_opportunity_queue",
            "--approval-decision",
            "defer",
            "--approval-batch-size",
            "4",
            "--safe-max-priority",
            "low",
            "--safe-max-risk",
            "medium",
        ]
        rc = cli_mod.main()
    finally:
        cli_mod._run = original_run
        sys.argv = original_argv

    assert rc == 0
    cmd = captured.get("cmd") or []
    assert "ophtxn_ops_pack.py" in " ".join(cmd)
    assert "--action" in cmd and "run" in cmd
    assert "--strict" in cmd
    assert "--timeout" in cmd and "180" in cmd
    assert "--approval-source" in cmd and "phase3_opportunity_queue" in cmd
    assert "--approval-decision" in cmd and "defer" in cmd
    assert "--approval-batch-size" in cmd and "4" in cmd
    assert "--safe-max-priority" in cmd and "low" in cmd
    assert "--safe-max-risk" in cmd and "medium" in cmd


if __name__ == "__main__":
    test_cli_ophtxn_ops_pack_forwards_flags()
    print("✓ CLI ophtxn-ops-pack forwarding tests passed")
