#!/usr/bin/env python3
"""
Tests for document ingestion in ResearcherAgent.
"""

import os
import sys
import tempfile
import json
from datetime import datetime, timezone

os.environ.setdefault("PERMANENCE_LOG_DIR", "/tmp/permanence-os-test-logs")

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(BASE_DIR)

from agents.researcher import ResearcherAgent


def test_compile_sources_from_documents():
    with tempfile.TemporaryDirectory() as tmp:
        doc_dir = os.path.join(tmp, "docs")
        os.makedirs(doc_dir, exist_ok=True)

        md_path = os.path.join(doc_dir, "note.md")
        with open(md_path, "w") as f:
            f.write("# Title\n\nThis is a test document for ingestion.\n")

        json_path = os.path.join(doc_dir, "data.json")
        with open(json_path, "w") as f:
            json.dump(
                {
                    "source": "example",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "confidence": 0.7,
                    "notes": "Example JSON source",
                },
                f,
            )

        output_path = os.path.join(tmp, "sources.json")
        ra = ResearcherAgent()
        sources = ra.compile_sources_from_documents(
            doc_dir=doc_dir, output_path=output_path, default_confidence=0.6, max_entries=10
        )

        assert os.path.exists(output_path)
        assert len(sources) >= 2
        assert any(src.get("source") == "note.md" for src in sources)
        assert any(src.get("source") == "example" for src in sources)


if __name__ == "__main__":
    test_compile_sources_from_documents()
    print("✓ Researcher document ingestion tests passed")
