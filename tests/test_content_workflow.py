#!/usr/bin/env python3
"""
Tests for scripts/content_workflow.py -- Content Workflow Pipeline.

Covers all 5 pipeline stages, stage transitions, data model,
SQLite persistence, tag extraction, stats, and CLI argument parsing.
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys
import tempfile
from pathlib import Path
from unittest import mock

import pytest

# Ensure scripts/ is on the path
BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR / "scripts"))

import content_workflow as cw


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_db(tmp_path):
    """Return a temporary database path for test isolation."""
    return str(tmp_path / "test_content_workflow.db")


@pytest.fixture
def captured_item(tmp_db):
    """Create and return a captured item for use in downstream tests."""
    result = cw.capture(
        source_type="note",
        body="AI governance is the key to trustworthy agent systems.",
        title="Governance Note",
        db_path=tmp_db,
    )
    assert result["ok"] is True
    return result["id"], tmp_db


@pytest.fixture
def processed_item(captured_item):
    """Create a processed item (capture -> process)."""
    item_id, tmp_db = captured_item
    result = cw.process_item(item_id, db_path=tmp_db)
    assert result["ok"] is True
    return item_id, tmp_db


@pytest.fixture
def created_item(processed_item):
    """Create a content-created item (process -> create)."""
    item_id, tmp_db = processed_item
    result = cw.create_from_item(item_id, output_type="thread", db_path=tmp_db)
    assert result["ok"] is True
    return item_id, tmp_db


# ---------------------------------------------------------------------------
# Stage 1: CAPTURE tests
# ---------------------------------------------------------------------------

class TestCapture:

    def test_capture_note(self, tmp_db):
        result = cw.capture(
            source_type="note",
            body="This is a quick idea about agent swarms.",
            db_path=tmp_db,
        )
        assert result["ok"] is True
        assert len(result["id"]) == 12
        assert result["item"]["stage"] == "capture"
        assert result["item"]["source_type"] == "note"

    def test_capture_bookmark(self, tmp_db):
        result = cw.capture_bookmark(
            url="https://example.com/article",
            text="Interesting article about AI safety.",
            db_path=tmp_db,
        )
        assert result["ok"] is True
        assert result["item"]["source_type"] == "bookmark"
        assert result["item"]["metadata"]["source_url"] == "https://example.com/article"

    def test_capture_url(self, tmp_db):
        result = cw.capture_url(
            url="https://example.com/research",
            title="Research Paper",
            db_path=tmp_db,
        )
        assert result["ok"] is True
        assert result["item"]["source_type"] == "url"

    def test_capture_voice_placeholder(self, tmp_db):
        result = cw.capture(
            source_type="voice",
            body="Transcribed voice memo about trading strategies.",
            title="Voice Memo #1",
            db_path=tmp_db,
        )
        assert result["ok"] is True
        assert result["item"]["source_type"] == "voice"

    def test_capture_file_placeholder(self, tmp_db):
        result = cw.capture(
            source_type="file",
            body="Content extracted from uploaded PDF.",
            title="Quarterly Report",
            metadata={"file_path": "/uploads/report.pdf"},
            db_path=tmp_db,
        )
        assert result["ok"] is True
        assert result["item"]["source_type"] == "file"
        assert result["item"]["metadata"]["file_path"] == "/uploads/report.pdf"

    def test_capture_invalid_source_type(self, tmp_db):
        result = cw.capture(
            source_type="telegram",
            body="Some content",
            db_path=tmp_db,
        )
        assert result["ok"] is False
        assert "Invalid source_type" in result["error"]

    def test_capture_empty_body_rejected(self, tmp_db):
        result = cw.capture(
            source_type="note",
            body="",
            db_path=tmp_db,
        )
        assert result["ok"] is False
        assert "body is required" in result["error"]

    def test_capture_whitespace_body_rejected(self, tmp_db):
        result = cw.capture(
            source_type="note",
            body="   ",
            db_path=tmp_db,
        )
        assert result["ok"] is False

    def test_capture_auto_title(self, tmp_db):
        long_body = "A" * 100
        result = cw.capture(
            source_type="note",
            body=long_body,
            db_path=tmp_db,
        )
        assert result["ok"] is True
        assert result["item"]["title"].endswith("...")
        assert len(result["item"]["title"]) <= 64  # 60 + "..."


# ---------------------------------------------------------------------------
# Stage 2: PROCESS tests
# ---------------------------------------------------------------------------

class TestProcess:

    def test_process_adds_tags(self, captured_item):
        item_id, tmp_db = captured_item
        result = cw.process_item(item_id, db_path=tmp_db)
        assert result["ok"] is True
        assert result["stage"] == "process"
        # The body mentions "governance" and "agent" so tags should be detected
        assert len(result["tags"]) > 0

    def test_process_detects_theme(self, captured_item):
        item_id, tmp_db = captured_item
        result = cw.process_item(item_id, db_path=tmp_db)
        assert result["ok"] is True
        # Should detect ai_governance or agent_systems
        assert result["theme"] in cw.THEME_MAP or result["theme"] == ""

    def test_process_generates_summary(self, captured_item):
        item_id, tmp_db = captured_item
        result = cw.process_item(item_id, db_path=tmp_db)
        assert result["ok"] is True
        assert len(result["summary"]) > 0

    def test_process_nonexistent_item(self, tmp_db):
        result = cw.process_item("nonexistent_id", db_path=tmp_db)
        assert result["ok"] is False
        assert "not found" in result["error"]

    def test_process_wrong_stage(self, processed_item):
        item_id, tmp_db = processed_item
        # Try to process again (already in process stage)
        result = cw.process_item(item_id, db_path=tmp_db)
        assert result["ok"] is False
        assert "expected 'capture'" in result["error"]


# ---------------------------------------------------------------------------
# Stage 3: CREATE tests
# ---------------------------------------------------------------------------

class TestCreate:

    def test_create_thread(self, processed_item):
        item_id, tmp_db = processed_item
        result = cw.create_from_item(item_id, output_type="thread", db_path=tmp_db)
        assert result["ok"] is True
        assert result["stage"] == "create"
        assert result["output_type"] == "thread"
        assert len(result["content_preview"]) > 0

    def test_create_invalid_output_type(self, processed_item):
        item_id, tmp_db = processed_item
        result = cw.create_from_item(item_id, output_type="podcast", db_path=tmp_db)
        assert result["ok"] is False
        assert "Invalid output_type" in result["error"]

    def test_create_wrong_stage(self, captured_item):
        item_id, tmp_db = captured_item
        # Item is in capture stage, not process
        result = cw.create_from_item(item_id, db_path=tmp_db)
        assert result["ok"] is False
        assert "expected 'process'" in result["error"]


# ---------------------------------------------------------------------------
# Stage 4: PUBLISH tests
# ---------------------------------------------------------------------------

class TestPublish:

    def test_publish_wrong_stage(self, processed_item):
        item_id, tmp_db = processed_item
        # Item is in process stage, not create
        result = cw.publish_item(item_id, db_path=tmp_db)
        assert result["ok"] is False
        assert "expected 'create'" in result["error"]

    def test_publish_moves_to_publish_stage(self, created_item):
        item_id, tmp_db = created_item
        result = cw.publish_item(item_id, platform="x", db_path=tmp_db)
        assert result["ok"] is True
        assert result["stage"] == "publish"
        assert result["platform"] == "x"


# ---------------------------------------------------------------------------
# Stage transitions (move)
# ---------------------------------------------------------------------------

class TestStageTransitions:

    def test_valid_forward_transition(self, captured_item):
        item_id, tmp_db = captured_item
        result = cw.move_item(item_id, to_stage="process", db_path=tmp_db)
        assert result["ok"] is True
        assert result["from_stage"] == "capture"
        assert result["to_stage"] == "process"

    def test_invalid_skip_transition(self, captured_item):
        item_id, tmp_db = captured_item
        # Cannot skip from capture directly to create
        result = cw.move_item(item_id, to_stage="create", db_path=tmp_db)
        assert result["ok"] is False
        assert "Cannot move" in result["error"]

    def test_invalid_backward_transition(self, processed_item):
        item_id, tmp_db = processed_item
        # Cannot go backward from process to capture
        result = cw.move_item(item_id, to_stage="capture", db_path=tmp_db)
        assert result["ok"] is False

    def test_invalid_stage_name(self, captured_item):
        item_id, tmp_db = captured_item
        result = cw.move_item(item_id, to_stage="nonexistent", db_path=tmp_db)
        assert result["ok"] is False
        assert "Invalid stage" in result["error"]

    def test_move_nonexistent_item(self, tmp_db):
        result = cw.move_item("does_not_exist", to_stage="process", db_path=tmp_db)
        assert result["ok"] is False
        assert "not found" in result["error"]

    def test_full_pipeline_transition(self, tmp_db):
        """Test the full pipeline: capture -> process -> create -> publish -> analyze."""
        # Capture
        result = cw.capture(
            source_type="note",
            body="Test full pipeline with agent orchestration topic.",
            db_path=tmp_db,
        )
        assert result["ok"] is True
        item_id = result["id"]

        # Move through stages
        for from_stage, to_stage in [
            ("capture", "process"),
            ("process", "create"),
            ("create", "publish"),
            ("publish", "analyze"),
        ]:
            result = cw.move_item(item_id, to_stage=to_stage, db_path=tmp_db)
            assert result["ok"] is True, f"Failed moving {from_stage} -> {to_stage}: {result}"
            assert result["to_stage"] == to_stage

        # Verify terminal stage
        result = cw.move_item(item_id, to_stage="capture", db_path=tmp_db)
        assert result["ok"] is False


# ---------------------------------------------------------------------------
# Tag extraction
# ---------------------------------------------------------------------------

class TestTagExtraction:

    def test_extract_governance_tags(self):
        tags = cw._extract_tags("AI governance and safety alignment")
        assert "ai_governance" in tags

    def test_extract_agent_tags(self):
        tags = cw._extract_tags("Building multi-agent swarm orchestration")
        assert "agent_systems" in tags

    def test_extract_multiple_tags(self):
        tags = cw._extract_tags(
            "AI governance with agent swarms for privacy and data sovereignty"
        )
        assert len(tags) >= 2

    def test_extract_no_tags(self):
        tags = cw._extract_tags("A nice day for a walk in the park")
        assert tags == []

    def test_detect_theme(self):
        theme = cw._detect_theme("trading market backtest order block")
        assert theme == "trading_intelligence"

    def test_detect_theme_empty(self):
        theme = cw._detect_theme("nothing relevant here")
        assert theme == ""


# ---------------------------------------------------------------------------
# Query and persistence
# ---------------------------------------------------------------------------

class TestQueryAndPersistence:

    def test_get_item(self, captured_item):
        item_id, tmp_db = captured_item
        item = cw.get_item(item_id, db_path=tmp_db)
        assert item is not None
        assert item["id"] == item_id
        assert item["stage"] == "capture"

    def test_get_nonexistent_item(self, tmp_db):
        item = cw.get_item("does_not_exist", db_path=tmp_db)
        assert item is None

    def test_list_all_items(self, tmp_db):
        # Create several items
        for i in range(3):
            cw.capture(source_type="note", body=f"Item {i}", db_path=tmp_db)
        items = cw.list_items(db_path=tmp_db)
        assert len(items) == 3

    def test_list_filter_by_stage(self, tmp_db):
        cw.capture(source_type="note", body="Item A", db_path=tmp_db)
        result = cw.capture(source_type="note", body="Item B with governance", db_path=tmp_db)
        cw.move_item(result["id"], to_stage="process", db_path=tmp_db)

        capture_items = cw.list_items(stage="capture", db_path=tmp_db)
        process_items = cw.list_items(stage="process", db_path=tmp_db)
        assert len(capture_items) == 1
        assert len(process_items) == 1

    def test_persistence_across_connections(self, tmp_db):
        """Verify data survives closing and reopening the database."""
        result = cw.capture(
            source_type="note",
            body="Persistence test item",
            db_path=tmp_db,
        )
        item_id = result["id"]

        # Get item through a new connection
        item = cw.get_item(item_id, db_path=tmp_db)
        assert item is not None
        assert item["body"] == "Persistence test item"


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

class TestStats:

    def test_stats_empty_db(self, tmp_db):
        stats = cw.get_stats(db_path=tmp_db)
        assert stats["total_items"] == 0
        assert all(v == 0 for v in stats["by_stage"].values())

    def test_stats_with_items(self, tmp_db):
        cw.capture(source_type="note", body="Item 1", db_path=tmp_db)
        cw.capture(source_type="bookmark", body="Item 2", db_path=tmp_db)
        result = cw.capture(source_type="url", body="Item 3 about governance", db_path=tmp_db)
        cw.move_item(result["id"], to_stage="process", db_path=tmp_db)

        stats = cw.get_stats(db_path=tmp_db)
        assert stats["total_items"] == 3
        assert stats["by_stage"]["capture"] == 2
        assert stats["by_stage"]["process"] == 1
        assert "note" in stats["by_source_type"]
        assert "bookmark" in stats["by_source_type"]

    def test_publishing_frequency(self, tmp_db):
        freq = cw.get_publishing_frequency(db_path=tmp_db)
        assert freq["total_published"] == 0
        assert freq["period_days"] == 30


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

class TestContentItem:

    def test_to_dict_roundtrip(self):
        item = cw.ContentItem(
            id="abc123def012",
            stage="capture",
            source_type="note",
            title="Test",
            body="Body text",
            tags=["ai", "governance"],
            theme="ai_governance",
            created_at="2026-03-21T00:00:00+00:00",
            updated_at="2026-03-21T00:00:00+00:00",
            metadata={"key": "value"},
        )
        d = item.to_dict()
        reconstructed = cw.ContentItem.from_dict(d)
        assert reconstructed.id == item.id
        assert reconstructed.tags == item.tags
        assert reconstructed.metadata == item.metadata

    def test_from_dict_handles_json_strings(self):
        d = {
            "id": "test123",
            "stage": "capture",
            "source_type": "note",
            "title": "Test",
            "body": "Body",
            "tags": '["ai", "governance"]',  # JSON string, not list
            "metadata": '{"key": "value"}',   # JSON string, not dict
        }
        item = cw.ContentItem.from_dict(d)
        assert item.tags == ["ai", "governance"]
        assert item.metadata == {"key": "value"}


# ---------------------------------------------------------------------------
# CLI argument parsing
# ---------------------------------------------------------------------------

class TestCLI:

    def test_cli_capture(self, tmp_db):
        exit_code = cw.main([
            "--action", "capture",
            "--type", "note",
            "--body", "CLI test capture",
            "--db-path", tmp_db,
        ])
        assert exit_code == 0
        items = cw.list_items(db_path=tmp_db)
        assert len(items) == 1

    def test_cli_list(self, tmp_db):
        cw.capture(source_type="note", body="Listed item", db_path=tmp_db)
        exit_code = cw.main([
            "--action", "list",
            "--db-path", tmp_db,
        ])
        assert exit_code == 0

    def test_cli_stats(self, tmp_db):
        exit_code = cw.main([
            "--action", "stats",
            "--db-path", tmp_db,
        ])
        assert exit_code == 0

    def test_cli_capture_missing_body(self, tmp_db):
        exit_code = cw.main([
            "--action", "capture",
            "--type", "note",
            "--db-path", tmp_db,
        ])
        assert exit_code == 1

    def test_cli_process_missing_id(self, tmp_db):
        exit_code = cw.main([
            "--action", "process",
            "--db-path", tmp_db,
        ])
        assert exit_code == 1

    def test_cli_move_missing_to(self, tmp_db):
        result = cw.capture(source_type="note", body="Move test", db_path=tmp_db)
        exit_code = cw.main([
            "--action", "move",
            "--id", result["id"],
            "--db-path", tmp_db,
        ])
        assert exit_code == 1

    def test_cli_get(self, tmp_db):
        result = cw.capture(source_type="note", body="Get test", db_path=tmp_db)
        exit_code = cw.main([
            "--action", "get",
            "--id", result["id"],
            "--db-path", tmp_db,
        ])
        assert exit_code == 0


# ---------------------------------------------------------------------------
# Summarize text
# ---------------------------------------------------------------------------

class TestSummarize:

    def test_short_text_unchanged(self):
        text = "Short text."
        assert cw._summarize_text(text) == text

    def test_long_text_truncated_at_sentence(self):
        text = "First sentence. Second sentence. " + "X" * 200
        summary = cw._summarize_text(text, max_length=50)
        assert len(summary) <= 50
        assert summary.endswith(".")

    def test_long_text_no_sentence_boundary(self):
        text = "A" * 300
        summary = cw._summarize_text(text, max_length=100)
        assert summary.endswith("...")


# ---------------------------------------------------------------------------
# ID generation
# ---------------------------------------------------------------------------

class TestIDGeneration:

    def test_id_length(self):
        item_id = cw._generate_id()
        assert len(item_id) == 12

    def test_id_uniqueness(self):
        ids = {cw._generate_id() for _ in range(100)}
        assert len(ids) == 100  # all unique
