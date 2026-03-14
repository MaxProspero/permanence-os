#!/usr/bin/env python3
"""Tests for no-spend mode, low-cost mode, budget dashboard, and tier presets."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.model_router import BUDGET_TIER_PRESETS, ModelRouter  # noqa: E402

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
    "PERMANENCE_LLM_MONTHLY_BUDGET_USD",
    "PERMANENCE_BUDGET_TIER",
]


def _restore_env(snapshot: dict[str, str | None]) -> None:
    for key, value in snapshot.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


def _mock_zero_spend(router: ModelRouter) -> None:
    router._estimate_monthly_spend_by_provider_usd = lambda: {  # type: ignore[assignment]
        "anthropic": 0.0,
        "openai": 0.0,
        "xai": 0.0,
        "ollama": 0.0,
    }


# ─── No-Spend Mode ───────────────────────────────────────────────────────────


def test_no_spend_mode_forces_ollama_for_all_tasks() -> None:
    snapshot = {key: os.environ.get(key) for key in MODEL_ENV_KEYS}
    try:
        for key in MODEL_ENV_KEYS:
            os.environ.pop(key, None)
        os.environ["PERMANENCE_MODEL_PROVIDER"] = "anthropic"
        os.environ["PERMANENCE_NO_SPEND_MODE"] = "1"
        with tempfile.TemporaryDirectory() as tmp:
            router = ModelRouter(log_path=str(Path(tmp) / "routing.jsonl"))
            _mock_zero_spend(router)
            assert router.no_spend_mode is True

            strategy = router.route("strategy")
            planning = router.route("planning")
            classification = router.route("classification")

            # All models must be ollama (qwen) models
            assert "qwen" in strategy
            assert "qwen" in planning
            assert "qwen" in classification
            assert router.selected_provider == "ollama"
    finally:
        _restore_env(snapshot)


def test_no_spend_mode_disabled_by_default() -> None:
    snapshot = {key: os.environ.get(key) for key in MODEL_ENV_KEYS}
    try:
        for key in MODEL_ENV_KEYS:
            os.environ.pop(key, None)
        os.environ["PERMANENCE_MODEL_PROVIDER"] = "anthropic"
        with tempfile.TemporaryDirectory() as tmp:
            router = ModelRouter(log_path=str(Path(tmp) / "routing.jsonl"))
            assert router.no_spend_mode is False
    finally:
        _restore_env(snapshot)


# ─── Low-Cost Mode ────────────────────────────────────────────────────────────


def test_low_cost_mode_skips_opus() -> None:
    snapshot = {key: os.environ.get(key) for key in MODEL_ENV_KEYS}
    try:
        for key in MODEL_ENV_KEYS:
            os.environ.pop(key, None)
        os.environ["PERMANENCE_MODEL_PROVIDER"] = "anthropic"
        os.environ["PERMANENCE_LOW_COST_MODE"] = "1"
        with tempfile.TemporaryDirectory() as tmp:
            router = ModelRouter(log_path=str(Path(tmp) / "routing.jsonl"))
            router._monthly_budget_snapshot = lambda: {  # type: ignore[assignment]
                "budget_usd": 10.0,
                "spend_usd": 1.0,
                "ratio": 0.1,
            }
            _mock_zero_spend(router)
            assert router.low_cost_mode is True

            # Strategy normally routes to opus, but low-cost mode caps at sonnet
            model = router.route("strategy")
            assert "opus" not in model
            assert "sonnet" in model or "haiku" in model
    finally:
        _restore_env(snapshot)


def test_low_cost_mode_haiku_tasks_stay_haiku() -> None:
    snapshot = {key: os.environ.get(key) for key in MODEL_ENV_KEYS}
    try:
        for key in MODEL_ENV_KEYS:
            os.environ.pop(key, None)
        os.environ["PERMANENCE_MODEL_PROVIDER"] = "anthropic"
        os.environ["PERMANENCE_LOW_COST_MODE"] = "1"
        with tempfile.TemporaryDirectory() as tmp:
            router = ModelRouter(log_path=str(Path(tmp) / "routing.jsonl"))
            router._monthly_budget_snapshot = lambda: {  # type: ignore[assignment]
                "budget_usd": 10.0,
                "spend_usd": 1.0,
                "ratio": 0.1,
            }
            _mock_zero_spend(router)
            model = router.route("classification")
            assert "haiku" in model
    finally:
        _restore_env(snapshot)


# ─── Budget Dashboard ─────────────────────────────────────────────────────────


def test_budget_dashboard_returns_complete_state() -> None:
    snapshot = {key: os.environ.get(key) for key in MODEL_ENV_KEYS}
    try:
        for key in MODEL_ENV_KEYS:
            os.environ.pop(key, None)
        os.environ["PERMANENCE_MODEL_PROVIDER"] = "anthropic"
        os.environ["PERMANENCE_LLM_MONTHLY_BUDGET_USD"] = "50"
        with tempfile.TemporaryDirectory() as tmp:
            router = ModelRouter(log_path=str(Path(tmp) / "routing.jsonl"))
            _mock_zero_spend(router)
            dashboard = router.get_budget_dashboard()

            assert "budget_usd" in dashboard
            assert "spend_usd" in dashboard
            assert "ratio" in dashboard
            assert "remaining_usd" in dashboard
            assert "tier" in dashboard
            assert "provider" in dashboard
            assert "no_spend_mode" in dashboard
            assert "low_cost_mode" in dashboard
            assert "spend_by_provider" in dashboard
            assert "provider_budget" in dashboard
            assert "warnings" in dashboard
            assert isinstance(dashboard["warnings"], list)

            assert dashboard["budget_usd"] == 50.0
            assert dashboard["spend_usd"] == 0.0
            assert dashboard["remaining_usd"] == 50.0
            assert dashboard["no_spend_mode"] is False
            assert dashboard["low_cost_mode"] is False
    finally:
        _restore_env(snapshot)


def test_budget_dashboard_warns_on_high_spend() -> None:
    snapshot = {key: os.environ.get(key) for key in MODEL_ENV_KEYS}
    try:
        for key in MODEL_ENV_KEYS:
            os.environ.pop(key, None)
        os.environ["PERMANENCE_MODEL_PROVIDER"] = "anthropic"
        with tempfile.TemporaryDirectory() as tmp:
            router = ModelRouter(log_path=str(Path(tmp) / "routing.jsonl"))
            router._monthly_budget_snapshot = lambda: {  # type: ignore[assignment]
                "budget_usd": 50.0,
                "spend_usd": 48.0,
                "ratio": 0.96,
            }
            _mock_zero_spend(router)
            dashboard = router.get_budget_dashboard()
            assert len(dashboard["warnings"]) > 0
            assert "critical" in dashboard["warnings"][0].lower()
    finally:
        _restore_env(snapshot)


def test_budget_dashboard_detects_no_spend_tier() -> None:
    snapshot = {key: os.environ.get(key) for key in MODEL_ENV_KEYS}
    try:
        for key in MODEL_ENV_KEYS:
            os.environ.pop(key, None)
        os.environ["PERMANENCE_MODEL_PROVIDER"] = "ollama"
        os.environ["PERMANENCE_NO_SPEND_MODE"] = "1"
        with tempfile.TemporaryDirectory() as tmp:
            router = ModelRouter(log_path=str(Path(tmp) / "routing.jsonl"))
            _mock_zero_spend(router)
            dashboard = router.get_budget_dashboard()
            assert dashboard["tier"] == "free"
            assert dashboard["no_spend_mode"] is True
    finally:
        _restore_env(snapshot)


# ─── Tier Presets ─────────────────────────────────────────────────────────────


def test_tier_presets_contain_required_keys() -> None:
    presets = ModelRouter.get_tier_presets()
    assert "free" in presets
    assert "light" in presets
    assert "standard" in presets
    assert "full" in presets
    for tier_name, preset in presets.items():
        assert "description" in preset
        assert "provider" in preset
        assert "budget_usd" in preset


def test_free_tier_has_zero_budget() -> None:
    assert BUDGET_TIER_PRESETS["free"]["budget_usd"] == 0.0
    assert BUDGET_TIER_PRESETS["free"]["no_spend"] is True


def test_full_tier_has_max_budget() -> None:
    assert BUDGET_TIER_PRESETS["full"]["budget_usd"] == 50.0
    assert BUDGET_TIER_PRESETS["full"]["no_spend"] is False


if __name__ == "__main__":
    test_no_spend_mode_forces_ollama_for_all_tasks()
    test_no_spend_mode_disabled_by_default()
    test_low_cost_mode_skips_opus()
    test_low_cost_mode_haiku_tasks_stay_haiku()
    test_budget_dashboard_returns_complete_state()
    test_budget_dashboard_warns_on_high_spend()
    test_budget_dashboard_detects_no_spend_tier()
    test_tier_presets_contain_required_keys()
    test_free_tier_has_zero_budget()
    test_full_tier_has_max_budget()
    print("✓ Model router modes tests passed")
