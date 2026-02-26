#!/usr/bin/env python3
"""Focused tests for dashboard_api helper behavior."""

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

try:
    import dashboard_api
except ModuleNotFoundError as exc:
    if exc.name == "flask":
        dashboard_api = None
    else:
        raise


def _skip_if_missing_dashboard_api() -> bool:
    if dashboard_api is not None:
        return False
    print("skipped: dashboard_api tests require flask")
    return True


def test_load_latest_task_summary_includes_model_routes():
    if _skip_if_missing_dashboard_api():
        return
    with tempfile.TemporaryDirectory() as tmp:
        episodic_dir = Path(tmp) / "memory" / "episodic"
        episodic_dir.mkdir(parents=True, exist_ok=True)
        state = {
            "task_id": "T-TEST-001",
            "stage": "DONE",
            "status": "DONE",
            "risk_tier": "LOW",
            "task_goal": "Test latest task summary",
            "artifacts": {"model_routes": {"planning": "claude-sonnet-4-6"}},
        }
        (episodic_dir / "T-TEST-001.json").write_text(json.dumps(state), encoding="utf-8")

        original = dict(dashboard_api.PATHS)
        try:
            dashboard_api.PATHS["episodic"] = str(episodic_dir)
            summary = dashboard_api._load_latest_task_summary()
            assert summary is not None
            assert summary["task_id"] == "T-TEST-001"
            assert summary["model_routes"]["planning"] == "claude-sonnet-4-6"
        finally:
            dashboard_api.PATHS.update(original)


def test_load_latest_briefing_supports_markdown():
    if _skip_if_missing_dashboard_api():
        return
    with tempfile.TemporaryDirectory() as tmp:
        briefings_dir = Path(tmp) / "outputs" / "briefings"
        briefings_dir.mkdir(parents=True, exist_ok=True)
        md_path = briefings_dir / "briefing_20260225-000000.md"
        md_path.write_text("# Briefing\n\n- Item A\n", encoding="utf-8")

        original = dict(dashboard_api.PATHS)
        try:
            dashboard_api.PATHS["briefings"] = str(briefings_dir)
            payload = dashboard_api._load_latest_briefing()
            assert payload is not None
            assert payload.get("format") == "markdown"
            assert "# Briefing" in payload.get("content_markdown", "")
        finally:
            dashboard_api.PATHS.update(original)


def test_load_promotion_status_reads_storage_log_fallback():
    if _skip_if_missing_dashboard_api():
        return
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        logs_dir = root / "logs"
        storage_root = root / "permanence_storage"
        storage_logs = storage_root / "logs"
        memory_working = root / "memory" / "working"
        outputs_dir = root / "outputs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        storage_logs.mkdir(parents=True, exist_ok=True)
        memory_working.mkdir(parents=True, exist_ok=True)
        outputs_dir.mkdir(parents=True, exist_ok=True)

        (storage_logs / "status_today.json").write_text('{"today_state":"PASS"}\n', encoding="utf-8")
        (storage_logs / "phase_gate_2026-02-25.md").write_text(
            "# Phase Gate\n\n- Phase gate: PASS\n",
            encoding="utf-8",
        )
        (memory_working / "promotion_queue.json").write_text(
            '[{"task_id":"T-1"},{"task_id":"T-2"}]\n',
            encoding="utf-8",
        )
        (outputs_dir / "promotion_review.md").write_text("# Promotion Review\n", encoding="utf-8")

        original_paths = dict(dashboard_api.PATHS)
        original_storage_root = os.environ.get("PERMANENCE_STORAGE_ROOT")
        original_memory_dir = os.environ.get("PERMANENCE_MEMORY_DIR")
        original_queue_path = os.environ.get("PERMANENCE_PROMOTION_QUEUE")
        try:
            dashboard_api.PATHS["logs"] = str(logs_dir)
            dashboard_api.PATHS["outputs"] = str(outputs_dir)
            os.environ["PERMANENCE_STORAGE_ROOT"] = str(storage_root)
            os.environ["PERMANENCE_MEMORY_DIR"] = str(root / "memory")
            os.environ["PERMANENCE_PROMOTION_QUEUE"] = str(memory_working / "promotion_queue.json")

            status = dashboard_api._load_promotion_status()
            assert status["queue_items"] == 2
            assert status["glance_gate"] == "PASS"
            assert status["phase_gate"] == "PASS"
            assert status["review_last_generated"] is not None
        finally:
            dashboard_api.PATHS.update(original_paths)
            if original_storage_root is None:
                os.environ.pop("PERMANENCE_STORAGE_ROOT", None)
            else:
                os.environ["PERMANENCE_STORAGE_ROOT"] = original_storage_root
            if original_memory_dir is None:
                os.environ.pop("PERMANENCE_MEMORY_DIR", None)
            else:
                os.environ["PERMANENCE_MEMORY_DIR"] = original_memory_dir
            if original_queue_path is None:
                os.environ.pop("PERMANENCE_PROMOTION_QUEUE", None)
            else:
                os.environ["PERMANENCE_PROMOTION_QUEUE"] = original_queue_path


