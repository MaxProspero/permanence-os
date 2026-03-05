#!/usr/bin/env python3
"""Tests for FOUNDATION API scaffold."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.foundation.server import create_app  # noqa: E402


def test_foundation_health_endpoint() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        app = create_app(storage_root=Path(tmp))
        client = app.test_client()
        resp = client.get("/health")
        assert resp.status_code == 200
        payload = resp.get_json() or {}
        assert payload.get("ok") is True
        assert payload.get("service") == "foundation-api"


def test_foundation_auth_onboarding_and_memory_flow() -> None:
    snapshot_passcode = os.environ.get("PERMANENCE_FOUNDATION_PASSCODE")
    try:
        os.environ["PERMANENCE_FOUNDATION_PASSCODE"] = "1234"
        with tempfile.TemporaryDirectory() as tmp:
            app = create_app(storage_root=Path(tmp))
            client = app.test_client()

            bad = client.post("/auth/session", json={"user_id": "u-1", "passcode": "nope"})
            assert bad.status_code == 403

            auth = client.post(
                "/auth/session",
                json={"user_id": "u-1", "name": "Payton", "passcode": "1234"},
            )
            assert auth.status_code == 200
            token = str((auth.get_json() or {}).get("token") or "")
            assert token
            headers = {"X-Session-Token": token}

            onboarding = client.post(
                "/onboarding/start",
                headers=headers,
                json={
                    "mission": "Build Ophtxn",
                    "goals": ["ship", "learn", "earn"],
                    "strengths": "builder,operator",
                    "growth_edges": "focus,delegation",
                    "personality_mode": "operator",
                },
            )
            assert onboarding.status_code == 200
            profile = (onboarding.get_json() or {}).get("profile") or {}
            assert profile.get("mission") == "Build Ophtxn"

            add = client.post(
                "/memory/entry",
                headers=headers,
                json={"text": "Founder directive committed", "tags": ["founder", "roadmap"]},
            )
            assert add.status_code == 200
            entry = (add.get_json() or {}).get("entry") or {}
            assert entry.get("user_id") == "u-1"

            rows = client.get("/memory/entry", headers=headers)
            assert rows.status_code == 200
            payload = rows.get_json() or {}
            assert int(payload.get("count") or 0) >= 1
            entries = payload.get("entries") or []
            assert isinstance(entries, list) and entries
    finally:
        if snapshot_passcode is None:
            os.environ.pop("PERMANENCE_FOUNDATION_PASSCODE", None)
        else:
            os.environ["PERMANENCE_FOUNDATION_PASSCODE"] = snapshot_passcode


def test_foundation_ophtxn_shell_and_ops_summary() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        tool_root = root / "tool"
        tool_root.mkdir(parents=True, exist_ok=True)

        (tool_root / "ophtxn_completion_20260305-000000.json").write_text(
            json.dumps({"completion_pct": 100, "blockers": [], "latest_markdown": "/tmp/completion.md"}) + "\n",
            encoding="utf-8",
        )
        (tool_root / "money_first_gate_20260305-000000.json").write_text(
            json.dumps(
                {
                    "status": {"gate_pass": True, "won_revenue_usd": 1500, "won_deals": 1},
                    "latest_markdown": "/tmp/money.md",
                }
            )
            + "\n",
            encoding="utf-8",
        )
        (tool_root / "comms_status_20260305-000000.json").write_text(
            json.dumps({"warnings": [], "latest_markdown": "/tmp/comms.md"}) + "\n",
            encoding="utf-8",
        )
        (tool_root / "self_improvement_20260305-000000.json").write_text(
            json.dumps({"pending_count": 0, "latest_markdown": "/tmp/improve.md"}) + "\n",
            encoding="utf-8",
        )
        (tool_root / "approval_execution_board_20260305-000000.json").write_text(
            json.dumps({"task_count": 12, "marked_queued_count": 3, "latest_markdown": "/tmp/approval.md"}) + "\n",
            encoding="utf-8",
        )

        app = create_app(storage_root=(root / "app"), tool_root=tool_root)
        client = app.test_client()

        shell = client.get("/app/ophtxn")
        assert shell.status_code == 200
        assert "Ophtxn App Shell" in (shell.get_data(as_text=True) or "")

        unauthorized = client.get("/ops/summary")
        assert unauthorized.status_code == 401

        auth = client.post("/auth/session", json={"user_id": "payton"})
        assert auth.status_code == 200
        token = str((auth.get_json() or {}).get("token") or "")
        assert token
        headers = {"X-Session-Token": token}

        summary = client.get("/ops/summary", headers=headers)
        assert summary.status_code == 200
        payload = summary.get_json() or {}
        assert payload.get("ok") is True
        metrics = payload.get("summary") or {}
        assert int(metrics.get("completion_pct") or 0) == 100
        assert bool(metrics.get("feature_work_unlocked")) is True
        assert int(metrics.get("approved_execution_tasks") or 0) == 12


if __name__ == "__main__":
    test_foundation_health_endpoint()
    test_foundation_auth_onboarding_and_memory_flow()
    test_foundation_ophtxn_shell_and_ops_summary()
    print("✓ Foundation API scaffold tests passed")
