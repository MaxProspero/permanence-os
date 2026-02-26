#!/usr/bin/env python3
"""Tests for revenue targets management script."""

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import scripts.revenue_targets as targets_mod  # noqa: E402


def test_revenue_targets_init_set_show():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        working_dir = root / "working"
        working_dir.mkdir(parents=True, exist_ok=True)
        path = working_dir / "revenue_targets.json"

        original = {
            "WORKING_DIR": targets_mod.WORKING_DIR,
            "TARGETS_PATH": targets_mod.TARGETS_PATH,
        }
        try:
            targets_mod.WORKING_DIR = working_dir
            targets_mod.TARGETS_PATH = path

            assert targets_mod.cmd_init(type("Args", (), {"force": False})()) == 0
            assert path.exists()

            set_args = type(
                "Args",
                (),
                {
                    "week_of": "2026-02-23",
                    "weekly_revenue_target": 5000,
                    "monthly_revenue_target": 20000,
                    "weekly_leads_target": 15,
                    "weekly_calls_target": 8,
                    "weekly_closes_target": 3,
                    "daily_outreach_target": 12,
                },
            )()
            assert targets_mod.cmd_set(set_args) == 0

            payload = json.loads(path.read_text(encoding="utf-8"))
            assert payload["weekly_revenue_target"] == 5000
            assert payload["monthly_revenue_target"] == 20000
            assert payload["daily_outreach_target"] == 12

            loaded = targets_mod.load_targets()
            assert loaded["weekly_leads_target"] == 15
            assert loaded["weekly_calls_target"] == 8
            assert loaded["weekly_closes_target"] == 3
        finally:
            targets_mod.WORKING_DIR = original["WORKING_DIR"]
            targets_mod.TARGETS_PATH = original["TARGETS_PATH"]


if __name__ == "__main__":
    test_revenue_targets_init_set_show()
    print("✓ Revenue targets tests passed")
