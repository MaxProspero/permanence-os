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


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class ModelRouter:
    """
    Canon-compliant model routing with append-only decision logging.
    """

    def __init__(self, log_path: Optional[str] = None):
        self.log_path = Path(log_path or os.getenv("PERMANENCE_MODEL_ROUTING_LOG", "logs/model_routing.jsonl"))
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.model_by_task = self._build_model_map()

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

    def route(self, task_type: str, context: Optional[Dict[str, Any]] = None) -> str:
        model = self.model_by_task.get(task_type, self.model_by_task["default"])
        self._log_decision(task_type=task_type, model=model, context=context)
        return model

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

    def _log_decision(self, task_type: str, model: str, context: Optional[Dict[str, Any]] = None) -> None:
        entry = {
            "timestamp": _utc_iso(),
            "task_type": task_type,
            "model_assigned": model,
            "context_keys": sorted(list((context or {}).keys())),
        }
        with open(self.log_path, "a") as f:
            f.write(json.dumps(entry) + "\n")

