"""
Permanence OS — Cost Tracker (v0.1)

Hooks into model adapters to track per-call LLM costs in SQLite.
Supports session, task, daily, and provider-level cost rollups.

Pricing is approximate and configurable. Ollama calls are $0.00
(local inference). Budget enforcement uses the existing
PERMANENCE_LLM_MONTHLY_BUDGET_USD env variable.

Usage:
    from core.cost_tracker import cost_tracker
    cost_tracker.record(model_response.metadata)
    summary = cost_tracker.session_total()
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional

from agents.utils import log


# ---------------------------------------------------------------------------
# Approximate pricing per 1M tokens (input / output)
# Updated: 2026-03
# ---------------------------------------------------------------------------
PRICING: Dict[str, Dict[str, float]] = {
    # Anthropic
    "claude-opus-4-6":              {"input": 15.00, "output": 75.00},
    "claude-sonnet-4-6":            {"input": 3.00,  "output": 15.00},
    "claude-haiku-4-5-20251001":    {"input": 0.80,  "output": 4.00},
    # OpenAI
    "gpt-4.1":                      {"input": 2.00,  "output": 8.00},
    "gpt-4o":                       {"input": 2.50,  "output": 10.00},
    "gpt-4o-mini":                  {"input": 0.15,  "output": 0.60},
    # xAI
    "grok-3-latest":                {"input": 3.00,  "output": 15.00},
    "grok-3-mini":                  {"input": 0.30,  "output": 0.50},
    "grok-2-mini":                  {"input": 0.10,  "output": 0.25},
    # Ollama — free (local)
    "ollama":                       {"input": 0.00,  "output": 0.00},
}


def estimate_cost(
    model_id: str,
    provider: str,
    input_tokens: int,
    output_tokens: int,
) -> float:
    """Estimate USD cost from token counts and known pricing."""
    if provider == "ollama":
        return 0.0

    pricing = PRICING.get(model_id, PRICING.get(provider, {}))
    if not pricing:
        return 0.0

    input_cost = (input_tokens / 1_000_000) * pricing.get("input", 0.0)
    output_cost = (output_tokens / 1_000_000) * pricing.get("output", 0.0)
    return round(input_cost + output_cost, 8)


class CostTracker:
    """Tracks LLM call costs in the Synthesis DB."""

    def __init__(self, session_id: str | None = None):
        self.session_id = session_id or f"session_{uuid.uuid4().hex[:12]}"
        self._db = None
        self._budget_usd: Optional[float] = None

        budget_env = os.getenv("PERMANENCE_LLM_MONTHLY_BUDGET_USD", "").strip()
        if budget_env:
            try:
                self._budget_usd = float(budget_env)
            except ValueError:
                pass

    def _get_db(self):
        """Lazy-load SynthesisDB to avoid import cycles."""
        if self._db is None:
            try:
                from core.synthesis_db import SynthesisDB

                self._db = SynthesisDB()
            except Exception as exc:
                log(f"CostTracker: cannot init SynthesisDB: {exc}", level="WARNING")
                return None
        return self._db

    def record(
        self,
        metadata: Dict[str, Any],
        task_id: str = "",
    ) -> Optional[float]:
        """Record a model call from its ModelResponse.metadata dict.

        Returns estimated cost in USD, or None if recording failed.
        """
        model_id = str(metadata.get("model", ""))
        tier = str(metadata.get("tier", ""))
        provider = str(metadata.get("provider", ""))
        input_tokens = int(metadata.get("input_tokens", 0))
        output_tokens = int(metadata.get("output_tokens", 0))

        cost = estimate_cost(model_id, provider, input_tokens, output_tokens)

        db = self._get_db()
        if db is None:
            return cost

        try:
            db.log_cost(
                model_id=model_id,
                tier=tier,
                provider=provider,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost_usd=cost,
                session_id=self.session_id,
                task_id=task_id,
            )
        except Exception as exc:
            log(f"CostTracker: failed to log cost: {exc}", level="WARNING")
            return cost

        # Budget warning
        if self._budget_usd and self._budget_usd > 0:
            monthly = self.monthly_total()
            if monthly >= self._budget_usd * 0.9:
                log(
                    f"⚠ Monthly LLM spend ${monthly:.4f} is ≥90% of "
                    f"${self._budget_usd:.2f} budget",
                    level="WARNING",
                )

        return cost

    def session_total(self) -> float:
        """Total USD spent in the current session."""
        db = self._get_db()
        if db is None:
            return 0.0
        summary = db.get_cost_summary(session_id=self.session_id)
        return float(summary.get("total_usd", 0.0))

    def task_total(self, task_id: str) -> float:
        """Total USD spent on a specific task."""
        db = self._get_db()
        if db is None:
            return 0.0
        conn = db._get_conn()
        row = conn.execute(
            "SELECT COALESCE(SUM(cost_usd), 0.0) AS total FROM model_cost_log WHERE task_id = ?",
            (task_id,),
        ).fetchone()
        return float(row["total"]) if row else 0.0

    def daily_total(self, date_str: str | None = None) -> float:
        """Total USD spent on a given day (YYYY-MM-DD), default today."""
        if not date_str:
            date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        since = f"{date_str}T00:00:00+00:00"
        db = self._get_db()
        if db is None:
            return 0.0
        summary = db.get_cost_summary(since_iso=since)
        return float(summary.get("total_usd", 0.0))

    def monthly_total(self) -> float:
        """Total USD spent in the current calendar month."""
        now = datetime.now(timezone.utc)
        first_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        since = first_of_month.isoformat()
        db = self._get_db()
        if db is None:
            return 0.0
        summary = db.get_cost_summary(since_iso=since)
        return float(summary.get("total_usd", 0.0))

    def by_provider(self) -> list[dict]:
        """Cost breakdown by provider (all time or scoped by since_iso)."""
        db = self._get_db()
        if db is None:
            return []
        return db.get_cost_by_provider()

    def budget_status(self) -> Dict[str, Any]:
        """Return budget utilization status."""
        monthly = self.monthly_total()
        budget = self._budget_usd or 0.0
        utilization = (monthly / budget * 100) if budget > 0 else 0.0
        return {
            "monthly_spend_usd": round(monthly, 6),
            "budget_usd": budget,
            "utilization_pct": round(utilization, 2),
            "remaining_usd": round(max(0, budget - monthly), 6),
            "over_budget": monthly > budget if budget > 0 else False,
        }


# ---------------------------------------------------------------------------
# Module-level singleton (lazy)
# ---------------------------------------------------------------------------
_tracker: Optional[CostTracker] = None


def get_cost_tracker() -> CostTracker:
    """Get the global CostTracker singleton."""
    global _tracker
    if _tracker is None:
        _tracker = CostTracker()
    return _tracker


# Convenience alias
cost_tracker = None  # Will be initialized on first use


def _ensure_tracker() -> CostTracker:
    global cost_tracker
    if cost_tracker is None:
        cost_tracker = get_cost_tracker()
    return cost_tracker
