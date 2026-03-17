#!/usr/bin/env python3
"""Tests for core.model_router."""

import json
import os
import sys
import tempfile

os.environ.setdefault("PERMANENCE_LOG_DIR", "/tmp/permanence-os-test-logs")

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.model_router import ModelRouter
from core.model_policy import classify_task_context


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
    "PERMANENCE_HYBRID_MODE",
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


def _make_hybrid_router(tmp):
    """Create a ModelRouter in hybrid mode."""
    log_path = os.path.join(tmp, "routing.jsonl")
    for key in MODEL_ENV_KEYS:
        os.environ.pop(key, None)
    os.environ["PERMANENCE_MODEL_PROVIDER"] = "anthropic"
    os.environ["PERMANENCE_HYBRID_MODE"] = "1"
    router = ModelRouter(log_path=log_path)
    router._estimate_monthly_spend_by_provider_usd = lambda: {
        "anthropic": 0.0, "openai": 0.0, "xai": 0.0, "ollama": 0.0,
    }
    return router


# ── Hybrid Routing Tests ─────────────────────────────────────────────────

def test_hybrid_routes_routine_to_ollama():
    """Routine tasks go to Ollama (free) in hybrid mode."""
    snapshot = {key: os.environ.get(key) for key in MODEL_ENV_KEYS}
    with tempfile.TemporaryDirectory() as tmp:
        try:
            router = _make_hybrid_router(tmp)
            model = router.route("classification")
            assert "qwen" in model, f"Expected Ollama model, got {model}"
            assert router.selected_provider == "ollama"
        finally:
            _restore_env(snapshot)


def test_hybrid_routes_summarization_to_ollama():
    """Summarization (low-priority) goes to Ollama in hybrid mode."""
    snapshot = {key: os.environ.get(key) for key in MODEL_ENV_KEYS}
    with tempfile.TemporaryDirectory() as tmp:
        try:
            router = _make_hybrid_router(tmp)
            model = router.route("summarization")
            assert "qwen" in model, f"Expected Ollama model, got {model}"
            assert router.selected_provider == "ollama"
        finally:
            _restore_env(snapshot)


def test_hybrid_routes_planning_to_ollama():
    """Planning (medium-priority) goes to Ollama in hybrid mode."""
    snapshot = {key: os.environ.get(key) for key in MODEL_ENV_KEYS}
    with tempfile.TemporaryDirectory() as tmp:
        try:
            router = _make_hybrid_router(tmp)
            model = router.route("planning")
            assert "qwen" in model, f"Expected Ollama model, got {model}"
            assert router.selected_provider == "ollama"
        finally:
            _restore_env(snapshot)


def test_hybrid_routes_strategy_to_paid():
    """Strategy (opus-tier, critical) goes to paid provider in hybrid mode."""
    snapshot = {key: os.environ.get(key) for key in MODEL_ENV_KEYS}
    with tempfile.TemporaryDirectory() as tmp:
        try:
            router = _make_hybrid_router(tmp)
            model = router.route("strategy")
            assert "qwen" not in model, f"Expected paid model, got {model}"
            assert router.selected_provider != "ollama"
        finally:
            _restore_env(snapshot)


def test_hybrid_routes_canon_interpretation_to_paid():
    """Canon interpretation (critical task) goes to paid provider."""
    snapshot = {key: os.environ.get(key) for key in MODEL_ENV_KEYS}
    with tempfile.TemporaryDirectory() as tmp:
        try:
            router = _make_hybrid_router(tmp)
            model = router.route("canon_interpretation")
            assert "qwen" not in model, f"Expected paid model, got {model}"
            assert router.selected_provider != "ollama"
        finally:
            _restore_env(snapshot)


def test_hybrid_routes_finance_analysis_to_paid():
    """Finance analysis should never default to Ollama in hybrid mode."""
    snapshot = {key: os.environ.get(key) for key in MODEL_ENV_KEYS}
    with tempfile.TemporaryDirectory() as tmp:
        try:
            router = _make_hybrid_router(tmp)
            model = router.route("finance_analysis")
            assert "qwen" not in model, f"Expected paid model, got {model}"
            assert router.selected_provider != "ollama"
        finally:
            _restore_env(snapshot)


