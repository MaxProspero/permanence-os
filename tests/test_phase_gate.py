#!/usr/bin/env python3
"""Tests for phase gate evaluation."""

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from scripts.phase_gate import evaluate_phase_gate  # noqa: E402


def _write_run(log_dir: Path, stamp: str, b: int, d: int, n: int) -> None:
    path = log_dir / f"run_{stamp}.log"
    path.write_text(
        "=== Briefing Run Started: test ===\n"
        f"Briefing Status: {b} | Digest Status: {d} | NotebookLM Status: {n}\n"
    )


def _write_streak(streak_file: Path, current_streak: int) -> None:
    streak_file.write_text(
        json.dumps(
            {
                "target": 7,
                "current_streak": current_streak,
                "remaining_to_target": max(7 - current_streak, 0),
                "last_date": "2026-02-06",
                "last_status": "PASS" if current_streak > 0 else "FAIL",
                "history": {},
            }
        )
    )


def test_phase_gate_passes_when_reliability_and_streak_pass():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        log_dir = root / "logs"
        log_dir.mkdir()
        streak_file = root / "reliability_streak.json"
        _write_run(log_dir, "20260206-070000", 0, 0, 0)
        _write_run(log_dir, "20260206-120000", 0, 0, 0)
        _write_run(log_dir, "20260206-190000", 0, 0, 0)
        _write_streak(streak_file, 7)

        ok, report = evaluate_phase_gate(
            log_dir=log_dir,
            streak_path=streak_file,
            days=1,
            slots=[7, 12, 19],
            tolerance_minutes=30,
            require_notebooklm=False,
            include_today=False,
            target_streak=7,
        )
        assert ok is True
        assert "Phase gate: PASS" in report


def test_phase_gate_fails_when_streak_short():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        log_dir = root / "logs"
        log_dir.mkdir()
        streak_file = root / "reliability_streak.json"
        _write_run(log_dir, "20260206-070000", 0, 0, 0)
        _write_run(log_dir, "20260206-120000", 0, 0, 0)
        _write_run(log_dir, "20260206-190000", 0, 0, 0)
        _write_streak(streak_file, 3)

        ok, report = evaluate_phase_gate(
            log_dir=log_dir,
            streak_path=streak_file,
            days=1,
            slots=[7, 12, 19],
            tolerance_minutes=30,
            require_notebooklm=False,
            include_today=False,
            target_streak=7,
        )
        assert ok is False
        assert "Streak gate: FAIL" in report


def test_phase_gate_fails_when_reliability_fails():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        log_dir = root / "logs"
        log_dir.mkdir()
        streak_file = root / "reliability_streak.json"
        _write_run(log_dir, "20260206-070000", 0, 0, 0)
        _write_streak(streak_file, 7)

        ok, report = evaluate_phase_gate(
            log_dir=log_dir,
            streak_path=streak_file,
            days=1,
            slots=[7, 12, 19],
            tolerance_minutes=30,
            require_notebooklm=False,
            include_today=False,
            target_streak=7,
        )
        assert ok is False
        assert "Reliability gate: FAIL" in report
