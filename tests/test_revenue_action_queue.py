#!/usr/bin/env python3
"""Tests for revenue action queue generation."""

import json
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import scripts.revenue_action_queue as queue_mod  # noqa: E402


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    payload = "".join(json.dumps(row) + "\n" for row in rows)
    path.write_text(payload, encoding="utf-8")


def test_revenue_action_queue_uses_pipeline_and_funnel_signals():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        outputs_dir = root / "outputs"
        tool_dir = root / "tool"
        working_dir = root / "working"
        outputs_dir.mkdir(parents=True, exist_ok=True)
        tool_dir.mkdir(parents=True, exist_ok=True)
        working_dir.mkdir(parents=True, exist_ok=True)

        now = datetime.now(timezone.utc)
        now_iso = now.isoformat()
        stale_iso = (now - timedelta(days=5)).isoformat()
        due_today = now.date().isoformat()
        due_tomorrow = (now.date() + timedelta(days=1)).isoformat()

        (outputs_dir / "email_triage_20260226-120000.md").write_text(
            "\n".join(
                [
                    "# Email Triage",
                    "## P0 (1)",
                    "- [30] Hot prospect asking for proposal",
                    "## P1 (0)",
                    "## P2 (0)",
                    "## P3 (0)",
                ]
            ),
            encoding="utf-8",
        )
        (outputs_dir / "social_summary_20260226-120000.md").write_text(
            "\n".join(
                [
                    "# Social Draft Summary",
                    "- FOUNDATION case-study post [LinkedIn] (2026-02-26T12:00:00Z)",
                ]
            ),
            encoding="utf-8",
        )

        pipeline_rows = [
            {
                "lead_id": "L-100",
                "name": "Alpha Co",
                "stage": "qualified",
                "est_value": 1800,
                "next_action": "Book fit call",
                "next_action_due": due_today,
                "created_at": now_iso,
                "updated_at": now_iso,
                "closed_at": None,
            },
            {
                "lead_id": "L-101",
                "name": "Beta Co",
                "stage": "proposal_sent",
                "est_value": 2500,
                "next_action": "Follow up on proposal",
                "next_action_due": due_tomorrow,
                "created_at": now_iso,
                "updated_at": stale_iso,
                "closed_at": None,
            },
            {
                "lead_id": "L-102",
                "name": "Gamma Co",
                "stage": "won",
                "est_value": 1500,
                "actual_value": 1500,
                "next_action": "",
                "next_action_due": "",
                "created_at": now_iso,
                "updated_at": now_iso,
                "closed_at": now_iso,
            },
        ]
        (working_dir / "sales_pipeline.json").write_text(json.dumps(pipeline_rows), encoding="utf-8")

        intake_rows = [
            {"name": "Intake One", "email": "i1@example.com", "created_at": now_iso},
            {"name": "Intake Two", "email": "i2@example.com", "created_at": now_iso},
            {"name": "Intake Three", "email": "i3@example.com", "created_at": now_iso},
        ]
        _write_jsonl(working_dir / "revenue_intake.jsonl", intake_rows)

        original = {
            "OUTPUT_DIR": queue_mod.OUTPUT_DIR,
            "TOOL_DIR": queue_mod.TOOL_DIR,
            "WORKING_DIR": queue_mod.WORKING_DIR,
            "PIPELINE_PATH": queue_mod.PIPELINE_PATH,
            "INTAKE_PATH": queue_mod.INTAKE_PATH,
            "PLAYBOOK_PATH": queue_mod.PLAYBOOK_PATH,
        }
        try:
            queue_mod.OUTPUT_DIR = outputs_dir
            queue_mod.TOOL_DIR = tool_dir
            queue_mod.WORKING_DIR = working_dir
            queue_mod.PIPELINE_PATH = working_dir / "sales_pipeline.json"
            queue_mod.INTAKE_PATH = working_dir / "revenue_intake.jsonl"
            queue_mod.PLAYBOOK_PATH = working_dir / "revenue_playbook.json"
            rc = queue_mod.main()
        finally:
            queue_mod.OUTPUT_DIR = original["OUTPUT_DIR"]
            queue_mod.TOOL_DIR = original["TOOL_DIR"]
            queue_mod.WORKING_DIR = original["WORKING_DIR"]
            queue_mod.PIPELINE_PATH = original["PIPELINE_PATH"]
            queue_mod.INTAKE_PATH = original["INTAKE_PATH"]
            queue_mod.PLAYBOOK_PATH = original["PLAYBOOK_PATH"]

        assert rc == 0

        latest_md = outputs_dir / "revenue_action_queue_latest.md"
        assert latest_md.exists()
        content = latest_md.read_text(encoding="utf-8")
        assert "## Funnel Signals" in content
        assert "## Next 7 Actions" in content
        assert "Alpha Co (L-100)" in content

        payloads = sorted(tool_dir.glob("revenue_action_queue_*.json"))
        assert payloads
        payload = json.loads(payloads[-1].read_text(encoding="utf-8"))
        assert payload["funnel"]["pipeline_total"] == 3
        assert payload["funnel"]["bottleneck"] is not None
        assert len(payload["actions"]) == 7
        assert any(action["type"] == "pipeline_urgent" for action in payload["actions"])
        assert any(action["type"] == "funnel_bottleneck" for action in payload["actions"])


