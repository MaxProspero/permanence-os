"""
Tests for scripts/semantic_search.py -- Cross-System Semantic Search

Covers:
  - Search across entities
  - Search across documents
  - Search across content workflow items
  - Combined search with type filter
  - Empty query returns nothing
  - Limit parameter works
  - Results have correct structure (id, type, title, snippet, score)
  - Graceful handling when databases don't exist
"""

import json
import os
import sqlite3
from pathlib import Path

import pytest

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.semantic_search import (
    search,
    search_content,
    search_documents,
    search_entities,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def entity_db(tmp_path):
    """Create a temporary entity graph database with test data."""
    db_path = str(tmp_path / "entity_graph.db")
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE entities (
            id TEXT PRIMARY KEY,
            entity_type TEXT NOT NULL,
            title TEXT NOT NULL,
            status TEXT DEFAULT 'active',
            properties TEXT DEFAULT '{}',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            created_by TEXT DEFAULT 'user'
        )
    """)
    # Insert test entities
    entities = [
        ("ent001", "NOTE", "Machine Learning Notes", "active",
         json.dumps({"topic": "ML"}), "2026-03-01T00:00:00Z", "2026-03-01T00:00:00Z", "user"),
        ("ent002", "TASK", "Review AI governance paper", "active",
         json.dumps({"priority": "high"}), "2026-03-02T00:00:00Z", "2026-03-02T00:00:00Z", "user"),
        ("ent003", "TICKER", "AAPL Analysis", "active",
         json.dumps({"symbol": "AAPL"}), "2026-03-03T00:00:00Z", "2026-03-03T00:00:00Z", "user"),
        ("ent004", "NOTE", "Deep learning architectures", "active",
         json.dumps({}), "2026-03-04T00:00:00Z", "2026-03-04T00:00:00Z", "user"),
        ("ent005", "DOCUMENT", "Governance framework doc", "deleted",
         json.dumps({}), "2026-03-05T00:00:00Z", "2026-03-05T00:00:00Z", "user"),
    ]
    conn.executemany(
        """INSERT INTO entities
           (id, entity_type, title, status, properties, created_at, updated_at, created_by)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        entities,
    )
    conn.commit()
    conn.close()
    return db_path


