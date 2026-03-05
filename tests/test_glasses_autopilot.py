#!/usr/bin/env python3
"""Tests for glasses_autopilot importer."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import scripts.glasses_autopilot as autopilot_mod  # noqa: E402


def _set_env(root: Path) -> dict[str, str]:
    env = {
        "PERMANENCE_WORKING_DIR": str(root / "working"),
        "PERMANENCE_OUTPUT_DIR": str(root / "outputs"),
        "PERMANENCE_TOOL_DIR": str(root / "tool"),
        "PERMANENCE_ATTACHMENT_INBOX_DIR": str(root / "attachments"),
        "PERMANENCE_RECEPTION_QUEUE_DIR": str(root / "reception"),
        "PERMANENCE_RESEARCH_INBOX_PATH": str(root / "working" / "research" / "inbox.jsonl"),
    }
    previous: dict[str, str] = {}
    for key, value in env.items():
        previous[key] = os.environ.get(key, "")
        os.environ[key] = value
    return previous


def _restore_env(previous: dict[str, str]) -> None:
    for key, value in previous.items():
        if value:
            os.environ[key] = value
        elif key in os.environ:
            del os.environ[key]


def test_glasses_autopilot_imports_new_export_once() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        downloads = root / "Downloads"
        downloads.mkdir(parents=True, exist_ok=True)
        previous = _set_env(root)
        try:
            export = downloads / "nearby_glasses_detected_001.json"
            payload = {
                "export_timestamp": 1760000000000,
                "detections": [
                    {
                        "timestamp": 1760000000000,
                        "deviceAddress": "AA:BB:CC:DD:EE:FF",
                        "deviceName": "Ray-Ban Meta",
                        "rssi": -71,
                        "companyId": "0x058E",
                        "companyName": "Meta Platforms",
                        "detectionReason": "Meta company ID (0x058E)",
                    }
                ],
            }
            export.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

            state_path = root / "working" / "glasses" / "autopilot_state.json"
            rc = autopilot_mod.main(
                [
                    "--action",
                    "run",
                    "--downloads-dir",
                    str(downloads),
                    "--state-path",
                    str(state_path),
                    "--no-attachment-pipeline",
                    "--no-research-process",
                ]
            )
            assert rc == 0
            assert state_path.exists()
            state = json.loads(state_path.read_text(encoding="utf-8"))
            assert isinstance(state.get("processed"), dict)
            assert len(state["processed"]) == 1

            events_path = root / "working" / "glasses" / "events.jsonl"
            rows = [json.loads(line) for line in events_path.read_text(encoding="utf-8").splitlines() if line.strip()]
            assert len(rows) == 1
            assert rows[0].get("source") == "yj_nearbyglasses"

            rc2 = autopilot_mod.main(
                [
                    "--action",
                    "run",
                    "--downloads-dir",
                    str(downloads),
                    "--state-path",
                    str(state_path),
                    "--no-attachment-pipeline",
                    "--no-research-process",
                ]
            )
            assert rc2 == 0
            rows2 = [json.loads(line) for line in events_path.read_text(encoding="utf-8").splitlines() if line.strip()]
            assert len(rows2) == 1
        finally:
            _restore_env(previous)


if __name__ == "__main__":
    test_glasses_autopilot_imports_new_export_once()
    print("✓ Glasses autopilot tests passed")
