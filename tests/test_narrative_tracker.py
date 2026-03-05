#!/usr/bin/env python3
"""Tests for narrative tracker."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import scripts.narrative_tracker as narrative_mod  # noqa: E402


def test_narrative_tracker_scores_hypotheses() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        working = root / "working"
        output = root / "outputs"
        tool = root / "tool"
        working.mkdir(parents=True, exist_ok=True)
        output.mkdir(parents=True, exist_ok=True)
        tool.mkdir(parents=True, exist_ok=True)

        hypotheses_path = working / "narrative_tracker_hypotheses.json"
        hypotheses_path.write_text(
            json.dumps(
                [
                    {
                        "hypothesis_id": "NAR-T1",
                        "title": "Liquidity stress underpricing",
                        "category": "macro",
                        "support_keywords": ["funding stress", "repo"],
                        "contradict_keywords": ["funding stable"],
                        "money_keywords": ["yield", "gold"],
                    }
                ]
            )
            + "\n",
            encoding="utf-8",
        )

        (tool / "social_research_ingest_20260303-120000.json").write_text(
            json.dumps(
                {
                    "top_items": [
                        {
                            "source": "X Macro Desk",
                            "title": "Repo funding stress rising as liquidity tightens",
                            "summary": "Analysts point to yield pressure and downside risk.",
                            "link": "https://x.com/i/web/status/1",
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
                            "title": "Bond yield spike pushes gold higher",
                            "summary": "Market reprices rates risk.",
                            "link": "https://example.com/news/2",
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
                            "event": "Liquidity watch",
                            "summary": "Funding stress appears in cross-asset spreads.",
                            "source_url": "https://example.com/world/2",
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        (tool / "market_backtest_queue_20260303-120000.json").write_text(
            json.dumps(
                {
                    "setups": [
                        {
                            "symbol": "XAUUSD",
                            "strategy_name": "Liquidity Sweep + FVG (ICC/SMC)",
                            "priority": "HIGH",
                            "signal_score": 4.2,
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )

        original = {
            "WORKING_DIR": narrative_mod.WORKING_DIR,
            "OUTPUT_DIR": narrative_mod.OUTPUT_DIR,
            "TOOL_DIR": narrative_mod.TOOL_DIR,
            "HYPOTHESES_PATH": narrative_mod.HYPOTHESES_PATH,
        }
        try:
            narrative_mod.WORKING_DIR = working
            narrative_mod.OUTPUT_DIR = output
            narrative_mod.TOOL_DIR = tool
            narrative_mod.HYPOTHESES_PATH = hypotheses_path
            rc = narrative_mod.main([])
        finally:
            narrative_mod.WORKING_DIR = original["WORKING_DIR"]
            narrative_mod.OUTPUT_DIR = original["OUTPUT_DIR"]
            narrative_mod.TOOL_DIR = original["TOOL_DIR"]
            narrative_mod.HYPOTHESES_PATH = original["HYPOTHESES_PATH"]

        assert rc == 0
        assert (output / "narrative_tracker_latest.md").exists()
        payload_files = sorted(tool.glob("narrative_tracker_*.json"))
        assert payload_files
        payload = json.loads(payload_files[-1].read_text(encoding="utf-8"))
        assert int(payload.get("hypothesis_count", 0)) == 1
        row = (payload.get("rows") or [])[0]
        assert row.get("hypothesis_id") == "NAR-T1"
        assert row.get("money_hits_total", 0) >= 1
        assert row.get("status") in {"supported", "unverified", "contradicted"}


if __name__ == "__main__":
    test_narrative_tracker_scores_hypotheses()
    print("✓ Narrative tracker tests passed")
