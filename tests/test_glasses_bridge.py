#!/usr/bin/env python3
"""Tests for smart-glasses bridge intake/ingest flows."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import scripts.glasses_bridge as bridge_mod  # noqa: E402


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


def test_glasses_bridge_intake_writes_events_and_queues() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        previous = _set_env(root)
        try:
            media_file = root / "camera.jpg"
            media_file.write_bytes(b"\xff\xd8\xff\xe0fake-jpeg")

            rc = bridge_mod.main(
                [
                    "--action",
                    "intake",
                    "--source",
                    "visionclaw",
                    "--channel",
                    "telegram",
                    "--sender",
                    "rayban-agent",
                    "--text",
                    "What am I looking at? https://example.com/context",
                    "--media",
                    str(media_file),
                ]
            )
            assert rc == 0

            events_path = root / "working" / "glasses" / "events.jsonl"
            assert events_path.exists()
            rows = [json.loads(line) for line in events_path.read_text(encoding="utf-8").splitlines() if line.strip()]
            assert len(rows) == 1
            row = rows[0]
            assert row.get("source") == "visionclaw"
            assert row.get("channel") == "telegram"
            assert "example.com/context" in " ".join(row.get("urls") or [])
            assert len(row.get("media_files") or []) == 1

            copied_media = root / "attachments"
            assert any(item.name.startswith("glasses_") for item in copied_media.iterdir())

            ari_inbox = root / "reception" / "ari_inbox.jsonl"
            assert ari_inbox.exists()
            ari_rows = [json.loads(line) for line in ari_inbox.read_text(encoding="utf-8").splitlines() if line.strip()]
            assert len(ari_rows) == 1
            assert ari_rows[0].get("channel") == "telegram"

            research_inbox = root / "working" / "research" / "inbox.jsonl"
            assert research_inbox.exists()
            research_rows = [
                json.loads(line) for line in research_inbox.read_text(encoding="utf-8").splitlines() if line.strip()
            ]
            assert len(research_rows) == 1
            assert "https://example.com/context" in " ".join(research_rows[0].get("urls") or [])
        finally:
            _restore_env(previous)


def test_glasses_bridge_ingests_nearby_glasses_export() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        previous = _set_env(root)
        try:
            export_path = root / "nearby_glasses_export.json"
            payload = {
                "export_timestamp": 1760000000000,
                "detections": [
                    {
                        "timestamp": 1760000000000,
                        "deviceAddress": "AA:BB:CC:DD:EE:FF",
                        "deviceName": "Ray-Ban Meta",
                        "rssi": -64,
                        "companyId": "0x058E",
                        "companyName": "Meta Platforms",
                        "manufacturerData": "abcdef",
                        "detectionReason": "Meta company ID (0x058E)",
                    }
                ],
            }
            export_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

            rc = bridge_mod.main(
                [
                    "--action",
                    "ingest",
                    "--from-json",
                    str(export_path),
                    "--no-research",
                    "--no-reception",
                ]
            )
            assert rc == 0

            events_path = root / "working" / "glasses" / "events.jsonl"
            rows = [json.loads(line) for line in events_path.read_text(encoding="utf-8").splitlines() if line.strip()]
            assert len(rows) == 1
            row = rows[0]
            assert row.get("source") == "yj_nearbyglasses"
            assert "Nearby-glasses detection" in str(row.get("message") or "")

            status_rc = bridge_mod.main(["--action", "status"])
            assert status_rc == 0
        finally:
            _restore_env(previous)


if __name__ == "__main__":
    test_glasses_bridge_intake_writes_events_and_queues()
    test_glasses_bridge_ingests_nearby_glasses_export()
    print("✓ Glasses bridge tests passed")
