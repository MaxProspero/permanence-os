#!/usr/bin/env python3
"""Tests for social trend ingest."""

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import scripts.social_research_ingest as social_mod  # noqa: E402


def test_social_research_ingest_ranks_feed_items():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        outputs = root / "outputs"
        tool = root / "tool"
        working = root / "working"
        outputs.mkdir(parents=True, exist_ok=True)
        tool.mkdir(parents=True, exist_ok=True)
        working.mkdir(parents=True, exist_ok=True)

        feed_xml = working / "social_feed.xml"
        feed_xml.write_text(
            """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Demo Social Feed</title>
    <item>
      <title>AI automation playbook for SaaS growth</title>
      <description>Agents and automation workflows to monetize clips.</description>
      <link>https://example.com/social/1</link>
      <pubDate>Sun, 01 Mar 2026 16:00:00 GMT</pubDate>
    </item>
    <item>
      <title>Generic post</title>
      <description>Nothing notable</description>
      <link>https://example.com/social/2</link>
      <pubDate>Sun, 20 Feb 2026 16:00:00 GMT</pubDate>
    </item>
  </channel>
</rss>
""",
            encoding="utf-8",
        )

        feeds_path = working / "social_research_feeds.json"
        feeds_path.write_text(
            json.dumps(
                [
                    {
                        "name": "Local Demo Feed",
                        "platform": "reddit",
                        "url": f"file://{feed_xml}",
                    }
                ]
            )
            + "\n",
            encoding="utf-8",
        )

        original = {
            "OUTPUT_DIR": social_mod.OUTPUT_DIR,
            "TOOL_DIR": social_mod.TOOL_DIR,
            "WORKING_DIR": social_mod.WORKING_DIR,
            "FEEDS_PATH": social_mod.FEEDS_PATH,
        }
        env_original = os.environ.get("PERMANENCE_SOCIAL_KEYWORDS")
        try:
            social_mod.OUTPUT_DIR = outputs
            social_mod.TOOL_DIR = tool
            social_mod.WORKING_DIR = working
            social_mod.FEEDS_PATH = feeds_path
            os.environ["PERMANENCE_SOCIAL_KEYWORDS"] = "ai,automation,saas,monetize"
            rc = social_mod.main([])
        finally:
            social_mod.OUTPUT_DIR = original["OUTPUT_DIR"]
            social_mod.TOOL_DIR = original["TOOL_DIR"]
            social_mod.WORKING_DIR = original["WORKING_DIR"]
            social_mod.FEEDS_PATH = original["FEEDS_PATH"]
            if env_original is None:
                os.environ.pop("PERMANENCE_SOCIAL_KEYWORDS", None)
            else:
                os.environ["PERMANENCE_SOCIAL_KEYWORDS"] = env_original

        assert rc == 0
        latest = outputs / "social_research_ingest_latest.md"
        assert latest.exists()
        content = latest.read_text(encoding="utf-8")
        assert "Social Research Ingest" in content
        assert "AI automation playbook for SaaS growth" in content

        tool_files = sorted(tool.glob("social_research_ingest_*.json"))
        assert tool_files
        payload = json.loads(tool_files[-1].read_text(encoding="utf-8"))
        assert payload.get("item_count", 0) >= 1
        assert payload.get("filtered_out_count", 0) >= 1
        assert payload.get("policy_path", "").endswith("social_discernment_policy.json")
        top = payload.get("top_items") or []
        assert top
        assert "ai" in (top[0].get("matched_keywords") or [])


