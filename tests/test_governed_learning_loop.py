#!/usr/bin/env python3
"""Tests for governed learning loop."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import scripts.governed_learning_loop as learn_mod  # noqa: E402


def test_governed_learning_status_writes_report_and_template() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        outputs = root / "outputs"
        tool = root / "tool"
        working = root / "working"
        outputs.mkdir(parents=True, exist_ok=True)
        tool.mkdir(parents=True, exist_ok=True)
        working.mkdir(parents=True, exist_ok=True)

        original = {
            "OUTPUT_DIR": learn_mod.OUTPUT_DIR,
            "TOOL_DIR": learn_mod.TOOL_DIR,
            "WORKING_DIR": learn_mod.WORKING_DIR,
            "POLICY_PATH": learn_mod.POLICY_PATH,
            "STATE_PATH": learn_mod.STATE_PATH,
        }
        try:
            learn_mod.OUTPUT_DIR = outputs
            learn_mod.TOOL_DIR = tool
            learn_mod.WORKING_DIR = working
            learn_mod.POLICY_PATH = working / "governed_learning_policy.json"
            learn_mod.STATE_PATH = working / "governed_learning_state.json"

            rc = learn_mod.main(["--action", "status"])
        finally:
            learn_mod.OUTPUT_DIR = original["OUTPUT_DIR"]
            learn_mod.TOOL_DIR = original["TOOL_DIR"]
            learn_mod.WORKING_DIR = original["WORKING_DIR"]
            learn_mod.POLICY_PATH = original["POLICY_PATH"]
            learn_mod.STATE_PATH = original["STATE_PATH"]

        assert rc == 0
        assert (working / "governed_learning_policy.json").exists()
        latest = outputs / "governed_learning_latest.md"
        assert latest.exists()
        content = latest.read_text(encoding="utf-8")
        assert "Governed Learning" in content
        assert "Policy enabled: False" in content


def test_governed_learning_run_requires_approval() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        outputs = root / "outputs"
        tool = root / "tool"
        working = root / "working"
        outputs.mkdir(parents=True, exist_ok=True)
        tool.mkdir(parents=True, exist_ok=True)
        working.mkdir(parents=True, exist_ok=True)

        policy_path = working / "governed_learning_policy.json"
        policy = learn_mod._default_policy()
        policy["enabled"] = True
        policy["require_explicit_approval"] = True
        policy["pipelines"]["openclaw_health"]["enabled"] = False
        policy_path.write_text(json.dumps(policy, indent=2) + "\n", encoding="utf-8")

        original = {
            "OUTPUT_DIR": learn_mod.OUTPUT_DIR,
            "TOOL_DIR": learn_mod.TOOL_DIR,
            "WORKING_DIR": learn_mod.WORKING_DIR,
            "POLICY_PATH": learn_mod.POLICY_PATH,
            "STATE_PATH": learn_mod.STATE_PATH,
        }
        try:
            learn_mod.OUTPUT_DIR = outputs
            learn_mod.TOOL_DIR = tool
            learn_mod.WORKING_DIR = working
            learn_mod.POLICY_PATH = policy_path
            learn_mod.STATE_PATH = working / "governed_learning_state.json"
            rc = learn_mod.main(["--action", "run"])
        finally:
            learn_mod.OUTPUT_DIR = original["OUTPUT_DIR"]
            learn_mod.TOOL_DIR = original["TOOL_DIR"]
            learn_mod.WORKING_DIR = original["WORKING_DIR"]
            learn_mod.POLICY_PATH = original["POLICY_PATH"]
            learn_mod.STATE_PATH = original["STATE_PATH"]

        assert rc == 1
        latest = outputs / "governed_learning_latest.md"
        assert latest.exists()
        content = latest.read_text(encoding="utf-8")
        assert "## Blocked" in content
        assert "missing approval" in content.lower()


def test_governed_learning_run_executes_when_approved() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        outputs = root / "outputs"
        tool = root / "tool"
        working = root / "working"
        outputs.mkdir(parents=True, exist_ok=True)
        tool.mkdir(parents=True, exist_ok=True)
        working.mkdir(parents=True, exist_ok=True)

        policy_path = working / "governed_learning_policy.json"
        state_path = working / "governed_learning_state.json"
        policy = learn_mod._default_policy()
        policy["enabled"] = True
        policy["require_explicit_approval"] = True
        policy["max_runs_per_day"] = 5
        policy["pipelines"]["openclaw_health"]["enabled"] = False
        policy_path.write_text(json.dumps(policy, indent=2) + "\n", encoding="utf-8")

        called: list[list[str]] = []

        def _fake_exec(argv: list[str], timeout: int, env: dict[str, str]) -> dict[str, object]:
            called.append(list(argv))
            return {"ok": True, "returncode": 0, "stdout": "ok", "stderr": "-"}

        original = {
            "OUTPUT_DIR": learn_mod.OUTPUT_DIR,
            "TOOL_DIR": learn_mod.TOOL_DIR,
            "WORKING_DIR": learn_mod.WORKING_DIR,
            "POLICY_PATH": learn_mod.POLICY_PATH,
            "STATE_PATH": learn_mod.STATE_PATH,
            "PERMANENCE_AGENT_EXTERNAL_WRITE_ENABLE": os.environ.get("PERMANENCE_AGENT_EXTERNAL_WRITE_ENABLE"),
        }
        try:
            learn_mod.OUTPUT_DIR = outputs
            learn_mod.TOOL_DIR = tool
            learn_mod.WORKING_DIR = working
            learn_mod.POLICY_PATH = policy_path
            learn_mod.STATE_PATH = state_path
            os.environ["PERMANENCE_AGENT_EXTERNAL_WRITE_ENABLE"] = "0"
            with patch.object(learn_mod, "_execute_pipeline", side_effect=_fake_exec):
                rc = learn_mod.main(
                    [
                        "--action",
                        "run",
                        "--approved-by",
                        "payton",
                        "--approval-note",
                        "operator approved",
                    ]
                )
        finally:
            learn_mod.OUTPUT_DIR = original["OUTPUT_DIR"]
            learn_mod.TOOL_DIR = original["TOOL_DIR"]
            learn_mod.WORKING_DIR = original["WORKING_DIR"]
            learn_mod.POLICY_PATH = original["POLICY_PATH"]
            learn_mod.STATE_PATH = original["STATE_PATH"]
            if original["PERMANENCE_AGENT_EXTERNAL_WRITE_ENABLE"] is None:
                os.environ.pop("PERMANENCE_AGENT_EXTERNAL_WRITE_ENABLE", None)
            else:
                os.environ["PERMANENCE_AGENT_EXTERNAL_WRITE_ENABLE"] = original[
                    "PERMANENCE_AGENT_EXTERNAL_WRITE_ENABLE"
                ]

        assert rc == 0
        assert called
        joined = " ".join(" ".join(argv) for argv in called)
        assert "social-research-ingest" in joined
        assert "github-trending-ingest" in joined
        assert "world-watch" in joined
        assert "market-focus-brief" in joined
        assert state_path.exists()
        state = json.loads(state_path.read_text(encoding="utf-8"))
        runs = state.get("runs_by_day") or {}
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        assert int(runs.get(today, 0)) >= 1


if __name__ == "__main__":
    test_governed_learning_status_writes_report_and_template()
    test_governed_learning_run_requires_approval()
    test_governed_learning_run_executes_when_approved()
    print("✓ Governed learning loop tests passed")
