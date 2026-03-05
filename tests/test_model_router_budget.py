#!/usr/bin/env python3
"""Tests for budget-aware model routing."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.model_router import ModelRouter  # noqa: E402


def test_model_router_keeps_opus_when_budget_ok() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        log_path = Path(tmp) / "routing.jsonl"
        router = ModelRouter(log_path=str(log_path))
        router._monthly_budget_snapshot = lambda: {"budget_usd": 50.0, "spend_usd": 10.0, "ratio": 0.2}  # type: ignore[assignment]
        model = router.route("strategy")
        assert "opus" in model


def test_model_router_downgrades_opus_to_sonnet_on_warning() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        log_path = Path(tmp) / "routing.jsonl"
        router = ModelRouter(log_path=str(log_path))
        router._monthly_budget_snapshot = lambda: {"budget_usd": 50.0, "spend_usd": 42.0, "ratio": 0.84}  # type: ignore[assignment]
        model = router.route("strategy")
        assert "sonnet" in model

        rows = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        assert rows
        assert rows[-1].get("budget_policy") == "budget_warning_downgrade_opus_to_sonnet"
        assert float(rows[-1].get("budget_ratio", 0.0)) >= 0.84


def test_model_router_downgrades_medium_to_haiku_on_critical() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        log_path = Path(tmp) / "routing.jsonl"
        router = ModelRouter(log_path=str(log_path))
        router._monthly_budget_snapshot = lambda: {"budget_usd": 50.0, "spend_usd": 49.0, "ratio": 0.98}  # type: ignore[assignment]
        model = router.route("planning")
        assert "haiku" in model


if __name__ == "__main__":
    test_model_router_keeps_opus_when_budget_ok()
    test_model_router_downgrades_opus_to_sonnet_on_warning()
    test_model_router_downgrades_medium_to_haiku_on_critical()
    print("✓ Model router budget tests passed")
