#!/usr/bin/env python3
"""Tests for Google Docs parsing helpers."""

import json
import os
import tempfile

from agents.researcher import ResearcherAgent


def test_extract_google_doc_text():
    agent = ResearcherAgent()
    doc = {
        "body": {
            "content": [
                {
                    "paragraph": {
                        "elements": [
                            {"textRun": {"content": "Hello "}},
                            {"textRun": {"content": "world"}},
                        ]
                    }
                },
                {"paragraph": {"elements": [{"textRun": {"content": "\nNext line"}}]}},
            ]
        }
    }
    text = agent._extract_google_doc_text(doc)
    assert "Hello world" in text
    assert "Next line" in text


def test_read_ids_file_json():
    agent = ResearcherAgent()
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "ids.json")
        with open(path, "w") as f:
            json.dump(["doc1", "doc2"], f)
        ids = agent._read_ids_file(path)
        assert ids == ["doc1", "doc2"]

