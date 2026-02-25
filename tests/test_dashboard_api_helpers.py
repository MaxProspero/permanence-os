#!/usr/bin/env python3
"""Focused tests for dashboard_api helper behavior."""

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import dashboard_api


def test_load_latest_task_summary_includes_model_routes():
    with tempfile.TemporaryDirectory() as tmp:
        episodic_dir = Path(tmp) / "memory" / "episodic"
        episodic_dir.mkdir(parents=True, exist_ok=True)
        state = {
            "task_id": "T-TEST-001",
            "stage": "DONE",
            "status": "DONE",
            "risk_tier": "LOW",
            "task_goal": "Test latest task summary",
            "artifacts": {"model_routes": {"planning": "claude-sonnet-4-6"}},
        }
        (episodic_dir / "T-TEST-001.json").write_text(json.dumps(state), encoding="utf-8")

        original = dict(dashboard_api.PATHS)
        try:
            dashboard_api.PATHS["episodic"] = str(episodic_dir)
            summary = dashboard_api._load_latest_task_summary()
            assert summary is not None
            assert summary["task_id"] == "T-TEST-001"
            assert summary["model_routes"]["planning"] == "claude-sonnet-4-6"
        finally:
            dashboard_api.PATHS.update(original)


def test_load_latest_briefing_supports_markdown():
    with tempfile.TemporaryDirectory() as tmp:
        briefings_dir = Path(tmp) / "outputs" / "briefings"
        briefings_dir.mkdir(parents=True, exist_ok=True)
        md_path = briefings_dir / "briefing_20260225-000000.md"
        md_path.write_text("# Briefing\n\n- Item A\n", encoding="utf-8")

        original = dict(dashboard_api.PATHS)
        try:
            dashboard_api.PATHS["briefings"] = str(briefings_dir)
            payload = dashboard_api._load_latest_briefing()
            assert payload is not None
            assert payload.get("format") == "markdown"
            assert "# Briefing" in payload.get("content_markdown", "")
        finally:
            dashboard_api.PATHS.update(original)


def test_load_promotion_status_reads_storage_log_fallback():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        logs_dir = root / "logs"
        storage_root = root / "permanence_storage"
        storage_logs = storage_root / "logs"
        memory_working = root / "memory" / "working"
        outputs_dir = root / "outputs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        storage_logs.mkdir(parents=True, exist_ok=True)
        memory_working.mkdir(parents=True, exist_ok=True)
        outputs_dir.mkdir(parents=True, exist_ok=True)

        (storage_logs / "status_today.json").write_text('{"today_state":"PASS"}\n', encoding="utf-8")
        (storage_logs / "phase_gate_2026-02-25.md").write_text(
            "# Phase Gate\n\n- Phase gate: PASS\n",
            encoding="utf-8",
        )
        (memory_working / "promotion_queue.json").write_text(
            '[{"task_id":"T-1"},{"task_id":"T-2"}]\n',
            encoding="utf-8",
        )
        (outputs_dir / "promotion_review.md").write_text("# Promotion Review\n", encoding="utf-8")

        original_paths = dict(dashboard_api.PATHS)
        original_storage_root = os.environ.get("PERMANENCE_STORAGE_ROOT")
        original_memory_dir = os.environ.get("PERMANENCE_MEMORY_DIR")
        original_queue_path = os.environ.get("PERMANENCE_PROMOTION_QUEUE")
        try:
            dashboard_api.PATHS["logs"] = str(logs_dir)
            dashboard_api.PATHS["outputs"] = str(outputs_dir)
            os.environ["PERMANENCE_STORAGE_ROOT"] = str(storage_root)
            os.environ["PERMANENCE_MEMORY_DIR"] = str(root / "memory")
            os.environ["PERMANENCE_PROMOTION_QUEUE"] = str(memory_working / "promotion_queue.json")

            status = dashboard_api._load_promotion_status()
            assert status["queue_items"] == 2
            assert status["glance_gate"] == "PASS"
            assert status["phase_gate"] == "PASS"
            assert status["review_last_generated"] is not None
        finally:
            dashboard_api.PATHS.update(original_paths)
            if original_storage_root is None:
                os.environ.pop("PERMANENCE_STORAGE_ROOT", None)
            else:
                os.environ["PERMANENCE_STORAGE_ROOT"] = original_storage_root
            if original_memory_dir is None:
                os.environ.pop("PERMANENCE_MEMORY_DIR", None)
            else:
                os.environ["PERMANENCE_MEMORY_DIR"] = original_memory_dir
            if original_queue_path is None:
                os.environ.pop("PERMANENCE_PROMOTION_QUEUE", None)
            else:
                os.environ["PERMANENCE_PROMOTION_QUEUE"] = original_queue_path


if __name__ == "__main__":
    test_load_latest_task_summary_includes_model_routes()
    test_load_latest_briefing_supports_markdown()
    test_load_promotion_status_reads_storage_log_fallback()
    print("✓ Dashboard API helper tests passed")
