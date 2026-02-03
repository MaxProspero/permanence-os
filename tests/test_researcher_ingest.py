#!/usr/bin/env python3
"""Tests for Researcher tool output ingestion."""

import os
import json
import tempfile
import sys

os.environ.setdefault("PERMANENCE_LOG_DIR", "/tmp/permanence-os-test-logs")

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from agents.researcher import ResearcherAgent


def test_ingest_tool_outputs():
    ra = ResearcherAgent()
    with tempfile.TemporaryDirectory() as temp:
        tool_dir = os.path.join(temp, "tool")
        os.makedirs(tool_dir, exist_ok=True)

        json_path = os.path.join(tool_dir, "tool_output.json")
        with open(json_path, "w") as f:
            json.dump({"url": "https://example.com", "retrieved_at": "2026-02-02T00:00:00+00:00"}, f)

        text_path = os.path.join(tool_dir, "raw.txt")
        with open(text_path, "w") as f:
            f.write("raw output")

        out_path = os.path.join(temp, "sources.json")
        sources = ra.compile_sources_from_tool_memory(tool_dir=tool_dir, output_path=out_path, default_confidence=0.4)

        assert len(sources) >= 2
        for src in sources:
            assert "source" in src
            assert "timestamp" in src
            assert "confidence" in src

        with open(out_path, "r") as f:
            saved = json.load(f)
        assert len(saved) == len(sources)


if __name__ == "__main__":
    test_ingest_tool_outputs()
    print("✓ Researcher ingest tests passed")
