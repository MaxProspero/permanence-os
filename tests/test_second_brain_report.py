#!/usr/bin/env python3
"""Tests for second brain unified report."""

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import scripts.second_brain_report as brain_mod  # noqa: E402


def test_second_brain_report_aggregates_sources():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        working = root / "working"
        outputs = root / "outputs"
        tool = root / "tool"
        working.mkdir(parents=True, exist_ok=True)
        outputs.mkdir(parents=True, exist_ok=True)
        tool.mkdir(parents=True, exist_ok=True)

        (tool / "life_os_brief_20260227-120000.json").write_text(
            json.dumps({"open_task_count": 3, "top_actions": [{"task_id": "LIFE-1"}]}), encoding="utf-8"
        )
        (tool / "side_business_portfolio_20260227-120000.json").write_text(
            json.dumps({"stream_count": 4, "totals": {"weekly_gap_usd": 1200}}), encoding="utf-8"
        )
        (tool / "github_research_ingest_20260227-120000.json").write_text(
            json.dumps({"repo_count": 2, "repos": [{"top_actions": ["a", "b"]}, {"top_actions": ["c"]}]}),
            encoding="utf-8",
        )
        (tool / "github_trending_ingest_20260227-120000.json").write_text(
            json.dumps({"repo_count": 9, "top_items": [{"repo": "ruvnet/RuView"}]}),
            encoding="utf-8",
        )
        (tool / "ecosystem_research_ingest_20260227-120000.json").write_text(
            json.dumps({"repo_count": 11, "developer_count": 7, "docs_count": 4, "communities_count": 3}),
            encoding="utf-8",
        )
        (tool / "social_research_ingest_20260227-120000.json").write_text(
            json.dumps({"item_count": 12, "top_items": [{"title": "trend"}]}), encoding="utf-8"
        )
        (tool / "prediction_lab_20260227-120000.json").write_text(
            json.dumps({"manual_review_candidates": 2, "results": [{"id": "PM-1"}]}), encoding="utf-8"
        )
        (tool / "clipping_pipeline_20260227-120000.json").write_text(
            json.dumps({"job_count": 2, "candidate_count": 5}), encoding="utf-8"
        )
        (tool / "world_watch_20260227-120000.json").write_text(
            json.dumps({"item_count": 22, "high_alert_count": 5, "top_alerts": [{"event_id": "e1"}]}),
            encoding="utf-8",
        )
        (tool / "world_watch_alerts_20260227-120000.json").write_text(
            json.dumps({"dispatch_results": [{"channel": "discord", "ok": True}]}),
            encoding="utf-8",
        )
        (tool / "opportunity_ranker_20260227-120000.json").write_text(
            json.dumps({"item_count": 6, "top_items": [{"opportunity_id": "opp-1"}]}), encoding="utf-8"
        )
        (tool / "opportunity_approval_queue_20260227-120000.json").write_text(
            json.dumps({"queued_count": 3, "pending_total": 9}), encoding="utf-8"
        )
        (tool / "revenue_execution_board_20260227-120000.json").write_text(
            json.dumps({"pipeline": {"open_count": 6, "weighted_value": 9800}}), encoding="utf-8"
        )
        (tool / "revenue_cost_recovery_20260227-120000.json").write_text(
            json.dumps({"recovery_plan": {"target_recovery_usd": 180, "target_closes": 1, "daily_outreach_needed": 4}}),
            encoding="utf-8",
        )
        (working / "founder_note_cards.json").write_text(
            json.dumps({"note_cards": [{"card_id": "1"}, {"card_id": "2"}], "implementation_directives": [1, 2, 3]}),
            encoding="utf-8",
        )

        original = {
            "WORKING_DIR": brain_mod.WORKING_DIR,
            "OUTPUT_DIR": brain_mod.OUTPUT_DIR,
            "TOOL_DIR": brain_mod.TOOL_DIR,
        }
        try:
            brain_mod.WORKING_DIR = working
            brain_mod.OUTPUT_DIR = outputs
            brain_mod.TOOL_DIR = tool
            rc = brain_mod.main()
        finally:
            brain_mod.WORKING_DIR = original["WORKING_DIR"]
            brain_mod.OUTPUT_DIR = original["OUTPUT_DIR"]
            brain_mod.TOOL_DIR = original["TOOL_DIR"]

        assert rc == 0
        latest = outputs / "second_brain_report_latest.md"
        assert latest.exists()
        content = latest.read_text(encoding="utf-8")
        assert "Second Brain Report" in content
        assert "GitHub repos scanned: 2" in content
        assert "GitHub trending repos tracked: 9" in content
        assert "Ecosystem repos tracked: 11" in content
        assert "Ecosystem developers tracked: 7" in content
        assert "Prediction hypotheses: 1" in content
        assert "Global alerts tracked: 22" in content
        assert "High global alerts: 5" in content
        assert "Opportunities ranked: 6" in content
        assert "Opportunities queued: 3" in content
        assert "Founder note cards captured: 2" in content
        assert "API/tool recovery target: $180" in content

        tool_files = sorted(tool.glob("second_brain_report_*.json"))
        assert tool_files
        payload = json.loads(tool_files[-1].read_text(encoding="utf-8"))
        assert payload.get("snapshot", {}).get("portfolio", {}).get("stream_count") == 4
        assert payload.get("snapshot", {}).get("research", {}).get("social_item_count") == 12
        assert payload.get("snapshot", {}).get("research", {}).get("github_trending_count") == 9
        assert payload.get("snapshot", {}).get("research", {}).get("ecosystem_repo_count") == 11
        assert payload.get("snapshot", {}).get("research", {}).get("ecosystem_developer_count") == 7
        assert payload.get("snapshot", {}).get("world_watch", {}).get("high_alert_count") == 5
        assert payload.get("snapshot", {}).get("opportunities", {}).get("pending_total") == 9
        assert payload.get("snapshot", {}).get("cost_recovery", {}).get("target_closes") == 1
        assert payload.get("snapshot", {}).get("founder", {}).get("note_card_count") == 2
        assert payload.get("snapshot", {}).get("founder", {}).get("directive_count") == 3


if __name__ == "__main__":
    test_second_brain_report_aggregates_sources()
    print("✓ Second brain report tests passed")
