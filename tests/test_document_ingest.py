"""
Tests for core/document_ingest.py -- Document Ingestion System

Covers:
  - Plain text ingestion
  - URL ingestion (mocked)
  - File ingestion (markdown, text)
  - Chunk splitting at paragraph boundaries
  - Search by keyword
  - Delete document
  - List documents
  - Duplicate detection (same content_hash)
  - Empty input handling
  - Very long document chunking
  - get_document / get_chunks
  - CLI entry point
"""

import os
import sqlite3
import tempfile
from pathlib import Path
from unittest import mock

import pytest

# Ensure project root is importable
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.document_ingest import (
    _content_hash,
    _detect_source_type,
    _extract_from_markdown,
    _extract_from_text_file,
    _store_document,
    chunk_text,
    delete_document,
    get_chunks,
    get_document,
    ingest,
    ingest_file,
    ingest_text,
    ingest_url,
    list_documents,
    main,
    search_documents,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def db_path(tmp_path):
    """Provide a temporary database path."""
    return str(tmp_path / "test_documents.db")


@pytest.fixture
def sample_text():
    return (
        "Machine learning is a subset of artificial intelligence. "
        "It focuses on building systems that learn from data.\n\n"
        "Deep learning is a further subset of machine learning. "
        "It uses neural networks with many layers.\n\n"
        "Natural language processing allows computers to understand human language."
    )


@pytest.fixture
def long_text():
    """Generate a text long enough to produce multiple chunks."""
    paragraphs = []
    for i in range(30):
        paragraphs.append(
            f"Paragraph {i}: This is a substantial block of text that discusses "
            f"topic number {i} in considerable detail. The purpose of this paragraph "
            f"is to ensure that we have enough content to trigger chunking behavior "
            f"in the document ingestion system. Each paragraph adds roughly 300 "
            f"characters of meaningful content to the overall document."
        )
    return "\n\n".join(paragraphs)


# ---------------------------------------------------------------------------
# Source type detection
# ---------------------------------------------------------------------------

class TestDetectSourceType:
    def test_url_detection(self):
        assert _detect_source_type("https://example.com/article") == "url"
        assert _detect_source_type("http://example.com") == "url"

    def test_pdf_detection(self):
        assert _detect_source_type("report.pdf") == "pdf"
        assert _detect_source_type("/path/to/file.PDF") == "pdf"

    def test_markdown_detection(self):
        assert _detect_source_type("notes.md") == "markdown"
        assert _detect_source_type("doc.markdown") == "markdown"

    def test_docx_detection(self):
        assert _detect_source_type("paper.docx") == "docx"

    def test_text_file_detection(self):
        assert _detect_source_type("readme.txt") == "text_file"

    def test_plain_text_fallback(self):
        assert _detect_source_type("just some text content") == "text"
        assert _detect_source_type("") == "text"


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------

class TestChunking:
    def test_short_text_single_chunk(self):
        text = "Short paragraph."
        chunks = chunk_text(text)
        assert len(chunks) == 1
        assert chunks[0] == "Short paragraph."

    def test_empty_text(self):
        assert chunk_text("") == []
        assert chunk_text("   ") == []

    def test_paragraph_boundary_splitting(self, sample_text):
        chunks = chunk_text(sample_text, max_size=200)
        assert len(chunks) >= 2
        # Each chunk should not exceed max_size (with some tolerance for sentence boundaries)
        for chunk in chunks:
            assert len(chunk) <= 250  # Allow slight overflow for sentence completion

    def test_long_document_chunking(self, long_text):
        chunks = chunk_text(long_text, max_size=2000)
        assert len(chunks) > 1
        # Verify all text is preserved (no data loss)
        reconstructed = "\n\n".join(chunks)
        # Some whitespace normalization is acceptable
        assert len(reconstructed) >= len(long_text) * 0.9

    def test_single_long_paragraph(self):
        # One paragraph with no paragraph breaks, exceeds max_size
        long_para = ". ".join(f"Sentence number {i} is here" for i in range(100))
        chunks = chunk_text(long_para, max_size=500)
        assert len(chunks) >= 2

    def test_respects_max_size(self, long_text):
        chunks = chunk_text(long_text, max_size=500)
        for chunk in chunks:
            # Allow tolerance for sentence completion
            assert len(chunk) <= 600


# ---------------------------------------------------------------------------
# Ingestion -- plain text
# ---------------------------------------------------------------------------

class TestIngestText:
    def test_basic_text_ingestion(self, db_path, sample_text):
        result = ingest_text(sample_text, title="ML Overview", db_path=db_path)
        assert result["ok"] is True
        assert result["id"]
        assert result["title"] == "ML Overview"
        assert result["word_count"] > 0
        assert result["chunk_count"] >= 1

    def test_auto_title_generation(self, db_path):
        text = "This is a piece of text without an explicit title provided by the user."
        result = ingest_text(text, db_path=db_path)
        assert result["ok"] is True
        assert result["title"]
        assert len(result["title"]) <= 63  # 60 chars + "..."

    def test_empty_text_rejected(self, db_path):
        result = ingest_text("", db_path=db_path)
        assert result["ok"] is False
        assert "empty" in result["error"].lower()

    def test_whitespace_only_rejected(self, db_path):
        result = ingest_text("   \n\n  ", db_path=db_path)
        assert result["ok"] is False


# ---------------------------------------------------------------------------
# Ingestion -- URL (mocked)
# ---------------------------------------------------------------------------

class TestIngestUrl:
    def test_url_ingestion_success(self, db_path):
        html = """
        <html>
        <head><title>Test Article</title></head>
        <body>
            <h1>Test Article</h1>
            <p>This is the body of a test article about machine learning.</p>
            <p>It has multiple paragraphs of content.</p>
        </body>
        </html>
        """
        mock_response = mock.MagicMock()
        mock_response.read.return_value = html.encode("utf-8")
        mock_response.__enter__ = mock.MagicMock(return_value=mock_response)
        mock_response.__exit__ = mock.MagicMock(return_value=False)

        with mock.patch("urllib.request.urlopen", return_value=mock_response):
            result = ingest_url("https://example.com/article", db_path=db_path)

        assert result["ok"] is True
        assert result["source_type"] == "url"
        assert result["title"] == "Test Article"
        assert result["word_count"] > 0

    def test_url_empty_rejected(self, db_path):
        result = ingest_url("", db_path=db_path)
        assert result["ok"] is False

    def test_url_fetch_failure(self, db_path):
        import urllib.error
        with mock.patch(
            "urllib.request.urlopen",
            side_effect=urllib.error.URLError("Connection refused"),
        ):
            result = ingest_url("https://example.com/404", db_path=db_path)
        assert result["ok"] is False
        assert "failed" in result["error"].lower() or "error" in result["error"].lower()


# ---------------------------------------------------------------------------
# Ingestion -- file
# ---------------------------------------------------------------------------

class TestIngestFile:
    def test_markdown_file(self, db_path, tmp_path):
        md_file = tmp_path / "test.md"
        md_file.write_text("# My Document\n\nThis is a markdown document with content.")
        result = ingest_file(str(md_file), db_path=db_path)
        assert result["ok"] is True
        assert result["title"] == "My Document"
        assert result["source_type"] == "markdown"

    def test_text_file(self, db_path, tmp_path):
        txt_file = tmp_path / "test.txt"
        txt_file.write_text("Plain text content in a file.")
        result = ingest_file(str(txt_file), db_path=db_path)
        assert result["ok"] is True
        assert result["source_type"] == "text_file"

    def test_nonexistent_file(self, db_path):
        result = ingest_file("/nonexistent/file.txt", db_path=db_path)
        assert result["ok"] is False
        assert "not found" in result["error"].lower()

    def test_empty_path_rejected(self, db_path):
        result = ingest_file("", db_path=db_path)
        assert result["ok"] is False

    def test_empty_file(self, db_path, tmp_path):
        empty_file = tmp_path / "empty.txt"
        empty_file.write_text("")
        result = ingest_file(str(empty_file), db_path=db_path)
        assert result["ok"] is False
        assert "no text" in result["error"].lower() or "empty" in result["error"].lower()


# ---------------------------------------------------------------------------
# Auto-detection via ingest()
# ---------------------------------------------------------------------------

class TestIngestAutoDetect:
    def test_auto_detect_text(self, db_path):
        result = ingest("Some plain text content.", db_path=db_path)
        assert result["ok"] is True
        assert result["source_type"] == "text"

    def test_auto_detect_markdown_file(self, db_path, tmp_path):
        md_file = tmp_path / "auto.md"
        md_file.write_text("# Auto Detected\n\nContent here.")
        result = ingest(str(md_file), db_path=db_path)
        assert result["ok"] is True
        assert result["source_type"] == "markdown"

    def test_empty_source_rejected(self, db_path):
        result = ingest("", db_path=db_path)
        assert result["ok"] is False

    def test_explicit_type_override(self, db_path):
        result = ingest(
            "This is text but we say it is text.",
            source_type="text",
            db_path=db_path,
        )
        assert result["ok"] is True


# ---------------------------------------------------------------------------
# Duplicate detection
# ---------------------------------------------------------------------------

class TestDuplicateDetection:
    def test_same_content_detected(self, db_path):
        text = "This exact content should only be stored once."
        r1 = ingest_text(text, title="First", db_path=db_path)
        r2 = ingest_text(text, title="Second", db_path=db_path)
        assert r1["ok"] is True
        assert r2["ok"] is True
        assert r2.get("duplicate") is True
        assert r2["id"] == r1["id"]

    def test_different_content_not_duplicate(self, db_path):
        r1 = ingest_text("Content version A.", title="A", db_path=db_path)
        r2 = ingest_text("Content version B.", title="B", db_path=db_path)
        assert r1["ok"] is True
        assert r2["ok"] is True
        assert r2.get("duplicate") is not True
        assert r2["id"] != r1["id"]


# ---------------------------------------------------------------------------
# Content hash
# ---------------------------------------------------------------------------

class TestContentHash:
    def test_deterministic(self):
        h1 = _content_hash("hello world")
        h2 = _content_hash("hello world")
        assert h1 == h2

    def test_different_content(self):
        h1 = _content_hash("hello")
        h2 = _content_hash("world")
        assert h1 != h2

    def test_hash_length(self):
        h = _content_hash("test")
        assert len(h) == 32


# ---------------------------------------------------------------------------
# Query operations
# ---------------------------------------------------------------------------

class TestGetDocument:
    def test_get_existing(self, db_path, sample_text):
        result = ingest_text(sample_text, title="Get Test", db_path=db_path)
        doc = get_document(result["id"], db_path=db_path)
        assert doc is not None
        assert doc["id"] == result["id"]
        assert doc["title"] == "Get Test"
        assert doc["full_text"] == sample_text

    def test_get_nonexistent(self, db_path):
        doc = get_document("nonexistent_id", db_path=db_path)
        assert doc is None


class TestGetChunks:
    def test_get_chunks(self, db_path, sample_text):
        result = ingest_text(sample_text, title="Chunk Test", db_path=db_path)
        chunks = get_chunks(result["id"], db_path=db_path)
        assert len(chunks) >= 1
        assert chunks[0]["document_id"] == result["id"]
        assert chunks[0]["chunk_index"] == 0
        assert chunks[0]["word_count"] > 0

    def test_get_chunks_nonexistent(self, db_path):
        chunks = get_chunks("nonexistent_id", db_path=db_path)
        assert chunks == []


class TestListDocuments:
    def test_list_empty(self, db_path):
        docs = list_documents(db_path=db_path)
        assert docs == []

    def test_list_after_ingest(self, db_path):
        ingest_text("Document one.", title="Doc 1", db_path=db_path)
        ingest_text("Document two.", title="Doc 2", db_path=db_path)
        docs = list_documents(db_path=db_path)
        assert len(docs) == 2

    def test_list_limit(self, db_path):
        for i in range(5):
            ingest_text(f"Document number {i} content.", title=f"Doc {i}", db_path=db_path)
        docs = list_documents(limit=3, db_path=db_path)
        assert len(docs) == 3


class TestDeleteDocument:
    def test_delete_existing(self, db_path):
        result = ingest_text("Delete me.", title="To Delete", db_path=db_path)
        assert delete_document(result["id"], db_path=db_path) is True
        assert get_document(result["id"], db_path=db_path) is None
        assert get_chunks(result["id"], db_path=db_path) == []

    def test_delete_nonexistent(self, db_path):
        assert delete_document("nonexistent_id", db_path=db_path) is False


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------

class TestSearchDocuments:
    def test_search_by_keyword(self, db_path, sample_text):
        ingest_text(sample_text, title="ML Overview", db_path=db_path)
        results = search_documents("machine learning", db_path=db_path)
        assert len(results) >= 1
        assert results[0]["title"] == "ML Overview"

    def test_search_empty_query(self, db_path):
        results = search_documents("", db_path=db_path)
        assert results == []

    def test_search_no_results(self, db_path):
        ingest_text("Nothing relevant here.", title="Irrelevant", db_path=db_path)
        results = search_documents("quantum computing", db_path=db_path)
        assert len(results) == 0

    def test_search_limit(self, db_path):
        for i in range(5):
            ingest_text(
                f"Document about topic alpha number {i}.",
                title=f"Alpha {i}",
                db_path=db_path,
            )
        results = search_documents("alpha", limit=3, db_path=db_path)
        assert len(results) <= 3

    def test_search_result_structure(self, db_path, sample_text):
        ingest_text(sample_text, title="Structure Test", db_path=db_path)
        results = search_documents("neural", db_path=db_path)
        assert len(results) >= 1
        r = results[0]
        assert "id" in r
        assert "title" in r
        assert "snippet" in r
        assert "source_type" in r
        assert "created_at" in r


# ---------------------------------------------------------------------------
# Long document
# ---------------------------------------------------------------------------

class TestLongDocumentIngestion:
    def test_long_document_creates_multiple_chunks(self, db_path, long_text):
        result = ingest_text(long_text, title="Long Doc", db_path=db_path)
        assert result["ok"] is True
        assert result["chunk_count"] > 1
        chunks = get_chunks(result["id"], db_path=db_path)
        assert len(chunks) == result["chunk_count"]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

class TestCLI:
    def test_cli_ingest_text(self, db_path):
        rc = main([
            "--action", "ingest",
            "--source", "CLI test content.",
            "--source-type", "text",
            "--title", "CLI Test",
            "--db-path", db_path,
        ])
        assert rc == 0

    def test_cli_list(self, db_path):
        main([
            "--action", "ingest",
            "--source", "Item for listing.",
            "--db-path", db_path,
        ])
        rc = main(["--action", "list", "--db-path", db_path])
        assert rc == 0

    def test_cli_search(self, db_path):
        main([
            "--action", "ingest",
            "--source", "Searchable content about governance.",
            "--db-path", db_path,
        ])
        rc = main([
            "--action", "search",
            "--query", "governance",
            "--db-path", db_path,
        ])
        assert rc == 0

    def test_cli_missing_source(self, db_path):
        rc = main(["--action", "ingest", "--db-path", db_path])
        assert rc == 1

    def test_cli_missing_query(self, db_path):
        rc = main(["--action", "search", "--db-path", db_path])
        assert rc == 1
