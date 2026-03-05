#!/usr/bin/env python3
"""Tests for comms_digest helpers."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import scripts.comms_digest as mod  # noqa: E402


def test_split_chunks_splits_on_max_chars() -> None:
    text = "line1\nline2\nline3\nline4\n"
    chunks = mod._split_chunks(text, max_chars=12)
    assert len(chunks) >= 2


def test_build_digest_text_contains_metrics() -> None:
    payload = {
        "generated_at": "2026-03-03T00:00:00+00:00",
        "relay": {"new_messages": 2, "telegram_messages_sent": 1, "warnings": []},
        "telegram": {"updates_count": 4, "ingested_count": 3},
        "glasses": {"imported_count": 1, "candidate_count": 5},
        "comms": {"launchd": {"state": "not running", "runs": 9, "last_exit_code": 0}, "warnings": []},
        "readiness": {"blocked": False},
    }
    text = mod._build_digest_text(payload, max_warnings=5, include_paths=False)
    assert "discord -> telegram: new=2, sent=1" in text
    assert "telegram control: updates=4, ingested=3" in text
    assert "glasses autopilot: imported=1, scanned=5" in text


def test_latest_json_uses_newest_file() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        old = root / "discord_telegram_relay_1.json"
        new = root / "discord_telegram_relay_2.json"
        old.write_text(json.dumps({"x": 1}), encoding="utf-8")
        new.write_text(json.dumps({"x": 2}), encoding="utf-8")
        latest = mod._latest_json("discord_telegram_relay", root=root)
        assert latest == new


if __name__ == "__main__":
    test_split_chunks_splits_on_max_chars()
    test_build_digest_text_contains_metrics()
    test_latest_json_uses_newest_file()
    print("✓ Comms digest tests passed")