def test_load_revenue_snapshot_includes_pipeline_and_board():
    if _skip_if_missing_dashboard_api():
        return
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        outputs_dir = root / "outputs"
        working_dir = root / "working"
        outputs_dir.mkdir(parents=True, exist_ok=True)
        working_dir.mkdir(parents=True, exist_ok=True)

        (outputs_dir / "revenue_action_queue_20260225-000001.md").write_text(
            "\n".join(
                [
                    "# Revenue Action Queue",
                    "",
                    "## Next 7 Actions",
                    "1. [today] Send follow-up to lead A",
                    "2. [today] Publish FOUNDATION post",
                ]
            ),
            encoding="utf-8",
        )

        (outputs_dir / "revenue_execution_board_latest.md").write_text(
            "\n".join(
                [
                    "# Revenue Execution Board",
                    "",
                    "## Today's Non-Negotiables",
                    "1. [today] Send 5 DMs",
                    "2. [today] Run discovery call",
                    "",
                    "## Pipeline Urgent Actions (<=24h)",
                    "- L-1 | Lead A | due=2026-02-26 | Send proposal",
                    "",
                    "## Publish + Outreach Block",
                    "- Outreach target today: 10",
                    "",
                    "### Inbox Pressure",
                    "- P0: 1 | P1: 2 | P2: 3 | P3: 4",
                ]
            ),
            encoding="utf-8",
        )

        pipeline_path = working_dir / "sales_pipeline.json"
        pipeline_path.write_text(
            json.dumps(
                [
                    {
                        "lead_id": "L-1",
                        "name": "Lead A",
                        "stage": "qualified",
                        "est_value": 1500,
                        "next_action_due": "2026-02-26",
                    },
                    {
                        "lead_id": "L-2",
                        "name": "Lead B",
                        "stage": "won",
                        "est_value": 1000,
                        "actual_value": 1000,
                        "next_action_due": "",
                    },
                ]
            ),
            encoding="utf-8",
        )
        intake_path = working_dir / "revenue_intake.jsonl"
        intake_path.write_text(
            json.dumps(
                {
                    "name": "Intake Lead",
                    "email": "intake@example.com",
                    "workflow": "Operations",
                    "package": "Core",
                    "created_at": "2026-02-25T10:00:00Z",
                }
            )
            + "\n",
            encoding="utf-8",
        )
        action_status_path = working_dir / "revenue_action_status.jsonl"
        first_action = "[today] Send follow-up to lead A"
        action_status_path.write_text(
            json.dumps(
                {
                    "event_id": "RA-TEST-1",
                    "timestamp": "2026-02-25T11:00:00Z",
                    "action": first_action,
                    "action_hash": dashboard_api._action_hash(first_action),
                    "completed": True,
                    "source": "test",
                    "actor": "human",
                    "notes": "",
                }
            )
            + "\n",
            encoding="utf-8",
        )

        original_paths = dict(dashboard_api.PATHS)
        original_pipeline_path = os.environ.get("PERMANENCE_SALES_PIPELINE_PATH")
        original_intake_path = os.environ.get("PERMANENCE_REVENUE_INTAKE_PATH")
        original_action_status_path = os.environ.get("PERMANENCE_REVENUE_ACTION_STATUS_PATH")
        try:
            dashboard_api.PATHS["outputs"] = str(outputs_dir)
            dashboard_api.PATHS["working"] = str(working_dir)
            os.environ["PERMANENCE_SALES_PIPELINE_PATH"] = str(pipeline_path)
            os.environ["PERMANENCE_REVENUE_INTAKE_PATH"] = str(intake_path)
            os.environ["PERMANENCE_REVENUE_ACTION_STATUS_PATH"] = str(action_status_path)

            snapshot = dashboard_api._load_revenue_snapshot()
            assert snapshot["queue"]["count"] == 2
            assert snapshot["queue"]["completed_count"] == 1
            assert snapshot["queue"]["pending_count"] == 1
            assert len(snapshot["queue"]["items"]) == 2
            assert len(snapshot["board"]["non_negotiables"]) == 2
            assert snapshot["board"]["inbox_pressure"]["P1"] == 2
            assert snapshot["pipeline"]["total"] == 2
            assert snapshot["pipeline"]["open_count"] == 1
            assert snapshot["pipeline"]["weighted_value"] == 375.0
            assert snapshot["pipeline"]["urgent_count"] >= 0
            assert snapshot["intake"]["count"] == 1
            assert snapshot["funnel"]["pipeline_total"] == 2
            assert len(snapshot["funnel"]["segments"]) >= 4
            assert snapshot["funnel"]["bottleneck"] is not None
        finally:
            dashboard_api.PATHS.update(original_paths)
            if original_pipeline_path is None:
                os.environ.pop("PERMANENCE_SALES_PIPELINE_PATH", None)
            else:
                os.environ["PERMANENCE_SALES_PIPELINE_PATH"] = original_pipeline_path
            if original_intake_path is None:
                os.environ.pop("PERMANENCE_REVENUE_INTAKE_PATH", None)
            else:
                os.environ["PERMANENCE_REVENUE_INTAKE_PATH"] = original_intake_path
            if original_action_status_path is None:
                os.environ.pop("PERMANENCE_REVENUE_ACTION_STATUS_PATH", None)
            else:
                os.environ["PERMANENCE_REVENUE_ACTION_STATUS_PATH"] = original_action_status_path


