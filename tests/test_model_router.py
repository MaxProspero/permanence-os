#!/usr/bin/env python3
"""Tests for core.model_router."""

import json
import os
import sys
import tempfile

os.environ.setdefault("PERMANENCE_LOG_DIR", "/tmp/permanence-os-test-logs")

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.model_router import ModelRouter


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


def test_route_defaults_to_sonnet_for_unknown_task():
    snapshot = {key: os.environ.get(key) for key in MODEL_ENV_KEYS}
    with tempfile.TemporaryDirectory() as tmp:
        log_path = os.path.join(tmp, "routing.jsonl")
        for key in MODEL_ENV_KEYS:
            os.environ.pop(key, None)
        os.environ["PERMANENCE_MODEL_PROVIDER"] = "anthropic"
        try:
            router = ModelRouter(log_path=log_path)
            router._estimate_monthly_spend_by_provider_usd = lambda: {  # type: ignore[assignment]
                "anthropic": 0.0,
                "openai": 0.0,
                "xai": 0.0,
                "ollama": 0.0,
            }
            model = router.route("unknown-task")
            assert "sonnet" in model
        finally:
            _restore_env(snapshot)


def test_route_uses_haiku_for_classification():
    snapshot = {key: os.environ.get(key) for key in MODEL_ENV_KEYS}
    with tempfile.TemporaryDirectory() as tmp:
        log_path = os.path.join(tmp, "routing.jsonl")
        for key in MODEL_ENV_KEYS:
            os.environ.pop(key, None)
        os.environ["PERMANENCE_MODEL_PROVIDER"] = "anthropic"
        try:
            router = ModelRouter(log_path=log_path)
            router._estimate_monthly_spend_by_provider_usd = lambda: {  # type: ignore[assignment]
                "anthropic": 0.0,
                "openai": 0.0,
                "xai": 0.0,
                "ollama": 0.0,
            }
            model = router.route("classification")
            assert "haiku" in model
        finally:
            _restore_env(snapshot)


def test_env_override_for_opus_model():
    snapshot = {key: os.environ.get(key) for key in MODEL_ENV_KEYS}
    with tempfile.TemporaryDirectory() as tmp:
        log_path = os.path.join(tmp, "routing.jsonl")
        for key in MODEL_ENV_KEYS:
            os.environ.pop(key, None)
        os.environ["PERMANENCE_MODEL_OPUS"] = "claude-opus-custom"
        os.environ["PERMANENCE_MODEL_PROVIDER"] = "anthropic"
        try:
            router = ModelRouter(log_path=log_path)
            router._estimate_monthly_spend_by_provider_usd = lambda: {  # type: ignore[assignment]
                "anthropic": 0.0,
                "openai": 0.0,
                "xai": 0.0,
                "ollama": 0.0,
            }
            model = router.route("strategy")
            assert model == "claude-opus-custom"
        finally:
            _restore_env(snapshot)


def test_routing_log_is_append_only():
    snapshot = {key: os.environ.get(key) for key in MODEL_ENV_KEYS}
    with tempfile.TemporaryDirectory() as tmp:
        log_path = os.path.join(tmp, "routing.jsonl")
        for key in MODEL_ENV_KEYS:
            os.environ.pop(key, None)
        os.environ["PERMANENCE_MODEL_PROVIDER"] = "anthropic"
        try:
            router = ModelRouter(log_path=log_path)
            router._estimate_monthly_spend_by_provider_usd = lambda: {  # type: ignore[assignment]
                "anthropic": 0.0,
                "openai": 0.0,
                "xai": 0.0,
                "ollama": 0.0,
            }
            router.route("planning")
            router.route("execution")

            with open(log_path, "r") as f:
                lines = [line.strip() for line in f if line.strip()]

            assert len(lines) == 2
            first = json.loads(lines[0])
            second = json.loads(lines[1])
            assert first["task_type"] == "planning"
            assert second["task_type"] == "execution"
        finally:
            _restore_env(snapshot)


if __name__ == "__main__":
    test_route_defaults_to_sonnet_for_unknown_task()
    test_route_uses_haiku_for_classification()
    test_env_override_for_opus_model()
    test_routing_log_is_append_only()
    print("✓ Model router tests passed")
