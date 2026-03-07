#!/usr/bin/env python3
"""Tests for ophtxn_daily_ops no-spend operating brief."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import scripts.ophtxn_daily_ops as mod  # noqa: E402


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")


def test_daily_ops_morning_report_includes_no_spend_and_queue_metrics() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        outputs = root / "outputs"
        tool = root / "tool"
        working = root / "working"
        queue_path = working / "telegram_terminal_tasks.jsonl"
        approvals_path = root / "approvals.json"

        outputs.mkdir(parents=True, exist_ok=True)
        tool.mkdir(parents=True, exist_ok=True)
        working.mkdir(parents=True, exist_ok=True)
        _write_jsonl(
            queue_path,
            [
                {"task_id": "TERM-A", "status": "PENDING", "text": "ship morning plan"},
                {"task_id": "TERM-B", "status": "DONE", "text": "close old task"},
            ],
        )
        approvals_path.write_text(
            json.dumps(
                [
                    {"approval_id": "APR-1", "status": "PENDING_HUMAN_REVIEW", "title": "Review chronicle step"},
                    {"approval_id": "APR-2", "status": "APPROVED", "title": "Done"},
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        (tool / "comms_status_20260305-000000.json").write_text("{}\n", encoding="utf-8")
        (tool / "chronicle_control_20260305-000000.json").write_text("{}\n", encoding="utf-8")
        (tool / "low_cost_mode_20260305-000000.json").write_text("{}\n", encoding="utf-8")
        (tool / "terminal_task_queue_20260305-000000.json").write_text("{}\n", encoding="utf-8")
        (tool / "comms_doctor_20260305-000000.json").write_text("{}\n", encoding="utf-8")

        original = {
            "OUTPUT_DIR": mod.OUTPUT_DIR,
            "TOOL_DIR": mod.TOOL_DIR,
            "WORKING_DIR": mod.WORKING_DIR,
            "QUEUE_PATH": mod.QUEUE_PATH,
            "APPROVALS_PATH": mod.APPROVALS_PATH,
        }
        original_env = {
            "PERMANENCE_NO_SPEND_MODE": os.environ.get("PERMANENCE_NO_SPEND_MODE"),
            "PERMANENCE_LOW_COST_MODE": os.environ.get("PERMANENCE_LOW_COST_MODE"),
            "PERMANENCE_MODEL_PROVIDER": os.environ.get("PERMANENCE_MODEL_PROVIDER"),
            "PERMANENCE_MODEL_PROVIDER_FALLBACKS": os.environ.get("PERMANENCE_MODEL_PROVIDER_FALLBACKS"),
            "PERMANENCE_MODEL_PROVIDER_CAPS_USD": os.environ.get("PERMANENCE_MODEL_PROVIDER_CAPS_USD"),
        }
        try:
            mod.OUTPUT_DIR = outputs
            mod.TOOL_DIR = tool
            mod.WORKING_DIR = working
            mod.QUEUE_PATH = queue_path
            mod.APPROVALS_PATH = approvals_path
            os.environ["PERMANENCE_NO_SPEND_MODE"] = "1"
            os.environ["PERMANENCE_LOW_COST_MODE"] = "1"
            os.environ["PERMANENCE_MODEL_PROVIDER"] = "ollama"
            os.environ["PERMANENCE_MODEL_PROVIDER_FALLBACKS"] = "ollama"
            os.environ["PERMANENCE_MODEL_PROVIDER_CAPS_USD"] = "anthropic=0,openai=0,xai=0,ollama=0"

            rc = mod.main(["--action", "morning", "--freshness-minutes", "100000"])
        finally:
            mod.OUTPUT_DIR = original["OUTPUT_DIR"]
            mod.TOOL_DIR = original["TOOL_DIR"]
            mod.WORKING_DIR = original["WORKING_DIR"]
            mod.QUEUE_PATH = original["QUEUE_PATH"]
            mod.APPROVALS_PATH = original["APPROVALS_PATH"]
            for key, value in original_env.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

        assert rc == 0
        latest = outputs / "ophtxn_daily_ops_latest.md"
        assert latest.exists()
        text = latest.read_text(encoding="utf-8")
        assert "No-spend mode: True" in text
        assert "Terminal queue pending: 1" in text
        assert "Approval queue pending: 1" in text


def test_daily_ops_strict_fails_when_no_spend_disabled() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        outputs = root / "outputs"
        tool = root / "tool"
        working = root / "working"
        queue_path = working / "telegram_terminal_tasks.jsonl"
        approvals_path = root / "approvals.json"
        outputs.mkdir(parents=True, exist_ok=True)
        tool.mkdir(parents=True, exist_ok=True)
        working.mkdir(parents=True, exist_ok=True)
        _write_jsonl(
            queue_path,
            [
                {"task_id": "TERM-A", "status": "PENDING", "text": "task a"},
                {"task_id": "TERM-B", "status": "PENDING", "text": "task b"},
            ],
        )
        approvals_path.write_text("[]\n", encoding="utf-8")

        original = {
            "OUTPUT_DIR": mod.OUTPUT_DIR,
            "TOOL_DIR": mod.TOOL_DIR,
            "WORKING_DIR": mod.WORKING_DIR,
            "QUEUE_PATH": mod.QUEUE_PATH,
            "APPROVALS_PATH": mod.APPROVALS_PATH,
        }
        original_env = {
            "PERMANENCE_NO_SPEND_MODE": os.environ.get("PERMANENCE_NO_SPEND_MODE"),
            "PERMANENCE_MODEL_PROVIDER": os.environ.get("PERMANENCE_MODEL_PROVIDER"),
        }
        try:
            mod.OUTPUT_DIR = outputs
            mod.TOOL_DIR = tool
            mod.WORKING_DIR = working
            mod.QUEUE_PATH = queue_path
            mod.APPROVALS_PATH = approvals_path
            os.environ["PERMANENCE_NO_SPEND_MODE"] = "0"
            os.environ["PERMANENCE_MODEL_PROVIDER"] = "anthropic"
            rc = mod.main(["--action", "hygiene", "--target-pending", "1", "--strict"])
        finally:
            mod.OUTPUT_DIR = original["OUTPUT_DIR"]
            mod.TOOL_DIR = original["TOOL_DIR"]
            mod.WORKING_DIR = original["WORKING_DIR"]
            mod.QUEUE_PATH = original["QUEUE_PATH"]
            mod.APPROVALS_PATH = original["APPROVALS_PATH"]
            for key, value in original_env.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

        assert rc == 2


def test_daily_ops_cycle_action_runs() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        outputs = root / "outputs"
        tool = root / "tool"
        working = root / "working"
        queue_path = working / "telegram_terminal_tasks.jsonl"
        approvals_path = root / "approvals.json"
        outputs.mkdir(parents=True, exist_ok=True)
        tool.mkdir(parents=True, exist_ok=True)
        working.mkdir(parents=True, exist_ok=True)
        _write_jsonl(queue_path, [])
        approvals_path.write_text("[]\n", encoding="utf-8")

        original = {
            "OUTPUT_DIR": mod.OUTPUT_DIR,
            "TOOL_DIR": mod.TOOL_DIR,
            "WORKING_DIR": mod.WORKING_DIR,
            "QUEUE_PATH": mod.QUEUE_PATH,
            "APPROVALS_PATH": mod.APPROVALS_PATH,
        }
        original_env = {
            "PERMANENCE_NO_SPEND_MODE": os.environ.get("PERMANENCE_NO_SPEND_MODE"),
            "PERMANENCE_MODEL_PROVIDER": os.environ.get("PERMANENCE_MODEL_PROVIDER"),
        }
        try:
            mod.OUTPUT_DIR = outputs
            mod.TOOL_DIR = tool
            mod.WORKING_DIR = working
            mod.QUEUE_PATH = queue_path
            mod.APPROVALS_PATH = approvals_path
            os.environ["PERMANENCE_NO_SPEND_MODE"] = "1"
            os.environ["PERMANENCE_MODEL_PROVIDER"] = "ollama"
            rc = mod.main(["--action", "cycle", "--freshness-minutes", "100000"])
        finally:
            mod.OUTPUT_DIR = original["OUTPUT_DIR"]
            mod.TOOL_DIR = original["TOOL_DIR"]
            mod.WORKING_DIR = original["WORKING_DIR"]
            mod.QUEUE_PATH = original["QUEUE_PATH"]
            mod.APPROVALS_PATH = original["APPROVALS_PATH"]
            for key, value in original_env.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

        assert rc == 0
        latest = outputs / "ophtxn_daily_ops_latest.md"
        assert latest.exists()
        text = latest.read_text(encoding="utf-8")
        assert "Action: cycle" in text
        assert "full-day cycle check" in text


if __name__ == "__main__":
    test_daily_ops_morning_report_includes_no_spend_and_queue_metrics()
    test_daily_ops_strict_fails_when_no_spend_disabled()
    test_daily_ops_cycle_action_runs()
    print("✓ Ophtxn daily ops tests passed")
