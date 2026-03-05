#!/usr/bin/env python3
"""Tests for comms_doctor helpers."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import scripts.comms_doctor as mod  # noqa: E402


def test_feed_stats_counts_enabled_rows() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "feeds.json"
        payload = [
            {"platform": "discord", "enabled": True, "channel_id": "111"},
            {"platform": "discord", "enabled": False, "channel_id": "222"},
            {"platform": "discord", "enabled": True, "channel_id": ""},
            {"platform": "telegram", "enabled": True, "channel_id": "333"},
        ]
        path.write_text(json.dumps(payload), encoding="utf-8")
        stats = mod._feed_stats(path)
        assert stats["exists"] is True
        assert stats["discord_rows"] == 3
        assert stats["enabled_discord_rows"] == 2
        assert stats["enabled_with_channel_id"] == 1


def test_component_freshness_missing() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        old_tool_dir = mod.TOOL_DIR
        mod.TOOL_DIR = Path(tmp)
        try:
            row = mod._component_freshness("missing_prefix", max_stale_minutes=10)
        finally:
            mod.TOOL_DIR = old_tool_dir
        assert row["status"] == "missing"
        assert row["present"] is False
        assert row["stale_minutes"] is None


def test_escalation_stats_counts_recent_rows() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "escalations.jsonl"
        rows = [
            {"created_at": "2026-03-03T12:00:00+00:00"},
            {"created_at": "2020-01-01T00:00:00+00:00"},
        ]
        with path.open("w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row) + "\n")
        stats = mod._escalation_stats(path, lookback_hours=48)
        assert stats["exists"] is True
        assert stats["total"] == 2


def test_build_payload_warning_shape() -> None:
    old_env = dict(os.environ)
    old_feeds = mod.FEEDS_PATH
    old_launchd_state = mod._launchd_state
    old_component_freshness = mod._component_freshness
    try:
        os.environ.pop("PERMANENCE_DISCORD_BOT_TOKEN", None)
        os.environ.pop("PERMANENCE_TELEGRAM_BOT_TOKEN", None)
        os.environ.pop("PERMANENCE_TELEGRAM_CHAT_ID", None)

        with tempfile.TemporaryDirectory() as tmp:
            feeds_path = Path(tmp) / "feeds.json"
            feeds_path.write_text("[]", encoding="utf-8")
            mod.FEEDS_PATH = feeds_path

            mod._launchd_state = lambda _label: {  # type: ignore[assignment]
                "installed": False,
                "state": "missing",
                "runs": 0,
                "last_exit_code": None,
            }
            mod._component_freshness = lambda prefix, max_stale_minutes: {  # type: ignore[assignment]
                "prefix": prefix,
                "status": "missing",
                "stale_minutes": None,
                "max_stale_minutes": max_stale_minutes,
                "path": "",
                "present": False,
            }

            payload = mod._build_payload(
                max_stale_minutes=30,
                digest_max_stale_minutes=1440,
                require_digest=True,
                require_escalation_digest=True,
                check_live=False,
                live_timeout=5,
                auto_repair=False,
                repair_timeout=10,
            )
    finally:
        os.environ.clear()
        os.environ.update(old_env)
        mod.FEEDS_PATH = old_feeds
        mod._launchd_state = old_launchd_state
        mod._component_freshness = old_component_freshness

    assert isinstance(payload, dict)
    assert "warnings" in payload
    assert "recommended_actions" in payload
    assert "comms_escalation_digest" in payload.get("launchd", {})
    assert "comms_escalation_digest" in payload.get("components", {})
    assert len(payload["warnings"]) >= 4


def test_live_token_checks_shape() -> None:
    old_tg = mod._live_telegram_check
    old_dc = mod._live_discord_check
    try:
        mod._live_telegram_check = lambda timeout: {  # type: ignore[assignment]
            "checked": True,
            "ok": True,
            "status_code": 200,
            "error": "",
        }
        mod._live_discord_check = lambda timeout: {  # type: ignore[assignment]
            "checked": True,
            "ok": False,
            "status_code": 401,
            "error": "Unauthorized",
        }
        payload = mod._live_token_checks(timeout=3)
    finally:
        mod._live_telegram_check = old_tg
        mod._live_discord_check = old_dc
    assert "telegram" in payload
    assert "discord" in payload
    assert payload["telegram"]["ok"] is True
    assert payload["discord"]["ok"] is False


if __name__ == "__main__":
    test_feed_stats_counts_enabled_rows()
    test_component_freshness_missing()
    test_escalation_stats_counts_recent_rows()
    test_build_payload_warning_shape()
    test_live_token_checks_shape()
    print("✓ Comms doctor tests passed")
