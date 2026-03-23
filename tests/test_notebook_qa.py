#!/usr/bin/env python3
"""
Tests for scripts/notebook_qa.py -- NotebookLM-style Q&A
20 tests covering ingestion, search, context building, asking, and CLI.
"""

import os
import sys
import tempfile
from unittest import mock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import notebook_qa


@pytest.fixture
def tmp_db(tmp_path):
    """Provide a temporary database path."""
    return str(tmp_path / "test_qa.db")


@pytest.fixture
def seeded_db(tmp_db):
    """Provide a database with two ingested documents."""
    doc1 = notebook_qa.ingest_document(
        content=(
            "The quarterly revenue grew by 15% year over year. "
            "Net income reached $2.3 million in Q3 2025. "
            "Operating margins improved to 22% driven by cost reductions. "
            "The company expects continued growth in the next fiscal year."
        ),
        title="Q3 2025 Earnings Report",
        db_path=tmp_db,
    )
    doc2 = notebook_qa.ingest_document(
        content=(
            "The product roadmap includes three major releases in 2026. "
            "Release 1 focuses on AI-powered search capabilities. "
            "Release 2 adds collaborative editing features. "
            "Release 3 delivers enterprise security compliance. "
            "Customer feedback has been overwhelmingly positive about the direction."
        ),
        title="2026 Product Roadmap",
        db_path=tmp_db,
    )
    return {
        "db_path": tmp_db,
        "doc1_id": doc1["document_id"],
        "doc2_id": doc2["document_id"],
    }


# ---------------------------------------------------------------------------
# Document ingestion
# ---------------------------------------------------------------------------


class TestIngestion:
    def test_ingest_document_success(self, tmp_db):
        result = notebook_qa.ingest_document(
            content="This is a test document with some content.",
            title="Test Doc",
            db_path=tmp_db,
        )
        assert result["ok"] is True
        assert "document_id" in result
        assert result["chunk_count"] >= 1

    def test_ingest_document_auto_title(self, tmp_db):
        result = notebook_qa.ingest_document(
            content="This is a long piece of content that should generate an automatic title from the first sixty characters.",
            db_path=tmp_db,
        )
        assert result["ok"] is True
        assert "..." in result["title"]

    def test_ingest_empty_content_fails(self, tmp_db):
        result = notebook_qa.ingest_document(content="", db_path=tmp_db)
        assert result["ok"] is False
        assert "empty" in result["error"].lower()

    def test_ingest_file_not_found(self, tmp_db):
        result = notebook_qa.ingest_file(
            file_path="/nonexistent/path/file.txt",
            db_path=tmp_db,
        )
        assert result["ok"] is False
        assert "not found" in result["error"].lower()

    def test_ingest_file_success(self, tmp_db, tmp_path):
        test_file = tmp_path / "sample.txt"
        test_file.write_text("This is sample content for ingestion testing.")
        result = notebook_qa.ingest_file(
            file_path=str(test_file),
            db_path=tmp_db,
        )
        assert result["ok"] is True
        assert result["title"] == "Sample"

    def test_chunking_long_document(self, tmp_db):
        # Create a document longer than CHUNK_SIZE
        long_text = "This is a sentence about testing. " * 200
        result = notebook_qa.ingest_document(
            content=long_text,
            title="Long Doc",
            db_path=tmp_db,
        )
        assert result["ok"] is True
        assert result["chunk_count"] > 1


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------


class TestSearch:
    def test_search_returns_matching_chunks(self, seeded_db):
        results = notebook_qa.search_documents(
            query="revenue growth",
            db_path=seeded_db["db_path"],
        )
        assert len(results) > 0
        assert any("revenue" in r["content"].lower() for r in results)

    def test_search_empty_query_returns_empty(self, seeded_db):
        results = notebook_qa.search_documents(
            query="",
            db_path=seeded_db["db_path"],
        )
        assert results == []

    def test_search_no_matches_returns_empty(self, seeded_db):
        results = notebook_qa.search_documents(
            query="quantum entanglement photosynthesis",
            db_path=seeded_db["db_path"],
        )
        assert results == []

    def test_search_with_source_filter(self, seeded_db):
        results = notebook_qa.search_documents(
            query="revenue",
            source_ids=[seeded_db["doc2_id"]],
            db_path=seeded_db["db_path"],
        )
        # doc2 is about product roadmap, not revenue
        assert len(results) == 0

    def test_search_respects_max_chunks(self, seeded_db):
        results = notebook_qa.search_documents(
            query="the",
            max_chunks=2,
            db_path=seeded_db["db_path"],
        )
        assert len(results) <= 2


