#!/usr/bin/env python3
"""Tests for Researcher URL fetch adapter."""

import os
import sys

os.environ.setdefault("PERMANENCE_LOG_DIR", "/tmp/permanence-os-test-logs")

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from agents.researcher import ResearcherAgent


def test_safe_url_blocks_localhost():
    ra = ResearcherAgent()
    assert ra._safe_url("http://127.0.0.1:8080") is False
    assert ra._safe_url("http://localhost:8080") is False


def test_safe_url_allows_https():
    ra = ResearcherAgent()
    assert ra._safe_url("https://example.com") is True


def test_read_urls_file():
    import tempfile
    from pathlib import Path

    ra = ResearcherAgent()
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "urls.txt"
        path.write_text("https://example.com\nhttps://example.org\n")
        urls = ra._read_urls_file(str(path))
        assert len(urls) == 2


if __name__ == "__main__":
    test_safe_url_blocks_localhost()
    test_safe_url_allows_https()
    test_read_urls_file()
    print("✓ Researcher url fetch tests passed")
