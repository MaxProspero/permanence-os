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


MODEL_ENV_KEYS = [
    "PERMANENCE_MODEL_PROVIDER",
    "PERMANENCE_MODEL_PROVIDER_FALLBACKS",
    "PERMANENCE_MODEL_PROVIDER_CAPS_USD",
    "PERMANENCE_MODEL_OPUS",
    "PERMANENCE_MODEL_SONNET",
    "PERMANENCE_MODEL_HAIKU",
    "PERMANENCE_DEFAULT_MODEL",
    "PERMANENCE_MODEL_BUDGET_WARNING_RATIO",
    "PERMANENCE_MODEL_BUDGET_CRITICAL_RATIO",
    "PERMANENCE_NO_SPEND_MODE",
    "PERMANENCE_LOW_COST_MODE",
<<<<<<< HEAD
    "PERMANENCE_HYBRID_MODE",
    "PERMANENCE_BUDGET_TIER",
=======
>>>>>>> origin/main
    "PERMANENCE_LLM_MONTHLY_BUDGET_USD",
]


def _restore_env(snapshot: dict[str, str | None]) -> None:
    for key, value in snapshot.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


def test_model_router_keeps_opus_when_budget_ok() -> None:
    snapshot = {key: os.environ.get(key) for key in MODEL_ENV_KEYS}
    with tempfile.TemporaryDirectory() as tmp:
        log_path = Path(tmp) / "routing.jsonl"
        for key in MODEL_ENV_KEYS:
            os.environ.pop(key, None)
        os.environ["PERMANENCE_MODEL_PROVIDER"] = "anthropic"
        try:
            router = ModelRouter(log_path=str(log_path))
            router._monthly_budget_snapshot = lambda: {"budget_usd": 50.0, "spend_usd": 10.0, "ratio": 0.2}  # type: ignore[assignment]
            router._estimate_monthly_spend_by_provider_usd = lambda: {  # type: ignore[assignment]
                "anthropic": 0.0,
                "openai": 0.0,
                "xai": 0.0,
                "ollama": 0.0,
            }
            model = router.route("strategy")
            assert "opus" in model
        finally:
            _restore_env(snapshot)


def test_model_router_downgrades_opus_to_sonnet_on_warning() -> None:
    snapshot = {key: os.environ.get(key) for key in MODEL_ENV_KEYS}
    with tempfile.TemporaryDirectory() as tmp:
        log_path = Path(tmp) / "routing.jsonl"
        for key in MODEL_ENV_KEYS:
            os.environ.pop(key, None)
        os.environ["PERMANENCE_MODEL_PROVIDER"] = "anthropic"
        try:
            router = ModelRouter(log_path=str(log_path))
            router._monthly_budget_snapshot = lambda: {"budget_usd": 50.0, "spend_usd": 42.0, "ratio": 0.84}  # type: ignore[assignment]
            router._estimate_monthly_spend_by_provider_usd = lambda: {  # type: ignore[assignment]
                "anthropic": 0.0,
                "openai": 0.0,
                "xai": 0.0,
                "ollama": 0.0,
            }
            model = router.route("strategy")
            assert "sonnet" in model

            rows = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]
            assert rows
            assert "budget_warning_downgrade_opus_to_sonnet" in str(rows[-1].get("budget_policy") or "")
            assert float(rows[-1].get("budget_ratio", 0.0)) >= 0.84
        finally:
            _restore_env(snapshot)


def test_model_router_downgrades_medium_to_haiku_on_critical() -> None:
    snapshot = {key: os.environ.get(key) for key in MODEL_ENV_KEYS}
    with tempfile.TemporaryDirectory() as tmp:
        log_path = Path(tmp) / "routing.jsonl"
        for key in MODEL_ENV_KEYS:
            os.environ.pop(key, None)
        os.environ["PERMANENCE_MODEL_PROVIDER"] = "anthropic"
        try:
            router = ModelRouter(log_path=str(log_path))
            router._monthly_budget_snapshot = lambda: {"budget_usd": 50.0, "spend_usd": 49.0, "ratio": 0.98}  # type: ignore[assignment]
            router._estimate_monthly_spend_by_provider_usd = lambda: {  # type: ignore[assignment]
                "anthropic": 0.0,
                "openai": 0.0,
                "xai": 0.0,
                "ollama": 0.0,
            }
            model = router.route("planning")
            assert "haiku" in model
        finally:
            _restore_env(snapshot)


if __name__ == "__main__":
    test_model_router_keeps_opus_when_budget_ok()
    test_model_router_downgrades_opus_to_sonnet_on_warning()
    test_model_router_downgrades_medium_to_haiku_on_critical()
    print("✓ Model router budget tests passed")
