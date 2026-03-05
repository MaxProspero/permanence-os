#!/usr/bin/env python3
"""Tests for prediction ingest pipeline."""

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import scripts.prediction_ingest as ingest_mod  # noqa: E402


def test_prediction_ingest_updates_signal_scores_from_feed():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        outputs = root / "outputs"
        tool = root / "tool"
        working = root / "working"
        outputs.mkdir(parents=True, exist_ok=True)
        tool.mkdir(parents=True, exist_ok=True)
        working.mkdir(parents=True, exist_ok=True)

        feed_xml_path = working / "feed.xml"
        feed_xml_path.write_text(
            """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Demo Feed</title>
    <item>
      <title>Fed rate cut odds increase</title>
      <description>Analysts discuss inflation trends and possible cut.</description>
      <link>https://example.com/fed</link>
      <pubDate>Sun, 01 Mar 2026 16:00:00 GMT</pubDate>
    </item>
  </channel>
</rss>
""",
            encoding="utf-8",
        )

        feeds_path = working / "prediction_news_feeds.json"
        feeds_path.write_text(
            json.dumps(
                [
                    {
                        "name": "Local Demo Feed",
                        "url": f"file://{feed_xml_path}",
                    }
                ]
            ),
            encoding="utf-8",
        )

        hypothesis_path = working / "prediction_hypotheses.json"
        hypothesis_path.write_text(
            json.dumps(
                [
                    {
                        "hypothesis_id": "PM-100",
                        "title": "Rate cut market",
                        "keywords": ["rate cut", "inflation"],
                        "negative_keywords": ["hike"],
                        "signal_score": 0.0,
                        "impact_direction": "up",
                    }
                ]
            ),
            encoding="utf-8",
        )

        original = {
            "OUTPUT_DIR": ingest_mod.OUTPUT_DIR,
            "TOOL_DIR": ingest_mod.TOOL_DIR,
            "FEEDS_PATH": ingest_mod.FEEDS_PATH,
            "TELEGRAM_SOURCES_PATH": ingest_mod.TELEGRAM_SOURCES_PATH,
            "HYPOTHESIS_PATH": ingest_mod.HYPOTHESIS_PATH,
            "MAX_ITEMS_PER_FEED": ingest_mod.MAX_ITEMS_PER_FEED,
        }
        try:
            ingest_mod.OUTPUT_DIR = outputs
            ingest_mod.TOOL_DIR = tool
            ingest_mod.FEEDS_PATH = feeds_path
            ingest_mod.TELEGRAM_SOURCES_PATH = working / "prediction_telegram_sources.json"
            ingest_mod.HYPOTHESIS_PATH = hypothesis_path
            ingest_mod.MAX_ITEMS_PER_FEED = 10
            rc = ingest_mod.main()
        finally:
            ingest_mod.OUTPUT_DIR = original["OUTPUT_DIR"]
            ingest_mod.TOOL_DIR = original["TOOL_DIR"]
            ingest_mod.FEEDS_PATH = original["FEEDS_PATH"]
            ingest_mod.TELEGRAM_SOURCES_PATH = original["TELEGRAM_SOURCES_PATH"]
            ingest_mod.HYPOTHESIS_PATH = original["HYPOTHESIS_PATH"]
            ingest_mod.MAX_ITEMS_PER_FEED = original["MAX_ITEMS_PER_FEED"]

        assert rc == 0
        latest = outputs / "prediction_ingest_latest.md"
        assert latest.exists()
        content = latest.read_text(encoding="utf-8")
        assert "Prediction Ingest" in content
        assert "Headlines ingested: 1" in content

        updated_rows = json.loads(hypothesis_path.read_text(encoding="utf-8"))
        assert updated_rows
        assert updated_rows[0]["signal_score"] > 0
        assert updated_rows[0]["signal_evidence"]

        tool_files = sorted(tool.glob("prediction_ingest_*.json"))
        assert tool_files
        payload = json.loads(tool_files[-1].read_text(encoding="utf-8"))
        assert payload.get("headline_count") == 1
        assert payload.get("feed_count") == 1


