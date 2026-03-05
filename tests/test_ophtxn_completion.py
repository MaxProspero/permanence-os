#!/usr/bin/env python3
"""Tests for ophtxn completion scoring."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import scripts.ophtxn_completion as mod  # noqa: E402


def _write_tool_payload(path: Path, prefix: str, payload: dict) -> None:
    path.mkdir(parents=True, exist_ok=True)
    row = path / f"{prefix}_20260305-000000.json"
    row.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def test_ophtxn_completion_scores_high_when_all_core_checks_ready() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        tool = root / "tool"
        working = root / "working"
        inbox = root / "inbox"
        inbox.mkdir(parents=True, exist_ok=True)
        (inbox / "telegram_share_intake.jsonl").write_text(
            json.dumps({"text": "shared memory row"}) + "\n",
            encoding="utf-8",
        )

        _write_tool_payload(tool, "integration_readiness", {"blocked": False})
        _write_tool_payload(
            tool,
            "comms_status",
            {"warnings": [], "launchd": {"installed": True, "state": "running"}},
        )
        _write_tool_payload(tool, "comms_doctor", {"warnings": []})
        _write_tool_payload(
            tool,
            "telegram_control",
            {"chat_agent_enabled": True, "target_chat_ids": ["-1003837160764", "8693377286"]},
        )
        _write_tool_payload(tool, "discord_telegram_relay", {"active_feeds": 1})
        _write_tool_payload(tool, "ophtxn_brain", {"chunk_count": 240})
        _write_tool_payload(tool, "self_improvement", {"policy_enabled": True, "pending_count": 1})
        _write_tool_payload(tool, "governed_learning", {"policy_enabled": True})
        _write_tool_payload(tool, "terminal_task_queue", {"pending_count": 1})
        _write_tool_payload(
            tool,
            "x_account_watch",
            {"watched_accounts": [{"handle": "a"}, {"handle": "b"}, {"handle": "c"}]},
        )

        original_working = mod.WORKING_DIR
        try:
            mod.WORKING_DIR = working
            payloads = mod._load_payloads(root=tool)
            scored = mod._score_payloads(payloads)
        finally:
            mod.WORKING_DIR = original_working

        assert int(scored.get("completion_pct", 0)) >= 95
        assert scored.get("blockers") == []


def test_ophtxn_completion_flags_learning_and_queue_blockers() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        tool = root / "tool"
        working = root / "working"

        _write_tool_payload(tool, "integration_readiness", {"blocked": False})
        _write_tool_payload(
            tool,
            "comms_status",
            {"warnings": [], "launchd": {"installed": True, "state": "running"}},
        )
        _write_tool_payload(tool, "comms_doctor", {"warnings": []})
        _write_tool_payload(tool, "telegram_control", {"chat_agent_enabled": True, "target_chat_ids": ["-100"]})
        _write_tool_payload(tool, "discord_telegram_relay", {"active_feeds": 1})
        _write_tool_payload(tool, "ophtxn_brain", {"chunk_count": 200})
        _write_tool_payload(tool, "self_improvement", {"policy_enabled": True, "pending_count": 4})
        _write_tool_payload(tool, "governed_learning", {"policy_enabled": False})
        _write_tool_payload(tool, "terminal_task_queue", {"pending_count": 6})
        _write_tool_payload(
            tool,
            "x_account_watch",
            {"watched_accounts": [{"handle": "a"}, {"handle": "b"}]},
        )

        original_working = mod.WORKING_DIR
        try:
            mod.WORKING_DIR = working
            payloads = mod._load_payloads(root=tool)
            scored = mod._score_payloads(payloads)
        finally:
            mod.WORKING_DIR = original_working

        blockers_text = "\n".join(scored.get("blockers") or [])
        assert "Governed learning policy disabled." in blockers_text
        assert "Terminal queue backlog high" in blockers_text
        assert int(scored.get("completion_pct", 0)) < 90


def test_ophtxn_completion_treats_launchd_idle_xpcproxy_as_healthy() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        tool = root / "tool"
        working = root / "working"
        inbox = root / "inbox"
        inbox.mkdir(parents=True, exist_ok=True)
        (inbox / "telegram_share_intake.jsonl").write_text(
            json.dumps({"text": "shared memory row"}) + "\n",
            encoding="utf-8",
        )

        _write_tool_payload(tool, "integration_readiness", {"blocked": False})
        _write_tool_payload(
            tool,
            "comms_status",
            {"warnings": [], "launchd": {"installed": True, "state": "xpcproxy", "last_exit_code": 0}},
        )
        _write_tool_payload(tool, "comms_doctor", {"warnings": []})
        _write_tool_payload(
            tool,
            "telegram_control",
            {"chat_agent_enabled": True, "target_chat_ids": ["-1003837160764", "8693377286"]},
        )
        _write_tool_payload(tool, "discord_telegram_relay", {"active_feeds": 1})
        _write_tool_payload(tool, "ophtxn_brain", {"chunk_count": 240})
        _write_tool_payload(tool, "self_improvement", {"policy_enabled": True, "pending_count": 0})
        _write_tool_payload(tool, "governed_learning", {"policy_enabled": True})
        _write_tool_payload(tool, "terminal_task_queue", {"pending_count": 0})
        _write_tool_payload(
            tool,
            "x_account_watch",
            {"watched_accounts": [{"handle": "a"}, {"handle": "b"}, {"handle": "c"}]},
        )

        original_working = mod.WORKING_DIR
        try:
            mod.WORKING_DIR = working
            payloads = mod._load_payloads(root=tool)
            scored = mod._score_payloads(payloads)
        finally:
            mod.WORKING_DIR = original_working

        blockers_text = "\n".join(scored.get("blockers") or [])
        assert "Comms loop automation is not running." not in blockers_text


if __name__ == "__main__":
    test_ophtxn_completion_scores_high_when_all_core_checks_ready()
    test_ophtxn_completion_flags_learning_and_queue_blockers()
    test_ophtxn_completion_treats_launchd_idle_xpcproxy_as_healthy()
    print("✓ Ophtxn completion tests passed")
