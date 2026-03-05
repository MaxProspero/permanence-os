#!/usr/bin/env python3
"""Tests for market backtest queue builder."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import scripts.market_backtest_queue as backtest_mod  # noqa: E402


def test_market_backtest_queue_builds_setups() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        working = root / "working"
        output = root / "outputs"
        tool = root / "tool"
        working.mkdir(parents=True, exist_ok=True)
        output.mkdir(parents=True, exist_ok=True)
        tool.mkdir(parents=True, exist_ok=True)

        (tool / "social_research_ingest_20260303-120000.json").write_text(
            json.dumps(
                {
                    "top_items": [
                        {
                            "source": "YouTube Reviewer",
                            "platform": "youtube",
                            "title": "XAUUSD liquidity sweep + FVG backtest walkthrough",
                            "summary": "ICC/SMC setup with BOS and order block confirmation.",
                            "link": "https://www.youtube.com/watch?v=demo123",
                            "published": "2026-03-03T12:00:00+00:00",
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        (tool / "prediction_ingest_20260303-120000.json").write_text(
            json.dumps(
                {
                    "headlines": [
                        {
                            "source": "Reuters",
                            "title": "Treasury yields jump as inflation fears return",
                            "summary": "Rates and dollar volatility pressure risk assets.",
                            "link": "https://example.com/news/1",
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        (tool / "world_watch_20260303-120000.json").write_text(
            json.dumps(
                {
                    "top_alerts": [
                        {
                            "event": "Gold spikes during policy shock",
                            "summary": "XAUUSD volatility rises after macro event.",
                            "source_url": "https://example.com/world/1",
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        (tool / "prediction_lab_20260303-120000.json").write_text(
            json.dumps(
                {
                    "results": [
                        {
                            "title": "Gold momentum edge",
                            "market": "paper_demo",
                            "decision": "review_for_manual_execution",
                            "edge": 0.05,
                            "expected_pnl_per_1usd": 0.09,
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )

        original = {
            "WORKING_DIR": backtest_mod.WORKING_DIR,
            "OUTPUT_DIR": backtest_mod.OUTPUT_DIR,
            "TOOL_DIR": backtest_mod.TOOL_DIR,
            "WATCHLIST_PATH": backtest_mod.WATCHLIST_PATH,
        }
        try:
            backtest_mod.WORKING_DIR = working
            backtest_mod.OUTPUT_DIR = output
            backtest_mod.TOOL_DIR = tool
            backtest_mod.WATCHLIST_PATH = working / "market_backtest_watchlist.json"
            rc = backtest_mod.main([])
        finally:
            backtest_mod.WORKING_DIR = original["WORKING_DIR"]
            backtest_mod.OUTPUT_DIR = original["OUTPUT_DIR"]
            backtest_mod.TOOL_DIR = original["TOOL_DIR"]
            backtest_mod.WATCHLIST_PATH = original["WATCHLIST_PATH"]

        assert rc == 0
        assert (output / "market_backtest_queue_latest.md").exists()
        payload_files = sorted(tool.glob("market_backtest_queue_*.json"))
        assert payload_files
        payload = json.loads(payload_files[-1].read_text(encoding="utf-8"))
        assert int(payload.get("setup_count", 0)) >= 1
        first = (payload.get("setups") or [])[0]
        assert first.get("manual_approval_required") is True
        assert first.get("symbol") == "XAUUSD"


if __name__ == "__main__":
    test_market_backtest_queue_builds_setups()
    print("✓ Market backtest queue tests passed")
