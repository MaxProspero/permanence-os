#!/usr/bin/env python3
"""Tests for Practice Squad scrimmage and hyper simulation."""

from __future__ import annotations

import os
import tempfile

from memory.zero_point import ConfidenceLevel, MemoryType, ZeroPoint
from special.practice_squad import PracticeSquad


def _seed_recent(zp: ZeroPoint):
    zp.write(
        content="recent decision entry",
        memory_type=MemoryType.INSIGHT,
        tags=["decision"],
        source="test",
        author_agent="TEST",
        confidence=ConfidenceLevel.MEDIUM,
        evidence_count=2,
    )


def test_scrimmage_uses_recent_window_and_writes_training_insight():
    with tempfile.TemporaryDirectory() as tmp:
        zp = ZeroPoint(storage_path=os.path.join(tmp, "zp.json"))
        _seed_recent(zp)
        squad = PracticeSquad(zero_point=zp)
        result = squad.scrimmage(last_hours=24, replays=10)

        assert result["status"] == "OK"
        assert result["source_count"] >= 1
        assert result["mutated_count"] == result["source_count"] * 10

        training = zp.search(memory_type=MemoryType.TRAINING, requesting_agent="TEST")
        assert len(training) >= 1


def test_noise_injection_mutates_payload():
    with tempfile.TemporaryDirectory() as tmp:
        zp = ZeroPoint(storage_path=os.path.join(tmp, "zp.json"))
        squad = PracticeSquad(zero_point=zp)
        payload = {"entry_id": "x", "confidence": "HIGH"}

        mutated = squad._apply_noise(payload, "adversarial_injection")
        assert mutated["noise_type"] == "adversarial_injection"
        assert "adversarial_pattern" in mutated


def test_hyper_sim_completes_and_writes_entry():
    with tempfile.TemporaryDirectory() as tmp:
        zp = ZeroPoint(storage_path=os.path.join(tmp, "zp.json"))
        _seed_recent(zp)
        squad = PracticeSquad(zero_point=zp)
        result = squad.hyper_sim(iterations=1000, warp_speed=True, last_hours=24)

        assert result["status"] == "OK"
        assert result["iterations_ran"] == 1000
        training = zp.search(memory_type=MemoryType.TRAINING, requesting_agent="TEST")
        assert len(training) >= 1
