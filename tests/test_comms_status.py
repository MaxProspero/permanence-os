#!/usr/bin/env python3
"""Tests for comms_status helpers."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

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
        check_openclaw_channels=False,
    )
    assert isinstance(payload, dict)
    assert "launchd" in payload
    assert "components" in payload
    assert "escalations" in payload
    assert "transcription_queue" in payload
    assert "openclaw_channels" in payload["components"]
    assert "warnings" in payload


def test_openclaw_probe_parses_healthy_channels(monkeypatch) -> None:
    stdout = "\n".join(
        [
            "Checking channel status (probe)…",
            "Gateway reachable.",
            "- Telegram default (ophtxn-telegram): enabled, configured, running, mode:polling, works",
            "- Discord default (ophtxn-discord): enabled, configured, running, connected, works",
            "- iMessage default (ophtxn-imessage): enabled, configured, running, works",
        ]
    )

    def fake_run(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        return SimpleNamespace(returncode=0, stdout=stdout, stderr="")

    monkeypatch.setattr(mod.subprocess, "run", fake_run)
    probe = mod._openclaw_channels_probe()
    assert probe["invoked"] is True
    assert probe["gateway_reachable"] is True
    assert probe["telegram"]["found"] is True
    assert probe["telegram"]["works"] is True
    assert probe["discord"]["found"] is True
    assert probe["discord"]["works"] is True
    assert probe["imessage"]["found"] is True
    assert probe["imessage"]["works"] is True


def test_openclaw_probe_parses_imessage_probe_failed(monkeypatch) -> None:
    stdout = "\n".join(
        [
            "Checking channel status (probe)…",
            "Gateway reachable.",
            "- Telegram default (ophtxn-telegram): enabled, configured, running, works",
            "- Discord default (ophtxn-discord): enabled, configured, running, works",
            "- iMessage default (ophtxn-imessage): enabled, configured, running, probe failed",
        ]
    )

    def fake_run(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        return SimpleNamespace(returncode=0, stdout=stdout, stderr="")

    monkeypatch.setattr(mod.subprocess, "run", fake_run)
    probe = mod._openclaw_channels_probe()
    assert probe["imessage"]["found"] is True
    assert probe["imessage"]["works"] is False
    assert "probe failed" in str(probe["imessage"]["detail"]).lower()


def test_openclaw_probe_handles_missing_cli(monkeypatch) -> None:
    def fake_run(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        raise OSError("openclaw not found")

    monkeypatch.setattr(mod.subprocess, "run", fake_run)
    probe = mod._openclaw_channels_probe()
    assert probe["invoked"] is False
    assert probe["error"]


def _patch_payload_dependencies(monkeypatch) -> None:
    monkeypatch.setattr(
        mod,
        "_component_status",
        lambda *_args, **_kwargs: {"present": False, "stale_minutes": None, "warnings": []},
    )
    monkeypatch.setattr(
        mod,
        "_launchd_state",
        lambda: {"installed": True, "state": "running", "runs": 1, "last_exit_code": 0, "run_interval_seconds": 300},
    )
    monkeypatch.setattr(mod, "_latest_log", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        mod,
        "_escalation_stats",
        lambda _path, lookback_hours: {
            "path": str(_path),
            "exists": False,
            "total": 0,
            "recent": 0,
            "lookback_hours": lookback_hours,
            "recent_by_priority": {},
        },
    )
    monkeypatch.setattr(
        mod,
        "_transcription_queue_stats",
        lambda _path: {"path": str(_path), "exists": False, "total": 0, "pending": 0, "done": 0},
    )


def test_build_payload_does_not_require_imessage_by_default(monkeypatch) -> None:
    _patch_payload_dependencies(monkeypatch)
    monkeypatch.setattr(
        mod,
        "_openclaw_channels_probe",
        lambda **_kwargs: {
            "invoked": True,
            "error": "",
            "gateway_reachable": True,
            "telegram": {"found": True, "enabled": True, "configured": True, "running": True, "works": True, "detail": ""},
            "discord": {"found": True, "enabled": True, "configured": True, "running": True, "works": True, "detail": ""},
            "imessage": {"found": False, "enabled": False, "configured": False, "running": False, "works": False, "detail": ""},
        },
    )
    payload = mod._build_payload(
        comms_log_stale_minutes=20,
        component_stale_minutes=120,
        escalation_digest_stale_minutes=1500,
        escalation_hours=24,
        escalation_warn_count=8,
        voice_queue_warn_count=15,
        require_escalation_digest=False,
        check_openclaw_channels=True,
        require_openclaw_imessage=False,
    )
    warnings = payload.get("warnings") if isinstance(payload.get("warnings"), list) else []
    assert not any("imessage" in str(item).lower() for item in warnings)


def test_build_payload_can_require_imessage(monkeypatch) -> None:
    _patch_payload_dependencies(monkeypatch)
    monkeypatch.setattr(
        mod,
        "_openclaw_channels_probe",
        lambda **_kwargs: {
            "invoked": True,
            "error": "",
            "gateway_reachable": True,
            "telegram": {"found": True, "enabled": True, "configured": True, "running": True, "works": True, "detail": ""},
            "discord": {"found": True, "enabled": True, "configured": True, "running": True, "works": True, "detail": ""},
            "imessage": {"found": False, "enabled": False, "configured": False, "running": False, "works": False, "detail": ""},
        },
    )
    payload = mod._build_payload(
        comms_log_stale_minutes=20,
        component_stale_minutes=120,
        escalation_digest_stale_minutes=1500,
        escalation_hours=24,
        escalation_warn_count=8,
        voice_queue_warn_count=15,
        require_escalation_digest=False,
        check_openclaw_channels=True,
        require_openclaw_imessage=True,
    )
    warnings = payload.get("warnings") if isinstance(payload.get("warnings"), list) else []
    assert any("imessage" in str(item).lower() for item in warnings)


if __name__ == "__main__":
    test_latest_json_and_component_status()
    test_staleness_minutes_for_missing_file()
    test_escalation_and_transcription_queue_stats_shape()
    test_build_payload_shape()
    print("✓ Comms status tests passed")
