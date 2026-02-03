#!/usr/bin/env python3
"""Tests for OpenClaw health sync job."""

import os
import sys
import tempfile
from unittest.mock import patch

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from scripts.openclaw_health_sync import OpenClawHealthSync  # noqa: E402


def _make_sync(tmpdir: str) -> OpenClawHealthSync:
    return OpenClawHealthSync(poll_interval=1, state_file=f"{tmpdir}/state.json")


def test_healthy_on_success():
    with tempfile.TemporaryDirectory() as tmp:
        sync = _make_sync(tmp)
        with patch("scripts.openclaw_health_sync.capture_openclaw_status") as mock:
            mock.return_value = {"status": "ok", "reachable": True}
            result = sync.check_health()
            assert result["status"] == "healthy"
            assert result["consecutive_failures"] == 0


def test_degraded_after_threshold():
    with tempfile.TemporaryDirectory() as tmp:
        sync = _make_sync(tmp)
        with patch("scripts.openclaw_health_sync.capture_openclaw_status") as mock:
            mock.return_value = {"status": "error", "reachable": False}
            for _ in range(sync.DEGRADATION_THRESHOLD):
                result = sync.check_health()
            assert result["status"] == "degraded"


def test_unreachable_after_threshold():
    with tempfile.TemporaryDirectory() as tmp:
        sync = _make_sync(tmp)
        with patch("scripts.openclaw_health_sync.capture_openclaw_status") as mock:
            mock.return_value = {"status": "error", "reachable": False}
            for _ in range(sync.UNREACHABLE_THRESHOLD):
                result = sync.check_health()
            assert result["status"] == "unreachable"


def test_recovery_resets_failures():
    with tempfile.TemporaryDirectory() as tmp:
        sync = _make_sync(tmp)
        with patch("scripts.openclaw_health_sync.capture_openclaw_status") as mock:
            mock.return_value = {"status": "error", "reachable": False}
            for _ in range(3):
                sync.check_health()
            mock.return_value = {"status": "ok", "reachable": True}
            result = sync.check_health()
            assert result["status"] == "healthy"
            assert result["consecutive_failures"] == 0


if __name__ == "__main__":
    test_healthy_on_success()
    test_degraded_after_threshold()
    test_unreachable_after_threshold()
    test_recovery_resets_failures()
    print("✓ OpenClaw health sync tests passed")
