#!/usr/bin/env python3
"""Tests for Researcher web search adapter (mocked)."""

import os
import sys
import json
from unittest.mock import patch, MagicMock

os.environ.setdefault("PERMANENCE_LOG_DIR", "/tmp/permanence-os-test-logs")
os.environ["TAVILY_API_KEY"] = "test-key"

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from agents.researcher import ResearcherAgent


def test_web_search_compiles_sources():
    ra = ResearcherAgent()
    fake_response = MagicMock()
    fake_response.status_code = 200
    fake_response.json.return_value = {
        "results": [
            {"url": "https://example.com", "content": "Example content"},
            {"url": "https://example.org", "content": "Another content"},
        ]
    }
    with patch("requests.post", return_value=fake_response):
        sources = ra.compile_sources_from_web_search("test query", max_entries=2)
    assert len(sources) == 2
    assert sources[0]["source"].startswith("https://")
    assert sources[0]["origin"] == "tavily"


if __name__ == "__main__":
    test_web_search_compiles_sources()
    print("✓ Researcher web search tests passed")
