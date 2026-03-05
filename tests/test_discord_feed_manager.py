#!/usr/bin/env python3
"""Tests for discord_feed_manager utility."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import scripts.discord_feed_manager as manager_mod  # noqa: E402


def test_discord_feed_manager_add_enable_disable_remove() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        feeds_path = root / "social_research_feeds.json"
        feeds_path.write_text("[]\n", encoding="utf-8")

        rc_add = manager_mod.main(
            [
                "--action",
                "add",
                "--feeds-path",
                str(feeds_path),
                "--name",
                "Discord Test",
                "--channel-id",
                "1234567890",
                "--invite-url",
                "https://discord.gg/test",
                "--max-messages",
                "42",
                "--priority",
                "high",
                "--include-keyword",
                "gold",
                "--exclude-keyword",
                "spam",
                "--min-chars",
                "15",
            ]
        )
        assert rc_add == 0
        rows = json.loads(feeds_path.read_text(encoding="utf-8"))
        assert len(rows) == 1
        assert rows[0]["platform"] == "discord"
        assert rows[0]["enabled"] is True
        assert rows[0]["channel_id"] == "1234567890"
        assert int(rows[0]["max_messages"]) == 42
        assert rows[0]["priority"] == "high"
        assert rows[0]["include_keywords"] == ["gold"]
        assert rows[0]["exclude_keywords"] == ["spam"]
        assert int(rows[0]["min_chars"]) == 15

        rc_disable = manager_mod.main(
            [
                "--action",
                "disable",
                "--feeds-path",
                str(feeds_path),
                "--channel-id",
                "1234567890",
            ]
        )
        assert rc_disable == 0
        rows = json.loads(feeds_path.read_text(encoding="utf-8"))
        assert rows[0]["enabled"] is False

        rc_enable = manager_mod.main(
            [
                "--action",
                "enable",
                "--feeds-path",
                str(feeds_path),
                "--name",
                "Discord Test",
            ]
        )
        assert rc_enable == 0
        rows = json.loads(feeds_path.read_text(encoding="utf-8"))
        assert rows[0]["enabled"] is True

        rc_update_filters = manager_mod.main(
            [
                "--action",
                "add",
                "--feeds-path",
                str(feeds_path),
                "--channel-id",
                "1234567890",
                "--include-keyword",
                "xauusd, breakout",
                "--clear-filters",
                "--priority",
                "urgent",
            ]
        )
        assert rc_update_filters == 0
        rows = json.loads(feeds_path.read_text(encoding="utf-8"))
        assert rows[0]["priority"] == "urgent"
        assert rows[0]["include_keywords"] == ["xauusd", "breakout"]
        assert "exclude_keywords" not in rows[0]
        assert "min_chars" not in rows[0]

        rc_remove = manager_mod.main(
            [
                "--action",
                "remove",
                "--feeds-path",
                str(feeds_path),
                "--channel-id",
                "1234567890",
            ]
        )
        assert rc_remove == 0
        rows = json.loads(feeds_path.read_text(encoding="utf-8"))
        assert rows == []


def test_discord_feed_manager_add_with_channel_link() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        feeds_path = root / "social_research_feeds.json"
        feeds_path.write_text("[]\n", encoding="utf-8")

        rc = manager_mod.main(
            [
                "--action",
                "add",
                "--feeds-path",
                str(feeds_path),
                "--name",
                "Discord Link Feed",
                "--channel-link",
                "https://discord.com/channels/1478286326817362022/1478286327727390884",
            ]
        )
        assert rc == 0
        rows = json.loads(feeds_path.read_text(encoding="utf-8"))
        assert len(rows) == 1
        assert rows[0]["channel_id"] == "1478286327727390884"


if __name__ == "__main__":
    test_discord_feed_manager_add_enable_disable_remove()
    test_discord_feed_manager_add_with_channel_link()
    print("✓ Discord feed manager tests passed")
