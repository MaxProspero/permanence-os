#!/usr/bin/env python3
"""Tests for discord_telegram_relay helpers."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import scripts.discord_telegram_relay as relay_mod  # noqa: E402


def test_discord_feeds_filters_rows() -> None:
    rows = [
        {"name": "A", "platform": "discord", "enabled": True, "channel_id": "111"},
        {"name": "B", "platform": "discord", "enabled": False, "channel_id": "222"},
        {"name": "C", "platform": "discord", "channel_id": ""},
        {"name": "D", "platform": "reddit", "url": "https://example.com"},
    ]
    feeds = relay_mod._discord_feeds(rows)
    assert len(feeds) == 1
    assert feeds[0]["name"] == "A"


def test_extract_message_uses_attachment_fallback_and_link() -> None:
    item = {
        "id": "9001",
        "guild_id": "7001",
        "timestamp": "2026-03-03T16:00:00+00:00",
        "attachments": [{"filename": "pov.jpg", "url": "https://cdn.example/pov.jpg"}],
        "author": {"username": "payton"},
    }
    row = relay_mod._extract_message(item, source_name="Discord Alpha", channel_id="8001")
    assert row is not None
    assert row["source"] == "Discord Alpha"
    assert row["sender"] == "payton"
    assert "pov.jpg" in row["content"]
    assert row["link"].endswith("/7001/8001/9001")


def test_split_chunks_respects_max_chars() -> None:
    text = "line1\nline2\nline3\nline4\n"
    chunks = relay_mod._split_chunks(text, max_chars=12)
    assert len(chunks) >= 2
    assert all(len(chunk) <= 13 for chunk in chunks)


def test_build_digest_contains_sender_and_source() -> None:
    digest = relay_mod._build_digest(
        [
            {
                "source": "Discord Alpha",
                "sender": "trader",
                "content": "Breakout alert",
                "link": "https://discord.com/channels/1/2/3",
                "message_id": "123",
            }
        ]
    )
    assert "Discord Alpha" in digest
    assert "trader" in digest
    assert "Breakout alert" in digest
    assert "discord.com/channels/1/2/3" in digest


def test_parse_keywords_from_list_and_string() -> None:
    assert relay_mod._parse_keywords("Alpha, beta ,ALPHA") == ["alpha", "beta"]
    assert relay_mod._parse_keywords(["  one ", "two", "one"]) == ["one", "two"]


def test_passes_feed_filters_include_exclude_min_chars() -> None:
    message = {"content": "Gold breakout alert now"}
    feed = {"include_keywords": ["gold", "xauusd"], "exclude_keywords": ["spam"], "min_chars": 8}
    assert relay_mod._passes_feed_filters(message, feed) is True
    assert relay_mod._passes_feed_filters({"content": "short"}, feed) is False
    assert relay_mod._passes_feed_filters({"content": "xauusd spam signal"}, feed) is False
    assert relay_mod._passes_feed_filters({"content": "equities only"}, feed) is False


def test_should_escalate_respects_priority_and_keywords() -> None:
    message = {"content": "critical payment outage detected"}
    feed = {"priority": "high", "escalation_keywords": ["payment", "outage"]}
    assert relay_mod._should_escalate(message, feed, default_keywords=[], min_priority="high") is True
    assert relay_mod._should_escalate(message, {"priority": "low"}, default_keywords=["payment"], min_priority="high") is False


def test_sort_messages_prioritizes_feed_priority() -> None:
    rows = [
        {"message_id": "2", "feed_priority": "normal"},
        {"message_id": "1", "feed_priority": "urgent"},
        {"message_id": "3", "feed_priority": "high"},
    ]
    sorted_rows = relay_mod._sort_messages(rows)
    assert [r["message_id"] for r in sorted_rows] == ["1", "3", "2"]


def test_escalation_key_and_load_existing_keys() -> None:
    row = {"channel_id": "123", "message_id": "456"}
    assert relay_mod._escalation_key(row) == "123:456"
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "escalations.jsonl"
        path.write_text(
            '{"channel_id":"123","message_id":"456"}\n{"channel_id":"999","message_id":"1"}\n',
            encoding="utf-8",
        )
        keys = relay_mod._load_existing_escalation_keys(path)
        assert "123:456" in keys
        assert "999:1" in keys


def test_build_escalation_message_includes_priority_and_sender() -> None:
    text = relay_mod._build_escalation_message(
        [
            {
                "source": "Permanence",
                "priority": "urgent",
                "sender": "ops-bot",
                "message": "critical outage",
                "link": "https://discord.com/channels/1/2/3",
            }
        ]
    )
    assert "[urgent]" in text
    assert "ops-bot" in text
    assert "critical outage" in text


def test_mirror_messages_to_intake_writes_and_dedupes() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        intake_path = Path(tmp) / "telegram_share_intake.jsonl"
        rows = [
            {
                "source": "Permanence",
                "channel_id": "1478",
                "message_id": "9001",
                "sender": "ops-bot",
                "content": "critical outage",
                "link": "https://discord.com/channels/1/2/3",
                "feed_priority": "urgent",
            }
        ]
        first = relay_mod._mirror_messages_to_intake(rows, intake_path=intake_path)
        second = relay_mod._mirror_messages_to_intake(rows, intake_path=intake_path)
        assert first == 1
        assert second == 0
        lines = intake_path.read_text(encoding="utf-8").splitlines()
        assert len(lines) == 1
        assert "discord:1478:9001" in lines[0]


if __name__ == "__main__":
    test_discord_feeds_filters_rows()
    test_extract_message_uses_attachment_fallback_and_link()
    test_split_chunks_respects_max_chars()
    test_build_digest_contains_sender_and_source()
    test_parse_keywords_from_list_and_string()
    test_passes_feed_filters_include_exclude_min_chars()
    test_should_escalate_respects_priority_and_keywords()
    test_sort_messages_prioritizes_feed_priority()
    test_escalation_key_and_load_existing_keys()
    test_build_escalation_message_includes_priority_and_sender()
    test_mirror_messages_to_intake_writes_and_dedupes()
    print("✓ Discord Telegram relay tests passed")