def test_prediction_ingest_includes_telegram_channel_posts():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        outputs = root / "outputs"
        tool = root / "tool"
        working = root / "working"
        outputs.mkdir(parents=True, exist_ok=True)
        tool.mkdir(parents=True, exist_ok=True)
        working.mkdir(parents=True, exist_ok=True)

        feed_xml_path = working / "feed.xml"
        feed_xml_path.write_text(
            """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>Empty</title></channel></rss>
""",
            encoding="utf-8",
        )
        feeds_path = working / "prediction_news_feeds.json"
        feeds_path.write_text(
            json.dumps([{"name": "Empty Feed", "url": f"file://{feed_xml_path}"}]),
            encoding="utf-8",
        )

        telegram_html = working / "telegram.html"
        telegram_html.write_text(
            """
<html><body>
  <div class="tgme_widget_message_wrap">
    <div class="tgme_widget_message">
      <a class="tgme_widget_message_date" href="https://t.me/iccmafia/101"><time datetime="2026-03-02T00:00:00+00:00"></time></a>
      <div class="tgme_widget_message_text js-message_text">Liquidity rotation into rates and FX this week.</div>
    </div>
  </div>
</body></html>
""",
            encoding="utf-8",
        )
        telegram_sources_path = working / "prediction_telegram_sources.json"
        telegram_sources_path.write_text(
            json.dumps(
                [
                    {
                        "name": "ICC Mafia",
                        "channel": "iccmafia",
                        "url": f"file://{telegram_html}",
                        "enabled": True,
                    }
                ]
            ),
            encoding="utf-8",
        )

        hypothesis_path = working / "prediction_hypotheses.json"
        hypothesis_path.write_text(
            json.dumps(
                [
                    {
                        "hypothesis_id": "PM-TG-1",
                        "title": "Telegram-driven rates move",
                        "keywords": ["liquidity", "rates", "fx"],
                        "negative_keywords": [],
                        "signal_score": 0.0,
                        "impact_direction": "up",
                    }
                ]
            ),
            encoding="utf-8",
        )

        original = {
            "OUTPUT_DIR": ingest_mod.OUTPUT_DIR,
            "TOOL_DIR": ingest_mod.TOOL_DIR,
            "FEEDS_PATH": ingest_mod.FEEDS_PATH,
            "TELEGRAM_SOURCES_PATH": ingest_mod.TELEGRAM_SOURCES_PATH,
            "HYPOTHESIS_PATH": ingest_mod.HYPOTHESIS_PATH,
            "MAX_ITEMS_PER_FEED": ingest_mod.MAX_ITEMS_PER_FEED,
            "MAX_TELEGRAM_POSTS_PER_SOURCE": ingest_mod.MAX_TELEGRAM_POSTS_PER_SOURCE,
        }
        try:
            ingest_mod.OUTPUT_DIR = outputs
            ingest_mod.TOOL_DIR = tool
            ingest_mod.FEEDS_PATH = feeds_path
            ingest_mod.TELEGRAM_SOURCES_PATH = telegram_sources_path
            ingest_mod.HYPOTHESIS_PATH = hypothesis_path
            ingest_mod.MAX_ITEMS_PER_FEED = 5
            ingest_mod.MAX_TELEGRAM_POSTS_PER_SOURCE = 5
            rc = ingest_mod.main()
        finally:
            ingest_mod.OUTPUT_DIR = original["OUTPUT_DIR"]
            ingest_mod.TOOL_DIR = original["TOOL_DIR"]
            ingest_mod.FEEDS_PATH = original["FEEDS_PATH"]
            ingest_mod.TELEGRAM_SOURCES_PATH = original["TELEGRAM_SOURCES_PATH"]
            ingest_mod.HYPOTHESIS_PATH = original["HYPOTHESIS_PATH"]
            ingest_mod.MAX_ITEMS_PER_FEED = original["MAX_ITEMS_PER_FEED"]
            ingest_mod.MAX_TELEGRAM_POSTS_PER_SOURCE = original["MAX_TELEGRAM_POSTS_PER_SOURCE"]

        assert rc == 0
        updated_rows = json.loads(hypothesis_path.read_text(encoding="utf-8"))
        assert updated_rows[0]["signal_score"] > 0
        evidence = updated_rows[0]["signal_evidence"] or []
        assert evidence
        assert evidence[0]["source"] == "ICC Mafia"

        tool_files = sorted(tool.glob("prediction_ingest_*.json"))
        payload = json.loads(tool_files[-1].read_text(encoding="utf-8"))
        assert payload.get("telegram_source_count") == 1
        assert payload.get("headline_count", 0) >= 1


if __name__ == "__main__":
    test_prediction_ingest_updates_signal_scores_from_feed()
    test_prediction_ingest_includes_telegram_channel_posts()
    print("✓ Prediction ingest tests passed")