def test_hybrid_routes_research_synthesis_to_paid():
    """Research synthesis needs quality — goes to paid provider."""
    snapshot = {key: os.environ.get(key) for key in MODEL_ENV_KEYS}
    with tempfile.TemporaryDirectory() as tmp:
        try:
            router = _make_hybrid_router(tmp)
            model = router.route("research_synthesis")
            assert "qwen" not in model, f"Expected paid model, got {model}"
        finally:
            _restore_env(snapshot)


def test_finance_policy_marks_domain_high_risk_and_high_complexity():
    policy = classify_task_context(
        "portfolio_risk",
        {"portfolio_data": True, "financial_action": False},
    )
    assert policy["domain"] == "finance"
    assert policy["finance_domain"] is True
    assert policy["risk_tier"] == "high"
    assert policy["complexity_tier"] == "high"


def test_explain_route_includes_finance_domain_reason():
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
            decision = router.explain_route("finance_analysis", {"portfolio_data": True})
            reasons = decision.get("route_reasons") or []
            assert "domain:finance" in reasons
            assert "risk:high" in reasons
        finally:
            _restore_env(snapshot)


def test_hybrid_routes_execution_to_ollama():
    """Execution tasks go to Ollama — not in HYBRID_PAID_TASKS."""
    snapshot = {key: os.environ.get(key) for key in MODEL_ENV_KEYS}
    with tempfile.TemporaryDirectory() as tmp:
        try:
            router = _make_hybrid_router(tmp)
            model = router.route("execution")
            assert "qwen" in model, f"Expected Ollama model, got {model}"
            assert router.selected_provider == "ollama"
        finally:
            _restore_env(snapshot)


def test_hybrid_routes_formatting_to_ollama():
    """Formatting (lightweight) goes to Ollama."""
    snapshot = {key: os.environ.get(key) for key in MODEL_ENV_KEYS}
    with tempfile.TemporaryDirectory() as tmp:
        try:
            router = _make_hybrid_router(tmp)
            model = router.route("formatting")
            assert "qwen" in model, f"Expected Ollama model, got {model}"
            assert router.selected_provider == "ollama"
        finally:
            _restore_env(snapshot)


def test_hybrid_routes_unknown_task_to_ollama():
    """Unknown tasks default to Ollama in hybrid mode."""
    snapshot = {key: os.environ.get(key) for key in MODEL_ENV_KEYS}
    with tempfile.TemporaryDirectory() as tmp:
        try:
            router = _make_hybrid_router(tmp)
            model = router.route("random_task")
            assert "qwen" in model, f"Expected Ollama model, got {model}"
            assert router.selected_provider == "ollama"
        finally:
            _restore_env(snapshot)


def test_hybrid_mode_off_routes_to_primary():
    """Without hybrid mode, standard routing uses primary provider."""
    snapshot = {key: os.environ.get(key) for key in MODEL_ENV_KEYS}
    with tempfile.TemporaryDirectory() as tmp:
        log_path = os.path.join(tmp, "routing.jsonl")
        for key in MODEL_ENV_KEYS:
            os.environ.pop(key, None)
        os.environ["PERMANENCE_MODEL_PROVIDER"] = "anthropic"
        try:
            router = ModelRouter(log_path=log_path)
            router._estimate_monthly_spend_by_provider_usd = lambda: {
                "anthropic": 0.0, "openai": 0.0, "xai": 0.0, "ollama": 0.0,
            }
            assert not router.hybrid_mode
            model = router.route("classification")
            assert "haiku" in model  # anthropic haiku, not qwen
        finally:
            _restore_env(snapshot)


if __name__ == "__main__":
    test_route_defaults_to_sonnet_for_unknown_task()
    test_route_uses_haiku_for_classification()
    test_env_override_for_opus_model()
    test_routing_log_is_append_only()
    test_hybrid_routes_routine_to_ollama()
    test_hybrid_routes_summarization_to_ollama()
    test_hybrid_routes_planning_to_ollama()
    test_hybrid_routes_strategy_to_paid()
    test_hybrid_routes_canon_interpretation_to_paid()
    test_hybrid_routes_research_synthesis_to_paid()
    test_hybrid_routes_execution_to_ollama()
    test_hybrid_routes_formatting_to_ollama()
    test_hybrid_routes_unknown_task_to_ollama()
    test_hybrid_mode_off_routes_to_primary()
    print("✓ Model router tests passed")
