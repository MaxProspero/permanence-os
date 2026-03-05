#!/usr/bin/env python3
"""Tests for world watch alerts."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import scripts.world_watch_alerts as alerts_mod  # noqa: E402


def test_world_watch_alerts_builds_draft_without_dispatch() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        output = root / "outputs"
        tool = root / "tool"
        output.mkdir(parents=True, exist_ok=True)
        tool.mkdir(parents=True, exist_ok=True)

        (tool / "world_watch_20260301-120000.json").write_text(
            json.dumps(
                {
                    "top_events": [
                        {
                            "event_id": "evt-1",
                            "title": "Major earthquake event",
                            "category": "earthquake",
                            "region": "Offshore",
                            "severity_score": 88.0,
                            "url": "https://example.com/evt-1",
                        },
                        {
                            "event_id": "evt-2",
                            "title": "Severe storm warning",
                            "category": "weather_alert",
                            "region": "Region B",
                            "severity_score": 76.0,
                            "url": "https://example.com/evt-2",
                        },
                    ],
                    "alert_focus": {
                        "major_categories": ["market_stress", "weather_local", "earthquake"],
                        "always_include_categories": ["market_stress", "weather_local"],
                        "headline_keywords": ["market crash", "storm", "earthquake"],
                        "min_major_score": 68,
                    },
                    "map_views": [{"name": "World Monitor", "url": "https://www.worldmonitor.app/"}],
                    "market_monitors": [{"name": "TradingView Heatmap", "url": "https://www.tradingview.com/heatmap/stock/"}],
                }
            ),
            encoding="utf-8",
        )

        original = {
            "OUTPUT_DIR": alerts_mod.OUTPUT_DIR,
            "TOOL_DIR": alerts_mod.TOOL_DIR,
        }
        try:
            alerts_mod.OUTPUT_DIR = output
            alerts_mod.TOOL_DIR = tool
            rc = alerts_mod.main([])
        finally:
            alerts_mod.OUTPUT_DIR = original["OUTPUT_DIR"]
            alerts_mod.TOOL_DIR = original["TOOL_DIR"]

        assert rc == 0
        assert (output / "world_watch_alerts_latest.md").exists()
        payload_files = sorted(tool.glob("world_watch_alerts_*.json"))
        assert payload_files
        payload = json.loads(payload_files[-1].read_text(encoding="utf-8"))
        assert int(payload.get("alert_count", 0)) == 2
        assert payload.get("dispatch_results") == []
        assert "Permanence Market Alerts" in str(payload.get("message"))
        assert "TradingView Heatmap" in str(payload.get("message"))
        assert "https://www.tradingview.com/heatmap/stock/" not in str(payload.get("message"))
        focus = payload.get("focus") or {}
        assert "market_stress" in (focus.get("major_categories") or [])


def test_world_watch_alerts_includes_market_and_local_weather_categories() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        output = root / "outputs"
        tool = root / "tool"
        output.mkdir(parents=True, exist_ok=True)
        tool.mkdir(parents=True, exist_ok=True)

        (tool / "world_watch_20260301-120000.json").write_text(
            json.dumps(
                {
                    "top_events": [
                        {
                            "event_id": "evt-1",
                            "title": "Moderate local weather watch",
                            "category": "weather_local",
                            "region": "Home",
                            "severity_score": 48.0,
                            "url": "https://example.com/local-weather",
                        },
                        {
                            "event_id": "evt-2",
                            "title": "Global market stress elevated",
                            "category": "market_stress",
                            "region": "Global markets",
                            "severity_score": 66.0,
                            "url": "https://example.com/market-stress",
                        },
                        {
                            "event_id": "evt-3",
                            "title": "War escalation bulletin",
                            "category": "war_conflict",
                            "region": "Region Z",
                            "severity_score": 82.0,
                            "url": "https://example.com/war-1",
                        },
                    ],
                    "alert_focus": {
                        "major_categories": ["war_conflict", "market_stress", "weather_local"],
                        "always_include_categories": ["market_stress", "weather_local"],
                        "headline_keywords": ["war", "market", "weather"],
                        "min_major_score": 68,
                    },
                }
            ),
            encoding="utf-8",
        )

        original = {
            "OUTPUT_DIR": alerts_mod.OUTPUT_DIR,
            "TOOL_DIR": alerts_mod.TOOL_DIR,
        }
        try:
            alerts_mod.OUTPUT_DIR = output
            alerts_mod.TOOL_DIR = tool
            rc = alerts_mod.main([])
        finally:
            alerts_mod.OUTPUT_DIR = original["OUTPUT_DIR"]
            alerts_mod.TOOL_DIR = original["TOOL_DIR"]

        assert rc == 0
        payload_files = sorted(tool.glob("world_watch_alerts_*.json"))
        assert payload_files
        payload = json.loads(payload_files[-1].read_text(encoding="utf-8"))
        message = str(payload.get("message") or "")
        assert "Global market stress elevated" in message
        assert "Moderate local weather watch" in message


def test_world_watch_alerts_market_only_filters_non_market_categories() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        output = root / "outputs"
        tool = root / "tool"
        output.mkdir(parents=True, exist_ok=True)
        tool.mkdir(parents=True, exist_ok=True)

        (tool / "world_watch_20260301-120000.json").write_text(
            json.dumps(
                {
                    "top_events": [
                        {
                            "event_id": "evt-1",
                            "title": "Global market stress elevated",
                            "category": "market_stress",
                            "region": "Global markets",
                            "severity_score": 62.0,
                            "url": "https://example.com/market-stress",
                        },
                        {
                            "event_id": "evt-2",
                            "title": "Earthquake event",
                            "category": "earthquake",
                            "region": "Region B",
                            "severity_score": 90.0,
                            "url": "https://example.com/quake",
                        },
                        {
                            "event_id": "evt-3",
                            "title": "Local weather watch",
                            "category": "weather_local",
                            "region": "Home",
                            "severity_score": 70.0,
                            "url": "https://example.com/weather",
                        },
                    ],
                    "alert_focus": {
                        "market_only": True,
                        "major_categories": ["market_stress", "market_index", "crypto_market", "fx_market"],
                        "always_include_categories": ["market_stress"],
                        "headline_keywords": ["market", "selloff", "vix"],
                        "min_major_score": 55,
                    },
                }
            ),
            encoding="utf-8",
        )

        original = {
            "OUTPUT_DIR": alerts_mod.OUTPUT_DIR,
            "TOOL_DIR": alerts_mod.TOOL_DIR,
        }
        try:
            alerts_mod.OUTPUT_DIR = output
            alerts_mod.TOOL_DIR = tool
            rc = alerts_mod.main([])
        finally:
            alerts_mod.OUTPUT_DIR = original["OUTPUT_DIR"]
            alerts_mod.TOOL_DIR = original["TOOL_DIR"]

        assert rc == 0
        payload_files = sorted(tool.glob("world_watch_alerts_*.json"))
        assert payload_files
        payload = json.loads(payload_files[-1].read_text(encoding="utf-8"))
        message = str(payload.get("message") or "")
        assert "Global market stress elevated" in message
        assert "Earthquake event" not in message
        assert "Local weather watch" not in message
        assert (payload.get("focus") or {}).get("market_only") is True


def test_world_watch_alerts_market_only_keeps_required_market_mix() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        output = root / "outputs"
        tool = root / "tool"
        output.mkdir(parents=True, exist_ok=True)
        tool.mkdir(parents=True, exist_ok=True)

        (tool / "world_watch_20260301-120000.json").write_text(
            json.dumps(
                {
                    "top_events": [
                        {"event_id": "c1", "title": "Crypto 1", "category": "crypto_market", "severity_score": 90, "region": "crypto"},
                        {"event_id": "c2", "title": "Crypto 2", "category": "crypto_market", "severity_score": 88, "region": "crypto"},
                        {"event_id": "c3", "title": "Crypto 3", "category": "crypto_market", "severity_score": 86, "region": "crypto"},
                        {"event_id": "c4", "title": "Crypto 4", "category": "crypto_market", "severity_score": 84, "region": "crypto"},
                        {"event_id": "m1", "title": "Market stress", "category": "market_stress", "severity_score": 35, "region": "global"},
                        {"event_id": "e1", "title": "Equity watch", "category": "equity_watch", "severity_score": 34, "region": "us"},
                        {"event_id": "f1", "title": "FX watch", "category": "fx_market", "severity_score": 33, "region": "fx"},
                        {"event_id": "i1", "title": "Index watch", "category": "market_index", "severity_score": 32, "region": "us"},
                    ],
                    "alert_focus": {
                        "market_only": True,
                        "major_categories": ["market_stress", "market_index", "equity_watch", "crypto_market", "fx_market"],
                        "always_include_categories": ["market_stress", "market_index", "equity_watch", "fx_market"],
                        "headline_keywords": ["market", "crypto", "fx"],
                        "min_major_score": 60,
                    },
                }
            ),
            encoding="utf-8",
        )

        original = {
            "OUTPUT_DIR": alerts_mod.OUTPUT_DIR,
            "TOOL_DIR": alerts_mod.TOOL_DIR,
        }
        try:
            alerts_mod.OUTPUT_DIR = output
            alerts_mod.TOOL_DIR = tool
            rc = alerts_mod.main(["--max-alerts", "4"])
        finally:
            alerts_mod.OUTPUT_DIR = original["OUTPUT_DIR"]
            alerts_mod.TOOL_DIR = original["TOOL_DIR"]

        assert rc == 0
        payload_files = sorted(tool.glob("world_watch_alerts_*.json"))
        payload = json.loads(payload_files[-1].read_text(encoding="utf-8"))
        message = str(payload.get("message") or "")
        assert "Market stress" in message
        assert "Equity watch" in message
        assert "FX watch" in message
        assert "Index watch" in message


if __name__ == "__main__":
    test_world_watch_alerts_builds_draft_without_dispatch()
    test_world_watch_alerts_includes_market_and_local_weather_categories()
    test_world_watch_alerts_market_only_filters_non_market_categories()
    test_world_watch_alerts_market_only_keeps_required_market_mix()
    print("✓ World watch alerts tests passed")
