#!/usr/bin/env python3
"""Tests for comms_status helpers."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import scripts.comms_status as mod  # noqa: E402


def test_latest_json_and_component_status() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        old = root / "telegram_control_20260101-000000.json"
        new = root / "telegram_control_20260101-000001.json"
        old.write_text(json.dumps({"generated_at": "old", "updates_count": 1}), encoding="utf-8")
        new.write_text(json.dumps({"generated_at": "new", "updates_count": 2}), encoding="utf-8")

        latest = mod._latest_json("telegram_control", root=root)
        assert latest == new

        row = mod._component_status("telegram_control", ["updates_count"], root=root)
        assert row["present"] is True
        assert row["generated_at"] == "new"
        assert row["updates_count"] == 2


def test_staleness_minutes_for_missing_file() -> None:
    missing = Path("/tmp/does_not_exist_12345.log")
    assert mod._staleness_minutes(missing) is None


def test_escalation_and_transcription_queue_stats_shape() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        escalations_path = root / "escalations.jsonl"
        transcription_path = root / "transcription_queue.json"
        escalations_path.write_text(
            "\n".join(
                [
                    json.dumps({"created_at": "2026-03-03T12:00:00+00:00", "priority": "high"}),
                    json.dumps({"created_at": "2020-01-01T00:00:00+00:00", "priority": "low"}),
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        transcription_path.write_text(
            json.dumps(
                [
                    {"status": "queued"},
                    {"status": "done"},
                    {"status": "processing"},
                ]
            ),
            encoding="utf-8",
        )

        esc_stats = mod._escalation_stats(escalations_path, lookback_hours=48)
        queue_stats = mod._transcription_queue_stats(transcription_path)

        assert esc_stats["exists"] is True
        assert esc_stats["total"] == 2
        assert queue_stats["exists"] is True
        assert queue_stats["pending"] == 2
        assert queue_stats["done"] == 1


def test_build_payload_shape() -> None:
    payload = mod._build_payload(
        comms_log_stale_minutes=20,
        component_stale_minutes=120,
        escalation_digest_stale_minutes=1500,
        escalation_hours=24,
        escalation_warn_count=8,
        voice_queue_warn_count=15,
        require_escalation_digest=False,
    )
    assert isinstance(payload, dict)
    assert "launchd" in payload
    assert "components" in payload
    assert "escalations" in payload
    assert "transcription_queue" in payload
    assert "warnings" in payload


if __name__ == "__main__":
    test_latest_json_and_component_status()
    test_staleness_minutes_for_missing_file()
    test_escalation_and_transcription_queue_stats_shape()
    test_build_payload_shape()
    print("✓ Comms status tests passed")
