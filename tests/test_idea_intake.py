#!/usr/bin/env python3
"""Tests for idea_intake pipeline."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import scripts.idea_intake as mod  # noqa: E402


def _append_jsonl(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload) + "\n")


def test_idea_intake_process_ranks_and_queues_approvals() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        output = root / "outputs"
        tool = root / "tool"
        working = root / "working"
        intake = root / "inbox" / "telegram_share_intake.jsonl"
        state = root / "working" / "idea_intake" / "state.json"
        policy = root / "working" / "idea_intake" / "policy.json"
        approvals = root / "memory" / "approvals.json"
        output.mkdir(parents=True, exist_ok=True)
        tool.mkdir(parents=True, exist_ok=True)
        working.mkdir(parents=True, exist_ok=True)

        _append_jsonl(
            intake,
            {
                "intake_id": "INT-AAA111",
                "created_at": "2026-03-05T00:00:00Z",
                "source": "telegram-share",
                "channel": "telegram",
                "text": "New OpenAI repo: https://github.com/openai/symphony and Cloudflare MCP https://github.com/cloudflare/mcp",
                "urls": ["https://github.com/openai/symphony", "https://github.com/cloudflare/mcp"],
            },
        )
        _append_jsonl(
            intake,
            {
                "intake_id": "INT-BBB222",
                "created_at": "2026-03-05T00:01:00Z",
                "source": "telegram-share",
                "channel": "telegram",
                "text": "Read this strategy piece https://mitsloan.mit.edu/ideas-made-to-matter/how-digital-business-models-are-evolving-age-agentic-ai",
            },
        )

        original = {
            "WORKING_DIR": mod.WORKING_DIR,
            "OUTPUT_DIR": mod.OUTPUT_DIR,
            "TOOL_DIR": mod.TOOL_DIR,
            "INTAKE_PATH": mod.INTAKE_PATH,
            "STATE_PATH": mod.STATE_PATH,
            "POLICY_PATH": mod.POLICY_PATH,
            "APPROVALS_PATH": mod.APPROVALS_PATH,
        }
        try:
            mod.WORKING_DIR = working
            mod.OUTPUT_DIR = output
            mod.TOOL_DIR = tool
            mod.INTAKE_PATH = intake
            mod.STATE_PATH = state
            mod.POLICY_PATH = policy
            mod.APPROVALS_PATH = approvals
            rc = mod.main(
                [
                    "--action",
                    "process",
                    "--queue-approvals",
                    "--queue-limit",
                    "3",
                    "--queue-min-score",
                    "50",
                ]
            )
        finally:
            mod.WORKING_DIR = original["WORKING_DIR"]
            mod.OUTPUT_DIR = original["OUTPUT_DIR"]
            mod.TOOL_DIR = original["TOOL_DIR"]
            mod.INTAKE_PATH = original["INTAKE_PATH"]
            mod.STATE_PATH = original["STATE_PATH"]
            mod.POLICY_PATH = original["POLICY_PATH"]
            mod.APPROVALS_PATH = original["APPROVALS_PATH"]

        assert rc == 0
        latest = output / "idea_intake_latest.md"
        assert latest.exists()
        text = latest.read_text(encoding="utf-8")
        assert "Ranked ideas:" in text
        payload_files = sorted(tool.glob("idea_intake_*.json"))
        assert payload_files
        payload = json.loads(payload_files[-1].read_text(encoding="utf-8"))
        assert int(payload.get("item_count", 0)) >= 2
        top_items = payload.get("top_items") if isinstance(payload.get("top_items"), list) else []
        assert any("github.com/openai/symphony" in str(row.get("url") or "") for row in top_items if isinstance(row, dict))
        assert approvals.exists()
        approvals_payload = json.loads(approvals.read_text(encoding="utf-8"))
        assert isinstance(approvals_payload, list)
        assert any(str(row.get("source") or "") == "idea_intake_queue" for row in approvals_payload if isinstance(row, dict))
        assert state.exists()


def test_idea_intake_intake_and_strict_repeat_run() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        output = root / "outputs"
        tool = root / "tool"
        working = root / "working"
        intake = root / "inbox" / "telegram_share_intake.jsonl"
        state = root / "working" / "idea_intake" / "state.json"
        policy = root / "working" / "idea_intake" / "policy.json"
        approvals = root / "memory" / "approvals.json"
        output.mkdir(parents=True, exist_ok=True)
        tool.mkdir(parents=True, exist_ok=True)
        working.mkdir(parents=True, exist_ok=True)

        original = {
            "WORKING_DIR": mod.WORKING_DIR,
            "OUTPUT_DIR": mod.OUTPUT_DIR,
            "TOOL_DIR": mod.TOOL_DIR,
            "INTAKE_PATH": mod.INTAKE_PATH,
            "STATE_PATH": mod.STATE_PATH,
            "POLICY_PATH": mod.POLICY_PATH,
            "APPROVALS_PATH": mod.APPROVALS_PATH,
        }
        try:
            mod.WORKING_DIR = working
            mod.OUTPUT_DIR = output
            mod.TOOL_DIR = tool
            mod.INTAKE_PATH = intake
            mod.STATE_PATH = state
            mod.POLICY_PATH = policy
            mod.APPROVALS_PATH = approvals
            intake_rc = mod.main(
                [
                    "--action",
                    "intake",
                    "--text",
                    "Track this post https://x.com/roundtablespace/status/2029478270438133918?s=46",
                    "--source",
                    "manual-test",
                    "--channel",
                    "cli",
                ]
            )
            assert intake_rc == 0
            first_run = mod.main(["--action", "process"])
            second_run = mod.main(["--action", "process", "--strict"])
        finally:
            mod.WORKING_DIR = original["WORKING_DIR"]
            mod.OUTPUT_DIR = original["OUTPUT_DIR"]
            mod.TOOL_DIR = original["TOOL_DIR"]
            mod.INTAKE_PATH = original["INTAKE_PATH"]
            mod.STATE_PATH = original["STATE_PATH"]
            mod.POLICY_PATH = original["POLICY_PATH"]
            mod.APPROVALS_PATH = original["APPROVALS_PATH"]

        assert first_run == 0
        assert second_run == 1
        stat = mod._status(intake_path=intake, state_path=state)
        assert int(stat.get("entries_total", 0)) >= 1
        assert int(stat.get("entries_pending", 0)) == 0


if __name__ == "__main__":
    test_idea_intake_process_ranks_and_queues_approvals()
    test_idea_intake_intake_and_strict_repeat_run()
    print("✓ Idea intake tests passed")