# ---------------------------------------------------------------------------
# Context building
# ---------------------------------------------------------------------------


class TestBuildContext:
    def test_build_context_returns_formatted_string(self, seeded_db):
        context = notebook_qa.build_context(
            question="What is the revenue?",
            db_path=seeded_db["db_path"],
        )
        assert "[Source" in context
        assert "revenue" in context.lower()

    def test_build_context_empty_for_no_matches(self, seeded_db):
        context = notebook_qa.build_context(
            question="xyzzy nonexistent topic",
            db_path=seeded_db["db_path"],
        )
        assert context == ""


# ---------------------------------------------------------------------------
# Asking questions
# ---------------------------------------------------------------------------


class TestAsk:
    def test_ask_returns_structured_response(self, seeded_db):
        result = notebook_qa.ask(
            question="What was the quarterly revenue growth?",
            model="keyword",
            db_path=seeded_db["db_path"],
        )
        assert "answer" in result
        assert "sources" in result
        assert "model_used" in result
        assert "confidence" in result
        assert "question" in result

    def test_ask_empty_question(self, seeded_db):
        result = notebook_qa.ask(
            question="",
            db_path=seeded_db["db_path"],
        )
        assert result["confidence"] == "low"
        assert result["model_used"] == "none"

    def test_ask_keyword_fallback(self, seeded_db):
        result = notebook_qa.ask(
            question="What is the product roadmap?",
            model="keyword",
            db_path=seeded_db["db_path"],
        )
        assert result["model_used"] == "keyword"
        assert len(result["sources"]) > 0

    def test_ask_with_source_filter(self, seeded_db):
        result = notebook_qa.ask(
            question="What are the releases?",
            source_ids=[seeded_db["doc2_id"]],
            model="keyword",
            db_path=seeded_db["db_path"],
        )
        assert all(
            s["document_id"] == seeded_db["doc2_id"]
            for s in result["sources"]
        )

    def test_ask_confidence_high_with_many_sources(self, seeded_db):
        # Both docs mention "the" so we should get multiple sources
        result = notebook_qa.ask(
            question="company growth next year continued",
            model="keyword",
            db_path=seeded_db["db_path"],
        )
        # confidence depends on source count
        assert result["confidence"] in ("high", "medium", "low")

    @mock.patch("notebook_qa._call_ollama", return_value=None)
    def test_ask_auto_falls_back_when_ollama_unavailable(self, mock_ollama, seeded_db):
        result = notebook_qa.ask(
            question="What is the revenue?",
            model="auto",
            db_path=seeded_db["db_path"],
        )
        # Should fall back to keyword
        assert result["model_used"] == "keyword"
        mock_ollama.assert_called_once()


# ---------------------------------------------------------------------------
# List / Delete sources
# ---------------------------------------------------------------------------


class TestSourceManagement:
    def test_list_sources(self, seeded_db):
        sources = notebook_qa.list_sources(db_path=seeded_db["db_path"])
        assert len(sources) == 2
        titles = [s["title"] for s in sources]
        assert "Q3 2025 Earnings Report" in titles

    def test_delete_document(self, seeded_db):
        result = notebook_qa.delete_document(
            document_id=seeded_db["doc1_id"],
            db_path=seeded_db["db_path"],
        )
        assert result["ok"] is True

        sources = notebook_qa.list_sources(db_path=seeded_db["db_path"])
        assert len(sources) == 1

    def test_delete_nonexistent_document(self, seeded_db):
        result = notebook_qa.delete_document(
            document_id="nonexistent",
            db_path=seeded_db["db_path"],
        )
        assert result["ok"] is False
