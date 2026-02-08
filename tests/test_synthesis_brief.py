#!/usr/bin/env python3
"""Tests for governed synthesis brief flow."""

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import agents.synthesis_agent as synthesis_mod  # noqa: E402


class _DummyPaths:
    def __init__(self, root: Path):
        self.outputs_synthesis_drafts = root / "drafts"
        self.outputs_synthesis_final = root / "final"
        self.outputs_synthesis_drafts.mkdir(parents=True, exist_ok=True)
        self.outputs_synthesis_final.mkdir(parents=True, exist_ok=True)


class _DummyStorage:
    def __init__(self, root: Path):
        self.paths = _DummyPaths(root)


def test_synthesis_generate_and_approve():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        sources_path = tmp_path / "sources.json"
        sources = [
            {
                "source": "canon-note",
                "notes": "Compression and governance need explicit risk handling",
                "timestamp": "2026-02-07T00:00:00+00:00",
                "title": "Governance note",
            },
            {
                "source": "market-note",
                "notes": "Trading systems require disciplined risk controls",
                "timestamp": "2026-02-06T00:00:00+00:00",
                "title": "Trading note",
            },
        ]
        sources_path.write_text(json.dumps(sources))

        original_storage = synthesis_mod.storage
        try:
            synthesis_mod.storage = _DummyStorage(tmp_path)
            agent = synthesis_mod.SynthesisAgent(days=30, max_sources=10)
            agent.sources_path = sources_path
            draft_path, final_path = agent.generate(auto_detect=True)

            assert draft_path.exists()
            draft_text = draft_path.read_text()
            assert "Strategic Synthesis" in draft_text
            assert "Theme detection confidence:" in draft_text

            approved = agent.approve(draft_path, final_path)
            assert approved.exists()
            assert approved.read_text() == draft_text
        finally:
            synthesis_mod.storage = original_storage

