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


TASKS_OPUS = ("canon_interpretation", "strategy", "code_generation", "adversarial_review")
TASKS_SONNET = ("research_synthesis", "planning", "review", "execution", "conciliation")
TASKS_HAIKU = ("classification", "summarization", "tagging", "formatting")

DEFAULT_MODEL_BY_TASK_BY_PROVIDER: Dict[str, Dict[str, str]] = {
    "anthropic": {
        "canon_interpretation": "claude-opus-4-6",
        "strategy": "claude-opus-4-6",
        "code_generation": "claude-opus-4-6",
        "adversarial_review": "claude-opus-4-6",
        "research_synthesis": "claude-sonnet-4-6",
        "planning": "claude-sonnet-4-6",
        "review": "claude-sonnet-4-6",
        "execution": "claude-sonnet-4-6",
        "conciliation": "claude-sonnet-4-6",
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
        "research_synthesis": "gpt-4o",
        "planning": "gpt-4o",
        "review": "gpt-4o",
        "execution": "gpt-4o",
        "conciliation": "gpt-4o",
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
        "research_synthesis": "grok-3-mini",
        "planning": "grok-3-mini",
        "review": "grok-3-mini",
        "execution": "grok-3-mini",
        "conciliation": "grok-3-mini",
        "classification": "grok-2-mini",
        "summarization": "grok-2-mini",
        "tagging": "grok-2-mini",
        "formatting": "grok-2-mini",
        "default": "grok-3-mini",
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


class ModelRouter:
    """
    Canon-compliant model routing with append-only decision logging.
    """

    def __init__(self, log_path: Optional[str] = None):
        self.log_path = Path(log_path or os.getenv("PERMANENCE_MODEL_ROUTING_LOG", "logs/model_routing.jsonl"))
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.provider = self._normalize_provider(os.getenv("PERMANENCE_MODEL_PROVIDER", "anthropic"))
        self.model_by_task = self._build_model_map()
        self.tier_model_index = self._build_tier_model_index()
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

    @staticmethod
    def _normalize_provider(value: str) -> str:
        token = str(value or "").strip().lower()
        if token in {"claude", "anthropic"}:
            return "anthropic"
        if token in {"openai", "gpt"}:
            return "openai"
        if token in {"xai", "grok"}:
            return "xai"
        return "anthropic"

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

    def _build_tier_model_index(self) -> Dict[str, set[str]]:
        index: Dict[str, set[str]] = {"opus": set(), "sonnet": set(), "haiku": set()}
        for task_type, model_name in self.model_by_task.items():
            tier = self._task_default_tier(task_type)
            token = str(model_name or "").strip().lower()
            if token:
                index[tier].add(token)
        return index

    def _model_for_tier(self, tier: str) -> str:
        normalized = str(tier or "sonnet").strip().lower() or "sonnet"
        defaults = DEFAULT_MODEL_BY_TASK_BY_PROVIDER.get(self.provider, DEFAULT_MODEL_BY_TASK_BY_PROVIDER["anthropic"])
        if normalized == "opus":
            return self.model_by_task.get("strategy", defaults["strategy"])
        if normalized == "haiku":
            return self.model_by_task.get("summarization", defaults["summarization"])
        return self.model_by_task.get("execution", defaults["execution"])

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

    def _budget_adjusted_model(self, task_type: str, model: str, snapshot: Dict[str, float]) -> tuple[str, str]:
        ratio = float(snapshot.get("ratio", 0.0))
        model_tier = self._tier_for_model(model_name=model, task_type=task_type)
        high_stakes = set(TASKS_OPUS)
        medium_stakes = set(TASKS_SONNET)
        low_stakes = set(TASKS_HAIKU)
        sonnet_model = self._model_for_tier("sonnet")
        haiku_model = self._model_for_tier("haiku")

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

    def route(self, task_type: str, context: Optional[Dict[str, Any]] = None) -> str:
        raw_model = self.model_by_task.get(task_type, self.model_by_task["default"])
        budget_snapshot = self._monthly_budget_snapshot()
        adjusted_model, budget_policy = self._budget_adjusted_model(
            task_type=task_type,
            model=raw_model,
            snapshot=budget_snapshot,
        )
        self._log_decision(
            task_type=task_type,
            model=adjusted_model,
            context=context,
            budget_snapshot=budget_snapshot,
            budget_policy=budget_policy,
            raw_model=raw_model,
        )
        return adjusted_model

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
        try:
            from models.registry import registry

            return registry.get_by_tier(tier=tier, model_name=model_name, provider=self.provider)
        except Exception as exc:
            self._log_decision(
                task_type=task_type,
                model=model_name,
                context={
                    "warning": f"adapter_unavailable: {exc.__class__.__name__}",
                    "provider": self.provider,
                },
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
    ) -> None:
        entry = {
            "timestamp": _utc_iso(),
            "task_type": task_type,
            "provider": self.provider,
            "model_assigned": model,
            "raw_model": raw_model or model,
            "budget_policy": budget_policy or "unknown",
            "budget_llm_monthly_usd": float((budget_snapshot or {}).get("budget_usd", 0.0)),
            "budget_spend_estimate_usd": float((budget_snapshot or {}).get("spend_usd", 0.0)),
            "budget_ratio": float((budget_snapshot or {}).get("ratio", 0.0)),
            "context_keys": sorted(list((context or {}).keys())),
        }
        with open(self.log_path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry) + "\n")
