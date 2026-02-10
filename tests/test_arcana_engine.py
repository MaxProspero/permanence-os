#!/usr/bin/env python3
"""Tests for Arcana Engine heuristics."""

from __future__ import annotations

import os
import tempfile

from memory.zero_point import ZeroPoint
from special.arcana_engine import ArcanaEngine


def test_digital_root_math():
    with tempfile.TemporaryDirectory() as tmp:
        zp = ZeroPoint(storage_path=os.path.join(tmp, "zp.json"))
        arcana = ArcanaEngine(zero_point=zp)
        assert arcana.calculate_digital_root(369) == 9
        assert arcana.calculate_digital_root(123) == 6
        assert arcana.calculate_digital_root(0) == 0


def test_scan_for_patterns_flags_3_6_9_with_required_fields():
    with tempfile.TemporaryDirectory() as tmp:
        zp = ZeroPoint(storage_path=os.path.join(tmp, "zp.json"))
        arcana = ArcanaEngine(zero_point=zp)
        report = arcana.scan_for_patterns([123, 111, 42, 369])

        assert "confidence" in report
        assert "heuristic_source" in report
        assert report["signal_type"] == "heuristic"
        assert report["alignment_count"] >= 2


def test_looking_glass_returns_exactly_three_branches():
    with tempfile.TemporaryDirectory() as tmp:
        zp = ZeroPoint(storage_path=os.path.join(tmp, "zp.json"))
        arcana = ArcanaEngine(zero_point=zp)
        report = arcana.project_looking_glass({"action": "test"}, branches=3)
        assert len(report["branches"]) == 3


def test_outputs_do_not_claim_oracle_or_prediction_labels():
    with tempfile.TemporaryDirectory() as tmp:
        zp = ZeroPoint(storage_path=os.path.join(tmp, "zp.json"))
        arcana = ArcanaEngine(zero_point=zp)
        report = arcana.scan_for_patterns([369, 123])
        text = str(report).lower()
        assert "oracle" not in text
        assert report["signal_type"] == "heuristic"
