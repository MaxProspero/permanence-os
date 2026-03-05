#!/usr/bin/env python3
"""Tests for platform change watch ingest + queue workflow."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import scripts.platform_change_watch as watch_mod  # noqa: E402


def test_platform_change_watch_collects_alerts_and_queues_actions() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        outputs = root / "outputs"
        tool = root / "tool"
        working = root / "working"
        email_dir = working / "email"
        scan_root = root / "scan"
        outputs.mkdir(parents=True, exist_ok=True)
        tool.mkdir(parents=True, exist_ok=True)
        email_dir.mkdir(parents=True, exist_ok=True)
        scan_root.mkdir(parents=True, exist_ok=True)

        feed_xml = working / "x_changelog.xml"
        feed_xml.write_text(
            """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>X Changelog</title>
    <item>
      <title>Breaking change: X API endpoint deprecated and removed</title>
      <description>Action required before deadline to migrate auth flow.</description>
      <link>https://docs.x.com/changelog/example</link>
      <pubDate>Wed, 04 Mar 2026 20:00:00 GMT</pubDate>
    </item>
  </channel>
</rss>
""",
            encoding="utf-8",
        )

        watchlist_path = working / "platform_change_watchlist.json"
        watchlist_path.write_text(
            json.dumps(
                [
                    {
                        "name": "Local X Changelog",
                        "platform": "x",
                        "url": f"file://{feed_xml}",
                        "enabled": True,
                        "max_items": 10,
                    }
                ]
            )
            + "\n",
            encoding="utf-8",
        )

        email_path = email_dir / "inbox.json"
        email_path.write_text(
            json.dumps(
                [
                    {
                        "id": "msg-1",
                        "from": "X Developers <noreply@x.com>",
                        "subject": "Action required: migrate due to deprecation",
                        "snippet": "Breaking auth update. Old token flow sunset soon.",
                        "date": "Wed, 04 Mar 2026 21:00:00 GMT",
                    }
                ]
            )
            + "\n",
            encoding="utf-8",
        )

        (scan_root / "x_integration.py").write_text(
            "X_URL='https://api.twitter.com/2/tweets/search/recent'\n",
            encoding="utf-8",
        )

        queue_path = working / "platform_change_action_queue.jsonl"
        original = {
            "OUTPUT_DIR": watch_mod.OUTPUT_DIR,
            "TOOL_DIR": watch_mod.TOOL_DIR,
            "WORKING_DIR": watch_mod.WORKING_DIR,
        }
        try:
            watch_mod.OUTPUT_DIR = outputs
            watch_mod.TOOL_DIR = tool
            watch_mod.WORKING_DIR = working
            rc = watch_mod.main(
                [
                    "--watchlist-path",
                    str(watchlist_path),
                    "--email-path",
                    str(email_path),
                    "--queue-path",
                    str(queue_path),
                    "--scan-root",
                    str(scan_root),
                    "--lookback-days",
                    "30",
                ]
            )
        finally:
            watch_mod.OUTPUT_DIR = original["OUTPUT_DIR"]
            watch_mod.TOOL_DIR = original["TOOL_DIR"]
            watch_mod.WORKING_DIR = original["WORKING_DIR"]

        assert rc == 0
        latest = outputs / "platform_change_watch_latest.md"
        assert latest.exists()
        text = latest.read_text(encoding="utf-8")
        assert "Platform Change Watch" in text
        assert "Breaking change: X API endpoint deprecated and removed" in text
        assert "Queue items added" in text

        payload_files = sorted(tool.glob("platform_change_watch_*.json"))
        assert payload_files
        payload = json.loads(payload_files[-1].read_text(encoding="utf-8"))
        assert int(payload.get("alert_count", 0)) >= 1
        assert int(payload.get("email_signal_count", 0)) >= 1
        footprint = payload.get("integration_footprint") or {}
        assert int((footprint.get("x") or {}).get("hit_count", 0)) >= 1

        queue_lines = [line for line in queue_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        assert queue_lines
        queue_item = json.loads(queue_lines[-1])
        assert queue_item.get("status") == "PENDING"
        assert queue_item.get("platform") == "x"


def test_platform_change_watch_strict_mode_fails_on_critical_alert() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        outputs = root / "outputs"
        tool = root / "tool"
        working = root / "working"
        outputs.mkdir(parents=True, exist_ok=True)
        tool.mkdir(parents=True, exist_ok=True)
        working.mkdir(parents=True, exist_ok=True)

        feed_xml = working / "critical_feed.xml"
        feed_xml.write_text(
            """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <item>
      <title>Breaking deprecation remove required migration now</title>
      <description>Action required before deadline.</description>
      <link>https://example.com/critical</link>
      <pubDate>Wed, 04 Mar 2026 20:00:00 GMT</pubDate>
    </item>
  </channel>
</rss>
""",
            encoding="utf-8",
        )
        watchlist_path = working / "watch.json"
        watchlist_path.write_text(
            json.dumps([{"name": "Critical Feed", "platform": "x", "url": f"file://{feed_xml}", "enabled": True}]) + "\n",
            encoding="utf-8",
        )
        queue_path = working / "queue.jsonl"

        original = {
            "OUTPUT_DIR": watch_mod.OUTPUT_DIR,
            "TOOL_DIR": watch_mod.TOOL_DIR,
            "WORKING_DIR": watch_mod.WORKING_DIR,
        }
        try:
            watch_mod.OUTPUT_DIR = outputs
            watch_mod.TOOL_DIR = tool
            watch_mod.WORKING_DIR = working
            rc = watch_mod.main(
                [
                    "--watchlist-path",
                    str(watchlist_path),
                    "--queue-path",
                    str(queue_path),
                    "--strict",
                    "--lookback-days",
                    "30",
                ]
            )
        finally:
            watch_mod.OUTPUT_DIR = original["OUTPUT_DIR"]
            watch_mod.TOOL_DIR = original["TOOL_DIR"]
            watch_mod.WORKING_DIR = original["WORKING_DIR"]

        assert rc == 1
        latest = outputs / "platform_change_watch_latest.md"
        assert latest.exists()
        assert "Critical:" in latest.read_text(encoding="utf-8")


if __name__ == "__main__":
    test_platform_change_watch_collects_alerts_and_queues_actions()
    test_platform_change_watch_strict_mode_fails_on_critical_alert()
    print("✓ platform_change_watch tests passed")