def test_revenue_action_queue_falls_back_to_template_actions():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        outputs_dir = root / "outputs"
        tool_dir = root / "tool"
        working_dir = root / "working"
        outputs_dir.mkdir(parents=True, exist_ok=True)
        tool_dir.mkdir(parents=True, exist_ok=True)
        working_dir.mkdir(parents=True, exist_ok=True)
        (working_dir / "sales_pipeline.json").write_text("[]\n", encoding="utf-8")
        (working_dir / "revenue_intake.jsonl").write_text("", encoding="utf-8")

        original = {
            "OUTPUT_DIR": queue_mod.OUTPUT_DIR,
            "TOOL_DIR": queue_mod.TOOL_DIR,
            "WORKING_DIR": queue_mod.WORKING_DIR,
            "PIPELINE_PATH": queue_mod.PIPELINE_PATH,
            "INTAKE_PATH": queue_mod.INTAKE_PATH,
            "PLAYBOOK_PATH": queue_mod.PLAYBOOK_PATH,
        }
        try:
            queue_mod.OUTPUT_DIR = outputs_dir
            queue_mod.TOOL_DIR = tool_dir
            queue_mod.WORKING_DIR = working_dir
            queue_mod.PIPELINE_PATH = working_dir / "sales_pipeline.json"
            queue_mod.INTAKE_PATH = working_dir / "revenue_intake.jsonl"
            queue_mod.PLAYBOOK_PATH = working_dir / "revenue_playbook.json"
            rc = queue_mod.main()
        finally:
            queue_mod.OUTPUT_DIR = original["OUTPUT_DIR"]
            queue_mod.TOOL_DIR = original["TOOL_DIR"]
            queue_mod.WORKING_DIR = original["WORKING_DIR"]
            queue_mod.PIPELINE_PATH = original["PIPELINE_PATH"]
            queue_mod.INTAKE_PATH = original["INTAKE_PATH"]
            queue_mod.PLAYBOOK_PATH = original["PLAYBOOK_PATH"]

        assert rc == 0
        payloads = sorted(tool_dir.glob("revenue_action_queue_*.json"))
        assert payloads
        payload = json.loads(payloads[-1].read_text(encoding="utf-8"))
        assert len(payload["actions"]) == 7
        assert any(action["type"] == "offer_clarity" for action in payload["actions"])


