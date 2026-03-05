#!/usr/bin/env python3
"""Regression tests for ophtxn-production CLI forwarding."""

from __future__ import annotations

import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import cli as cli_mod  # noqa: E402


def _run_cli(argv: list[str]) -> list[str]:
    captured: dict[str, list[str]] = {}
    original_run = cli_mod._run
    original_argv = list(sys.argv)
    try:
        cli_mod._run = lambda cmd: captured.setdefault("cmd", cmd) and 0  # type: ignore[assignment]
        sys.argv = argv
        rc = cli_mod.main()
    finally:
        cli_mod._run = original_run
        sys.argv = original_argv
    assert rc == 0
    return captured.get("cmd") or []


def test_cli_ophtxn_production_ops_forwards_flags() -> None:
    cmd = _run_cli(
        [
            "cli.py",
            "ophtxn-production",
            "--action",
            "status",
            "--config",
            "/tmp/prod.json",
            "--force-template",
            "--check-api",
            "--check-wrangler",
            "--strict",
            "--min-score",
            "85",
            "--output",
            "/tmp/prod.md",
        ]
    )
    assert "ophtxn_production_ops.py" in " ".join(cmd)
    assert "--action" in cmd and "status" in cmd
    assert "--config" in cmd and "/tmp/prod.json" in cmd
    assert "--force-template" in cmd
    assert "--check-api" in cmd
    assert "--check-wrangler" in cmd
    assert "--strict" in cmd
    assert "--min-score" in cmd and "85.0" in cmd
    assert "--output" in cmd and "/tmp/prod.md" in cmd


def test_cli_ophtxn_production_ops_deploy_plan_action_forwards() -> None:
    cmd = _run_cli(["cli.py", "ophtxn-production", "--action", "deploy-plan"])
    assert "ophtxn_production_ops.py" in " ".join(cmd)
    assert "--action" in cmd and "deploy-plan" in cmd


def test_cli_ophtxn_production_ops_preflight_action_forwards() -> None:
    cmd = _run_cli(["cli.py", "ophtxn-production", "--action", "preflight", "--check-wrangler", "--strict"])
    assert "ophtxn_production_ops.py" in " ".join(cmd)
    assert "--action" in cmd and "preflight" in cmd
    assert "--check-wrangler" in cmd
    assert "--strict" in cmd


def test_cli_ophtxn_production_ops_configure_forwards_fields() -> None:
    cmd = _run_cli(
        [
            "cli.py",
            "ophtxn-production",
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
            "--annual-domain-cost",
            "14",
        ]
    )
    assert "ophtxn_production_ops.py" in " ".join(cmd)
    assert "--action" in cmd and "configure" in cmd
    assert "--domain" in cmd and "ophtxn.com" in cmd
    assert "--api-domain" in cmd and "api.ophtxn.com" in cmd
    assert "--site-url" in cmd and "https://ophtxn.com" in cmd
    assert "--api-base" in cmd and "https://api.ophtxn.com" in cmd
    assert "--monthly-hosting" in cmd and "9.0" in cmd
    assert "--annual-domain-cost" in cmd and "14.0" in cmd


def test_cli_ophtxn_production_ops_configure_forwards_no_spend() -> None:
    cmd = _run_cli(
        [
            "cli.py",
            "ophtxn-production",
            "--action",
            "configure",
            "--no-spend",
        ]
    )
    assert "ophtxn_production_ops.py" in " ".join(cmd)
    assert "--action" in cmd and "configure" in cmd
    assert "--no-spend" in cmd


if __name__ == "__main__":
    test_cli_ophtxn_production_ops_forwards_flags()
    test_cli_ophtxn_production_ops_deploy_plan_action_forwards()
    test_cli_ophtxn_production_ops_preflight_action_forwards()
    test_cli_ophtxn_production_ops_configure_forwards_fields()
    test_cli_ophtxn_production_ops_configure_forwards_no_spend()
    print("✓ CLI ophtxn-production forwarding tests passed")
