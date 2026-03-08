#!/usr/bin/env python3
"""Tests for provider-aware routing behavior."""

import os
import sys
import tempfile
from pathlib import Path

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.model_router import ModelRouter  # noqa: E402
import models.registry as registry_mod  # noqa: E402


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
]


def _restore_env(snapshot: dict[str, str | None]) -> None:
    for key, value in snapshot.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


def test_model_router_uses_provider_default_map():
    snapshot = {key: os.environ.get(key) for key in MODEL_ENV_KEYS}
    try:
        for key in MODEL_ENV_KEYS:
            os.environ.pop(key, None)
        os.environ["PERMANENCE_MODEL_PROVIDER"] = "openai"
        with tempfile.TemporaryDirectory() as tmp:
            router = ModelRouter(log_path=str(Path(tmp) / "routing.jsonl"))
            router._estimate_monthly_spend_by_provider_usd = lambda: {  # type: ignore[assignment]
                "anthropic": 0.0,
                "openai": 0.0,
                "xai": 0.0,
                "ollama": 0.0,
            }
            assert router.provider == "openai"
            assert router.model_by_task.get("planning") == "gpt-4o"
            assert router.model_by_task.get("summarization") == "gpt-4o-mini"
    finally:
        _restore_env(snapshot)


def test_model_router_budget_downgrade_works_for_openai_models():
    snapshot = {key: os.environ.get(key) for key in MODEL_ENV_KEYS}
    try:
        for key in MODEL_ENV_KEYS:
            os.environ.pop(key, None)
        os.environ["PERMANENCE_MODEL_PROVIDER"] = "openai"
        with tempfile.TemporaryDirectory() as tmp:
            router = ModelRouter(log_path=str(Path(tmp) / "routing.jsonl"))
            router._monthly_budget_snapshot = lambda: {"budget_usd": 50.0, "spend_usd": 49.0, "ratio": 0.98}  # type: ignore[assignment]
            router._estimate_monthly_spend_by_provider_usd = lambda: {  # type: ignore[assignment]
                "anthropic": 0.0,
                "openai": 0.0,
                "xai": 0.0,
                "ollama": 0.0,
            }
            model = router.route("planning")
            assert model == "gpt-4o-mini"
    finally:
        _restore_env(snapshot)


def test_model_router_get_model_forwards_provider_and_model_name():
    snapshot = {key: os.environ.get(key) for key in MODEL_ENV_KEYS}
    original_registry = registry_mod.registry
    captured: dict[str, str] = {}

    class _DummyModel:
        def generate(self, prompt: str, system: str = None):
            _ = (prompt, system)
            return None

        def is_available(self) -> bool:
            return True

    class _StubRegistry:
        def get_by_tier(self, tier: str, model_name: str = "", provider: str = ""):
            captured["tier"] = tier
            captured["model_name"] = model_name
            captured["provider"] = provider
            return _DummyModel()

    try:
        for key in MODEL_ENV_KEYS:
            os.environ.pop(key, None)
        os.environ["PERMANENCE_MODEL_PROVIDER"] = "xai"
        registry_mod.registry = _StubRegistry()
        with tempfile.TemporaryDirectory() as tmp:
            router = ModelRouter(log_path=str(Path(tmp) / "routing.jsonl"))
            router._monthly_budget_snapshot = lambda: {"budget_usd": 50.0, "spend_usd": 10.0, "ratio": 0.2}  # type: ignore[assignment]
            router._estimate_monthly_spend_by_provider_usd = lambda: {  # type: ignore[assignment]
                "anthropic": 0.0,
                "openai": 0.0,
                "xai": 0.0,
                "ollama": 0.0,
            }
            model = router.get_model("planning")
            assert model is not None
    finally:
        registry_mod.registry = original_registry
        _restore_env(snapshot)

    assert captured.get("provider") == "xai"
    assert captured.get("model_name") == "grok-3-mini"
    assert captured.get("tier") == "sonnet"


def test_model_router_provider_cap_failover_to_openai():
    snapshot = {key: os.environ.get(key) for key in MODEL_ENV_KEYS}
    try:
        os.environ["PERMANENCE_MODEL_PROVIDER"] = "anthropic"
        os.environ["PERMANENCE_MODEL_PROVIDER_FALLBACKS"] = "anthropic,openai,xai"
        os.environ["PERMANENCE_MODEL_PROVIDER_CAPS_USD"] = "anthropic=5,openai=30,xai=10"
        with tempfile.TemporaryDirectory() as tmp:
            router = ModelRouter(log_path=str(Path(tmp) / "routing.jsonl"))
            router._monthly_budget_snapshot = lambda: {"budget_usd": 50.0, "spend_usd": 10.0, "ratio": 0.2}  # type: ignore[assignment]
            router._estimate_monthly_spend_by_provider_usd = lambda: {  # type: ignore[assignment]
                "anthropic": 5.1,
                "openai": 1.0,
                "xai": 0.0,
                "ollama": 0.0,
            }
            model = router.route("planning")
            assert model == "gpt-4o"
            assert router.selected_provider == "openai"
    finally:
        _restore_env(snapshot)


def test_model_router_provider_cap_exhausted_stays_primary():
    snapshot = {key: os.environ.get(key) for key in MODEL_ENV_KEYS}
    try:
        os.environ["PERMANENCE_MODEL_PROVIDER"] = "anthropic"
        os.environ["PERMANENCE_MODEL_PROVIDER_FALLBACKS"] = "anthropic,openai,xai"
        os.environ["PERMANENCE_MODEL_PROVIDER_CAPS_USD"] = "anthropic=5,openai=2,xai=1,ollama=1"
        with tempfile.TemporaryDirectory() as tmp:
            router = ModelRouter(log_path=str(Path(tmp) / "routing.jsonl"))
            router._monthly_budget_snapshot = lambda: {"budget_usd": 50.0, "spend_usd": 20.0, "ratio": 0.5}  # type: ignore[assignment]
            router._estimate_monthly_spend_by_provider_usd = lambda: {  # type: ignore[assignment]
                "anthropic": 6.0,
                "openai": 2.5,
                "xai": 1.1,
                "ollama": 1.2,
            }
            model = router.route("planning")
            assert model == "claude-sonnet-4-6"
            assert router.selected_provider == "anthropic"
    finally:
        _restore_env(snapshot)


def test_model_router_uses_ollama_default_map():
    snapshot = {key: os.environ.get(key) for key in MODEL_ENV_KEYS}
    try:
        for key in MODEL_ENV_KEYS:
            os.environ.pop(key, None)
        os.environ["PERMANENCE_MODEL_PROVIDER"] = "ollama"
        with tempfile.TemporaryDirectory() as tmp:
            router = ModelRouter(log_path=str(Path(tmp) / "routing.jsonl"))
            router._estimate_monthly_spend_by_provider_usd = lambda: {  # type: ignore[assignment]
                "anthropic": 0.0,
                "openai": 0.0,
                "xai": 0.0,
                "ollama": 0.0,
            }
            assert router.provider == "ollama"
            assert router.model_by_task.get("planning") == "qwen3:4b"
            assert router.model_by_task.get("summarization") == "qwen2.5:3b"
    finally:
        _restore_env(snapshot)


if __name__ == "__main__":
    test_model_router_uses_provider_default_map()
    test_model_router_budget_downgrade_works_for_openai_models()
    test_model_router_get_model_forwards_provider_and_model_name()
    test_model_router_provider_cap_failover_to_openai()
    test_model_router_provider_cap_exhausted_stays_primary()
    test_model_router_uses_ollama_default_map()
    print("✓ Model router provider tests passed")
