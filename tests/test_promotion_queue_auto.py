#!/usr/bin/env python3
"""Tests for auto promotion queue behavior."""

import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SCRIPT = os.path.join(BASE_DIR, "scripts", "promotion_queue.py")


def _write_episode(path: Path, task_id: str, *, risk_tier: str = "LOW", sources: int = 2) -> None:
    now = datetime.now(timezone.utc).isoformat()
    payload = {
        "task_id": task_id,
        "task_goal": f"Goal for {task_id}",
        "stage": "DONE",
        "status": "DONE",
        "risk_tier": risk_tier,
        "sources": [{"id": f"s{i}"} for i in range(sources)],
        "created_at": now,
        "updated_at": now,
    }
    path.write_text(json.dumps(payload))


def _write_passing_gates(log_dir: Path) -> None:
    (log_dir / "status_today.json").write_text(json.dumps({"today_state": "PASS"}))
    (log_dir / "phase_gate_2026-02-25.md").write_text("# Phase Gate\n\n- Phase gate: PASS\n")


def _queue_path(memory_dir: Path) -> Path:
    return memory_dir / "working" / "promotion_queue.json"


def _env(memory_dir: Path, log_dir: Path) -> dict[str, str]:
    env = os.environ.copy()
    env["PERMANENCE_MEMORY_DIR"] = str(memory_dir)
    env["PERMANENCE_LOG_DIR"] = str(log_dir)
    return env


def test_auto_blocks_when_required_gates_fail():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        memory_dir = root / "memory"
        episodic_dir = memory_dir / "episodic"
        working_dir = memory_dir / "working"
        log_dir = root / "logs"
        episodic_dir.mkdir(parents=True, exist_ok=True)
        working_dir.mkdir(parents=True, exist_ok=True)
        log_dir.mkdir(parents=True, exist_ok=True)
        _write_episode(episodic_dir / "T-BLOCKED.json", "T-BLOCKED")

        result = subprocess.run(
            [sys.executable, SCRIPT, "auto", "--since-hours", "0"],
            env=_env(memory_dir, log_dir),
            capture_output=True,
            text=True,
            check=False,
        )

        assert result.returncode == 3
        assert "Auto promotion blocked" in result.stdout
        assert not _queue_path(memory_dir).exists()


def test_auto_adds_eligible_episode_when_gates_pass():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        memory_dir = root / "memory"
        episodic_dir = memory_dir / "episodic"
        working_dir = memory_dir / "working"
        log_dir = root / "logs"
        episodic_dir.mkdir(parents=True, exist_ok=True)
        working_dir.mkdir(parents=True, exist_ok=True)
        log_dir.mkdir(parents=True, exist_ok=True)
        _write_episode(episodic_dir / "T-AUTO-PASS.json", "T-AUTO-PASS")
        _write_passing_gates(log_dir)

        result = subprocess.run(
            [sys.executable, SCRIPT, "auto", "--max-add", "5"],
            env=_env(memory_dir, log_dir),
            capture_output=True,
            text=True,
            check=False,
        )

        assert result.returncode == 0
        assert "Auto promotion candidates added: 1" in result.stdout
        queue = json.loads(_queue_path(memory_dir).read_text())
        assert len(queue) == 1
        assert queue[0]["task_id"] == "T-AUTO-PASS"
        assert queue[0]["auto"] is True


def test_auto_dry_run_reports_candidates_without_writing_queue():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        memory_dir = root / "memory"
        episodic_dir = memory_dir / "episodic"
        working_dir = memory_dir / "working"
        log_dir = root / "logs"
        episodic_dir.mkdir(parents=True, exist_ok=True)
        working_dir.mkdir(parents=True, exist_ok=True)
        log_dir.mkdir(parents=True, exist_ok=True)
        _write_episode(episodic_dir / "T-AUTO-DRY.json", "T-AUTO-DRY")
        _write_passing_gates(log_dir)

        result = subprocess.run(
            [sys.executable, SCRIPT, "auto", "--dry-run", "--since-hours", "0"],
            env=_env(memory_dir, log_dir),
            capture_output=True,
            text=True,
            check=False,
        )

        assert result.returncode == 0
        assert "[DRY RUN] would add: T-AUTO-DRY" in result.stdout
        assert "Auto promotion candidates added: 1" in result.stdout
        assert not _queue_path(memory_dir).exists()


def test_auto_finds_gates_in_storage_root_logs_fallback():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        memory_dir = root / "memory"
        episodic_dir = memory_dir / "episodic"
        working_dir = memory_dir / "working"
        log_dir = root / "logs"
        storage_root = root / "permanence_storage"
        storage_logs = storage_root / "logs"
        episodic_dir.mkdir(parents=True, exist_ok=True)
        working_dir.mkdir(parents=True, exist_ok=True)
        log_dir.mkdir(parents=True, exist_ok=True)
        storage_logs.mkdir(parents=True, exist_ok=True)
        _write_episode(episodic_dir / "T-AUTO-STORAGE.json", "T-AUTO-STORAGE")
        _write_passing_gates(storage_logs)

        env = _env(memory_dir, log_dir)
        env["PERMANENCE_STORAGE_ROOT"] = str(storage_root)
        result = subprocess.run(
            [sys.executable, SCRIPT, "auto", "--since-hours", "0"],
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )

        assert result.returncode == 0
        assert "Auto promotion candidates added: 1" in result.stdout
        queue = json.loads(_queue_path(memory_dir).read_text())
        assert len(queue) == 1
        assert queue[0]["task_id"] == "T-AUTO-STORAGE"
