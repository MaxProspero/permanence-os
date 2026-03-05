#!/usr/bin/env python3
"""Tests for market focus brief report."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import scripts.market_focus_brief as brief_mod  # noqa: E402


def test_market_focus_brief_generates_priority_and_core_watchlist() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        output = root / "outputs"
        tool = root / "tool"
        working = root / "working"
        output.mkdir(parents=True, exist_ok=True)
        tool.mkdir(parents=True, exist_ok=True)
        working.mkdir(parents=True, exist_ok=True)

        (tool / "world_watch_20260303-100000.json").write_text(
            json.dumps(
                {
                    "top_events": [
                        {
                            "event_id": "m1",
                            "category": "market_stress",
                            "title": "Global market stress elevated",
                            "summary": "S&P -1.90% day | Nasdaq -2.30% day | Dow -1.40% day | VIX 26.10",
                            "severity_score": 78.0,
                        },
                        {
                            "event_id": "e1",
                            "category": "equity_watch",
                            "title": "Apple (AAPL) +3.24% day (221.10)",
                            "summary": "Apple (AAPL) daily +3.24% and 5-day +5.10%.",
                            "severity_score": 73.0,
                        },
                        {
                            "event_id": "e2",
                            "category": "equity_watch",
                            "title": "Microsoft (MSFT) +0.52% day (405.02)",
                            "summary": "Microsoft (MSFT) daily +0.52% and 5-day +1.20%.",
                            "severity_score": 44.0,
                        },
                        {
                            "event_id": "c1",
                            "category": "crypto_market",
                            "title": "Bitcoin (BTC) -5.10% day",
                            "summary": "Bitcoin (BTC) 24h -5.10% | 7d -8.20% | price $84,200.00",
                            "severity_score": 70.0,
                        },
                    ],
                    "market_monitors": [
                        {"name": "Polymarket", "url": "https://polymarket.com/", "type": "prediction_market"},
                        {"name": "Kalshi", "url": "https://kalshi.com/", "type": "prediction_market"},
                    ],
                }
            ),
            encoding="utf-8",
        )

        sources_path = working / "world_watch_sources.json"
        sources_path.write_text(
            json.dumps(
                {
                    "data_sources": [
                        {
                            "id": "stooq_equity_watchlist",
                            "type": "stooq_equity_watchlist",
                            "always_include_symbols": ["AAPL.US", "MSFT.US", "NVDA.US", "AMD.US", "PLTR.US"],
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )

        original = {
            "OUTPUT_DIR": brief_mod.OUTPUT_DIR,
            "TOOL_DIR": brief_mod.TOOL_DIR,
            "WORKING_DIR": brief_mod.WORKING_DIR,
            "SOURCES_PATH": brief_mod.SOURCES_PATH,
        }
        try:
            brief_mod.OUTPUT_DIR = output
            brief_mod.TOOL_DIR = tool
            brief_mod.WORKING_DIR = working
            brief_mod.SOURCES_PATH = sources_path
            rc = brief_mod.main()
        finally:
            brief_mod.OUTPUT_DIR = original["OUTPUT_DIR"]
            brief_mod.TOOL_DIR = original["TOOL_DIR"]
            brief_mod.WORKING_DIR = original["WORKING_DIR"]
            brief_mod.SOURCES_PATH = original["SOURCES_PATH"]

        assert rc == 0
        latest = output / "market_focus_brief_latest.md"
        assert latest.exists()
        content = latest.read_text(encoding="utf-8")
        assert "Market Focus Brief" in content
        assert "Apple (AAPL)" in content
        assert "Core Watchlist" in content
        assert "Polymarket" in content
        assert "- NVDA: QUIET" in content

        payload_files = sorted(tool.glob("market_focus_brief_*.json"))
        assert payload_files
        payload = json.loads(payload_files[-1].read_text(encoding="utf-8"))
        assert int(payload.get("priority_count", 0)) >= 2
        cards = payload.get("notification_cards") or []
        assert cards and isinstance(cards, list)
        watch = payload.get("core_watchlist") or []
        assert any(str(row.get("symbol")) == "AAPL" for row in watch)
        assert any(str(row.get("symbol")) == "NVDA" and str(row.get("status")) == "QUIET" for row in watch)


if __name__ == "__main__":
    test_market_focus_brief_generates_priority_and_core_watchlist()
    print("✓ Market focus brief tests passed")

