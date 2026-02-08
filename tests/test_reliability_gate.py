#!/usr/bin/env python3
"""Tests for reliability gate evaluation."""

import os
import sys
import tempfile
from pathlib import Path

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from scripts.reliability_gate import evaluate_reliability  # noqa: E402


def _write_run(log_dir: Path, stamp: str, b: int, d: int, n: int) -> None:
    path = log_dir / f"run_{stamp}.log"
    path.write_text(
        "=== Briefing Run Started: test ===\n"
        f"Briefing Status: {b} | Digest Status: {d} | NotebookLM Status: {n}\n"
    )


def test_reliability_fail_when_missing_slots():
    with tempfile.TemporaryDirectory() as tmp:
        log_dir = Path(tmp)
        # One run only: guaranteed missing slots for 2-day window.
        _write_run(log_dir, "20260206-070000", 0, 0, 0)
        ok, report = evaluate_reliability(
            log_dir=log_dir,
            days=2,
            slots=[7, 12, 19],
            tolerance_minutes=30,
            require_notebooklm=False,
            include_today=False,
        )
        assert ok is False
        assert "Missing:" in report
        assert "Gate result: FAIL" in report


def test_reliability_pass_single_day_all_slots():
    with tempfile.TemporaryDirectory() as tmp:
        log_dir = Path(tmp)
        # Build complete slots for one day.
        _write_run(log_dir, "20260206-070000", 0, 0, 0)
        _write_run(log_dir, "20260206-120000", 0, 0, 0)
        _write_run(log_dir, "20260206-190000", 0, 0, 0)
        ok, report = evaluate_reliability(
            log_dir=log_dir,
            days=1,
            slots=[7, 12, 19],
            tolerance_minutes=30,
            require_notebooklm=False,
            include_today=False,
        )
        assert ok is True
        assert "Gate result: PASS" in report


def test_reliability_slot_recovery_prefers_success():
    with tempfile.TemporaryDirectory() as tmp:
        log_dir = Path(tmp)
        # Same slot window: first failed, then successful retry.
        _write_run(log_dir, "20260206-190500", 1, 0, 0)
        _write_run(log_dir, "20260206-193500", 0, 0, 0)
        ok, report = evaluate_reliability(
            log_dir=log_dir,
            days=1,
            slots=[19],
            tolerance_minutes=90,
            require_notebooklm=False,
            include_today=False,
        )
        assert ok is True
        assert "Gate result: PASS" in report
