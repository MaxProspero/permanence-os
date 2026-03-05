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


DEFAULT_MODEL_BY_TASK: Dict[str, str] = {
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
}

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
        self.model_by_task = self._build_model_map()
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

    def _build_model_map(self) -> Dict[str, str]:
        model_map = dict(DEFAULT_MODEL_BY_TASK)
        opus = os.getenv("PERMANENCE_MODEL_OPUS")
        sonnet = os.getenv("PERMANENCE_MODEL_SONNET")
        haiku = os.getenv("PERMANENCE_MODEL_HAIKU")
        default_model = os.getenv("PERMANENCE_DEFAULT_MODEL")

        if opus:
            for key in ("canon_interpretation", "strategy", "code_generation", "adversarial_review"):
                model_map[key] = opus
        if sonnet:
            for key in ("research_synthesis", "planning", "review", "execution", "conciliation"):
                model_map[key] = sonnet
        if haiku:
            for key in ("classification", "summarization", "tagging", "formatting"):
                model_map[key] = haiku
        if default_model:
            model_map["default"] = default_model

        return model_map

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
                tier = self._tier_for_model(model)
                fallback = {
                    "opus": "claude-opus-4-6",
                    "sonnet": "claude-sonnet-4-6",
                    "haiku": "claude-haiku-4-5-20251001",
                }.get(tier, "claude-sonnet-4-6")
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
        lowered = str(model or "").lower()
        high_stakes = {"canon_interpretation", "strategy", "adversarial_review", "code_generation"}
        medium_stakes = {"research_synthesis", "planning", "review", "conciliation"}
        low_stakes = {"classification", "summarization", "tagging", "formatting"}
        sonnet_model = self.model_by_task.get("execution", DEFAULT_MODEL_BY_TASK["execution"])
        haiku_model = self.model_by_task.get("summarization", DEFAULT_MODEL_BY_TASK["summarization"])

        if ratio >= self.budget_critical_ratio:
            if task_type in high_stakes and "opus" in lowered:
                return sonnet_model, "budget_critical_downgrade_high_to_sonnet"
            if task_type in medium_stakes and "haiku" not in lowered:
                return haiku_model, "budget_critical_downgrade_medium_to_haiku"
            if task_type in low_stakes and "haiku" not in lowered:
                return haiku_model, "budget_critical_downgrade_low_to_haiku"
            return model, "budget_critical_no_change"

        if ratio >= self.budget_warning_ratio:
            if "opus" in lowered:
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
        tier = self._tier_for_model(model_name)
        try:
            from models.registry import registry

            return registry.get_by_tier(tier)
        except Exception as exc:
            self._log_decision(
                task_type=task_type,
                model=model_name,
                context={"warning": f"adapter_unavailable: {exc.__class__.__name__}"},
            )
            return None

    @staticmethod
    def _tier_for_model(model_name: str) -> str:
        lower = (model_name or "").lower()
        if "opus" in lower:
            return "opus"
        if "haiku" in lower:
            return "haiku"
        return "sonnet"

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
