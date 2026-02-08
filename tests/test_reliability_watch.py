#!/usr/bin/env python3
"""Tests for reliability watch controller."""

import argparse
import json
import os
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import scripts.reliability_watch as watch_mod  # noqa: E402


def _write_run(log_dir: Path, stamp: str, b: int, d: int, n: int) -> None:
    (log_dir / f"run_{stamp}.log").write_text(
        "=== Briefing Run Started: test ===\n"
        f"Briefing Status: {b} | Digest Status: {d} | NotebookLM Status: {n}\n"
    )


def _args(state_file: Path, log_dir: Path, alert_log: Path) -> argparse.Namespace:
    return argparse.Namespace(
        start=False,
        check=False,
        status=False,
        stop=False,
        arm=False,
        disarm=False,
        install_agent=False,
        uninstall_agent=False,
        force=False,
        days=7,
        slots=[7],
        tolerance_minutes=90,
        check_interval_minutes=30,
        state_file=str(state_file),
        log_dir=str(log_dir),
        alert_log=str(alert_log),
        plist_path=str(Path.home() / "Library" / "LaunchAgents" / "com.permanence.reliability-watch.plist"),
        immediate_check=True,
    )


def test_parse_slots():
    assert watch_mod.parse_slots("7,12,19") == [7, 12, 19]


def test_cmd_start_writes_state():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        state_file = root / "state.json"
        args = _args(state_file=state_file, log_dir=root / "logs", alert_log=root / "alerts.log")
        args.start = True
        rc = watch_mod.cmd_start(args)
        assert rc == 0
        data = json.loads(state_file.read_text())
        assert data["completed"] is False
        assert data["slots"] == [7]


def test_cmd_check_dedupes_failures_and_completes():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        log_dir = root / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        state_file = root / "state.json"
        alert_log = root / "alerts.log"
        args = _args(state_file=state_file, log_dir=log_dir, alert_log=alert_log)

        # Build a 1-day window that has one successful run and is already complete.
        now = datetime.now()
        day = (now - timedelta(days=1)).date()
        stamp = f"{day.strftime('%Y%m%d')}-070000"
        _write_run(log_dir, stamp, 0, 0, 0)

        state = {
            "started_at_local": datetime(day.year, day.month, day.day, 0, 0, 0).isoformat(),
            "ends_at_local": (now - timedelta(minutes=1)).isoformat(),
            "days": 1,
            "slots": [7],
            "tolerance_minutes": 90,
            "completed": False,
            "stopped": False,
            "notified_keys": [],
            "failures": [],
            "last_summary": {},
            "last_check_local": None,
        }
        state_file.write_text(json.dumps(state))

        with patch.object(watch_mod, "_notify") as mock_notify, patch.object(
            watch_mod, "_stop_launch_agent"
        ) as mock_stop:
            rc = watch_mod.cmd_check(args)
            assert rc == 0
            new_state = json.loads(state_file.read_text())
            assert new_state["completed"] is True
            assert new_state["result"] == "PASS"
            assert mock_notify.call_count >= 1
            assert mock_stop.call_count == 1
