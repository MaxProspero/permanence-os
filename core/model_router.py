#!/usr/bin/env python3
"""
Model routing layer for Permanence OS.

This module centralizes task->model routing and optional adapter retrieval.
Routing decisions are logged append-only for auditability.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from core.model_capabilities import DEFAULT_MODEL_CAPABILITIES
from core.model_policy import classify_task_context

PROVIDERS = ("anthropic", "openai", "xai", "openclaw", "ollama")

BUDGET_TIER_PRESETS: Dict[str, Dict[str, Any]] = {
    "free": {
        "description": "Local models only — zero cost",
        "provider": "ollama",
        "fallbacks": "ollama",
        "budget_usd": 0.0,
        "provider_caps": "anthropic=0,openai=0,xai=0,ollama=0",
        "no_spend": True,
    },
    "light": {
        "description": "Haiku + local — minimal cost",
        "provider": "anthropic",
        "fallbacks": "anthropic,ollama",
        "budget_usd": 5.0,
        "provider_caps": "anthropic=5,openai=0,xai=0,ollama=0",
        "no_spend": False,
    },
    "standard": {
        "description": "Sonnet + Haiku + local — balanced",
        "provider": "anthropic",
        "fallbacks": "anthropic,openai,ollama",
        "budget_usd": 25.0,
        "provider_caps": "anthropic=15,openai=8,xai=2,ollama=0",
        "no_spend": False,
    },
    "full": {
        "description": "Opus + Sonnet + Haiku + local — full power",
        "provider": "anthropic",
        "fallbacks": "anthropic,openai,xai,ollama",
        "budget_usd": 50.0,
        "provider_caps": "anthropic=30,openai=15,xai=5,ollama=0",
        "no_spend": False,
    },
}

TASKS_OPUS = (
    "canon_interpretation",
    "strategy",
    "code_generation",
    "adversarial_review",
    "deep_reflection",
    "finance_analysis",
    "portfolio_risk",
    "valuation",
)
TASKS_SONNET = (
    "research_synthesis",
    "planning",
    "review",
    "execution",
    "conciliation",
    "social_drafting",
    "financial_review",
    "market_monitoring",
)
TASKS_HAIKU = ("classification", "summarization", "tagging", "formatting")

# ── AI Paper Insights (v0.4) ────────────────────────────────────────────
# ParamMem: Temperature-controlled reflection for agent self-improvement.
# Higher temperature for brainstorming/reflection tasks, lower for execution.
DEFAULT_REFLECTION_TEMPERATURE = float(os.getenv("PERMANENCE_REFLECTION_TEMP", "0.7"))
DEFAULT_EXECUTION_TEMPERATURE = float(os.getenv("PERMANENCE_EXECUTION_TEMP", "0.3"))

# Theory of Mind: ToM reasoning only for strong models.
# Weak/local models hallucinate social reasoning — strip ToM prompts automatically.
TOM_CAPABLE_MODELS = {
    "claude-opus-4-6", "claude-sonnet-4-6",
    "gpt-4.1", "gpt-4o",
    "grok-3-latest",
}
# Tasks that benefit from Theory of Mind reasoning
TOM_TASKS = ("conciliation", "social_drafting", "strategy")

DEFAULT_MODEL_BY_TASK_BY_PROVIDER: Dict[str, Dict[str, str]] = {
    "anthropic": {
        "canon_interpretation": "claude-opus-4-6",
        "strategy": "claude-opus-4-6",
        "code_generation": "claude-opus-4-6",
        "adversarial_review": "claude-opus-4-6",
        "finance_analysis": "claude-opus-4-6",
        "portfolio_risk": "claude-opus-4-6",
        "valuation": "claude-opus-4-6",
        "research_synthesis": "claude-sonnet-4-6",
        "planning": "claude-sonnet-4-6",
        "review": "claude-sonnet-4-6",
        "execution": "claude-sonnet-4-6",
        "conciliation": "claude-sonnet-4-6",
        "financial_review": "claude-sonnet-4-6",
        "market_monitoring": "claude-sonnet-4-6",
        "classification": "claude-haiku-4-5-20251001",
        "summarization": "claude-haiku-4-5-20251001",
        "tagging": "claude-haiku-4-5-20251001",
        "formatting": "claude-haiku-4-5-20251001",
        "default": "claude-sonnet-4-6",
    },
    "openai": {
        "canon_interpretation": "gpt-4.1",
        "strategy": "gpt-4.1",
        "code_generation": "gpt-4.1",
        "adversarial_review": "gpt-4.1",
        "finance_analysis": "gpt-4.1",
        "portfolio_risk": "gpt-4.1",
        "valuation": "gpt-4.1",
        "research_synthesis": "gpt-4o",
        "planning": "gpt-4o",
        "review": "gpt-4o",
        "execution": "gpt-4o",
        "conciliation": "gpt-4o",
        "financial_review": "gpt-4o",
        "market_monitoring": "gpt-4o",
        "classification": "gpt-4o-mini",
        "summarization": "gpt-4o-mini",
        "tagging": "gpt-4o-mini",
        "formatting": "gpt-4o-mini",
        "default": "gpt-4o",
    },
    "xai": {
        "canon_interpretation": "grok-3-latest",
        "strategy": "grok-3-latest",
        "code_generation": "grok-3-latest",
        "adversarial_review": "grok-3-latest",
        "finance_analysis": "grok-3-latest",
        "portfolio_risk": "grok-3-latest",
        "valuation": "grok-3-latest",
        "research_synthesis": "grok-3-mini",
        "planning": "grok-3-mini",
        "review": "grok-3-mini",
        "execution": "grok-3-mini",
        "conciliation": "grok-3-mini",
        "financial_review": "grok-3-mini",
        "market_monitoring": "grok-3-mini",
        "classification": "grok-2-mini",
        "summarization": "grok-2-mini",
        "tagging": "grok-2-mini",
        "formatting": "grok-2-mini",
        "default": "grok-3-mini",
    },
    "openclaw": {
        "canon_interpretation": "openclaw-opus",
        "strategy": "openclaw-opus",
        "code_generation": "openclaw-opus",
        "adversarial_review": "openclaw-opus",
        "finance_analysis": "openclaw-opus",
        "portfolio_risk": "openclaw-opus",
        "valuation": "openclaw-opus",
        "research_synthesis": "openclaw-sonnet",
        "planning": "openclaw-sonnet",
        "review": "openclaw-sonnet",
        "execution": "openclaw-sonnet",
        "conciliation": "openclaw-sonnet",
        "financial_review": "openclaw-sonnet",
        "market_monitoring": "openclaw-sonnet",
        "classification": "openclaw-haiku",
        "summarization": "openclaw-haiku",
        "tagging": "openclaw-haiku",
        "formatting": "openclaw-haiku",
        "default": "openclaw-sonnet",
    },
    "ollama": {
        "canon_interpretation": "qwen2.5:7b",
        "strategy": "qwen2.5:7b",
        "code_generation": "qwen2.5:7b",
        "adversarial_review": "qwen2.5:7b",
        "finance_analysis": "qwen2.5:7b",
        "portfolio_risk": "qwen2.5:7b",
        "valuation": "qwen2.5:7b",
        "research_synthesis": "qwen2.5:7b",
        "planning": "qwen2.5:7b",
        "review": "qwen2.5:7b",
        "execution": "qwen2.5:7b",
        "conciliation": "qwen2.5:7b",
        "social_drafting": "qwen2.5:7b",
        "financial_review": "qwen2.5:7b",
        "market_monitoring": "qwen2.5:7b",
        "deep_reflection": "qwen2.5:7b",
        "classification": "qwen2.5:3b",
        "summarization": "qwen2.5:3b",
        "tagging": "qwen2.5:3b",
        "formatting": "qwen2.5:3b",
        "routine": "qwen2.5:3b",
        "default": "qwen2.5:7b",
    },
}
DEFAULT_MODEL_BY_TASK: Dict[str, str] = DEFAULT_MODEL_BY_TASK_BY_PROVIDER["anthropic"]

DEFAULT_LLM_MONTHLY_BUDGET_USD = 50.0
DEFAULT_BUDGET_WARNING_RATIO = 0.75
DEFAULT_BUDGET_CRITICAL_RATIO = 0.90
DEFAULT_WORKING_DIR = Path("memory") / "working"
DEFAULT_COST_PLAN_PATH = DEFAULT_WORKING_DIR / "api_cost_plan.json"
DEFAULT_MODEL_CALL_LOG = Path("logs") / "model_calls.jsonl"
DEFAULT_MODEL_PRICING_PER_1M: Dict[str, Dict[str, float]] = {
    "claude-opus-4-6": {"input": 15.0, "output": 75.0},
    "claude-sonnet-4-6": {"input": 3.0, "output": 15.0},
    "claude-haiku-4-5-20251001": {"input": 0.8, "output": 4.0},
    "gpt-4.1": {"input": 2.0, "output": 8.0},
    "gpt-4o": {"input": 5.0, "output": 15.0},
    "gpt-4o-mini": {"input": 0.15, "output": 0.6},
    "grok-3-latest": {"input": 5.0, "output": 15.0},
    "grok-3-mini": {"input": 1.5, "output": 4.5},
    "grok-2-mini": {"input": 0.5, "output": 1.5},
    "qwen3:8b": {"input": 0.0, "output": 0.0},
    "qwen3:4b": {"input": 0.0, "output": 0.0},
    "qwen2.5:7b": {"input": 0.0, "output": 0.0},
    "qwen2.5:3b": {"input": 0.0, "output": 0.0},
}


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return int(default)


def _bool_flag(name: str) -> bool:
    value = str(os.getenv(name, "")).strip().lower()
    return value in {"1", "true", "yes", "on"}


def _provider_from_model(model_name: str) -> str:
    token = str(model_name or "").strip().lower()
    if not token:
        return ""
    if token.startswith("claude") or "anthropic" in token:
        return "anthropic"
    if token.startswith("grok") or token.startswith("xai"):
        return "xai"
    if token.startswith("openclaw") or token.startswith("claw"):
        return "openclaw"
    if token.startswith("gpt") or token.startswith("o1") or token.startswith("o3") or token.startswith("o4"):
        return "openai"
    if token.startswith("qwen") or token.startswith("llama") or token.startswith("gemma") or "ollama" in token:
        return "ollama"
    return ""


class ModelRouter:
    """
    Canon-compliant model routing with append-only decision logging.
    """

    def __init__(self, log_path: Optional[str] = None):
        self.log_path = Path(log_path or os.getenv("PERMANENCE_MODEL_ROUTING_LOG", "logs/model_routing.jsonl"))
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.provider = self._normalize_provider(os.getenv("PERMANENCE_MODEL_PROVIDER", "anthropic"))
        self.provider_fallbacks = self._provider_fallbacks()
        self.model_by_task = self._build_model_map()
        self.tier_model_index = self._build_tier_model_index()
        self.selected_provider = self.provider
        self.cost_plan_path = Path(
            os.getenv("PERMANENCE_COST_RECOVERY_PLAN_PATH", str(DEFAULT_COST_PLAN_PATH))
        )
        self.model_call_log_path = Path(
            os.getenv("PERMANENCE_MODEL_CALL_LOG_PATH", str(DEFAULT_MODEL_CALL_LOG))
        )
        self.budget_warning_ratio = max(
            0.0,
            min(
                1.0,
                _safe_float(
                    os.getenv("PERMANENCE_MODEL_BUDGET_WARNING_RATIO", DEFAULT_BUDGET_WARNING_RATIO),
                    DEFAULT_BUDGET_WARNING_RATIO,
                ),
            ),
        )
        self.budget_critical_ratio = max(
            self.budget_warning_ratio,
            min(
                1.0,
                _safe_float(
                    os.getenv("PERMANENCE_MODEL_BUDGET_CRITICAL_RATIO", DEFAULT_BUDGET_CRITICAL_RATIO),
                    DEFAULT_BUDGET_CRITICAL_RATIO,
                ),
            ),
        )
        self.no_spend_mode = _bool_flag("PERMANENCE_NO_SPEND_MODE")
        self.low_cost_mode = _bool_flag("PERMANENCE_LOW_COST_MODE")
        self.hybrid_mode = _bool_flag("PERMANENCE_HYBRID_MODE")
        self.budget_tier = str(os.getenv("PERMANENCE_BUDGET_TIER", "")).strip().lower() or ""

    @staticmethod
    def _normalize_provider(value: str) -> str:
        token = str(value or "").strip().lower()
        if token in {"claude", "anthropic"}:
            return "anthropic"
        if token in {"openai", "gpt"}:
            return "openai"
        if token in {"xai", "grok"}:
            return "xai"
        if token in {"openclaw", "open_claw", "claw"}:
            return "openclaw"
        if token in {"ollama", "local", "qwen"}:
            return "ollama"
        return "anthropic"

    def _provider_fallbacks(self) -> list[str]:
        raw = str(os.getenv("PERMANENCE_MODEL_PROVIDER_FALLBACKS", "anthropic,openai,xai,openclaw,ollama"))
        ordered: list[str] = []
        primary = self._normalize_provider(self.provider)
        if primary in PROVIDERS:
            ordered.append(primary)
        for token in raw.split(","):
            candidate = self._normalize_provider(token)
            if candidate in PROVIDERS and candidate not in ordered:
                ordered.append(candidate)
        for candidate in PROVIDERS:
            if candidate not in ordered:
                ordered.append(candidate)
        return ordered

    @staticmethod
    def _task_default_tier(task_type: str) -> str:
        key = str(task_type or "").strip().lower()
        if key in TASKS_OPUS:
            return "opus"
        if key in TASKS_HAIKU:
            return "haiku"
        return "sonnet"

    def _build_model_map(self) -> Dict[str, str]:
        defaults = DEFAULT_MODEL_BY_TASK_BY_PROVIDER.get(self.provider, DEFAULT_MODEL_BY_TASK_BY_PROVIDER["anthropic"])
        model_map = dict(defaults)
        opus = os.getenv("PERMANENCE_MODEL_OPUS")
        sonnet = os.getenv("PERMANENCE_MODEL_SONNET")
        haiku = os.getenv("PERMANENCE_MODEL_HAIKU")
        default_model = os.getenv("PERMANENCE_DEFAULT_MODEL")

        if opus:
            for key in TASKS_OPUS:
                model_map[key] = opus
        if sonnet:
            for key in TASKS_SONNET:
                model_map[key] = sonnet
        if haiku:
            for key in TASKS_HAIKU:
                model_map[key] = haiku
        if default_model:
            model_map["default"] = default_model

        return model_map

    def _build_model_map_for_provider(self, provider: str) -> Dict[str, str]:
        normalized_provider = self._normalize_provider(provider)
        defaults = DEFAULT_MODEL_BY_TASK_BY_PROVIDER.get(
            normalized_provider, DEFAULT_MODEL_BY_TASK_BY_PROVIDER["anthropic"]
        )
        model_map = dict(defaults)
        provider_token = normalized_provider.upper()
        opus = os.getenv(f"PERMANENCE_{provider_token}_MODEL_OPUS")
        sonnet = os.getenv(f"PERMANENCE_{provider_token}_MODEL_SONNET")
        haiku = os.getenv(f"PERMANENCE_{provider_token}_MODEL_HAIKU")
        default_model = os.getenv(f"PERMANENCE_{provider_token}_DEFAULT_MODEL")
        if opus:
            for key in TASKS_OPUS:
                model_map[key] = opus
        if sonnet:
            for key in TASKS_SONNET:
                model_map[key] = sonnet
        if haiku:
            for key in TASKS_HAIKU:
                model_map[key] = haiku
        if default_model:
            model_map["default"] = default_model

        if normalized_provider == self.provider:
            # Honor generic overrides for the active provider.
            generic_opus = os.getenv("PERMANENCE_MODEL_OPUS")
            generic_sonnet = os.getenv("PERMANENCE_MODEL_SONNET")
            generic_haiku = os.getenv("PERMANENCE_MODEL_HAIKU")
            generic_default = os.getenv("PERMANENCE_DEFAULT_MODEL")
            if generic_opus:
                for key in TASKS_OPUS:
                    model_map[key] = generic_opus
            if generic_sonnet:
                for key in TASKS_SONNET:
                    model_map[key] = generic_sonnet
            if generic_haiku:
                for key in TASKS_HAIKU:
                    model_map[key] = generic_haiku
            if generic_default:
                model_map["default"] = generic_default

        return model_map

    def _build_tier_model_index(self) -> Dict[str, set[str]]:
        index: Dict[str, set[str]] = {"opus": set(), "sonnet": set(), "haiku": set()}
        for task_type, model_name in self.model_by_task.items():
            tier = self._task_default_tier(task_type)
            token = str(model_name or "").strip().lower()
            if token:
                index[tier].add(token)
        return index

    def _model_for_tier(self, tier: str, model_map: Optional[Dict[str, str]] = None) -> str:
        normalized = str(tier or "sonnet").strip().lower() or "sonnet"
        source_model_map = model_map or self.model_by_task
        defaults = DEFAULT_MODEL_BY_TASK_BY_PROVIDER.get(self.provider, DEFAULT_MODEL_BY_TASK_BY_PROVIDER["anthropic"])
        if normalized == "opus":
            return source_model_map.get("strategy", defaults["strategy"])
        if normalized == "haiku":
            return source_model_map.get("summarization", defaults["summarization"])
        return source_model_map.get("execution", defaults["execution"])

    def _load_cost_plan(self) -> Dict[str, Any]:
        if not self.cost_plan_path.exists():
            return {}
        try:
            payload = json.loads(self.cost_plan_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return payload if isinstance(payload, dict) else {}

    def _model_pricing(self) -> Dict[str, Dict[str, float]]:
        pricing = dict(DEFAULT_MODEL_PRICING_PER_1M)
        for model_name in tuple(pricing.keys()):
            env_key_base = model_name.upper().replace("-", "_")
            in_key = f"PERMANENCE_PRICE_{env_key_base}_INPUT_PER_1M_USD"
            out_key = f"PERMANENCE_PRICE_{env_key_base}_OUTPUT_PER_1M_USD"
            in_price = _safe_float(os.getenv(in_key), pricing[model_name]["input"])
            out_price = _safe_float(os.getenv(out_key), pricing[model_name]["output"])
            pricing[model_name] = {"input": max(0.0, in_price), "output": max(0.0, out_price)}
        return pricing

    def _estimate_monthly_spend_usd(self) -> float:
        path = self.model_call_log_path
        if not path.exists():
            return 0.0
        pricing = self._model_pricing()
        now = datetime.now(timezone.utc)
        total = 0.0
        try:
            rows = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            return 0.0
        for raw in rows[-8000:]:
            token = raw.strip()
            if not token:
                continue
            try:
                row = json.loads(token)
            except json.JSONDecodeError:
                continue
            if not isinstance(row, dict):
                continue
            stamp = str(row.get("timestamp") or "").strip()
            if not stamp:
                continue
            try:
                dt = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
            except ValueError:
                continue
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            if dt.year != now.year or dt.month != now.month:
                continue
            model = str(row.get("model") or "").strip()
            if not model:
                continue
            rates = pricing.get(model)
            if rates is None:
                tier = self._tier_for_model(model_name=model, task_type="")
                fallback = self._model_for_tier(tier)
                rates = pricing.get(fallback, {"input": 0.0, "output": 0.0})
            in_tokens = max(0, _safe_int(row.get("input_tokens"), 0))
            out_tokens = max(0, _safe_int(row.get("output_tokens"), 0))
            total += (in_tokens / 1_000_000.0) * float(rates.get("input", 0.0))
            total += (out_tokens / 1_000_000.0) * float(rates.get("output", 0.0))
        return round(total, 6)

    def _estimate_monthly_spend_by_provider_usd(self) -> Dict[str, float]:
        path = self.model_call_log_path
        totals: Dict[str, float] = {provider: 0.0 for provider in PROVIDERS}
        if not path.exists():
            return totals
        pricing = self._model_pricing()
        now = datetime.now(timezone.utc)
        try:
            rows = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            return totals
        for raw in rows[-8000:]:
            token = raw.strip()
            if not token:
                continue
            try:
                row = json.loads(token)
            except json.JSONDecodeError:
                continue
            if not isinstance(row, dict):
                continue
            stamp = str(row.get("timestamp") or "").strip()
            if not stamp:
                continue
            try:
                dt = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
            except ValueError:
                continue
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            if dt.year != now.year or dt.month != now.month:
                continue
            model = str(row.get("model") or "").strip()
            if not model:
                continue
            provider_raw = str(row.get("provider") or "").strip()
            provider = self._normalize_provider(provider_raw) if provider_raw else _provider_from_model(model)
            if provider not in totals:
                provider = self.provider
            rates = pricing.get(model)
            if rates is None:
                tier = self._tier_for_model(model_name=model, task_type="")
                fallback_model_map = self._build_model_map_for_provider(provider)
                fallback = self._model_for_tier(tier=tier, model_map=fallback_model_map)
                rates = pricing.get(fallback, {"input": 0.0, "output": 0.0})
            in_tokens = max(0, _safe_int(row.get("input_tokens"), 0))
            out_tokens = max(0, _safe_int(row.get("output_tokens"), 0))
            spend = (in_tokens / 1_000_000.0) * float(rates.get("input", 0.0))
            spend += (out_tokens / 1_000_000.0) * float(rates.get("output", 0.0))
            totals[provider] = float(totals.get(provider, 0.0)) + spend
        return {key: round(value, 6) for key, value in totals.items()}

    @staticmethod
    def _parse_provider_caps(raw: str) -> Dict[str, float]:
        out: Dict[str, float] = {}
        token = str(raw or "").strip()
        if not token:
            return out
        if token.startswith("{"):
            try:
                payload = json.loads(token)
            except json.JSONDecodeError:
                payload = {}
            if isinstance(payload, dict):
                for key, value in payload.items():
                    provider = str(key or "").strip().lower()
                    if provider in PROVIDERS:
                        out[provider] = max(0.0, _safe_float(value, 0.0))
                return out
        for row in token.split(","):
            if "=" not in row:
                continue
            key, value = row.split("=", 1)
            provider = str(key or "").strip().lower()
            if provider not in PROVIDERS:
                continue
            out[provider] = max(0.0, _safe_float(value, 0.0))
        return out

    def _provider_budget_caps(self, total_budget: float, cost_plan: Dict[str, Any]) -> Dict[str, float]:
        caps = {provider: float(total_budget) for provider in PROVIDERS}
        plan_caps = cost_plan.get("llm_provider_caps_usd")
        if isinstance(plan_caps, dict):
            for provider, value in plan_caps.items():
                key = self._normalize_provider(str(provider or ""))
                if key in caps:
                    caps[key] = max(0.0, _safe_float(value, total_budget))
        env_caps = self._parse_provider_caps(os.getenv("PERMANENCE_MODEL_PROVIDER_CAPS_USD", ""))
        for provider, value in env_caps.items():
            caps[provider] = max(0.0, float(value))
        return caps

    def _provider_budget_snapshot(self, budget_snapshot: Dict[str, float]) -> Dict[str, Dict[str, float]]:
        total_budget = max(1.0, float(budget_snapshot.get("budget_usd", DEFAULT_LLM_MONTHLY_BUDGET_USD)))
        cost_plan = self._load_cost_plan()
        caps = self._provider_budget_caps(total_budget=total_budget, cost_plan=cost_plan)
        spends = self._estimate_monthly_spend_by_provider_usd()
        out: Dict[str, Dict[str, float]] = {}
        for provider in PROVIDERS:
            cap = max(0.0, float(caps.get(provider, total_budget)))
            spend = max(0.0, float(spends.get(provider, 0.0)))
            ratio = 1.0 if cap <= 0.0 and spend > 0.0 else (spend / cap if cap > 0.0 else 0.0)
            out[provider] = {
                "cap_usd": round(cap, 4),
                "spend_usd": round(spend, 4),
                "ratio": round(ratio, 6),
                "capped": bool(cap > 0.0),
            }
        return out

    def _provider_for_task(
        self,
        task_type: str,
        budget_snapshot: Dict[str, float],
    ) -> tuple[str, str]:
        provider_budget = self._provider_budget_snapshot(budget_snapshot)
        self._last_provider_budget_snapshot = provider_budget
        preferred = self.provider if self.provider in PROVIDERS else "anthropic"
        preferred_row = provider_budget.get(preferred, {"ratio": 0.0})
        preferred_ratio = float(preferred_row.get("ratio", 0.0))
        preferred_capped = bool(preferred_row.get("capped"))

        if preferred_capped and preferred_ratio >= 1.0:
            for candidate in self.provider_fallbacks:
                row = provider_budget.get(candidate, {"ratio": 0.0, "capped": False})
                ratio = float(row.get("ratio", 0.0))
                capped = bool(row.get("capped"))
                if candidate == preferred:
                    continue
                if (not capped) or ratio < 1.0:
                    return candidate, f"provider_cap_failover_{preferred}_to_{candidate}"
            return preferred, f"provider_cap_exhausted_{preferred}"

        if preferred_ratio >= self.budget_critical_ratio:
            for candidate in self.provider_fallbacks:
                if candidate == preferred:
                    continue
                row = provider_budget.get(candidate, {"ratio": 0.0})
                ratio = float(row.get("ratio", 0.0))
                if ratio < preferred_ratio and ratio < self.budget_critical_ratio:
                    return candidate, f"provider_critical_failover_{preferred}_to_{candidate}"

        return preferred, "provider_ok"

    def _monthly_budget_snapshot(self) -> Dict[str, float]:
        cost_plan = self._load_cost_plan()
        budget = _safe_float(
            os.getenv("PERMANENCE_LLM_MONTHLY_BUDGET_USD", cost_plan.get("llm_monthly_budget_usd")),
            DEFAULT_LLM_MONTHLY_BUDGET_USD,
        )
        budget = max(1.0, budget)
        spend = max(0.0, self._estimate_monthly_spend_usd())
        ratio = spend / budget if budget > 0 else 0.0
        return {
            "budget_usd": round(budget, 2),
            "spend_usd": round(spend, 4),
            "ratio": round(ratio, 6),
        }

    def _budget_adjusted_model(
        self,
        task_type: str,
        model: str,
        snapshot: Dict[str, float],
        model_map: Optional[Dict[str, str]] = None,
    ) -> tuple[str, str]:
        ratio = float(snapshot.get("ratio", 0.0))
        model_tier = self._tier_for_model(model_name=model, task_type=task_type)
        high_stakes = set(TASKS_OPUS)
        medium_stakes = set(TASKS_SONNET)
        low_stakes = set(TASKS_HAIKU)
        sonnet_model = self._model_for_tier("sonnet", model_map=model_map)
        haiku_model = self._model_for_tier("haiku", model_map=model_map)

        if ratio >= self.budget_critical_ratio:
            if task_type in high_stakes and model_tier == "opus":
                return sonnet_model, "budget_critical_downgrade_high_to_sonnet"
            if task_type in medium_stakes and model_tier != "haiku":
                return haiku_model, "budget_critical_downgrade_medium_to_haiku"
            if task_type in low_stakes and model_tier != "haiku":
                return haiku_model, "budget_critical_downgrade_low_to_haiku"
            return model, "budget_critical_no_change"

        if ratio >= self.budget_warning_ratio:
            if model_tier == "opus":
                return sonnet_model, "budget_warning_downgrade_opus_to_sonnet"
            return model, "budget_warning_no_change"

        return model, "budget_ok"

    # Tasks that REQUIRE paid models for quality — everything else goes to Ollama
    HYBRID_PAID_TASKS = frozenset(TASKS_OPUS) | {
        "research_synthesis",
        "conciliation",
        "social_drafting",
        "financial_review",
        "market_monitoring",
    }

    def explain_route(self, task_type: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        task_key = str(task_type or "").strip().lower() or "default"
        route_context = dict(context or {})
        policy = classify_task_context(task_type=task_key, context=route_context)

        if self.no_spend_mode:
            ollama_map = self._build_model_map_for_provider("ollama")
            model = ollama_map.get(task_key, ollama_map.get("default", "qwen2.5:7b"))
            provider = "ollama"
            return self._decision_payload(
                task_type=task_key,
                model=model,
                raw_model=model,
                provider=provider,
                budget_policy="no_spend_mode",
                context={**route_context, "policy": "no_spend_mode"},
                budget_snapshot=self._monthly_budget_snapshot(),
                route_mode="no_spend",
                policy=policy,
            )

        if self.low_cost_mode:
            return self._explain_low_cost(task_type=task_key, context=route_context, policy=policy)

        if self.hybrid_mode:
            return self._explain_hybrid(task_type=task_key, context=route_context, policy=policy)

        budget_snapshot = self._monthly_budget_snapshot()
        selected_provider, provider_policy = self._provider_for_task(
            task_type=task_key,
            budget_snapshot=budget_snapshot,
        )
        selected_map = self.model_by_task if selected_provider == self.provider else self._build_model_map_for_provider(
            selected_provider
        )
        raw_model = selected_map.get(task_key, selected_map.get("default", self.model_by_task["default"]))
        adjusted_model, budget_policy = self._budget_adjusted_model(
            task_type=task_key,
            model=raw_model,
            snapshot=budget_snapshot,
            model_map=selected_map,
        )
        return self._decision_payload(
            task_type=task_key,
            model=adjusted_model,
            raw_model=raw_model,
            provider=selected_provider,
            budget_policy=f"{provider_policy}|{budget_policy}",
            context={
                **route_context,
                "provider_policy": provider_policy,
                "provider_selected": selected_provider,
            },
            budget_snapshot=budget_snapshot,
            route_mode="standard",
            policy=policy,
        )

    def route(self, task_type: str, context: Optional[Dict[str, Any]] = None) -> str:
        decision = self.explain_route(task_type=task_type, context=context)
        self.selected_provider = self._normalize_provider(str(decision.get("provider") or self.provider))
        self._log_decision(
            task_type=str(decision.get("task_type") or task_type),
            model=str(decision.get("model_assigned") or ""),
            context=decision.get("context"),
            budget_snapshot=decision.get("budget_snapshot"),
            budget_policy=str(decision.get("budget_policy") or ""),
            raw_model=str(decision.get("raw_model") or ""),
            provider=str(decision.get("provider") or ""),
        )
        return str(decision.get("model_assigned") or "")

    def _route_hybrid(self, task_type: str, context: Optional[Dict[str, Any]] = None) -> str:
        """
        Hybrid routing: local Ollama by default, paid APIs for quality-critical tasks.

        Strategy:
        1. Routine/low-priority tasks → Ollama (free)
        2. Critical/high-quality tasks → paid provider (if budget allows)
        3. If paid provider budget exhausted → Ollama fallback

        This is the "Perplexity approach" — free for most things, premium when needed.
        """
        ollama_map = self._build_model_map_for_provider("ollama")
        key = str(task_type or "").strip().lower()

        # Task requires paid model quality?
        needs_paid = key in self.HYBRID_PAID_TASKS

        if not needs_paid:
            # Route to Ollama — free
            model = ollama_map.get(key, ollama_map.get("default", "qwen2.5:7b"))
            self.selected_provider = "ollama"
            self._log_decision(
                task_type=task_type,
                model=model,
                context={**(context or {}), "policy": "hybrid_local"},
                budget_policy="hybrid_local_free",
                raw_model=model,
                provider="ollama",
            )
            return model

        # Task needs paid quality — check budget and route accordingly
        budget_snapshot = self._monthly_budget_snapshot()
        selected_provider, provider_policy = self._provider_for_task(
            task_type=task_type,
            budget_snapshot=budget_snapshot,
        )

        # If selected provider is exhausted/capped, fall back to Ollama
        provider_budget = self._provider_budget_snapshot(budget_snapshot)
        provider_row = provider_budget.get(selected_provider, {"ratio": 0.0, "capped": False})
        if bool(provider_row.get("capped")) and float(provider_row.get("ratio", 0.0)) >= 1.0:
            model = ollama_map.get(key, ollama_map.get("default", "qwen2.5:7b"))
            self.selected_provider = "ollama"
            self._log_decision(
                task_type=task_type,
                model=model,
                context={**(context or {}), "policy": "hybrid_paid_exhausted_fallback"},
                budget_policy="hybrid_paid_exhausted_to_ollama",
                raw_model=model,
                provider="ollama",
            )
            return model

        # Route to paid provider
        selected_map = (
            self.model_by_task
            if selected_provider == self.provider
            else self._build_model_map_for_provider(selected_provider)
        )
        raw_model = selected_map.get(task_type, selected_map.get("default", self.model_by_task["default"]))
        adjusted_model, budget_policy = self._budget_adjusted_model(
            task_type=task_type,
            model=raw_model,
            snapshot=budget_snapshot,
            model_map=selected_map,
        )
        self.selected_provider = selected_provider
        self._log_decision(
            task_type=task_type,
            model=adjusted_model,
            context={
                **(context or {}),
                "provider_policy": provider_policy,
                "provider_selected": selected_provider,
                "policy": "hybrid_paid",
            },
            budget_snapshot=budget_snapshot,
            budget_policy=f"hybrid_paid|{provider_policy}|{budget_policy}",
            raw_model=raw_model,
        )
        return adjusted_model

    def _explain_hybrid(
        self,
        task_type: str,
        context: Optional[Dict[str, Any]] = None,
        policy: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        route_context = dict(context or {})
        policy = dict(policy or classify_task_context(task_type=task_type, context=route_context))
        ollama_map = self._build_model_map_for_provider("ollama")
        key = str(task_type or "").strip().lower()
        needs_paid = key in self.HYBRID_PAID_TASKS

        if not needs_paid:
            model = ollama_map.get(key, ollama_map.get("default", "qwen2.5:7b"))
            return self._decision_payload(
                task_type=key,
                model=model,
                raw_model=model,
                provider="ollama",
                budget_policy="hybrid_local_free",
                context={**route_context, "policy": "hybrid_local"},
                budget_snapshot=self._monthly_budget_snapshot(),
                route_mode="hybrid",
                policy=policy,
            )

        budget_snapshot = self._monthly_budget_snapshot()
        selected_provider, provider_policy = self._provider_for_task(
            task_type=key,
            budget_snapshot=budget_snapshot,
        )
        provider_budget = self._provider_budget_snapshot(budget_snapshot)
        provider_row = provider_budget.get(selected_provider, {"ratio": 0.0, "capped": False})
        if bool(provider_row.get("capped")) and float(provider_row.get("ratio", 0.0)) >= 1.0:
            model = ollama_map.get(key, ollama_map.get("default", "qwen2.5:7b"))
            return self._decision_payload(
                task_type=key,
                model=model,
                raw_model=model,
                provider="ollama",
                budget_policy="hybrid_paid_exhausted_to_ollama",
                context={**route_context, "policy": "hybrid_paid_exhausted_fallback"},
                budget_snapshot=budget_snapshot,
                route_mode="hybrid",
                policy=policy,
            )

        selected_map = self.model_by_task if selected_provider == self.provider else self._build_model_map_for_provider(
            selected_provider
        )
        raw_model = selected_map.get(key, selected_map.get("default", self.model_by_task["default"]))
        adjusted_model, budget_policy = self._budget_adjusted_model(
            task_type=key,
            model=raw_model,
            snapshot=budget_snapshot,
            model_map=selected_map,
        )
        return self._decision_payload(
            task_type=key,
            model=adjusted_model,
            raw_model=raw_model,
            provider=selected_provider,
            budget_policy=f"hybrid_paid|{provider_policy}|{budget_policy}",
            context={
                **route_context,
                "provider_policy": provider_policy,
                "provider_selected": selected_provider,
                "policy": "hybrid_paid",
            },
            budget_snapshot=budget_snapshot,
            route_mode="hybrid",
            policy=policy,
        )

    def get_temperature(self, task_type: str, context: Optional[Dict[str, Any]] = None) -> float:
        """Return appropriate temperature based on task type.

        ParamMem insight: Use higher temperature for reflection/brainstorming
        tasks to increase diversity of self-improvement ideas, lower for execution.
        """
        reflection_tasks = {"deep_reflection", "strategy", "canon_interpretation", "adversarial_review"}
        if task_type in reflection_tasks:
            return DEFAULT_REFLECTION_TEMPERATURE
        return DEFAULT_EXECUTION_TEMPERATURE

    def requires_tom(self, task_type: str, model: str) -> bool:
        """Check if Theory of Mind reasoning should be applied.

        Theory of Mind insight: ToM reasoning only for strong models.
        Weak/local models hallucinate social reasoning — strip ToM from task context.
        """
        if task_type not in TOM_TASKS:
            return False
        return model in TOM_CAPABLE_MODELS

    def _route_low_cost(self, task_type: str, context: Optional[Dict[str, Any]] = None) -> str:
        """Route in low-cost mode: skip opus, prefer haiku, fall back to ollama."""
        budget_snapshot = self._monthly_budget_snapshot()
        selected_provider, provider_policy = self._provider_for_task(
            task_type=task_type,
            budget_snapshot=budget_snapshot,
        )
        selected_map = (
            self.model_by_task
            if selected_provider == self.provider
            else self._build_model_map_for_provider(selected_provider)
        )
        raw_model = selected_map.get(task_type, selected_map.get("default", self.model_by_task["default"]))
        tier = self._tier_for_model(model_name=raw_model, task_type=task_type)

        # In low-cost mode, downgrade opus → sonnet, and prefer haiku for medium tasks.
        if tier == "opus":
            raw_model = self._model_for_tier("sonnet", model_map=selected_map)
            tier = "sonnet"

        # Apply normal budget adjustments on top of the low-cost cap.
        adjusted_model, budget_policy = self._budget_adjusted_model(
            task_type=task_type,
            model=raw_model,
            snapshot=budget_snapshot,
            model_map=selected_map,
        )
        self.selected_provider = selected_provider
        self._log_decision(
            task_type=task_type,
            model=adjusted_model,
            context={
                **(context or {}),
                "provider_policy": provider_policy,
                "provider_selected": selected_provider,
                "low_cost_mode": True,
            },
            budget_snapshot=budget_snapshot,
            budget_policy=f"low_cost|{provider_policy}|{budget_policy}",
            raw_model=raw_model,
        )
        return adjusted_model

    def _explain_low_cost(
        self,
        task_type: str,
        context: Optional[Dict[str, Any]] = None,
        policy: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        route_context = dict(context or {})
        policy = dict(policy or classify_task_context(task_type=task_type, context=route_context))
        budget_snapshot = self._monthly_budget_snapshot()
        selected_provider, provider_policy = self._provider_for_task(
            task_type=task_type,
            budget_snapshot=budget_snapshot,
        )
        selected_map = (
            self.model_by_task
            if selected_provider == self.provider
            else self._build_model_map_for_provider(selected_provider)
        )
        raw_model = selected_map.get(task_type, selected_map.get("default", self.model_by_task["default"]))
        tier = self._tier_for_model(model_name=raw_model, task_type=task_type)
        if tier == "opus":
            raw_model = self._model_for_tier("sonnet", model_map=selected_map)

        adjusted_model, budget_policy = self._budget_adjusted_model(
            task_type=task_type,
            model=raw_model,
            snapshot=budget_snapshot,
            model_map=selected_map,
        )
        return self._decision_payload(
            task_type=task_type,
            model=adjusted_model,
            raw_model=raw_model,
            provider=selected_provider,
            budget_policy=f"low_cost|{provider_policy}|{budget_policy}",
            context={
                **route_context,
                "provider_policy": provider_policy,
                "provider_selected": selected_provider,
                "low_cost_mode": True,
            },
            budget_snapshot=budget_snapshot,
            route_mode="low_cost",
            policy=policy,
        )

    def get_budget_dashboard(self) -> Dict[str, Any]:
        """Return comprehensive budget state for UI dashboard consumption."""
        budget_snapshot = self._monthly_budget_snapshot()
        provider_budget = self._provider_budget_snapshot(budget_snapshot)
        spend_by_provider = self._estimate_monthly_spend_by_provider_usd()
        total_spend = sum(spend_by_provider.values())

        # Determine effective tier
        tier = self.budget_tier
        if not tier:
            if self.no_spend_mode:
                tier = "free"
            elif self.low_cost_mode:
                tier = "light"
            elif float(budget_snapshot.get("budget_usd", 50.0)) >= 40.0:
                tier = "full"
            elif float(budget_snapshot.get("budget_usd", 50.0)) >= 15.0:
                tier = "standard"
            else:
                tier = "light"

        preset = BUDGET_TIER_PRESETS.get(tier, {})

        # Build warnings
        warnings: list[str] = []
        ratio = float(budget_snapshot.get("ratio", 0.0))
        if ratio >= self.budget_critical_ratio:
            warnings.append(f"Budget critical: {ratio:.0%} of monthly limit used")
        elif ratio >= self.budget_warning_ratio:
            warnings.append(f"Budget warning: {ratio:.0%} of monthly limit used")

        for p_name, p_data in provider_budget.items():
            p_ratio = float(p_data.get("ratio", 0.0))
            if p_data.get("capped") and p_ratio >= 1.0:
                warnings.append(f"Provider {p_name} cap exhausted ({p_ratio:.0%})")

        return {
            "budget_usd": float(budget_snapshot.get("budget_usd", 0.0)),
            "spend_usd": round(total_spend, 4),
            "ratio": round(ratio, 4),
            "remaining_usd": round(max(0.0, float(budget_snapshot.get("budget_usd", 0.0)) - total_spend), 4),
            "tier": tier,
            "tier_description": str(preset.get("description", "")),
            "provider": self.provider,
            "selected_provider": getattr(self, "selected_provider", self.provider),
            "no_spend_mode": self.no_spend_mode,
            "low_cost_mode": self.low_cost_mode,
            "warning_ratio": self.budget_warning_ratio,
            "critical_ratio": self.budget_critical_ratio,
            "spend_by_provider": spend_by_provider,
            "provider_budget": {
                name: {
                    "cap_usd": float(data.get("cap_usd", 0.0)),
                    "spend_usd": float(data.get("spend_usd", 0.0)),
                    "ratio": float(data.get("ratio", 0.0)),
                }
                for name, data in provider_budget.items()
            },
            "warnings": warnings,
        }

    @staticmethod
    def get_tier_presets() -> Dict[str, Dict[str, Any]]:
        """Return available budget tier presets for configuration UI."""
        return dict(BUDGET_TIER_PRESETS)

    def route_for_stage(self, stage: str, context: Optional[Dict[str, Any]] = None) -> str:
        stage_key = (stage or "").strip().lower()
        task_type = {
            "planning": "planning",
            "research": "research_synthesis",
            "execution": "execution",
            "output_review": "review",
            "conciliation": "conciliation",
            "validation": "canon_interpretation",
        }.get(stage_key, "default")
        return self.route(task_type=task_type, context=context)

    def get_model(self, task_type: str):
        """
        Return provider adapter for a task type, or None if unavailable.
        """
        model_name = self.route(task_type)
        tier = self._tier_for_model(model_name=model_name, task_type=task_type)
        provider = self._normalize_provider(getattr(self, "selected_provider", self.provider))
        try:
            from models.registry import registry

            return registry.get_by_tier(tier=tier, model_name=model_name, provider=provider)
        except Exception as exc:
            self._log_decision(
                task_type=task_type,
                model=model_name,
                context={
                    "warning": f"adapter_unavailable: {exc.__class__.__name__}",
                    "provider": provider,
                },
                provider=provider,
            )
            return None

    def _tier_for_model(self, model_name: str, task_type: str = "") -> str:
        lower = (model_name or "").lower()
        if not lower:
            return self._task_default_tier(task_type)
        if "opus" in lower:
            return "opus"
        if "haiku" in lower:
            return "haiku"
        if lower.startswith("qwen2.5:3b"):
            return "haiku"
        if lower.startswith("qwen3:8b"):
            return "opus"
        if lower.startswith("qwen3:4b") or lower.startswith("qwen2.5"):
            return "sonnet"
        if "gpt-4o-mini" in lower or "gpt-5-nano" in lower or "grok-2-mini" in lower:
            return "haiku"
        if "gpt-4.1" in lower or "gpt-5" in lower or "grok-3-latest" in lower:
            return "opus"
        if lower in self.tier_model_index.get("opus", set()):
            return "opus"
        if lower in self.tier_model_index.get("haiku", set()):
            return "haiku"
        if lower in self.tier_model_index.get("sonnet", set()):
            return "sonnet"
        return self._task_default_tier(task_type)

    def _log_decision(
        self,
        task_type: str,
        model: str,
        context: Optional[Dict[str, Any]] = None,
        budget_snapshot: Optional[Dict[str, float]] = None,
        budget_policy: str = "",
        raw_model: str = "",
        provider: str = "",
    ) -> None:
        selected_provider = self._normalize_provider(provider or getattr(self, "selected_provider", self.provider))
        provider_budget = getattr(self, "_last_provider_budget_snapshot", {}) or {}
        entry = {
            "timestamp": _utc_iso(),
            "task_type": task_type,
            "provider": selected_provider,
            "model_assigned": model,
            "raw_model": raw_model or model,
            "budget_policy": budget_policy or "unknown",
            "budget_llm_monthly_usd": float((budget_snapshot or {}).get("budget_usd", 0.0)),
            "budget_spend_estimate_usd": float((budget_snapshot or {}).get("spend_usd", 0.0)),
            "budget_ratio": float((budget_snapshot or {}).get("ratio", 0.0)),
            "provider_budget": provider_budget,
            "context_keys": sorted(list((context or {}).keys())),
        }
        with open(self.log_path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry) + "\n")

    def _decision_payload(
        self,
        task_type: str,
        model: str,
        raw_model: str,
        provider: str,
        budget_policy: str,
        context: Optional[Dict[str, Any]],
        budget_snapshot: Optional[Dict[str, float]],
        route_mode: str,
        policy: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        normalized_provider = self._normalize_provider(provider or self.provider)
        provider_budget = self._provider_budget_snapshot(budget_snapshot or self._monthly_budget_snapshot())
        capabilities = DEFAULT_MODEL_CAPABILITIES.get(normalized_provider, {}).get(model, {})
        route_context = dict(context or {})
        policy = dict(policy or {})
        reasons = [
            f"mode:{route_mode}",
            f"provider:{normalized_provider}",
            f"budget:{budget_policy or 'unknown'}",
        ]
        if policy.get("privacy_tier"):
            reasons.append(f"privacy:{policy['privacy_tier']}")
        if policy.get("domain"):
            reasons.append(f"domain:{policy['domain']}")
        if policy.get("risk_tier"):
            reasons.append(f"risk:{policy['risk_tier']}")
        if policy.get("complexity_tier"):
            reasons.append(f"complexity:{policy['complexity_tier']}")
        if capabilities.get("strengths"):
            reasons.append(f"strengths:{','.join(capabilities.get('strengths', [])[:3])}")

        return {
            "timestamp": _utc_iso(),
            "task_type": task_type,
            "provider": normalized_provider,
            "model_assigned": model,
            "raw_model": raw_model or model,
            "route_mode": route_mode,
            "budget_policy": budget_policy or "unknown",
            "budget_snapshot": budget_snapshot or {},
            "provider_budget": provider_budget,
            "policy": policy,
            "capabilities": capabilities,
            "route_reasons": reasons,
            "context": route_context,
        }
