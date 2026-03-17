#!/usr/bin/env python3
"""Tests for X bookmark analyzer."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import scripts.x_bookmark_analyzer as ba_mod  # noqa: E402


class TestClusterByTopic:
    def test_clusters_bookmarks(self):
        bookmarks = [
            {"text": "agent system", "topic_tags": ["agents", "ai"], "handle": "a"},
            {"text": "another agent", "topic_tags": ["agents"], "handle": "b"},
            {"text": "saas product", "topic_tags": ["startup"], "handle": "c"},
        ]
        clusters = ba_mod._cluster_by_topic(bookmarks)
        assert "agents" in clusters
        assert len(clusters["agents"]) == 2
        assert "startup" in clusters

    def test_empty_bookmarks(self):
        clusters = ba_mod._cluster_by_topic([])
        assert clusters == {}


class TestIdentifyKeyAuthors:
    def test_counts_authors(self):
        bookmarks = [
            {"handle": "user1"},
            {"handle": "user1"},
            {"handle": "user2"},
        ]
        authors = ba_mod._identify_key_authors(bookmarks)
        assert authors[0] == ("user1", 2)
        assert authors[1] == ("user2", 1)

    def test_skips_empty_handles(self):
        bookmarks = [{"handle": ""}, {"handle": "user1"}]
        authors = ba_mod._identify_key_authors(bookmarks)
        assert len(authors) == 1


class TestExtractIdeaCandidates:
    def test_creates_candidates_for_clusters(self):
        clusters = {
            "agents": [
                {"text": "agent system", "handle": "a", "url": "u1"},
                {"text": "another agent", "handle": "b", "url": "u2"},
            ],
        }
        ideas = ba_mod._extract_idea_candidates(clusters)
        assert len(ideas) == 1
        assert "agents" in ideas[0]["title"].lower()

    def test_skips_single_item_clusters(self):
        clusters = {
            "solo": [{"text": "only one", "handle": "a", "url": "u1"}],
        }
        ideas = ba_mod._extract_idea_candidates(clusters)
        assert len(ideas) == 0


class TestWriteIntelligenceBrief:
    def test_produces_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "outputs"
            tool_dir = Path(tmp) / "tool"
            with patch.object(ba_mod, "OUTPUT_DIR", out_dir), patch.object(ba_mod, "TOOL_DIR", tool_dir):
                clusters = {"agents": [{"text": "test", "handle": "a", "url": "u1"}]}
                authors = [("user1", 3)]
                ideas = [{"title": "Test idea", "summary": "test", "recommended_action": "review"}]
                bookmarks = [{"text": "test", "handle": "a"}]
                md_path, json_path = ba_mod._write_intelligence_brief(clusters, authors, ideas, bookmarks)
                assert md_path.exists()
                assert json_path.exists()
                content = md_path.read_text()
                assert "Bookmark Intelligence Brief" in content
