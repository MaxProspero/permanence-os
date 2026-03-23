#!/usr/bin/env python3
"""
OpenClaw health sync job.
Detects degradation and logs HR notifications.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

import sys

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(BASE_DIR)

from scripts.openclaw_status import capture_openclaw_status  # noqa: E402


logger = logging.getLogger("permanence.openclaw_sync")


class OpenClawHealthSync:
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNREACHABLE = "unreachable"

    DEGRADATION_THRESHOLD = 3
    UNREACHABLE_THRESHOLD = 5

    def __init__(
        self,
        poll_interval: int = 60,
        state_file: Optional[str] = None,
        on_degradation: Optional[Callable[[str, int], None]] = None,
    ):
        self.poll_interval = poll_interval
        state_file = state_file or os.path.join(BASE_DIR, "memory", "tool", "openclaw_health_state.json")
        self.state_file = Path(state_file)
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.on_degradation = on_degradation

        self._consecutive_failures = 0
        self._current_state = self.HEALTHY
        self._last_check = None
        self._load_state()

    def _load_state(self) -> None:
        if not self.state_file.exists():
            return
        try:
            data = json.loads(self.state_file.read_text())
            self._consecutive_failures = data.get("consecutive_failures", 0)
            self._current_state = data.get("current_state", self.HEALTHY)
            self._last_check = data.get("last_check")
        except (json.JSONDecodeError, OSError):
            return

    def _save_state(self) -> None:
        payload = {
            "consecutive_failures": self._consecutive_failures,
            "current_state": self._current_state,
            "last_check": self._last_check,
        }
        self.state_file.write_text(json.dumps(payload, indent=2))

    def check_health(self) -> dict:
        self._last_check = datetime.now(timezone.utc).isoformat()
        openclaw = capture_openclaw_status()
        previous_state = self._current_state

        if openclaw.get("status") == "ok" and openclaw.get("reachable"):
            self._consecutive_failures = 0
            self._current_state = self.HEALTHY
        else:
            self._consecutive_failures += 1
            if self._consecutive_failures >= self.UNREACHABLE_THRESHOLD:
                self._current_state = self.UNREACHABLE
            elif self._consecutive_failures >= self.DEGRADATION_THRESHOLD:
                self._current_state = self.DEGRADED

        state_changed = self._current_state != previous_state
        if state_changed:
            logger.warning(
                "OpenClaw state changed: %s → %s (failures: %s)",
                previous_state,
                self._current_state,
                self._consecutive_failures,
            )
            if self._current_state in {self.DEGRADED, self.UNREACHABLE}:
                self._notify_degradation()

        self._save_state()
        return {
            "status": self._current_state,
            "openclaw": openclaw,
            "consecutive_failures": self._consecutive_failures,
            "state_changed": state_changed,
            "timestamp": self._last_check,
        }

    def _notify_degradation(self) -> None:
        if self.on_degradation:
            self.on_degradation(self._current_state, self._consecutive_failures)

        hr_log = Path(os.path.join(BASE_DIR, "logs", "hr_notifications.jsonl"))
        hr_log.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "type": "tool_degradation",
            "tool": "openclaw",
            "state": self._current_state,
            "consecutive_failures": self._consecutive_failures,
            "timestamp": self._last_check,
            "recommended_action": "Review OpenClaw gateway connectivity",
        }
        with open(hr_log, "a") as f:
            f.write(json.dumps(payload) + "\n")

    def run_sync_loop(self, max_iterations: Optional[int] = None) -> None:
        logger.info("Starting OpenClaw health sync (interval: %ss)", self.poll_interval)
        iterations = 0
        try:
            while max_iterations is None or iterations < max_iterations:
                self.check_health()
                iterations += 1
                time.sleep(self.poll_interval)
        except KeyboardInterrupt:
            logger.info("OpenClaw health sync stopped by user")
        finally:
            self._save_state()


def notify_hr_agent(state: str, failures: int) -> None:
    logger.info("HR Agent notification queued: OpenClaw %s (%s failures)", state, failures)


def main() -> int:
    parser = argparse.ArgumentParser(description="OpenClaw health sync")
    parser.add_argument("--interval", type=int, default=60, help="Poll interval in seconds")
    parser.add_argument("--once", action="store_true", help="Single check then exit")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    sync = OpenClawHealthSync(poll_interval=args.interval, on_degradation=notify_hr_agent)
    if args.once:
        result = sync.check_health()
        print(json.dumps(result, indent=2))
        return 0
    sync.run_sync_loop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
