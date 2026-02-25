#!/usr/bin/env python3
"""Tests for daily promotion workflow."""

import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SCRIPT = os.path.join(BASE_DIR, "scripts", "promotion_daily.py")


def _write_episode(path: Path, task_id: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    payload = {
        "task_id": task_id,
        "task_goal": f"Goal for {task_id}",
        "stage": "DONE",
        "status": "DONE",
        "risk_tier": "LOW",
        "sources": [{"id": "s1"}, {"id": "s2"}],
        "created_at": now,
        "updated_at": now,
    }
    path.write_text(json.dumps(payload))


def _write_passing_gates(log_dir: Path) -> None:
    (log_dir / "status_today.json").write_text(json.dumps({"today_state": "PASS"}))
    (log_dir / "phase_gate_2026-02-25.md").write_text("# Phase Gate\n\n- Phase gate: PASS\n")


def _env(memory_dir: Path, log_dir: Path, output_dir: Path) -> dict[str, str]:
    env = os.environ.copy()
    env["PERMANENCE_MEMORY_DIR"] = str(memory_dir)
    env["PERMANENCE_LOG_DIR"] = str(log_dir)
    env["PERMANENCE_OUTPUT_DIR"] = str(output_dir)
    return env


def test_promotion_daily_runs_queue_and_review_when_gates_pass():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        memory_dir = root / "memory"
        episodic_dir = memory_dir / "episodic"
        working_dir = memory_dir / "working"
        log_dir = root / "logs"
        output_dir = root / "outputs"
        episodic_dir.mkdir(parents=True, exist_ok=True)
        working_dir.mkdir(parents=True, exist_ok=True)
        log_dir.mkdir(parents=True, exist_ok=True)
        output_dir.mkdir(parents=True, exist_ok=True)
        _write_episode(episodic_dir / "T-DAILY-PASS.json", "T-DAILY-PASS")
        _write_passing_gates(log_dir)

        result = subprocess.run(
            [sys.executable, SCRIPT, "--since-hours", "0"],
            env=_env(memory_dir, log_dir, output_dir),
            capture_output=True,
            text=True,
            check=False,
        )

        assert result.returncode == 0
        assert "promotion-daily: completed queue auto and promotion review" in result.stdout
        queue_path = memory_dir / "working" / "promotion_queue.json"
        assert queue_path.exists()
        queue = json.loads(queue_path.read_text())
        assert len(queue) == 1
        assert queue[0]["task_id"] == "T-DAILY-PASS"
        assert (output_dir / "promotion_review.md").exists()


def test_promotion_daily_skips_queue_when_gates_fail_but_writes_review():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        memory_dir = root / "memory"
        episodic_dir = memory_dir / "episodic"
        working_dir = memory_dir / "working"
        log_dir = root / "logs"
        output_dir = root / "outputs"
        episodic_dir.mkdir(parents=True, exist_ok=True)
        working_dir.mkdir(parents=True, exist_ok=True)
        log_dir.mkdir(parents=True, exist_ok=True)
        output_dir.mkdir(parents=True, exist_ok=True)
        _write_episode(episodic_dir / "T-DAILY-BLOCKED.json", "T-DAILY-BLOCKED")

        result = subprocess.run(
            [sys.executable, SCRIPT],
            env=_env(memory_dir, log_dir, output_dir),
            capture_output=True,
            text=True,
            check=False,
        )

        assert result.returncode == 0
        assert "queue auto skipped by governance gates" in result.stdout
        assert not (memory_dir / "working" / "promotion_queue.json").exists()
        review_text = (output_dir / "promotion_review.md").read_text()
        assert "- Queue items: 0" in review_text


def test_promotion_daily_strict_gates_fails_when_blocked():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        memory_dir = root / "memory"
        episodic_dir = memory_dir / "episodic"
        working_dir = memory_dir / "working"
        log_dir = root / "logs"
        output_dir = root / "outputs"
        episodic_dir.mkdir(parents=True, exist_ok=True)
        working_dir.mkdir(parents=True, exist_ok=True)
        log_dir.mkdir(parents=True, exist_ok=True)
        output_dir.mkdir(parents=True, exist_ok=True)
        _write_episode(episodic_dir / "T-DAILY-STRICT.json", "T-DAILY-STRICT")

        result = subprocess.run(
            [sys.executable, SCRIPT, "--strict-gates"],
            env=_env(memory_dir, log_dir, output_dir),
            capture_output=True,
            text=True,
            check=False,
        )

        assert result.returncode == 3
        assert "strict mode" in result.stdout
        assert not (output_dir / "promotion_review.md").exists()


def test_promotion_daily_auto_phase_policy_allows_daytime_queue_with_glance_pass():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        memory_dir = root / "memory"
        episodic_dir = memory_dir / "episodic"
        working_dir = memory_dir / "working"
        log_dir = root / "logs"
        output_dir = root / "outputs"
        episodic_dir.mkdir(parents=True, exist_ok=True)
        working_dir.mkdir(parents=True, exist_ok=True)
        log_dir.mkdir(parents=True, exist_ok=True)
        output_dir.mkdir(parents=True, exist_ok=True)
        _write_episode(episodic_dir / "T-DAILY-AUTO-PHASE.json", "T-DAILY-AUTO-PHASE")
        (log_dir / "status_today.json").write_text(json.dumps({"today_state": "PASS"}), encoding="utf-8")

        result = subprocess.run(
            [
                sys.executable,
                SCRIPT,
                "--phase-policy",
                "auto",
                "--phase-enforce-hour",
                "23",
                "--since-hours",
                "0",
            ],
            env=_env(memory_dir, log_dir, output_dir),
            capture_output=True,
            text=True,
            check=False,
        )

        assert result.returncode == 0
        assert "phase=waived" in result.stdout
        queue = json.loads((memory_dir / "working" / "promotion_queue.json").read_text())
        assert len(queue) == 1
        assert queue[0]["task_id"] == "T-DAILY-AUTO-PHASE"


def test_promotion_daily_phase_policy_always_requires_phase_gate():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        memory_dir = root / "memory"
        episodic_dir = memory_dir / "episodic"
        working_dir = memory_dir / "working"
        log_dir = root / "logs"
        output_dir = root / "outputs"
        episodic_dir.mkdir(parents=True, exist_ok=True)
        working_dir.mkdir(parents=True, exist_ok=True)
        log_dir.mkdir(parents=True, exist_ok=True)
        output_dir.mkdir(parents=True, exist_ok=True)
        _write_episode(episodic_dir / "T-DAILY-PHASE-ALWAYS.json", "T-DAILY-PHASE-ALWAYS")
        (log_dir / "status_today.json").write_text(json.dumps({"today_state": "PASS"}), encoding="utf-8")

        result = subprocess.run(
            [sys.executable, SCRIPT, "--phase-policy", "always"],
            env=_env(memory_dir, log_dir, output_dir),
            capture_output=True,
            text=True,
            check=False,
        )

        assert result.returncode == 0
        assert "phase=required" in result.stdout
        assert "queue auto skipped by governance gates" in result.stdout
        assert not (memory_dir / "working" / "promotion_queue.json").exists()
