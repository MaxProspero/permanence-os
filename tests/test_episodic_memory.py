#!/usr/bin/env python3
"""Tests for episodic memory JSONL logger."""

import os
import sys
import tempfile
from pathlib import Path

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.memory import EpisodicMemory  # noqa: E402


def test_write_entry_creates_file():
    with tempfile.TemporaryDirectory() as tmp:
        memory = EpisodicMemory(memory_dir=tmp)
        entry = {
            "task_id": "test_001",
            "timestamp": "2026-02-03T14:30:22Z",
            "risk_tier": "LOW",
            "canon_checks": {"consulted": True},
            "governance": {"polemarch_decision": "APPROVE"},
        }
        path = memory.write_entry(entry)
        assert Path(path).exists()


def test_write_entry_requires_fields():
    with tempfile.TemporaryDirectory() as tmp:
        memory = EpisodicMemory(memory_dir=tmp)
        try:
            memory.write_entry({"task_id": "bad"})
            assert False, "Expected ValueError for missing fields"
        except ValueError:
            assert True


def test_read_entries_filters_by_task_id():
    with tempfile.TemporaryDirectory() as tmp:
        memory = EpisodicMemory(memory_dir=tmp)
        memory.write_entry(
            {
                "task_id": "task_001",
                "timestamp": "2026-02-03T14:30:22Z",
                "risk_tier": "LOW",
                "canon_checks": {},
                "governance": {},
            }
        )
        memory.write_entry(
            {
                "task_id": "task_002",
                "timestamp": "2026-02-03T14:31:22Z",
                "risk_tier": "HIGH",
                "canon_checks": {},
                "governance": {},
            }
        )
        results = memory.read_entries(task_id="task_001")
        assert len(results) == 1
        assert results[0]["task_id"] == "task_001"


if __name__ == "__main__":
    test_write_entry_creates_file()
    test_write_entry_requires_fields()
    test_read_entries_filters_by_task_id()
    print("✓ Episodic memory tests passed")
