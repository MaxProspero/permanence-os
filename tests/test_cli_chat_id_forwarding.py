#!/usr/bin/env python3
"""Regression tests for forwarding negative Telegram chat ids from CLI wrappers."""

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


def test_telegram_control_forwards_negative_chat_id_with_equals() -> None:
    cmd = _run_cli(["cli.py", "telegram-control", "--action", "poll", "--chat-id=-1001234567890"])
    assert "--chat-id=-1001234567890" in cmd


def test_telegram_control_forwards_negative_allowlist_chat_id_with_equals() -> None:
    cmd = _run_cli(
        [
            "cli.py",
            "telegram-control",
            "--action",
            "poll",
            "--enable-commands",
            "--command-allow-chat-id=-1001234567890",
        ]
    )
    assert "--command-allow-chat-id=-1001234567890" in cmd


def test_discord_relay_forwards_negative_chat_id_with_equals() -> None:
    cmd = _run_cli(["cli.py", "discord-telegram-relay", "--action", "status", "--chat-id=-1001234567890"])
    assert "--chat-id=-1001234567890" in cmd


def test_terminal_queue_forwards_negative_chat_id_with_equals() -> None:
    cmd = _run_cli(["cli.py", "terminal-task-queue", "--action", "list", "--chat-id=-1001234567890"])
    assert "--chat-id=-1001234567890" in cmd


if __name__ == "__main__":
    test_telegram_control_forwards_negative_chat_id_with_equals()
    test_telegram_control_forwards_negative_allowlist_chat_id_with_equals()
    test_discord_relay_forwards_negative_chat_id_with_equals()
    test_terminal_queue_forwards_negative_chat_id_with_equals()
    print("✓ CLI chat-id forwarding tests passed")
