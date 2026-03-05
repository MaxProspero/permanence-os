#!/usr/bin/env python3
"""Tests for integration readiness checks."""

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import scripts.integration_readiness as ready_mod  # noqa: E402


def test_integration_readiness_reports_blocked_when_required_missing():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        outputs = root / "outputs"
        tool = root / "tool"
        working = root / "working"
        outputs.mkdir(parents=True, exist_ok=True)
        tool.mkdir(parents=True, exist_ok=True)
        (working / "google").mkdir(parents=True, exist_ok=True)
        creds = working / "google" / "credentials.json"
        creds.write_text('{"installed": {}}\n', encoding="utf-8")

        original = {
            "OUTPUT_DIR": ready_mod.OUTPUT_DIR,
            "TOOL_DIR": ready_mod.TOOL_DIR,
            "WORKING_DIR": ready_mod.WORKING_DIR,
            "env": {k: os.environ.get(k) for k in [
                "ANTHROPIC_API_KEY",
                "PERMANENCE_GMAIL_CREDENTIALS",
                "PERMANENCE_GMAIL_TOKEN",
                "PERMANENCE_BOOKING_LINK",
                "PERMANENCE_PAYMENT_LINK",
                "PERMANENCE_REQUIRE_REVENUE_LINKS",
                "PERMANENCE_MODEL_PROVIDER",
            ]},
        }
        try:
            ready_mod.OUTPUT_DIR = outputs
            ready_mod.TOOL_DIR = tool
            ready_mod.WORKING_DIR = working

            os.environ["PERMANENCE_MODEL_PROVIDER"] = "anthropic"
            os.environ["ANTHROPIC_API_KEY"] = "sk-ant-test"
            os.environ["PERMANENCE_GMAIL_CREDENTIALS"] = str(creds)
            os.environ.pop("PERMANENCE_GMAIL_TOKEN", None)
            os.environ["PERMANENCE_REQUIRE_REVENUE_LINKS"] = "1"
            os.environ["PERMANENCE_BOOKING_LINK"] = "https://cal.example.com/foundation"
            os.environ["PERMANENCE_PAYMENT_LINK"] = "https://pay.example.com/foundation"

            rc = ready_mod.main()
        finally:
            ready_mod.OUTPUT_DIR = original["OUTPUT_DIR"]
            ready_mod.TOOL_DIR = original["TOOL_DIR"]
            ready_mod.WORKING_DIR = original["WORKING_DIR"]
            for key, value in original["env"].items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

        assert rc == 1
        latest_md = outputs / "integration_readiness_latest.md"
        assert latest_md.exists()
        content = latest_md.read_text(encoding="utf-8")
        assert "Overall status: BLOCKED" in content
        assert "PERMANENCE_GMAIL_TOKEN" in content

        payloads = sorted(tool.glob("integration_readiness_*.json"))
        assert payloads
        payload = json.loads(payloads[-1].read_text(encoding="utf-8"))
        assert payload.get("blocked") is True


def test_integration_readiness_reports_ready_when_required_present():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        outputs = root / "outputs"
        tool = root / "tool"
        working = root / "working"
        outputs.mkdir(parents=True, exist_ok=True)
        tool.mkdir(parents=True, exist_ok=True)
        (working / "google").mkdir(parents=True, exist_ok=True)
        creds = working / "google" / "credentials.json"
        token = working / "google" / "token.json"
        creds.write_text('{"installed": {}}\n', encoding="utf-8")
        token.write_text('{"access_token": "x"}\n', encoding="utf-8")

        original = {
            "OUTPUT_DIR": ready_mod.OUTPUT_DIR,
            "TOOL_DIR": ready_mod.TOOL_DIR,
            "WORKING_DIR": ready_mod.WORKING_DIR,
            "env": {k: os.environ.get(k) for k in [
                "ANTHROPIC_API_KEY",
                "PERMANENCE_GMAIL_CREDENTIALS",
                "PERMANENCE_GMAIL_TOKEN",
                "PERMANENCE_BOOKING_LINK",
                "PERMANENCE_PAYMENT_LINK",
                "PERMANENCE_REQUIRE_REVENUE_LINKS",
                "PERMANENCE_MODEL_PROVIDER",
            ]},
        }
        try:
            ready_mod.OUTPUT_DIR = outputs
            ready_mod.TOOL_DIR = tool
            ready_mod.WORKING_DIR = working

            os.environ["PERMANENCE_MODEL_PROVIDER"] = "anthropic"
            os.environ["ANTHROPIC_API_KEY"] = "sk-ant-test"
            os.environ["PERMANENCE_GMAIL_CREDENTIALS"] = str(creds)
            os.environ["PERMANENCE_GMAIL_TOKEN"] = str(token)
            os.environ["PERMANENCE_REQUIRE_REVENUE_LINKS"] = "1"
            os.environ["PERMANENCE_BOOKING_LINK"] = "https://cal.example.com/foundation"
            os.environ["PERMANENCE_PAYMENT_LINK"] = "https://pay.example.com/foundation"

            rc = ready_mod.main()
        finally:
            ready_mod.OUTPUT_DIR = original["OUTPUT_DIR"]
            ready_mod.TOOL_DIR = original["TOOL_DIR"]
            ready_mod.WORKING_DIR = original["WORKING_DIR"]
            for key, value in original["env"].items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

        assert rc == 0
        latest_md = outputs / "integration_readiness_latest.md"
        assert latest_md.exists()
        assert "Overall status: READY" in latest_md.read_text(encoding="utf-8")


