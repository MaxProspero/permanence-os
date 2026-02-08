#!/usr/bin/env python3
"""Tests for reliability streak tracking."""

import os
import sys
import tempfile
from pathlib import Path

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import scripts.reliability_streak as streak_mod  # noqa: E402


class _DummyPaths:
    def __init__(self, root: Path):
        self.logs = root / "logs"
        self.logs.mkdir(parents=True, exist_ok=True)


class _DummyStorage:
    def __init__(self, root: Path):
        self.paths = _DummyPaths(root)


def test_streak_increments_and_resets():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        original_storage = streak_mod.storage
        try:
            streak_mod.storage = _DummyStorage(tmp_path)
            s1 = streak_mod.update_streak(0, "2026-02-05")
            assert s1["current_streak"] == 1
            s2 = streak_mod.update_streak(0, "2026-02-06")
            assert s2["current_streak"] == 2
            s3 = streak_mod.update_streak(1, "2026-02-07")
            assert s3["current_streak"] == 0
        finally:
            streak_mod.storage = original_storage

