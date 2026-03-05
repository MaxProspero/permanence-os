#!/usr/bin/env python3
"""Tests for ophtxn_production_ops deployment checks and estimates."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import scripts.ophtxn_production_ops as mod  # noqa: E402


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_production_init_and_status_generates_runtime_and_report() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        outputs = root / "outputs"
        tool = root / "tool"
        working = root / "working"
        config_path = working / "prod.json"
        runtime_path = root / "site" / "foundation" / "runtime.config.js"
        index_path = root / "site" / "foundation" / "index.html"
        dashboard_path = root / "dashboard_api.py"

        _write(
            index_path,
            "<html><body><form id=\"leadForm\"></form><script>intake_captured; cta_click;</script></body></html>",
        )
        _write(
            dashboard_path,
            "@app.route(\"/api/revenue/intake\", methods=[\"POST\"])\n"
            "@app.route(\"/api/revenue/site-event\", methods=[\"POST\"])\n",
        )

        original = {
            "BASE_DIR": mod.BASE_DIR,
            "WORKING_DIR": mod.WORKING_DIR,
            "OUTPUT_DIR": mod.OUTPUT_DIR,
            "TOOL_DIR": mod.TOOL_DIR,
            "CONFIG_PATH_DEFAULT": mod.CONFIG_PATH_DEFAULT,
            "RUNTIME_CONFIG_PATH": mod.RUNTIME_CONFIG_PATH,
            "SITE_INDEX_PATH": mod.SITE_INDEX_PATH,
        }
        try:
            mod.BASE_DIR = root
            mod.WORKING_DIR = working
            mod.OUTPUT_DIR = outputs
            mod.TOOL_DIR = tool
            mod.CONFIG_PATH_DEFAULT = config_path
            mod.RUNTIME_CONFIG_PATH = runtime_path
            mod.SITE_INDEX_PATH = index_path

            rc = mod.main(["--action", "init", "--strict", "--min-score", "60"])
        finally:
            mod.BASE_DIR = original["BASE_DIR"]
            mod.WORKING_DIR = original["WORKING_DIR"]
            mod.OUTPUT_DIR = original["OUTPUT_DIR"]
            mod.TOOL_DIR = original["TOOL_DIR"]
            mod.CONFIG_PATH_DEFAULT = original["CONFIG_PATH_DEFAULT"]
            mod.RUNTIME_CONFIG_PATH = original["RUNTIME_CONFIG_PATH"]
            mod.SITE_INDEX_PATH = original["SITE_INDEX_PATH"]

        assert rc == 0
        assert config_path.exists()
        assert runtime_path.exists()
        latest = outputs / "ophtxn_production_ops_latest.md"
        assert latest.exists()
        text = latest.read_text(encoding="utf-8")
        assert "Status" in text
        assert "Cost Estimate" in text


def test_production_estimate_uses_config_budget() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        outputs = root / "outputs"
        tool = root / "tool"
        working = root / "working"
        config_path = working / "prod.json"
        config = mod._config_template()
        config["domain"]["annual_cost_usd"] = 15.0
        config["budget"]["monthly_hosting_usd"] = 10.0
        config["budget"]["monthly_analytics_usd"] = 5.0
        config["budget"]["monthly_lead_capture_usd"] = 0.0
        config["budget"]["monthly_monitoring_usd"] = 2.0
        config["budget"]["monthly_contingency_usd"] = 3.0
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")

        original = {
            "OUTPUT_DIR": mod.OUTPUT_DIR,
            "TOOL_DIR": mod.TOOL_DIR,
            "CONFIG_PATH_DEFAULT": mod.CONFIG_PATH_DEFAULT,
            "BASE_DIR": mod.BASE_DIR,
            "RUNTIME_CONFIG_PATH": mod.RUNTIME_CONFIG_PATH,
            "SITE_INDEX_PATH": mod.SITE_INDEX_PATH,
        }
        try:
            mod.OUTPUT_DIR = outputs
            mod.TOOL_DIR = tool
            mod.CONFIG_PATH_DEFAULT = config_path
            mod.BASE_DIR = root
            mod.RUNTIME_CONFIG_PATH = root / "site" / "foundation" / "runtime.config.js"
            mod.SITE_INDEX_PATH = root / "site" / "foundation" / "index.html"
            rc = mod.main(["--action", "estimate"])
        finally:
            mod.OUTPUT_DIR = original["OUTPUT_DIR"]
            mod.TOOL_DIR = original["TOOL_DIR"]
            mod.CONFIG_PATH_DEFAULT = original["CONFIG_PATH_DEFAULT"]
            mod.BASE_DIR = original["BASE_DIR"]
            mod.RUNTIME_CONFIG_PATH = original["RUNTIME_CONFIG_PATH"]
            mod.SITE_INDEX_PATH = original["SITE_INDEX_PATH"]

        assert rc == 0
        latest = outputs / "ophtxn_production_ops_latest.md"
        assert latest.exists()
        text = latest.read_text(encoding="utf-8")
        assert "Monthly total (USD): 20.0" in text
        assert "Annual total incl. domain (USD): 255.0" in text


def test_production_configure_updates_runtime_and_budget() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        outputs = root / "outputs"
        tool = root / "tool"
        working = root / "working"
        config_path = working / "prod.json"
        runtime_path = root / "site" / "foundation" / "runtime.config.js"
        index_path = root / "site" / "foundation" / "index.html"
        dashboard_path = root / "dashboard_api.py"
        _write(index_path, "<html><body><form id=\"leadForm\"></form><script>intake_captured; cta_click;</script></body></html>")
        _write(
            dashboard_path,
            "@app.route(\"/api/revenue/intake\", methods=[\"POST\"])\n"
            "@app.route(\"/api/revenue/site-event\", methods=[\"POST\"])\n",
        )

        original = {
            "BASE_DIR": mod.BASE_DIR,
            "WORKING_DIR": mod.WORKING_DIR,
            "OUTPUT_DIR": mod.OUTPUT_DIR,
            "TOOL_DIR": mod.TOOL_DIR,
            "CONFIG_PATH_DEFAULT": mod.CONFIG_PATH_DEFAULT,
            "RUNTIME_CONFIG_PATH": mod.RUNTIME_CONFIG_PATH,
            "SITE_INDEX_PATH": mod.SITE_INDEX_PATH,
        }
        try:
            mod.BASE_DIR = root
            mod.WORKING_DIR = working
            mod.OUTPUT_DIR = outputs
            mod.TOOL_DIR = tool
            mod.CONFIG_PATH_DEFAULT = config_path
            mod.RUNTIME_CONFIG_PATH = runtime_path
            mod.SITE_INDEX_PATH = index_path
            mod.main(["--action", "init"])
            rc = mod.main(
                [
                    "--action",
                    "configure",
                    "--domain",
                    "ophtxn.com",
                    "--api-domain",
                    "api.ophtxn.com",
                    "--site-url",
                    "https://ophtxn.com",
                    "--api-base",
                    "https://api.ophtxn.com",
                    "--monthly-hosting",
                    "9",
                    "--monthly-analytics",
                    "3",
                    "--monthly-monitoring",
                    "2",
                    "--annual-domain-cost",
                    "14",
                ]
            )
        finally:
            mod.BASE_DIR = original["BASE_DIR"]
            mod.WORKING_DIR = original["WORKING_DIR"]
            mod.OUTPUT_DIR = original["OUTPUT_DIR"]
            mod.TOOL_DIR = original["TOOL_DIR"]
            mod.CONFIG_PATH_DEFAULT = original["CONFIG_PATH_DEFAULT"]
            mod.RUNTIME_CONFIG_PATH = original["RUNTIME_CONFIG_PATH"]
            mod.SITE_INDEX_PATH = original["SITE_INDEX_PATH"]

        assert rc == 0
        payload = json.loads(config_path.read_text(encoding="utf-8"))
        assert payload["domain"]["primary_domain"] == "ophtxn.com"
        assert payload["domain"]["api_domain"] == "api.ophtxn.com"
        assert float(payload["budget"]["monthly_hosting_usd"]) == 9.0
        assert float(payload["budget"]["monthly_analytics_usd"]) == 3.0
        assert float(payload["budget"]["monthly_monitoring_usd"]) == 2.0
        assert float(payload["domain"]["annual_cost_usd"]) == 14.0
        runtime_text = runtime_path.read_text(encoding="utf-8")
        assert "https://ophtxn.com" in runtime_text
        assert "https://api.ophtxn.com" in runtime_text


def test_production_configure_no_spend_zeros_budget() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        outputs = root / "outputs"
        tool = root / "tool"
        working = root / "working"
        config_path = working / "prod.json"
        runtime_path = root / "site" / "foundation" / "runtime.config.js"
        index_path = root / "site" / "foundation" / "index.html"
        dashboard_path = root / "dashboard_api.py"
        _write(index_path, "<html><body><form id=\"leadForm\"></form><script>intake_captured; cta_click;</script></body></html>")
        _write(
            dashboard_path,
            "@app.route(\"/api/revenue/intake\", methods=[\"POST\"])\n"
            "@app.route(\"/api/revenue/site-event\", methods=[\"POST\"])\n",
        )

        original = {
            "BASE_DIR": mod.BASE_DIR,
            "WORKING_DIR": mod.WORKING_DIR,
            "OUTPUT_DIR": mod.OUTPUT_DIR,
            "TOOL_DIR": mod.TOOL_DIR,
            "CONFIG_PATH_DEFAULT": mod.CONFIG_PATH_DEFAULT,
            "RUNTIME_CONFIG_PATH": mod.RUNTIME_CONFIG_PATH,
            "SITE_INDEX_PATH": mod.SITE_INDEX_PATH,
        }
        try:
            mod.BASE_DIR = root
            mod.WORKING_DIR = working
            mod.OUTPUT_DIR = outputs
            mod.TOOL_DIR = tool
            mod.CONFIG_PATH_DEFAULT = config_path
            mod.RUNTIME_CONFIG_PATH = runtime_path
            mod.SITE_INDEX_PATH = index_path
            mod.main(["--action", "init"])
            rc = mod.main(
                [
                    "--action",
                    "configure",
                    "--monthly-hosting",
                    "10",
                    "--monthly-analytics",
                    "5",
                    "--monthly-lead-capture",
                    "3",
                    "--monthly-monitoring",
                    "2",
                    "--monthly-contingency",
                    "1",
                    "--no-spend",
                ]
            )
        finally:
            mod.BASE_DIR = original["BASE_DIR"]
            mod.WORKING_DIR = original["WORKING_DIR"]
            mod.OUTPUT_DIR = original["OUTPUT_DIR"]
            mod.TOOL_DIR = original["TOOL_DIR"]
            mod.CONFIG_PATH_DEFAULT = original["CONFIG_PATH_DEFAULT"]
            mod.RUNTIME_CONFIG_PATH = original["RUNTIME_CONFIG_PATH"]
            mod.SITE_INDEX_PATH = original["SITE_INDEX_PATH"]

        assert rc == 0
        payload = json.loads(config_path.read_text(encoding="utf-8"))
        budget = payload.get("budget") or {}
        assert float(budget.get("monthly_hosting_usd")) == 0.0
        assert float(budget.get("monthly_analytics_usd")) == 0.0
        assert float(budget.get("monthly_lead_capture_usd")) == 0.0
        assert float(budget.get("monthly_monitoring_usd")) == 0.0
        assert float(budget.get("monthly_contingency_usd")) == 0.0
        assert payload.get("profile") == "no_spend"


def test_production_preflight_generates_section() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        outputs = root / "outputs"
        tool = root / "tool"
        working = root / "working"
        config_path = working / "prod.json"
        runtime_path = root / "site" / "foundation" / "runtime.config.js"
        index_path = root / "site" / "foundation" / "index.html"
        dashboard_path = root / "dashboard_api.py"
        _write(index_path, "<html><body><form id=\"leadForm\"></form><script>intake_captured; cta_click;</script></body></html>")
        _write(
            dashboard_path,
            "@app.route(\"/api/revenue/intake\", methods=[\"POST\"])\n"
            "@app.route(\"/api/revenue/site-event\", methods=[\"POST\"])\n",
        )

        original = {
            "BASE_DIR": mod.BASE_DIR,
            "WORKING_DIR": mod.WORKING_DIR,
            "OUTPUT_DIR": mod.OUTPUT_DIR,
            "TOOL_DIR": mod.TOOL_DIR,
            "CONFIG_PATH_DEFAULT": mod.CONFIG_PATH_DEFAULT,
            "RUNTIME_CONFIG_PATH": mod.RUNTIME_CONFIG_PATH,
            "SITE_INDEX_PATH": mod.SITE_INDEX_PATH,
        }
        try:
            mod.BASE_DIR = root
            mod.WORKING_DIR = working
            mod.OUTPUT_DIR = outputs
            mod.TOOL_DIR = tool
            mod.CONFIG_PATH_DEFAULT = config_path
            mod.RUNTIME_CONFIG_PATH = runtime_path
            mod.SITE_INDEX_PATH = index_path
            mod.main(["--action", "init"])
            rc = mod.main(["--action", "preflight"])
        finally:
            mod.BASE_DIR = original["BASE_DIR"]
            mod.WORKING_DIR = original["WORKING_DIR"]
            mod.OUTPUT_DIR = original["OUTPUT_DIR"]
            mod.TOOL_DIR = original["TOOL_DIR"]
            mod.CONFIG_PATH_DEFAULT = original["CONFIG_PATH_DEFAULT"]
            mod.RUNTIME_CONFIG_PATH = original["RUNTIME_CONFIG_PATH"]
            mod.SITE_INDEX_PATH = original["SITE_INDEX_PATH"]

        assert rc == 0
        latest = outputs / "ophtxn_production_ops_latest.md"
        assert latest.exists()
        text = latest.read_text(encoding="utf-8")
        assert "Preflight" in text
        assert "tool:python3" in text


def test_wrangler_status_detects_not_authenticated_message() -> None:
    class _DummyProc:
        returncode = 0
        stdout = "You are not authenticated. Please run `wrangler login`."
        stderr = ""

    original_run = mod.subprocess.run
    original_which = mod.shutil.which
    try:
        mod.subprocess.run = lambda *args, **kwargs: _DummyProc()  # type: ignore[assignment]
        mod.shutil.which = lambda name: "/usr/bin/npx" if str(name) == "npx" else original_which(name)  # type: ignore[assignment]
        payload = mod._wrangler_status()
    finally:
        mod.subprocess.run = original_run
        mod.shutil.which = original_which

    assert payload["npx_available"] is True
    assert payload["wrangler_auth"] is False
    assert "not authenticated" in str(payload["detail"]).lower()


if __name__ == "__main__":
    test_production_init_and_status_generates_runtime_and_report()
    test_production_estimate_uses_config_budget()
    test_production_configure_updates_runtime_and_budget()
    test_production_configure_no_spend_zeros_budget()
    test_production_preflight_generates_section()
    test_wrangler_status_detects_not_authenticated_message()
    print("✓ ophtxn_production_ops tests passed")