def test_social_research_ingest_x_query_feed():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        outputs = root / "outputs"
        tool = root / "tool"
        working = root / "working"
        outputs.mkdir(parents=True, exist_ok=True)
        tool.mkdir(parents=True, exist_ok=True)
        working.mkdir(parents=True, exist_ok=True)

        feeds_path = working / "social_research_feeds.json"
        feeds_path.write_text(
            json.dumps(
                [
                    {
                        "name": "X Demo Feed",
                        "platform": "x",
                        "query": "(ai OR automation) -is:retweet lang:en",
                        "max_results": 10,
                    }
                ]
            )
            + "\n",
            encoding="utf-8",
        )

        class _FakeResponse:
            status_code = 200

            def raise_for_status(self):
                return None

            def json(self):
                return {
                    "data": [
                        {
                            "id": "1900000000000000000",
                            "text": "AI automation workflow that helps small business operators.",
                            "created_at": "2026-03-01T16:00:00Z",
                        }
                    ]
                }

        original = {
            "OUTPUT_DIR": social_mod.OUTPUT_DIR,
            "TOOL_DIR": social_mod.TOOL_DIR,
            "WORKING_DIR": social_mod.WORKING_DIR,
            "FEEDS_PATH": social_mod.FEEDS_PATH,
        }
        env_original = os.environ.get("PERMANENCE_SOCIAL_READ_TOKEN")
        keywords_original = os.environ.get("PERMANENCE_SOCIAL_KEYWORDS")
        try:
            social_mod.OUTPUT_DIR = outputs
            social_mod.TOOL_DIR = tool
            social_mod.WORKING_DIR = working
            social_mod.FEEDS_PATH = feeds_path
            os.environ["PERMANENCE_SOCIAL_READ_TOKEN"] = "test-social-read-token"
            os.environ["PERMANENCE_SOCIAL_KEYWORDS"] = "ai,automation,business"
            with patch.object(social_mod.requests, "get", return_value=_FakeResponse()):
                rc = social_mod.main([])
        finally:
            social_mod.OUTPUT_DIR = original["OUTPUT_DIR"]
            social_mod.TOOL_DIR = original["TOOL_DIR"]
            social_mod.WORKING_DIR = original["WORKING_DIR"]
            social_mod.FEEDS_PATH = original["FEEDS_PATH"]
            if env_original is None:
                os.environ.pop("PERMANENCE_SOCIAL_READ_TOKEN", None)
            else:
                os.environ["PERMANENCE_SOCIAL_READ_TOKEN"] = env_original
            if keywords_original is None:
                os.environ.pop("PERMANENCE_SOCIAL_KEYWORDS", None)
            else:
                os.environ["PERMANENCE_SOCIAL_KEYWORDS"] = keywords_original

        assert rc == 0
        latest = outputs / "social_research_ingest_latest.md"
        assert latest.exists()
        content = latest.read_text(encoding="utf-8")
        assert "AI automation workflow" in content

        tool_files = sorted(tool.glob("social_research_ingest_*.json"))
        assert tool_files
        payload = json.loads(tool_files[-1].read_text(encoding="utf-8"))
        top = payload.get("top_items") or []
        assert top
        assert top[0].get("source") == "X Demo Feed"
        assert top[0].get("platform") == "x"
        assert top[0].get("link") == "https://x.com/i/web/status/1900000000000000000"
        assert payload.get("filtered_out_count", -1) >= 0


def test_social_research_ingest_discord_channel_feed():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        outputs = root / "outputs"
        tool = root / "tool"
        working = root / "working"
        outputs.mkdir(parents=True, exist_ok=True)
        tool.mkdir(parents=True, exist_ok=True)
        working.mkdir(parents=True, exist_ok=True)

        feeds_path = working / "social_research_feeds.json"
        feeds_path.write_text(
            json.dumps(
                [
                    {
                        "name": "Discord Strategy Server",
                        "platform": "discord",
                        "channel_id": "123456789012345678",
                        "max_messages": 20,
                    }
                ]
            )
            + "\n",
            encoding="utf-8",
        )

        class _FakeDiscordResponse:
            status_code = 200

            def raise_for_status(self):
                return None

            def json(self):
                return [
                    {
                        "id": "1900000000000000001",
                        "guild_id": "111111111111111111",
                        "content": "ICC XAUUSD setup: BOS + FVG alignment, risk controlled.",
                        "timestamp": "2026-03-01T18:15:00.000000+00:00",
                    }
                ]

        original = {
            "OUTPUT_DIR": social_mod.OUTPUT_DIR,
            "TOOL_DIR": social_mod.TOOL_DIR,
            "WORKING_DIR": social_mod.WORKING_DIR,
            "FEEDS_PATH": social_mod.FEEDS_PATH,
        }
        discord_token_original = os.environ.get("PERMANENCE_DISCORD_BOT_TOKEN")
        keywords_original = os.environ.get("PERMANENCE_SOCIAL_KEYWORDS")
        try:
            social_mod.OUTPUT_DIR = outputs
            social_mod.TOOL_DIR = tool
            social_mod.WORKING_DIR = working
            social_mod.FEEDS_PATH = feeds_path
            os.environ["PERMANENCE_DISCORD_BOT_TOKEN"] = "discord_bot_token_value_abcdefghijklmnopqrstuvwxyz_123456"
            os.environ["PERMANENCE_SOCIAL_KEYWORDS"] = "xauusd,icc,risk,setup"
            with patch.object(social_mod.requests, "get", return_value=_FakeDiscordResponse()):
                rc = social_mod.main([])
        finally:
            social_mod.OUTPUT_DIR = original["OUTPUT_DIR"]
            social_mod.TOOL_DIR = original["TOOL_DIR"]
            social_mod.WORKING_DIR = original["WORKING_DIR"]
            social_mod.FEEDS_PATH = original["FEEDS_PATH"]
            if discord_token_original is None:
                os.environ.pop("PERMANENCE_DISCORD_BOT_TOKEN", None)
            else:
                os.environ["PERMANENCE_DISCORD_BOT_TOKEN"] = discord_token_original
            if keywords_original is None:
                os.environ.pop("PERMANENCE_SOCIAL_KEYWORDS", None)
            else:
                os.environ["PERMANENCE_SOCIAL_KEYWORDS"] = keywords_original

        assert rc == 0
        tool_files = sorted(tool.glob("social_research_ingest_*.json"))
        assert tool_files
        payload = json.loads(tool_files[-1].read_text(encoding="utf-8"))
        top = payload.get("top_items") or []
        assert top
        assert top[0].get("source") == "Discord Strategy Server"
        assert top[0].get("platform") == "discord"
        assert "discord.com/channels/" in str(top[0].get("link") or "")