def test_revenue_action_queue_filters_non_revenue_email_noise():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        outputs_dir = root / "outputs"
        tool_dir = root / "tool"
        working_dir = root / "working"
        outputs_dir.mkdir(parents=True, exist_ok=True)
        tool_dir.mkdir(parents=True, exist_ok=True)
        working_dir.mkdir(parents=True, exist_ok=True)

        now_iso = datetime.now(timezone.utc).isoformat()
        (outputs_dir / "email_triage_20260226-130000.md").write_text(
            "\n".join(
                [
                    "# Email Triage",
                    "## P0 (3)",
                    "- [30] Your Apple Account was used to sign in to iCloud on an iPad",
                    "- [28] Weekly digest from Coinbase Bytes",
                    "- [27] 10 Books to Help You Enter the Top 1% of Entrepreneurs Worldwide",
                    "- [26] TAKE ACTION: You're leaving money behind. We can help. Call 877-902-0006. — Fidelity Investments <Fidelity.Investments@mail.fidelity.com>",
                    "## P1 (0)",
                    "## P2 (0)",
                    "## P3 (0)",
                ]
            ),
            encoding="utf-8",
        )

        pipeline_rows = [
            {
                "lead_id": "L-200",
                "name": "Delta Co",
                "stage": "lead",
                "est_value": 1500,
                "next_action": "Send intake + book fit call",
                "next_action_due": datetime.now(timezone.utc).date().isoformat(),
                "created_at": now_iso,
                "updated_at": now_iso,
                "closed_at": None,
            }
        ]
        (working_dir / "sales_pipeline.json").write_text(json.dumps(pipeline_rows), encoding="utf-8")
        _write_jsonl(working_dir / "revenue_intake.jsonl", [])

        original = {
            "OUTPUT_DIR": queue_mod.OUTPUT_DIR,
            "TOOL_DIR": queue_mod.TOOL_DIR,
            "WORKING_DIR": queue_mod.WORKING_DIR,
            "PIPELINE_PATH": queue_mod.PIPELINE_PATH,
            "INTAKE_PATH": queue_mod.INTAKE_PATH,
            "PLAYBOOK_PATH": queue_mod.PLAYBOOK_PATH,
        }
        try:
            queue_mod.OUTPUT_DIR = outputs_dir
            queue_mod.TOOL_DIR = tool_dir
            queue_mod.WORKING_DIR = working_dir
            queue_mod.PIPELINE_PATH = working_dir / "sales_pipeline.json"
            queue_mod.INTAKE_PATH = working_dir / "revenue_intake.jsonl"
            queue_mod.PLAYBOOK_PATH = working_dir / "revenue_playbook.json"
            rc = queue_mod.main()
        finally:
            queue_mod.OUTPUT_DIR = original["OUTPUT_DIR"]
            queue_mod.TOOL_DIR = original["TOOL_DIR"]
            queue_mod.WORKING_DIR = original["WORKING_DIR"]
            queue_mod.PIPELINE_PATH = original["PIPELINE_PATH"]
            queue_mod.INTAKE_PATH = original["INTAKE_PATH"]
            queue_mod.PLAYBOOK_PATH = original["PLAYBOOK_PATH"]

        assert rc == 0
        payloads = sorted(tool_dir.glob("revenue_action_queue_*.json"))
        assert payloads
        payload = json.loads(payloads[-1].read_text(encoding="utf-8"))
        joined_actions = " || ".join(str(a.get("action") or "") for a in payload["actions"]).lower()
        assert "icloud" not in joined_actions
        assert "coinbase bytes" not in joined_actions
        assert "books to help you enter" not in joined_actions
        assert "fidelity investments" not in joined_actions


if __name__ == "__main__":
    test_revenue_action_queue_uses_pipeline_and_funnel_signals()
    test_revenue_action_queue_falls_back_to_template_actions()
    test_revenue_action_queue_filters_non_revenue_email_noise()
    print("✓ Revenue action queue tests passed")
