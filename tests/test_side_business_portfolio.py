#!/usr/bin/env python3
"""Tests for side business portfolio report."""

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import scripts.side_business_portfolio as portfolio_mod  # noqa: E402


def test_side_business_portfolio_generates_ranked_actions():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        outputs = root / "outputs"
        tool = root / "tool"
        working = root / "working"
        outputs.mkdir(parents=True, exist_ok=True)
        tool.mkdir(parents=True, exist_ok=True)
        working.mkdir(parents=True, exist_ok=True)

        portfolio_path = working / "side_business_portfolio.json"
        portfolio_path.write_text(
            json.dumps(
                [
                    {
                        "stream_id": "S-1",
                        "name": "Service Stream",
                        "stage": "validate",
                        "risk": "low",
                        "weekly_goal_usd": 2000,
                        "weekly_actual_usd": 100,
                        "pipeline_count": 3,
                        "next_action": "Send proposals",
                    },
                    {
                        "stream_id": "S-2",
                        "name": "Research Stream",
                        "stage": "build",
                        "risk": "high",
                        "weekly_goal_usd": 500,
                        "weekly_actual_usd": 0,
                        "pipeline_count": 0,
                        "next_action": "Backtest",
                    },
                ]
            ),
            encoding="utf-8",
        )

        original = {
            "OUTPUT_DIR": portfolio_mod.OUTPUT_DIR,
            "TOOL_DIR": portfolio_mod.TOOL_DIR,
            "PORTFOLIO_PATH": portfolio_mod.PORTFOLIO_PATH,
        }
        try:
            portfolio_mod.OUTPUT_DIR = outputs
            portfolio_mod.TOOL_DIR = tool
            portfolio_mod.PORTFOLIO_PATH = portfolio_path
            rc = portfolio_mod.main()
        finally:
            portfolio_mod.OUTPUT_DIR = original["OUTPUT_DIR"]
            portfolio_mod.TOOL_DIR = original["TOOL_DIR"]
            portfolio_mod.PORTFOLIO_PATH = original["PORTFOLIO_PATH"]

        assert rc == 0
        latest = outputs / "side_business_portfolio_latest.md"
        assert latest.exists()
        content = latest.read_text(encoding="utf-8")
        assert "Side Business Portfolio" in content
        assert "Service Stream" in content

        tool_files = sorted(tool.glob("side_business_portfolio_*.json"))
        assert tool_files
        payload = json.loads(tool_files[-1].read_text(encoding="utf-8"))
        assert payload.get("stream_count") == 2
        assert payload.get("totals", {}).get("weekly_goal_usd", 0) >= 2500


if __name__ == "__main__":
    test_side_business_portfolio_generates_ranked_actions()
    print("✓ Side business portfolio tests passed")
