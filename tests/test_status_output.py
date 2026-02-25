#!/usr/bin/env python3
"""Tests for scripts/status.py output."""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


def test_status_displays_model_routes_and_assist_flag():
    repo_root = Path(__file__).resolve().parents[1]
    script_path = repo_root / "scripts" / "status.py"

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        memory_dir = tmp_path / "memory"
        episodic_dir = memory_dir / "episodic"
        logs_dir = tmp_path / "logs"
        outputs_dir = tmp_path / "outputs"
        queue_path = memory_dir / "working" / "promotion_queue.json"

        episodic_dir.mkdir(parents=True, exist_ok=True)
        logs_dir.mkdir(parents=True, exist_ok=True)
        outputs_dir.mkdir(parents=True, exist_ok=True)
        queue_path.parent.mkdir(parents=True, exist_ok=True)

        state = {
            "task_id": "T-TEST-123",
            "stage": "DONE",
            "status": "DONE",
            "risk_tier": "LOW",
            "task_goal": "Verify status output",
            "artifacts": {
                "model_routes": {
                    "planning": "claude-sonnet-4-6",
                    "research": "claude-sonnet-4-6",
                    "execution": "claude-sonnet-4-6",
                    "review": "claude-sonnet-4-6",
                    "conciliation": "claude-sonnet-4-6",
                }
            },
        }
        (episodic_dir / "T-TEST-123.json").write_text(json.dumps(state), encoding="utf-8")
        (logs_dir / "2026-02-25.log").write_text("log line\n", encoding="utf-8")
        queue_path.write_text("[]\n", encoding="utf-8")

        env = os.environ.copy()
        env["PERMANENCE_MEMORY_DIR"] = str(memory_dir)
        env["PERMANENCE_LOG_DIR"] = str(logs_dir)
        env["PERMANENCE_OUTPUT_DIR"] = str(outputs_dir)
        env["PERMANENCE_PROMOTION_QUEUE"] = str(queue_path)
        env["PERMANENCE_ENABLE_MODEL_ASSIST"] = "true"

        output = subprocess.check_output([sys.executable, str(script_path)], env=env, text=True)

        assert "Latest Task: T-TEST-123" in output
        assert "Model Routes: planning=claude-sonnet-4-6" in output
        assert "conciliation=claude-sonnet-4-6" in output
        assert "Promotion Gates:" in output
        assert "Model Assist: enabled" in output


def test_status_reads_promotion_gates_from_storage_logs():
    repo_root = Path(__file__).resolve().parents[1]
    script_path = repo_root / "scripts" / "status.py"

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        memory_dir = tmp_path / "memory"
        episodic_dir = memory_dir / "episodic"
        logs_dir = tmp_path / "logs"
        outputs_dir = tmp_path / "outputs"
        storage_root = tmp_path / "permanence_storage"
        storage_logs = storage_root / "logs"
        queue_path = memory_dir / "working" / "promotion_queue.json"

        episodic_dir.mkdir(parents=True, exist_ok=True)
        logs_dir.mkdir(parents=True, exist_ok=True)
        outputs_dir.mkdir(parents=True, exist_ok=True)
        storage_logs.mkdir(parents=True, exist_ok=True)
        queue_path.parent.mkdir(parents=True, exist_ok=True)
        queue_path.write_text("[]\n", encoding="utf-8")
        (storage_logs / "status_today.json").write_text('{"today_state":"PASS"}\n', encoding="utf-8")
        (storage_logs / "phase_gate_2026-02-25.md").write_text(
            "# Phase Gate\n\n- Phase gate: PASS\n",
            encoding="utf-8",
        )

        env = os.environ.copy()
        env["PERMANENCE_MEMORY_DIR"] = str(memory_dir)
        env["PERMANENCE_LOG_DIR"] = str(logs_dir)
        env["PERMANENCE_OUTPUT_DIR"] = str(outputs_dir)
        env["PERMANENCE_PROMOTION_QUEUE"] = str(queue_path)
        env["PERMANENCE_STORAGE_ROOT"] = str(storage_root)

        output = subprocess.check_output([sys.executable, str(script_path)], env=env, text=True)
        assert "Promotion Gates: glance=PASS | phase=PASS" in output


if __name__ == "__main__":
    test_status_displays_model_routes_and_assist_flag()
    test_status_reads_promotion_gates_from_storage_logs()
    print("✓ Status output tests passed")
