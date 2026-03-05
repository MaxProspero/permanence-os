#!/usr/bin/env python3
"""Tests for opportunity ranker."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import scripts.opportunity_ranker as ranker_mod  # noqa: E402


def test_opportunity_ranker_generates_ranked_items() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        working = root / "working"
        output = root / "outputs"
        tool = root / "tool"
        working.mkdir(parents=True, exist_ok=True)
        output.mkdir(parents=True, exist_ok=True)
        tool.mkdir(parents=True, exist_ok=True)

        (tool / "social_research_ingest_20260301-120000.json").write_text(
            json.dumps(
                {
                    "item_count": 2,
                    "top_items": [
                        {
                            "title": "AI automation demand is rising",
                            "summary": "Founder workflows are moving to AI automations.",
                            "score": 5.2,
                            "matched_keywords": ["ai", "automation"],
                            "platform": "x",
                            "source": "X Agents",
                            "link": "https://x.com/i/web/status/123",
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        (tool / "github_research_ingest_20260301-120000.json").write_text(
            json.dumps(
                {
                    "repo_count": 1,
                    "repos": [
                        {
                            "repo": "acme/permanence-os",
                            "open_issues": 6,
                            "stale_issues": 2,
                            "stale_prs": 1,
                            "focus_label_hits": 2,
                            "top_actions": ["Review stale PR(s) older than threshold."],
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        (tool / "prediction_lab_20260301-120000.json").write_text(
            json.dumps(
                {
                    "manual_review_candidates": 1,
                    "results": [
                        {
                            "hypothesis_id": "PM-001",
                            "title": "Policy market edge",
                            "market": "paper_demo",
                            "edge": 0.08,
                            "expected_pnl_per_1usd": 0.15,
                            "suggested_stake_usd": 12.5,
                            "decision": "review_for_manual_execution",
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        (tool / "ecosystem_research_ingest_20260301-120000.json").write_text(
            json.dumps(
                {
                    "repo_count": 1,
                    "developer_count": 1,
                    "repos": [
                        {
                            "repo": "ruvnet/ruflo",
                            "priority_score": 54.0,
                            "stars": 18000,
                            "open_issues": 21,
                            "language": "TypeScript",
                            "updated_at": "2026-03-03T00:00:00+00:00",
                            "html_url": "https://github.com/ruvnet/ruflo",
                        }
                    ],
                    "developers": [
                        {
                            "login": "ruvnet",
                            "priority_score": 71.0,
                            "followers": 4200,
                            "public_repos": 55,
                            "html_url": "https://github.com/ruvnet",
                        }
                    ],
                    "docs": [{"url": "https://docs.github.com/en/codespaces/overview", "reachable": True, "status": 200}],
                    "communities": [{"url": "https://discord.gg/tradesbysci", "reachable": True, "status": 200}],
                }
            ),
            encoding="utf-8",
        )
        (tool / "side_business_portfolio_20260301-120000.json").write_text(
            json.dumps(
                {
                    "stream_count": 1,
                    "top_actions": [
                        {
                            "stream_id": "clip-studio",
                            "name": "Shorts Clipping Studio",
                            "risk": "medium",
                            "weekly_gap_usd": 1200,
                            "priority_score": 620,
                            "pipeline_count": 2,
                            "next_action": "Offer 5 clips in one niche and collect conversion stats.",
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )

        original = {
            "WORKING_DIR": ranker_mod.WORKING_DIR,
            "OUTPUT_DIR": ranker_mod.OUTPUT_DIR,
            "TOOL_DIR": ranker_mod.TOOL_DIR,
            "POLICY_PATH": ranker_mod.POLICY_PATH,
        }
        try:
            ranker_mod.WORKING_DIR = working
            ranker_mod.OUTPUT_DIR = output
            ranker_mod.TOOL_DIR = tool
            ranker_mod.POLICY_PATH = working / "opportunity_rank_policy.json"
            rc = ranker_mod.main([])
        finally:
            ranker_mod.WORKING_DIR = original["WORKING_DIR"]
            ranker_mod.OUTPUT_DIR = original["OUTPUT_DIR"]
            ranker_mod.TOOL_DIR = original["TOOL_DIR"]
            ranker_mod.POLICY_PATH = original["POLICY_PATH"]

        assert rc == 0
        assert (output / "opportunity_ranker_latest.md").exists()
        payload_files = sorted(tool.glob("opportunity_ranker_*.json"))
        assert payload_files
        payload = json.loads(payload_files[-1].read_text(encoding="utf-8"))
        assert int(payload.get("item_count", 0)) >= 3
        source_types = {str(row.get("source_type")) for row in payload.get("top_items", [])}
        assert "social" in source_types
        assert "github" in source_types
        assert "ecosystem" in source_types
        assert "prediction" in source_types
        assert "portfolio" in source_types
        assert all(bool(row.get("manual_approval_required")) for row in payload.get("top_items", []))


if __name__ == "__main__":
    test_opportunity_ranker_generates_ranked_items()
    print("✓ Opportunity ranker tests passed")
