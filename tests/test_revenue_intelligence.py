#!/usr/bin/env python3
"""Tests for revenue intelligence pipeline."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import scripts.revenue_intelligence as rev_mod  # noqa: E402


def _tmp_json(tmp: Path, name: str, data: dict) -> Path:
    path = tmp / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return path


class TestExtractBookmarkSignals:
    def test_extracts_items(self):
        payload = {
            "top_items": [
                {"text": "how to build saas with agents", "signal_score": 3, "topic_tags": ["saas", "agents"], "handle": "user1", "url": "https://x.com/1"},
                {"text": "random note", "signal_score": 0, "topic_tags": [], "handle": "user2", "url": "https://x.com/2"},
            ]
        }
        signals = rev_mod._extract_bookmark_signals(payload)
        assert len(signals) == 2
        assert signals[0]["text"] == "how to build saas with agents"
        assert signals[0]["source"] == "bookmark"

    def test_empty_payload(self):
        signals = rev_mod._extract_bookmark_signals({})
        assert signals == []

    def test_skips_empty_text(self):
        payload = {"top_items": [{"text": "", "signal_score": 0}]}
        signals = rev_mod._extract_bookmark_signals(payload)
        assert signals == []


class TestExtractOpportunitySignals:
    def test_extracts_items(self):
        payload = {
            "top_items": [
                {"title": "Build automation platform", "source_type": "social", "priority_score": 60.0, "proposed_action": "Validate demand.", "risk_tier": "LOW"},
            ]
        }
        signals = rev_mod._extract_opportunity_signals(payload)
        assert len(signals) == 1
        assert signals[0]["title"] == "Build automation platform"


class TestScoreRevenuePotential:
    def test_scores_bookmark_with_revenue_keywords(self):
        bookmark_signals = [
            {"text": "how to build saas revenue product", "score": 3.0, "topic_tags": ["startup", "product"], "handle": "u1", "url": "https://x.com/1"},
        ]
        candidates = rev_mod._score_revenue_potential(bookmark_signals, [], [], {})
        assert len(candidates) == 1
        assert candidates[0]["revenue_score"] > 0
        assert candidates[0]["manual_approval_required"] is True

    def test_skips_bookmark_without_revenue_keywords(self):
        bookmark_signals = [
            {"text": "pretty sunset photo", "score": 0.0, "topic_tags": [], "handle": "u2", "url": ""},
        ]
        candidates = rev_mod._score_revenue_potential(bookmark_signals, [], [], {})
        assert len(candidates) == 0

    def test_includes_high_score_opportunities(self):
        opportunity_signals = [
            {"title": "High value signal", "source": "social", "priority_score": 80.0, "proposed_action": "Act.", "risk_tier": "LOW"},
        ]
        candidates = rev_mod._score_revenue_potential([], opportunity_signals, [], {})
        assert len(candidates) == 1

    def test_sorted_by_score(self):
        bookmarks = [
            {"text": "saas growth startup monetize api", "score": 5.0, "topic_tags": ["startup"], "handle": "a", "url": ""},
            {"text": "small saas", "score": 1.0, "topic_tags": [], "handle": "b", "url": ""},
        ]
        candidates = rev_mod._score_revenue_potential(bookmarks, [], [], {})
        assert len(candidates) == 2
        assert candidates[0]["revenue_score"] >= candidates[1]["revenue_score"]


class TestWriteRevenueIntake:
    def test_writes_entries(self):
        with tempfile.TemporaryDirectory() as tmp:
            intake_path = Path(tmp) / "revenue_intake.jsonl"
            with patch.object(rev_mod, "REVENUE_INTAKE_PATH", intake_path):
                candidates = [
                    {"revenue_id": "rev1", "title": "Test", "source_pipeline": "bookmark", "revenue_score": 50, "priority": "MEDIUM", "proposed_action": "Test."},
                ]
                written = rev_mod._write_revenue_intake(candidates, max_items=10)
                assert written == 1
                lines = intake_path.read_text().strip().splitlines()
                assert len(lines) == 1
                row = json.loads(lines[0])
                assert row["revenue_id"] == "rev1"
                assert row["manual_approval_required"] is True

    def test_no_duplicates(self):
        with tempfile.TemporaryDirectory() as tmp:
            intake_path = Path(tmp) / "revenue_intake.jsonl"
            intake_path.write_text('{"revenue_id": "rev1"}\n', encoding="utf-8")
            with patch.object(rev_mod, "REVENUE_INTAKE_PATH", intake_path):
                candidates = [{"revenue_id": "rev1", "title": "Test"}]
                written = rev_mod._write_revenue_intake(candidates, max_items=10)
                assert written == 0


class TestWriteOutputs:
    def test_produces_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "outputs"
            tool_dir = Path(tmp) / "tool"
            with patch.object(rev_mod, "OUTPUT_DIR", out_dir), patch.object(rev_mod, "TOOL_DIR", tool_dir):
                md_path, json_path = rev_mod._write_outputs(
                    candidates=[{"title": "Test", "source_pipeline": "bookmark", "revenue_score": 50, "priority": "MEDIUM", "revenue_keywords": ["saas"], "proposed_action": "Act."}],
                    bookmark_count=5,
                    opportunity_count=3,
                    idea_count=2,
                    playbook={"offer_name": "Test Offer", "price_usd": 1500},
                    intake_written=1,
                    warnings=[],
                    source_paths={"bookmark": "none"},
                )
                assert md_path.exists()
                assert json_path.exists()
                content = md_path.read_text()
                assert "Revenue Intelligence Brief" in content
                assert "manual_approval_required" in content
