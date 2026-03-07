#!/usr/bin/env python3
"""Regression tests for approval-triage CLI forwarding."""

from __future__ import annotations

import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import cli as cli_mod  # noqa: E402


def test_cli_approval_triage_forwards_flags() -> None:
    captured: dict[str, list[str]] = {}
    original_run = cli_mod._run
    original_argv = list(sys.argv)
    try:
        cli_mod._run = lambda cmd: captured.setdefault("cmd", cmd) and 0  # type: ignore[assignment]
        sys.argv = [
            "cli.py",
            "approval-triage",
            "--action",
            "decide",
            "--approvals-path",
            "/tmp/approvals.json",
            "--source",
            "phase3_opportunity_queue",
            "--limit",
            "7",
            "--decision",
            "approve",
            "--proposal-id",
            "APR-123",
            "--decided-by",
            "payton",
            "--note",
            "approve next from telegram",
        ]
        rc = cli_mod.main()
    finally:
        cli_mod._run = original_run
        sys.argv = original_argv

    assert rc == 0
    cmd = captured.get("cmd") or []
    assert "approval_triage.py" in " ".join(cmd)
    assert "--action" in cmd and "decide" in cmd
    assert "--approvals-path" in cmd and "/tmp/approvals.json" in cmd
    assert "--source" in cmd and "phase3_opportunity_queue" in cmd
    assert "--limit" in cmd and "7" in cmd
    assert "--decision" in cmd and "approve" in cmd
    assert "--proposal-id" in cmd and "APR-123" in cmd
    assert "--decided-by" in cmd and "payton" in cmd
    assert "--note" in cmd and "approve next from telegram" in cmd


def test_cli_approval_triage_forwards_batch_flags() -> None:
    captured: dict[str, list[str]] = {}
    original_run = cli_mod._run
    original_argv = list(sys.argv)
    try:
        cli_mod._run = lambda cmd: captured.setdefault("cmd", cmd) and 0  # type: ignore[assignment]
        sys.argv = [
            "cli.py",
            "approval-triage",
            "--action",
            "decide-batch",
            "--decision",
            "approve",
            "--batch-size",
            "5",
            "--decided-by",
            "telegram",
        ]
        rc = cli_mod.main()
    finally:
        cli_mod._run = original_run
        sys.argv = original_argv

    assert rc == 0
    cmd = captured.get("cmd") or []
    assert "approval_triage.py" in " ".join(cmd)
    assert "--action" in cmd and "decide-batch" in cmd
    assert "--decision" in cmd and "approve" in cmd
    assert "--batch-size" in cmd and "5" in cmd
    assert "--decided-by" in cmd and "telegram" in cmd


def test_cli_approval_triage_forwards_safe_batch_flags() -> None:
    captured: dict[str, list[str]] = {}
    original_run = cli_mod._run
    original_argv = list(sys.argv)
    try:
        cli_mod._run = lambda cmd: captured.setdefault("cmd", cmd) and 0  # type: ignore[assignment]
        sys.argv = [
            "cli.py",
            "approval-triage",
            "--action",
            "decide-batch-safe",
            "--decision",
            "approve",
            "--batch-size",
            "4",
            "--safe-max-priority",
            "low",
            "--safe-max-risk",
            "medium",
            "--source",
            "phase3_opportunity_queue",
        ]
        rc = cli_mod.main()
    finally:
        cli_mod._run = original_run
        sys.argv = original_argv

    assert rc == 0
    cmd = captured.get("cmd") or []
    assert "approval_triage.py" in " ".join(cmd)
    assert "--action" in cmd and "decide-batch-safe" in cmd
    assert "--safe-max-priority" in cmd and "low" in cmd
    assert "--safe-max-risk" in cmd and "medium" in cmd
    assert "--source" in cmd and "phase3_opportunity_queue" in cmd


if __name__ == "__main__":
    test_cli_approval_triage_forwards_flags()
    test_cli_approval_triage_forwards_batch_flags()
    test_cli_approval_triage_forwards_safe_batch_flags()
    print("✓ CLI approval-triage forwarding tests passed")