def test_integration_readiness_redacts_webhook_preview():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        outputs = root / "outputs"
        tool = root / "tool"
        working = root / "working"
        outputs.mkdir(parents=True, exist_ok=True)
        tool.mkdir(parents=True, exist_ok=True)
        (working / "google").mkdir(parents=True, exist_ok=True)
        creds = working / "google" / "credentials.json"
        token = working / "google" / "token.json"
        creds.write_text('{"installed": {}}\n', encoding="utf-8")
        token.write_text('{"access_token": "x"}\n', encoding="utf-8")
        webhook = "https://discord.com/api/webhooks/123/secret-token"

        original = {
            "OUTPUT_DIR": ready_mod.OUTPUT_DIR,
            "TOOL_DIR": ready_mod.TOOL_DIR,
            "WORKING_DIR": ready_mod.WORKING_DIR,
            "env": {k: os.environ.get(k) for k in [
                "ANTHROPIC_API_KEY",
                "PERMANENCE_GMAIL_CREDENTIALS",
                "PERMANENCE_GMAIL_TOKEN",
                "PERMANENCE_DISCORD_ALERT_WEBHOOK_URL",
                "PERMANENCE_MODEL_PROVIDER",
            ]},
        }
        try:
            ready_mod.OUTPUT_DIR = outputs
            ready_mod.TOOL_DIR = tool
            ready_mod.WORKING_DIR = working

            os.environ["PERMANENCE_MODEL_PROVIDER"] = "anthropic"
            os.environ["ANTHROPIC_API_KEY"] = "sk-ant-test"
            os.environ["PERMANENCE_GMAIL_CREDENTIALS"] = str(creds)
            os.environ["PERMANENCE_GMAIL_TOKEN"] = str(token)
            os.environ["PERMANENCE_DISCORD_ALERT_WEBHOOK_URL"] = webhook

            rc = ready_mod.main()
        finally:
            ready_mod.OUTPUT_DIR = original["OUTPUT_DIR"]
            ready_mod.TOOL_DIR = original["TOOL_DIR"]
            ready_mod.WORKING_DIR = original["WORKING_DIR"]
            for key, value in original["env"].items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

        assert rc == 0
        latest_md = outputs / "integration_readiness_latest.md"
        content = latest_md.read_text(encoding="utf-8")
        assert webhook not in content
        assert "PERMANENCE_DISCORD_ALERT_WEBHOOK_URL | optional | READY | (set)" in content

        payloads = sorted(tool.glob("integration_readiness_*.json"))
        assert payloads
        payload = json.loads(payloads[-1].read_text(encoding="utf-8"))
        rows = [row for row in payload.get("checks", []) if row.get("key") == "PERMANENCE_DISCORD_ALERT_WEBHOOK_URL"]
        assert rows
        assert rows[0].get("value_preview") == "(set)"


if __name__ == "__main__":
    test_integration_readiness_reports_blocked_when_required_missing()
    test_integration_readiness_reports_ready_when_required_present()
    test_integration_readiness_redacts_webhook_preview()
    print("✓ Integration readiness tests passed")