def test_revenue_action_endpoint_tracks_completion():
    if _skip_if_missing_dashboard_api():
        return
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        working_dir = root / "working"
        outputs_dir = root / "outputs"
        logs_dir = root / "logs"
        working_dir.mkdir(parents=True, exist_ok=True)
        outputs_dir.mkdir(parents=True, exist_ok=True)
        logs_dir.mkdir(parents=True, exist_ok=True)
        action_status_path = working_dir / "revenue_action_status.jsonl"

        original_paths = dict(dashboard_api.PATHS)
        original_action_status_path = os.environ.get("PERMANENCE_REVENUE_ACTION_STATUS_PATH")
        try:
            dashboard_api.PATHS["working"] = str(working_dir)
            dashboard_api.PATHS["outputs"] = str(outputs_dir)
            dashboard_api.PATHS["logs"] = str(logs_dir)
            dashboard_api.PATHS["api_log"] = str(logs_dir / "dashboard_api.log")
            os.environ["PERMANENCE_REVENUE_ACTION_STATUS_PATH"] = str(action_status_path)

            client = dashboard_api.app.test_client()
            response = client.post(
                "/api/revenue/action",
                json={
                    "action": "[today] Send follow-up to lead A",
                    "completed": True,
                    "source": "dashboard",
                    "actor": "human",
                },
            )
            assert response.status_code == 200
            payload = response.get_json() or {}
            assert payload.get("status") == "UPDATED"
            assert payload.get("completed") is True

            state = dashboard_api._load_revenue_action_status()
            action_hash = dashboard_api._action_hash("[today] Send follow-up to lead A")
            assert action_hash in state
            assert state[action_hash]["completed"] is True
        finally:
            dashboard_api.PATHS.update(original_paths)
            if original_action_status_path is None:
                os.environ.pop("PERMANENCE_REVENUE_ACTION_STATUS_PATH", None)
            else:
                os.environ["PERMANENCE_REVENUE_ACTION_STATUS_PATH"] = original_action_status_path


