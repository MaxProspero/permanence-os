from __future__ import annotations

from typing import Any, Dict


def classify_task_context(task_type: str, context: Dict[str, Any] | None = None) -> Dict[str, Any]:
    payload = dict(context or {})
    task_key = str(task_type or "").strip().lower()

    privacy_tier = "standard"
    if payload.get("contains_secrets") or payload.get("local_only"):
        privacy_tier = "restricted"
    elif payload.get("public_data_only"):
        privacy_tier = "public"

    risk_tier = "medium"
    if payload.get("requires_approval") or payload.get("external_write") or payload.get("financial_action"):
        risk_tier = "high"
    elif task_key in {"classification", "summarization", "tagging", "formatting", "routine"}:
        risk_tier = "low"

    complexity_tier = "medium"
    if task_key in {"canon_interpretation", "strategy", "code_generation", "adversarial_review", "deep_reflection"}:
        complexity_tier = "high"
    elif task_key in {"classification", "summarization", "tagging", "formatting", "routine"}:
        complexity_tier = "low"

    return {
        "task_type": task_key,
        "privacy_tier": privacy_tier,
        "risk_tier": risk_tier,
        "complexity_tier": complexity_tier,
        "tool_required": bool(payload.get("tool_required")),
        "external_write": bool(payload.get("external_write")),
        "requires_approval": bool(payload.get("requires_approval")),
    }
