#!/usr/bin/env python3
"""Regression tests for platform-change-watch CLI forwarding."""

from __future__ import annotations

import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import cli as cli_mod  # noqa: E402


def test_cli_platform_change_watch_forwards_flags() -> None:
    captured: dict[str, list[str]] = {}
    original_run = cli_mod._run
    original_argv = list(sys.argv)
    try:
        cli_mod._run = lambda cmd: captured.setdefault("cmd", cmd) and 0  # type: ignore[assignment]
        sys.argv = [
            "cli.py",
            "platform-change-watch",
            "--watchlist-path",
            "/tmp/watch.json",
            "--email-path",
            "/tmp/email.json",
            "--queue-path",
            "/tmp/queue.jsonl",
            "--scan-root",
            "/tmp/code",
            "--lookback-days",
            "21",
            "--min-score",
            "42",
            "--max-items",
            "12",
            "--strict",
            "--no-queue",
        ]
        rc = cli_mod.main()
    finally:
        cli_mod._run = original_run
        sys.argv = original_argv

    assert rc == 0
    cmd = captured.get("cmd") or []
    assert "platform_change_watch.py" in " ".join(cmd)
    assert "--watchlist-path" in cmd
    assert "/tmp/watch.json" in cmd
    assert "--email-path" in cmd
    assert "/tmp/email.json" in cmd
    assert "--queue-path" in cmd
    assert "/tmp/queue.jsonl" in cmd
    assert "--scan-root" in cmd
    assert "/tmp/code" in cmd
    assert "--lookback-days" in cmd
    assert "21" in cmd
    assert "--min-score" in cmd
    assert "42.0" in cmd
    assert "--max-items" in cmd
    assert "12" in cmd
    assert "--strict" in cmd
    assert "--no-queue" in cmd


if __name__ == "__main__":
    test_cli_platform_change_watch_forwards_flags()
    print("✓ CLI platform-change-watch forwarding tests passed")