def test_revenue_run_loop_endpoint_executes_queue_commands():
    if _skip_if_missing_dashboard_api():
        return
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        working_dir = root / "working"
        outputs_dir = root / "outputs"
        logs_dir = root / "logs"
        working_dir.mkdir(parents=True, exist_ok=True)
        outputs_dir.mkdir(parents=True, exist_ok=True)
        logs_dir.mkdir(parents=True, exist_ok=True)

        original_paths = dict(dashboard_api.PATHS)
        try:
            dashboard_api.PATHS["working"] = str(working_dir)
            dashboard_api.PATHS["outputs"] = str(outputs_dir)
            dashboard_api.PATHS["logs"] = str(logs_dir)
            dashboard_api.PATHS["api_log"] = str(logs_dir / "dashboard_api.log")

            client = dashboard_api.app.test_client()
            with patch.object(dashboard_api.subprocess, "call", return_value=0) as mock_call:
                response = client.post("/api/revenue/run-loop", json={"mode": "queue"})
            assert response.status_code == 200
            payload = response.get_json() or {}
            assert payload.get("status") == "OK"
            assert payload.get("mode") == "queue"
            assert len(payload.get("commands") or []) == 4
            assert mock_call.call_count == 4
        finally:
            dashboard_api.PATHS.update(original_paths)


def test_revenue_run_loop_endpoint_rejects_invalid_mode():
    if _skip_if_missing_dashboard_api():
        return
    client = dashboard_api.app.test_client()
    response = client.post("/api/revenue/run-loop", json={"mode": "invalid"})
    assert response.status_code == 400


def test_revenue_intake_endpoint_creates_lead_and_persists_rows():
    if _skip_if_missing_dashboard_api():
        return
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        working_dir = root / "working"
        outputs_dir = root / "outputs"
        logs_dir = root / "logs"
        working_dir.mkdir(parents=True, exist_ok=True)
        outputs_dir.mkdir(parents=True, exist_ok=True)
        logs_dir.mkdir(parents=True, exist_ok=True)

        intake_path = working_dir / "revenue_intake.jsonl"
        pipeline_path = working_dir / "sales_pipeline.json"
        pipeline_path.write_text("[]\n", encoding="utf-8")

        original_paths = dict(dashboard_api.PATHS)
        original_pipeline_path = os.environ.get("PERMANENCE_SALES_PIPELINE_PATH")
        original_intake_path = os.environ.get("PERMANENCE_REVENUE_INTAKE_PATH")
        try:
            dashboard_api.PATHS["working"] = str(working_dir)
            dashboard_api.PATHS["outputs"] = str(outputs_dir)
            dashboard_api.PATHS["logs"] = str(logs_dir)
            dashboard_api.PATHS["api_log"] = str(logs_dir / "dashboard_api.log")
            os.environ["PERMANENCE_SALES_PIPELINE_PATH"] = str(pipeline_path)
            os.environ["PERMANENCE_REVENUE_INTAKE_PATH"] = str(intake_path)

            client = dashboard_api.app.test_client()
            response = client.post(
                "/api/revenue/intake",
                json={
                    "name": "Alex Founder",
                    "email": "alex@example.com",
                    "workflow": "Operations",
                    "package": "Core",
                    "blocker": "No daily operating cadence",
                    "source": "foundation_site",
                },
            )
            assert response.status_code == 200
            payload = response.get_json() or {}
            assert payload.get("status") == "CAPTURED"
            assert payload.get("lead_id")

            intake_rows = dashboard_api._load_intake_rows(limit=10)
            assert len(intake_rows) == 1
            assert intake_rows[0]["email"] == "alex@example.com"

            pipeline_rows = dashboard_api._pipeline_rows(open_only=False, limit=10)
            assert len(pipeline_rows) == 1
            assert pipeline_rows[0]["name"] == "Alex Founder"
            assert pipeline_rows[0]["stage"] == "lead"

            pipeline_response = client.get("/api/revenue/pipeline?open_only=1&limit=10")
            assert pipeline_response.status_code == 200
            pipeline_payload = pipeline_response.get_json() or {}
            assert pipeline_payload.get("count") == 1
        finally:
            dashboard_api.PATHS.update(original_paths)
            if original_pipeline_path is None:
                os.environ.pop("PERMANENCE_SALES_PIPELINE_PATH", None)
            else:
                os.environ["PERMANENCE_SALES_PIPELINE_PATH"] = original_pipeline_path
            if original_intake_path is None:
                os.environ.pop("PERMANENCE_REVENUE_INTAKE_PATH", None)
            else:
                os.environ["PERMANENCE_REVENUE_INTAKE_PATH"] = original_intake_path


