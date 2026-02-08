#!/usr/bin/env python3
"""Tests for glance status generation."""

import json
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from scripts.status_glance import compute_glance  # noqa: E402


def _write_run(log_dir: Path, stamp: str, b: int, d: int, n: int) -> None:
    path = log_dir / f"run_{stamp}.log"
    path.write_text(
        "=== Briefing Run Started: test ===\n"
        f"Briefing Status: {b} | Digest Status: {d} | NotebookLM Status: {n}\n"
    )


def _write_streak(path: Path, current: int, target: int = 7) -> None:
    path.write_text(
        json.dumps(
            {
                "current_streak": current,
                "target": target,
                "last_date": "2026-02-06",
                "last_status": "PASS" if current > 0 else "FAIL",
                "history": {},
            }
        )
    )


def _write_phase(log_dir: Path, result: str) -> None:
    (log_dir / "phase_gate_2026-02-06.md").write_text(f"# Phase Gate\n\n- Phase gate: {result}\n")


def test_glance_pending_before_first_slot():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        auto_logs = root / "automation"
        auto_logs.mkdir(parents=True, exist_ok=True)
        streak = root / "reliability_streak.json"
        _write_streak(streak, 0)
        payload = compute_glance(
            log_dir=auto_logs,
            streak_path=streak,
            slots=[7, 12, 19],
            tolerance_minutes=30,
            now_local=datetime(2026, 2, 6, 6, 0, 0),
        )
        assert payload["today_state"] == "PENDING"
        assert payload["slot_progress"] == "0/0"


def test_glance_pass_with_completed_slots():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        auto_logs = root / "automation"
        auto_logs.mkdir(parents=True, exist_ok=True)
        streak = root / "reliability_streak.json"
        _write_streak(streak, 3)
        _write_run(auto_logs, "20260206-070000", 0, 0, 0)
        _write_run(auto_logs, "20260206-120000", 0, 0, 0)
        payload = compute_glance(
            log_dir=auto_logs,
            streak_path=streak,
            slots=[7, 12, 19],
            tolerance_minutes=30,
            now_local=datetime(2026, 2, 6, 12, 30, 0),
        )
        assert payload["today_state"] == "PASS"
        assert payload["slot_progress"] == "2/2"


def test_glance_uses_phase_result_when_present():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        auto_logs = root / "automation"
        auto_logs.mkdir(parents=True, exist_ok=True)
        streak = root / "reliability_streak.json"
        _write_streak(streak, 7)
        _write_phase(root, "PASS")
        _write_run(auto_logs, "20260206-070000", 0, 0, 0)
        payload = compute_glance(
            log_dir=auto_logs,
            streak_path=streak,
            slots=[7, 12, 19],
            tolerance_minutes=30,
            now_local=datetime(2026, 2, 6, 8, 0, 0),
        )
        assert payload["phase_gate"] == "PASS"
