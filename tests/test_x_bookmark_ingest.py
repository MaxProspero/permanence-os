#!/usr/bin/env python3
"""Tests for X bookmark ingest pipeline."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import scripts.x_bookmark_ingest as bm_mod  # noqa: E402


class TestClassifyTopic:
    def test_agents_topic(self):
        tags = bm_mod._classify_topic("how to build agentic systems with agents")
        assert "agents" in tags

    def test_multiple_topics(self):
        tags = bm_mod._classify_topic("ai saas startup using claude for automation")
        assert "ai" in tags
        assert "startup" in tags

    def test_no_match(self):
        tags = bm_mod._classify_topic("sunny weather today")
        assert tags == []

    def test_finance_topic(self):
        tags = bm_mod._classify_topic("stock market trading signals")
        assert "finance" in tags

    def test_neuroscience_topic(self):
        tags = bm_mod._classify_topic("how the human brain processes information")
        assert "neuroscience" in tags


class TestScoreBookmark:
    def test_score_with_tags(self):
        score = bm_mod._score_bookmark("test", ["agents", "ai", "startup"])
        assert score > 0

    def test_score_empty_tags(self):
        score = bm_mod._score_bookmark("test", [])
        assert score == 0

    def test_score_capped_at_10(self):
        score = bm_mod._score_bookmark("test", ["agents", "ai", "startup", "finance", "coding", "product"])
        assert score <= 10

    def test_agents_bonus(self):
        score_with = bm_mod._score_bookmark("test", ["agents"])
        score_without = bm_mod._score_bookmark("test", ["coding"])
        assert score_with > score_without


class TestBookmarkId:
    def test_deterministic(self):
        id1 = bm_mod._bookmark_id("https://x.com/test/123")
        id2 = bm_mod._bookmark_id("https://x.com/test/123")
        assert id1 == id2

    def test_prefix(self):
        bid = bm_mod._bookmark_id("https://x.com/test")
        assert bid.startswith("bookmark_")

    def test_different_urls_different_ids(self):
        id1 = bm_mod._bookmark_id("https://x.com/a")
        id2 = bm_mod._bookmark_id("https://x.com/b")
        assert id1 != id2


class TestDedupBookmarks:
    def test_filters_processed(self):
        bookmarks = [
            {"url": "https://x.com/1", "text": "first"},
            {"url": "https://x.com/2", "text": "second"},
        ]
        state = {"processed_ids": {"bookmark_" + "a" * 8: True}}
        with patch.object(bm_mod, "_bookmark_id", side_effect=lambda u: "bookmark_" + ("a" * 8 if "1" in u else "b" * 8)):
            new = bm_mod._dedup_bookmarks(bookmarks, state)
            assert len(new) == 1
            assert new[0]["text"] == "second"

    def test_empty_state(self):
        bookmarks = [{"url": "https://x.com/1", "text": "first"}]
        state = {"processed_ids": {}}
        new = bm_mod._dedup_bookmarks(bookmarks, state)
        assert len(new) == 1


class TestUpdateKnowledgeGraph:
    def test_adds_new_nodes(self):
        with tempfile.TemporaryDirectory() as tmp:
            graph_path = Path(tmp) / "graph.json"
            graph_path.write_text('{"nodes": {}, "edges": []}', encoding="utf-8")
            with patch.object(bm_mod, "GRAPH_PATH", graph_path):
                bookmarks = [
                    {
                        "url": "https://x.com/test/1",
                        "text": "test bookmark",
                        "author": "Test User",
                        "handle": "testuser",
                        "topic_tags": ["ai"],
                        "signal_score": 3,
                    }
                ]
                added = bm_mod._update_knowledge_graph(bookmarks)
                assert added == 1
                graph = json.loads(graph_path.read_text())
                assert len(graph["nodes"]) == 1

    def test_no_duplicates(self):
        with tempfile.TemporaryDirectory() as tmp:
            graph_path = Path(tmp) / "graph.json"
            bid = bm_mod._bookmark_id("https://x.com/test/1")
            existing = {"nodes": {bid: {"id": bid, "type": "bookmark"}}, "edges": []}
            graph_path.write_text(json.dumps(existing), encoding="utf-8")
            with patch.object(bm_mod, "GRAPH_PATH", graph_path):
                bookmarks = [{"url": "https://x.com/test/1", "text": "test", "author": "", "handle": "", "topic_tags": [], "signal_score": 0}]
                added = bm_mod._update_knowledge_graph(bookmarks)
                assert added == 0


class TestWriteIntakeJsonl:
    def test_writes_entries(self):
        with tempfile.TemporaryDirectory() as tmp:
            intake_path = Path(tmp) / "bookmark_intake.jsonl"
            with patch.object(bm_mod, "BOOKMARK_INTAKE_PATH", intake_path):
                bookmarks = [{"url": "https://x.com/1", "text": "test"}]
                bm_mod._write_intake_jsonl(bookmarks)
                lines = intake_path.read_text().strip().splitlines()
                assert len(lines) == 1
                row = json.loads(lines[0])
                assert row["source"] == "x_bookmark"


class TestImportCsv:
    def test_imports_csv(self):
        with tempfile.TemporaryDirectory() as tmp:
            csv_path = Path(tmp) / "bookmarks.csv"
            csv_path.write_text("url,text\nhttps://x.com/1,test bookmark\nhttps://x.com/2,another one\n", encoding="utf-8")
            bookmarks, warnings = bm_mod._import_csv(str(csv_path))
            assert len(bookmarks) == 2
            assert bookmarks[0]["url"] == "https://x.com/1"

    def test_missing_file(self):
        bookmarks, warnings = bm_mod._import_csv("/nonexistent/file.csv")
        assert bookmarks == []
        assert len(warnings) > 0