def test_revenue_pipeline_update_endpoint_changes_stage():
    if _skip_if_missing_dashboard_api():
        return
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        working_dir = root / "working"
        outputs_dir = root / "outputs"
        logs_dir = root / "logs"
        working_dir.mkdir(parents=True, exist_ok=True)
        outputs_dir.mkdir(parents=True, exist_ok=True)
        logs_dir.mkdir(parents=True, exist_ok=True)

        pipeline_path = working_dir / "sales_pipeline.json"
        pipeline_path.write_text(
            json.dumps(
                [
                    {
                        "lead_id": "L-TEST-1",
                        "name": "Pipeline Lead",
                        "source": "dashboard",
                        "stage": "lead",
                        "offer": "Permanence OS Foundation Setup",
                        "est_value": 1500,
                        "actual_value": None,
                        "next_action": "Initial outreach",
                        "next_action_due": "",
                        "notes": "",
                        "created_at": "2026-02-25T00:00:00Z",
                        "updated_at": "2026-02-25T00:00:00Z",
                        "closed_at": None,
                    }
                ]
            ),
            encoding="utf-8",
        )

        original_paths = dict(dashboard_api.PATHS)
        original_pipeline_path = os.environ.get("PERMANENCE_SALES_PIPELINE_PATH")
        try:
            dashboard_api.PATHS["working"] = str(working_dir)
            dashboard_api.PATHS["outputs"] = str(outputs_dir)
            dashboard_api.PATHS["logs"] = str(logs_dir)
            dashboard_api.PATHS["api_log"] = str(logs_dir / "dashboard_api.log")
            os.environ["PERMANENCE_SALES_PIPELINE_PATH"] = str(pipeline_path)

            client = dashboard_api.app.test_client()
            response = client.post(
                "/api/revenue/pipeline/L-TEST-1",
                json={
                    "stage": "qualified",
                    "next_action": "Book discovery call",
                    "next_action_due": "2026-02-26",
                },
            )
            assert response.status_code == 200
            payload = response.get_json() or {}
            assert payload.get("status") == "UPDATED"
            assert payload.get("lead", {}).get("stage") == "qualified"
            assert payload.get("lead", {}).get("next_action") == "Book discovery call"

            rows = dashboard_api._pipeline_rows(open_only=True, limit=10)
            assert len(rows) == 1
            assert rows[0]["stage"] == "qualified"
            assert rows[0]["next_action_due"] == "2026-02-26"
        finally:
            dashboard_api.PATHS.update(original_paths)
            if original_pipeline_path is None:
                os.environ.pop("PERMANENCE_SALES_PIPELINE_PATH", None)
            else:
                os.environ["PERMANENCE_SALES_PIPELINE_PATH"] = original_pipeline_path


if __name__ == "__main__":
    test_load_latest_task_summary_includes_model_routes()
    test_load_latest_briefing_supports_markdown()
    test_load_promotion_status_reads_storage_log_fallback()
    test_load_revenue_snapshot_includes_pipeline_and_board()
    test_revenue_action_endpoint_tracks_completion()
    test_revenue_run_loop_endpoint_executes_queue_commands()
    test_revenue_run_loop_endpoint_rejects_invalid_mode()
    test_revenue_intake_endpoint_creates_lead_and_persists_rows()
    test_revenue_pipeline_update_endpoint_changes_stage()
    print("✓ Dashboard API helper tests passed")
