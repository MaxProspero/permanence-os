#!/usr/bin/env python3
"""Tests for external connector access policy report."""

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import scripts.external_access_policy as policy_mod  # noqa: E402


def test_external_access_policy_writes_template_and_low_risk():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        outputs = root / "outputs"
        tool = root / "tool"
        working = root / "working"
        outputs.mkdir(parents=True, exist_ok=True)
        tool.mkdir(parents=True, exist_ok=True)
        working.mkdir(parents=True, exist_ok=True)

        policy_path = working / "agent_access_policy.json"

        original = {
            "OUTPUT_DIR": policy_mod.OUTPUT_DIR,
            "TOOL_DIR": policy_mod.TOOL_DIR,
            "WORKING_DIR": policy_mod.WORKING_DIR,
            "POLICY_PATH": policy_mod.POLICY_PATH,
            "env": {
                k: os.environ.get(k)
                for k in [
                    "PERMANENCE_GITHUB_READ_TOKEN",
                    "PERMANENCE_SOCIAL_READ_TOKEN",
                    "PERMANENCE_AGENT_EXTERNAL_WRITE_ENABLE",
                    "PERMANENCE_GITHUB_WRITE_TOKEN",
                    "PERMANENCE_SOCIAL_PUBLISH_TOKEN",
                    "GH_TOKEN",
                    "GITHUB_TOKEN",
                    "PERMANENCE_TELEGRAM_CHAT_ID",
                    "PERMANENCE_TELEGRAM_BOT_TOKEN",
                    "DISCORD_ALERT_WEBHOOK_URL",
                ]
            },
        }
        try:
            policy_mod.OUTPUT_DIR = outputs
            policy_mod.TOOL_DIR = tool
            policy_mod.WORKING_DIR = working
            policy_mod.POLICY_PATH = policy_path

            os.environ["PERMANENCE_GITHUB_READ_TOKEN"] = "ghr_test"
            os.environ["PERMANENCE_SOCIAL_READ_TOKEN"] = "soc_read_test"
            os.environ["PERMANENCE_AGENT_EXTERNAL_WRITE_ENABLE"] = "0"
            os.environ.pop("PERMANENCE_GITHUB_WRITE_TOKEN", None)
            os.environ.pop("PERMANENCE_SOCIAL_PUBLISH_TOKEN", None)
            os.environ.pop("GH_TOKEN", None)
            os.environ.pop("GITHUB_TOKEN", None)
            os.environ.pop("PERMANENCE_TELEGRAM_CHAT_ID", None)
            os.environ.pop("PERMANENCE_TELEGRAM_BOT_TOKEN", None)
            os.environ.pop("DISCORD_ALERT_WEBHOOK_URL", None)

            rc = policy_mod.main([])
        finally:
            policy_mod.OUTPUT_DIR = original["OUTPUT_DIR"]
            policy_mod.TOOL_DIR = original["TOOL_DIR"]
            policy_mod.WORKING_DIR = original["WORKING_DIR"]
            policy_mod.POLICY_PATH = original["POLICY_PATH"]
            for key, value in original["env"].items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

        assert rc == 0
        assert policy_path.exists()
        latest = outputs / "external_access_policy_latest.md"
        assert latest.exists()
        content = latest.read_text(encoding="utf-8")
        assert "Risk level: LOW" in content

        payload_files = sorted(tool.glob("external_access_policy_*.json"))
        assert payload_files
        payload = json.loads(payload_files[-1].read_text(encoding="utf-8"))
        assert payload.get("risk_level") == "low"


def test_external_access_policy_flags_high_risk_when_write_enabled():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        outputs = root / "outputs"
        tool = root / "tool"
        working = root / "working"
        outputs.mkdir(parents=True, exist_ok=True)
        tool.mkdir(parents=True, exist_ok=True)
        working.mkdir(parents=True, exist_ok=True)

        original = {
            "OUTPUT_DIR": policy_mod.OUTPUT_DIR,
            "TOOL_DIR": policy_mod.TOOL_DIR,
            "WORKING_DIR": policy_mod.WORKING_DIR,
            "POLICY_PATH": policy_mod.POLICY_PATH,
            "env": {
                k: os.environ.get(k)
                for k in [
                    "PERMANENCE_AGENT_EXTERNAL_WRITE_ENABLE",
                    "PERMANENCE_GITHUB_WRITE_TOKEN",
                    "PERMANENCE_SOCIAL_PUBLISH_TOKEN",
                ]
            },
        }
        try:
            policy_mod.OUTPUT_DIR = outputs
            policy_mod.TOOL_DIR = tool
            policy_mod.WORKING_DIR = working
            policy_mod.POLICY_PATH = working / "agent_access_policy.json"

            os.environ["PERMANENCE_AGENT_EXTERNAL_WRITE_ENABLE"] = "1"
            os.environ["PERMANENCE_GITHUB_WRITE_TOKEN"] = "ghw_test"
            os.environ.pop("PERMANENCE_SOCIAL_PUBLISH_TOKEN", None)

            rc = policy_mod.main(["--strict"])
        finally:
            policy_mod.OUTPUT_DIR = original["OUTPUT_DIR"]
            policy_mod.TOOL_DIR = original["TOOL_DIR"]
            policy_mod.WORKING_DIR = original["WORKING_DIR"]
            policy_mod.POLICY_PATH = original["POLICY_PATH"]
            for key, value in original["env"].items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

        assert rc == 1
        latest = outputs / "external_access_policy_latest.md"
        assert latest.exists()
        assert "Risk level: HIGH" in latest.read_text(encoding="utf-8")


if __name__ == "__main__":
    test_external_access_policy_writes_template_and_low_risk()
    test_external_access_policy_flags_high_risk_when_write_enabled()
    print("✓ External access policy tests passed")
