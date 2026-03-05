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
    "PERMANENCE_MODEL_OPUS",
    "PERMANENCE_MODEL_SONNET",
    "PERMANENCE_MODEL_HAIKU",
    "PERMANENCE_DEFAULT_MODEL",
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
        os.environ.pop("PERMANENCE_MODEL_OPUS", None)
        os.environ.pop("PERMANENCE_MODEL_SONNET", None)
        os.environ.pop("PERMANENCE_MODEL_HAIKU", None)
        os.environ.pop("PERMANENCE_DEFAULT_MODEL", None)
        os.environ["PERMANENCE_MODEL_PROVIDER"] = "openai"
        with tempfile.TemporaryDirectory() as tmp:
            router = ModelRouter(log_path=str(Path(tmp) / "routing.jsonl"))
            assert router.provider == "openai"
            assert router.model_by_task.get("planning") == "gpt-4o"
            assert router.model_by_task.get("summarization") == "gpt-4o-mini"
    finally:
        _restore_env(snapshot)


def test_model_router_budget_downgrade_works_for_openai_models():
    snapshot = {key: os.environ.get(key) for key in MODEL_ENV_KEYS}
    try:
        os.environ.pop("PERMANENCE_MODEL_OPUS", None)
        os.environ.pop("PERMANENCE_MODEL_SONNET", None)
        os.environ.pop("PERMANENCE_MODEL_HAIKU", None)
        os.environ.pop("PERMANENCE_DEFAULT_MODEL", None)
        os.environ["PERMANENCE_MODEL_PROVIDER"] = "openai"
        with tempfile.TemporaryDirectory() as tmp:
            router = ModelRouter(log_path=str(Path(tmp) / "routing.jsonl"))
            router._monthly_budget_snapshot = lambda: {"budget_usd": 50.0, "spend_usd": 49.0, "ratio": 0.98}  # type: ignore[assignment]
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
        os.environ.pop("PERMANENCE_MODEL_OPUS", None)
        os.environ.pop("PERMANENCE_MODEL_SONNET", None)
        os.environ.pop("PERMANENCE_MODEL_HAIKU", None)
        os.environ.pop("PERMANENCE_DEFAULT_MODEL", None)
        os.environ["PERMANENCE_MODEL_PROVIDER"] = "xai"
        registry_mod.registry = _StubRegistry()
        with tempfile.TemporaryDirectory() as tmp:
            router = ModelRouter(log_path=str(Path(tmp) / "routing.jsonl"))
            router._monthly_budget_snapshot = lambda: {"budget_usd": 50.0, "spend_usd": 10.0, "ratio": 0.2}  # type: ignore[assignment]
            model = router.get_model("planning")
            assert model is not None
    finally:
        registry_mod.registry = original_registry
        _restore_env(snapshot)

    assert captured.get("provider") == "xai"
    assert captured.get("model_name") == "grok-3-mini"
    assert captured.get("tier") == "sonnet"


if __name__ == "__main__":
    test_model_router_uses_provider_default_map()
    test_model_router_budget_downgrade_works_for_openai_models()
    test_model_router_get_model_forwards_provider_and_model_name()
    print("✓ Model router provider tests passed")