@pytest.fixture
def documents_db(tmp_path):
    """Create a temporary documents database with test data."""
    db_path = str(tmp_path / "documents.db")
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE documents (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL DEFAULT '',
            source TEXT NOT NULL DEFAULT '',
            source_type TEXT NOT NULL DEFAULT 'text',
            content_hash TEXT NOT NULL DEFAULT '',
            word_count INTEGER NOT NULL DEFAULT 0,
            chunk_count INTEGER NOT NULL DEFAULT 0,
            full_text TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE chunks (
            id TEXT PRIMARY KEY,
            document_id TEXT NOT NULL,
            chunk_index INTEGER NOT NULL,
            text TEXT NOT NULL DEFAULT '',
            word_count INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (document_id) REFERENCES documents(id)
        )
    """)
    # Insert test documents
    conn.execute(
        """INSERT INTO documents
           (id, title, source, source_type, content_hash, word_count, chunk_count, full_text, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        ("doc001", "Neural Network Guide", "https://example.com/nn",
         "url", "hash001", 500, 2,
         "Neural networks are computing systems inspired by biological neural networks.",
         "2026-03-10T00:00:00Z"),
    )
    conn.execute(
        """INSERT INTO documents
           (id, title, source, source_type, content_hash, word_count, chunk_count, full_text, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        ("doc002", "Governance Playbook", "local_file",
         "markdown", "hash002", 1200, 4,
         "AI governance requires transparent decision-making processes.",
         "2026-03-11T00:00:00Z"),
    )
    # Insert chunks
    chunks = [
        ("chk001", "doc001", 0, "Neural networks are computing systems inspired by biological neural networks.", 10),
        ("chk002", "doc001", 1, "Training involves adjusting weights through backpropagation.", 7),
        ("chk003", "doc002", 0, "AI governance requires transparent decision-making processes.", 8),
        ("chk004", "doc002", 1, "Every agent must preserve a human approval gate.", 9),
        ("chk005", "doc002", 2, "Risk management is essential for trading systems.", 7),
        ("chk006", "doc002", 3, "Compliance auditing reduces errors in automated workflows.", 7),
    ]
    conn.executemany(
        "INSERT INTO chunks (id, document_id, chunk_index, text, word_count) VALUES (?, ?, ?, ?, ?)",
        chunks,
    )
    conn.commit()
    conn.close()
    return db_path


@pytest.fixture
def content_db(tmp_path):
    """Create a temporary content workflow database with test data."""
    db_path = str(tmp_path / "content_workflow.db")
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE content_items (
            id TEXT PRIMARY KEY,
            stage TEXT NOT NULL DEFAULT 'capture',
            source_type TEXT NOT NULL DEFAULT 'note',
            title TEXT NOT NULL DEFAULT '',
            body TEXT NOT NULL DEFAULT '',
            tags TEXT NOT NULL DEFAULT '[]',
            theme TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            metadata TEXT NOT NULL DEFAULT '{}'
        )
    """)
    items = [
        ("cwi001", "capture", "note", "AI Safety Research",
         "Research notes on alignment and safety in AI systems.",
         "[]", "ai_governance", "2026-03-15T00:00:00Z", "2026-03-15T00:00:00Z", "{}"),
        ("cwi002", "process", "bookmark", "Trading Strategy Review",
         "SMC order blocks and liquidity analysis for swing trading.",
         "[]", "trading_intelligence", "2026-03-16T00:00:00Z", "2026-03-16T00:00:00Z", "{}"),
    ]
    conn.executemany(
        """INSERT INTO content_items
           (id, stage, source_type, title, body, tags, theme, created_at, updated_at, metadata)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        items,
    )
    conn.commit()
    conn.close()
    return db_path


# ---------------------------------------------------------------------------
# Entity search
# ---------------------------------------------------------------------------

class TestSearchEntities:
    def test_search_by_title(self, entity_db):
        results = search_entities("machine learning", db_path=entity_db)
        assert len(results) >= 1
        assert results[0]["title"] == "Machine Learning Notes"
        assert results[0]["type"] == "note"

    def test_search_by_properties(self, entity_db):
        results = search_entities("AAPL", db_path=entity_db)
        assert len(results) >= 1
        assert results[0]["id"] == "ent003"

    def test_empty_query(self, entity_db):
        results = search_entities("", db_path=entity_db)
        assert results == []

    def test_no_deleted_results(self, entity_db):
        results = search_entities("governance", db_path=entity_db)
        ids = [r["id"] for r in results]
        assert "ent005" not in ids  # deleted entity excluded

    def test_entity_type_filter(self, entity_db):
        results = search_entities("learning", entity_type="NOTE", db_path=entity_db)
        assert len(results) >= 1
        for r in results:
            assert r["type"] == "note"

    def test_nonexistent_db(self, tmp_path):
        results = search_entities("test", db_path=str(tmp_path / "nonexistent.db"))
        assert results == []


# ---------------------------------------------------------------------------
# Document search
# ---------------------------------------------------------------------------

class TestSearchDocuments:
    def test_search_by_content(self, documents_db):
        results = search_documents("neural", db_path=documents_db)
        assert len(results) >= 1
        assert results[0]["id"] == "doc001"
        assert results[0]["type"] == "document"

    def test_search_governance(self, documents_db):
        results = search_documents("governance", db_path=documents_db)
        assert len(results) >= 1
        assert results[0]["id"] == "doc002"

    def test_empty_query(self, documents_db):
        results = search_documents("", db_path=documents_db)
        assert results == []

    def test_no_results(self, documents_db):
        results = search_documents("quantum entanglement", db_path=documents_db)
        assert len(results) == 0

    def test_nonexistent_db(self, tmp_path):
        results = search_documents("test", db_path=str(tmp_path / "nonexistent.db"))
        assert results == []


# ---------------------------------------------------------------------------
# Content search
# ---------------------------------------------------------------------------

class TestSearchContent:
    def test_search_by_title(self, content_db):
        results = search_content("safety", db_path=content_db)
        assert len(results) >= 1
        assert results[0]["id"] == "cwi001"

    def test_search_by_body(self, content_db):
        results = search_content("order blocks", db_path=content_db)
        assert len(results) >= 1
        assert results[0]["id"] == "cwi002"

    def test_empty_query(self, content_db):
        results = search_content("", db_path=content_db)
        assert results == []

    def test_nonexistent_db(self, tmp_path):
        results = search_content("test", db_path=str(tmp_path / "nonexistent.db"))
        assert results == []


# ---------------------------------------------------------------------------
# Unified search
# ---------------------------------------------------------------------------

class TestUnifiedSearch:
    def test_search_across_all(self, entity_db, documents_db, content_db):
        results = search(
            "governance",
            entity_graph_db=entity_db,
            documents_db=documents_db,
            content_db=content_db,
        )
        assert len(results) >= 1
        # Should find results from multiple sources
        sources = {r["source"] for r in results}
        assert len(sources) >= 1  # At least one source has governance results

    def test_type_filter_document(self, entity_db, documents_db, content_db):
        results = search(
            "neural",
            types=["document"],
            entity_graph_db=entity_db,
            documents_db=documents_db,
            content_db=content_db,
        )
        for r in results:
            assert r["type"] == "document"

    def test_type_filter_note(self, entity_db, documents_db, content_db):
        results = search(
            "learning",
            types=["note"],
            entity_graph_db=entity_db,
            documents_db=documents_db,
            content_db=content_db,
        )
        for r in results:
            assert r["type"] == "note"

    def test_empty_query(self, entity_db, documents_db, content_db):
        results = search(
            "",
            entity_graph_db=entity_db,
            documents_db=documents_db,
            content_db=content_db,
        )
        assert results == []

    def test_limit_parameter(self, entity_db, documents_db, content_db):
        results = search(
            "a",  # broad query
            limit=3,
            entity_graph_db=entity_db,
            documents_db=documents_db,
            content_db=content_db,
        )
        assert len(results) <= 3

    def test_results_sorted_by_relevance(self, entity_db, documents_db, content_db):
        results = search(
            "governance",
            entity_graph_db=entity_db,
            documents_db=documents_db,
            content_db=content_db,
        )
        if len(results) >= 2:
            scores = [r["relevance_score"] for r in results]
            assert scores == sorted(scores, reverse=True)


# ---------------------------------------------------------------------------
# Result structure
# ---------------------------------------------------------------------------

class TestResultStructure:
    def test_entity_result_fields(self, entity_db):
        results = search_entities("machine", db_path=entity_db)
        assert len(results) >= 1
        r = results[0]
        assert "id" in r
        assert "type" in r
        assert "title" in r
        assert "snippet" in r
        assert "source" in r
        assert "relevance_score" in r
        assert "created_at" in r

    def test_document_result_fields(self, documents_db):
        results = search_documents("neural", db_path=documents_db)
        assert len(results) >= 1
        r = results[0]
        assert "id" in r
        assert "type" in r
        assert "title" in r
        assert "snippet" in r
        assert "source" in r
        assert "relevance_score" in r
        assert "created_at" in r

    def test_content_result_fields(self, content_db):
        results = search_content("safety", db_path=content_db)
        assert len(results) >= 1
        r = results[0]
        assert "id" in r
        assert "type" in r
        assert "title" in r
        assert "snippet" in r
        assert "source" in r
        assert "relevance_score" in r
        assert "created_at" in r

    def test_relevance_score_is_numeric(self, entity_db):
        results = search_entities("machine", db_path=entity_db)
        for r in results:
            assert isinstance(r["relevance_score"], (int, float))
            assert 0 <= r["relevance_score"] <= 1.0

    def test_snippet_length(self, documents_db):
        results = search_documents("neural", db_path=documents_db)
        for r in results:
            assert len(r["snippet"]) <= 203  # 200 + "..."
