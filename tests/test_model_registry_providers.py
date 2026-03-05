#!/usr/bin/env python3
"""Tests for multi-provider model registry behavior."""

import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from models.registry import ModelRegistry  # noqa: E402


class _StubAdapter:
    def __init__(self, tier: str, model_id: str | None = None, provider: str = ""):
        self.tier = tier
        self.model_id = model_id
        self.provider = provider


def test_registry_prefers_configured_provider():
    original_provider = os.environ.get("PERMANENCE_MODEL_PROVIDER")
    original_fallbacks = os.environ.get("PERMANENCE_MODEL_PROVIDER_FALLBACKS")
    os.environ["PERMANENCE_MODEL_PROVIDER"] = "openai"
    os.environ["PERMANENCE_MODEL_PROVIDER_FALLBACKS"] = "openai,anthropic"

    seen: list[str] = []
    registry = ModelRegistry()

    def fake_provider_class(provider: str):
        seen.append(provider)

        class _Adapter(_StubAdapter):
            def __init__(self, tier: str, model_id: str | None = None):
                super().__init__(tier=tier, model_id=model_id, provider=provider)

        return _Adapter

    original_provider_class = registry._provider_class
    try:
        registry._provider_class = fake_provider_class  # type: ignore[assignment]
        model = registry.get_by_tier("sonnet", model_name="gpt-4o")
    finally:
        registry._provider_class = original_provider_class  # type: ignore[assignment]
        if original_provider is None:
            os.environ.pop("PERMANENCE_MODEL_PROVIDER", None)
        else:
            os.environ["PERMANENCE_MODEL_PROVIDER"] = original_provider
        if original_fallbacks is None:
            os.environ.pop("PERMANENCE_MODEL_PROVIDER_FALLBACKS", None)
        else:
            os.environ["PERMANENCE_MODEL_PROVIDER_FALLBACKS"] = original_fallbacks

    assert model.provider == "openai"
    assert model.model_id == "gpt-4o"
    assert seen and seen[0] == "openai"


def test_registry_falls_back_when_primary_fails():
    original_provider = os.environ.get("PERMANENCE_MODEL_PROVIDER")
    original_fallbacks = os.environ.get("PERMANENCE_MODEL_PROVIDER_FALLBACKS")
    os.environ["PERMANENCE_MODEL_PROVIDER"] = "openai"
    os.environ["PERMANENCE_MODEL_PROVIDER_FALLBACKS"] = "openai,anthropic"

    seen: list[str] = []
    registry = ModelRegistry()

    def fake_provider_class(provider: str):
        seen.append(provider)
        if provider == "openai":
            class _FailAdapter:
                def __init__(self, tier: str, model_id: str | None = None):
                    raise RuntimeError("missing openai key")

            return _FailAdapter

        class _Adapter(_StubAdapter):
            def __init__(self, tier: str, model_id: str | None = None):
                super().__init__(tier=tier, model_id=model_id, provider=provider)

        return _Adapter

    original_provider_class = registry._provider_class
    try:
        registry._provider_class = fake_provider_class  # type: ignore[assignment]
        model = registry.get_by_tier("sonnet", model_name="gpt-4o")
    finally:
        registry._provider_class = original_provider_class  # type: ignore[assignment]
        if original_provider is None:
            os.environ.pop("PERMANENCE_MODEL_PROVIDER", None)
        else:
            os.environ["PERMANENCE_MODEL_PROVIDER"] = original_provider
        if original_fallbacks is None:
            os.environ.pop("PERMANENCE_MODEL_PROVIDER_FALLBACKS", None)
        else:
            os.environ["PERMANENCE_MODEL_PROVIDER_FALLBACKS"] = original_fallbacks

    assert model.provider == "anthropic"
    assert seen[:2] == ["openai", "anthropic"]


def test_registry_uses_model_name_provider_hint():
    original_provider = os.environ.get("PERMANENCE_MODEL_PROVIDER")
    original_fallbacks = os.environ.get("PERMANENCE_MODEL_PROVIDER_FALLBACKS")
    os.environ["PERMANENCE_MODEL_PROVIDER"] = "anthropic"
    os.environ["PERMANENCE_MODEL_PROVIDER_FALLBACKS"] = "anthropic,openai,xai"

    seen: list[str] = []
    registry = ModelRegistry()

    def fake_provider_class(provider: str):
        seen.append(provider)

        class _Adapter(_StubAdapter):
            def __init__(self, tier: str, model_id: str | None = None):
                super().__init__(tier=tier, model_id=model_id, provider=provider)

        return _Adapter

    original_provider_class = registry._provider_class
    try:
        registry._provider_class = fake_provider_class  # type: ignore[assignment]
        model = registry.get_by_tier("sonnet", model_name="grok-3-mini")
    finally:
        registry._provider_class = original_provider_class  # type: ignore[assignment]
        if original_provider is None:
            os.environ.pop("PERMANENCE_MODEL_PROVIDER", None)
        else:
            os.environ["PERMANENCE_MODEL_PROVIDER"] = original_provider
        if original_fallbacks is None:
            os.environ.pop("PERMANENCE_MODEL_PROVIDER_FALLBACKS", None)
        else:
            os.environ["PERMANENCE_MODEL_PROVIDER_FALLBACKS"] = original_fallbacks

    assert model.provider == "xai"
    assert seen and seen[0] == "xai"


def test_registry_supports_ollama_provider_alias():
    original_provider = os.environ.get("PERMANENCE_MODEL_PROVIDER")
    original_fallbacks = os.environ.get("PERMANENCE_MODEL_PROVIDER_FALLBACKS")
    os.environ["PERMANENCE_MODEL_PROVIDER"] = "local"
    os.environ["PERMANENCE_MODEL_PROVIDER_FALLBACKS"] = "ollama,anthropic,openai,xai"

    seen: list[str] = []
    registry = ModelRegistry()

    def fake_provider_class(provider: str):
        seen.append(provider)

        class _Adapter(_StubAdapter):
            def __init__(self, tier: str, model_id: str | None = None):
                super().__init__(tier=tier, model_id=model_id, provider=provider)

        return _Adapter

    original_provider_class = registry._provider_class
    try:
        registry._provider_class = fake_provider_class  # type: ignore[assignment]
        model = registry.get_by_tier("sonnet", model_name="qwen3:4b")
    finally:
        registry._provider_class = original_provider_class  # type: ignore[assignment]
        if original_provider is None:
            os.environ.pop("PERMANENCE_MODEL_PROVIDER", None)
        else:
            os.environ["PERMANENCE_MODEL_PROVIDER"] = original_provider
        if original_fallbacks is None:
            os.environ.pop("PERMANENCE_MODEL_PROVIDER_FALLBACKS", None)
        else:
            os.environ["PERMANENCE_MODEL_PROVIDER_FALLBACKS"] = original_fallbacks

    assert model.provider == "ollama"
    assert seen and seen[0] == "ollama"


if __name__ == "__main__":
    test_registry_prefers_configured_provider()
    test_registry_falls_back_when_primary_fails()
    test_registry_uses_model_name_provider_hint()
    test_registry_supports_ollama_provider_alias()
    print("✓ Model registry provider tests passed")