def test_social_research_ingest_youtube_channel_feed():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        outputs = root / "outputs"
        tool = root / "tool"
        working = root / "working"
        outputs.mkdir(parents=True, exist_ok=True)
        tool.mkdir(parents=True, exist_ok=True)
        working.mkdir(parents=True, exist_ok=True)

        feeds_path = working / "social_research_feeds.json"
        feeds_path.write_text(
            json.dumps(
                [
                    {
                        "name": "YouTube Market Reviewer",
                        "platform": "youtube",
                        "channel_id": "UC1234567890abcDEF",
                    }
                ]
            )
            + "\n",
            encoding="utf-8",
        )

        class _FakeYoutubeResponse:
            status_code = 200
            text = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <title>XAUUSD Backtest: Liquidity Sweep + FVG setup</title>
    <link rel="alternate" href="https://www.youtube.com/watch?v=abc123"/>
    <updated>2026-03-01T18:00:00+00:00</updated>
    <summary>Backtesting ICC concepts for gold and risk controls.</summary>
  </entry>
</feed>
"""

            def raise_for_status(self):
                return None

        original = {
            "OUTPUT_DIR": social_mod.OUTPUT_DIR,
            "TOOL_DIR": social_mod.TOOL_DIR,
            "WORKING_DIR": social_mod.WORKING_DIR,
            "FEEDS_PATH": social_mod.FEEDS_PATH,
        }
        keywords_original = os.environ.get("PERMANENCE_SOCIAL_KEYWORDS")
        try:
            social_mod.OUTPUT_DIR = outputs
            social_mod.TOOL_DIR = tool
            social_mod.WORKING_DIR = working
            social_mod.FEEDS_PATH = feeds_path
            os.environ["PERMANENCE_SOCIAL_KEYWORDS"] = "xauusd,backtest,liquidity"
            with patch.object(social_mod.requests, "get", return_value=_FakeYoutubeResponse()):
                rc = social_mod.main([])
        finally:
            social_mod.OUTPUT_DIR = original["OUTPUT_DIR"]
            social_mod.TOOL_DIR = original["TOOL_DIR"]
            social_mod.WORKING_DIR = original["WORKING_DIR"]
            social_mod.FEEDS_PATH = original["FEEDS_PATH"]
            if keywords_original is None:
                os.environ.pop("PERMANENCE_SOCIAL_KEYWORDS", None)
            else:
                os.environ["PERMANENCE_SOCIAL_KEYWORDS"] = keywords_original

        assert rc == 0
        tool_files = sorted(tool.glob("social_research_ingest_*.json"))
        assert tool_files
        payload = json.loads(tool_files[-1].read_text(encoding="utf-8"))
        top = payload.get("top_items") or []
        assert top
        assert top[0].get("source") == "YouTube Market Reviewer"
        assert top[0].get("platform") == "youtube"
        assert "youtube.com/watch?v=abc123" in str(top[0].get("link") or "")


if __name__ == "__main__":
    test_social_research_ingest_ranks_feed_items()
    test_social_research_ingest_x_query_feed()
    test_social_research_ingest_discord_channel_feed()
    test_social_research_ingest_youtube_channel_feed()
    print("✓ Social research ingest tests passed")
