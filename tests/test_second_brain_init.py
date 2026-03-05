#!/usr/bin/env python3
"""Tests for second brain template initializer."""

import os
import sys
import tempfile
from pathlib import Path

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import scripts.second_brain_init as init_mod  # noqa: E402


def test_second_brain_init_writes_templates():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        working = root / "working"
        working.mkdir(parents=True, exist_ok=True)

        original = {"WORKING_DIR": init_mod.WORKING_DIR}
        try:
            init_mod.WORKING_DIR = working
            rc = init_mod.main([])
        finally:
            init_mod.WORKING_DIR = original["WORKING_DIR"]

        assert rc == 0
        assert (working / "life_profile.json").exists()
        assert (working / "life_tasks.json").exists()
        assert (working / "side_business_portfolio.json").exists()
        assert (working / "prediction_hypotheses.json").exists()
        assert (working / "prediction_news_feeds.json").exists()
        assert (working / "prediction_telegram_sources.json").exists()
        assert (working / "github_research_targets.json").exists()
        assert (working / "github_trending_focus.json").exists()
        assert (working / "ecosystem_watchlist.json").exists()
        assert (working / "social_research_feeds.json").exists()
        assert (working / "social_discernment_policy.json").exists()
        assert (working / "market_backtest_watchlist.json").exists()
        assert (working / "narrative_tracker_hypotheses.json").exists()
        assert (working / "world_watch_sources.json").exists()
        assert (working / "agent_constitution.json").exists()
        assert (working / "founder_vision.json").exists()
        assert (working / "transcription_queue.json").exists()
        assert (working / "clipping_jobs.json").exists()
        assert (working / "clipping_transcripts" / "sample_transcript.txt").exists()


if __name__ == "__main__":
    test_second_brain_init_writes_templates()
    print("✓ Second brain init tests passed")
