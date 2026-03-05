#!/usr/bin/env python3
"""Tests for comms_escalation_digest helpers."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import scripts.comms_escalation_digest as mod  # noqa: E402


def test_read_jsonl_and_filter_recent() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "escalations.jsonl"
        rows = [
            {"created_at": "2026-03-03T12:00:00+00:00", "priority": "urgent"},
            {"created_at": "2020-01-01T00:00:00+00:00", "priority": "low"},
        ]
        with path.open("w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row) + "\n")
        loaded = mod._read_jsonl(path)
        assert len(loaded) == 2
        recent = mod._filter_recent(loaded, hours=48)
        assert isinstance(recent, list)


def test_summary_and_build_message() -> None:
    rows = [
        {"priority": "urgent", "source": "Permanence", "channel": "discord", "sender": "ops", "message": "critical"},
        {"priority": "high", "source": "Permanence", "channel": "discord", "sender": "ops", "message": "warning"},
    ]
    summary = mod._summary(rows)
    assert int(summary.get("count", 0)) == 2
    by_priority = summary.get("by_priority") if isinstance(summary.get("by_priority"), dict) else {}
    assert int(by_priority.get("urgent", 0)) == 1
    text = mod._build_message(rows, hours=24, max_items=5)
    assert "Comms Escalation Digest" in text
    assert "[urgent]" in text


if __name__ == "__main__":
    test_read_jsonl_and_filter_recent()
    test_summary_and_build_message()
    print("✓ Comms escalation digest tests passed")
