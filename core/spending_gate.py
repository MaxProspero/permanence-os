#!/usr/bin/env python3
"""
Permanence OS — Spending Gate (v2)

Human-approval-required gate for all real-money LLM API spending.
Core principle: USE PREPAID CREDITS FREELY. STOP BEFORE CHARGING THE CARD.

Flow:
  1. System tracks prepaid credit balance per provider
  2. Each API call deducts estimated cost from credit balance
  3. When credits run out → spending gate BLOCKS the call
  4. Agent logs an approval request → falls back to Ollama (free)
  5. Human approves → gate unlocks for that provider/amount
  6. No approval → system keeps running on Ollama (zero cost)

This gate is enforced BEFORE any API call, not after. No surprise charges.

v2 additions:
  - Time-limited approvals (30 min, 1 hour, end of day, custom)
  - Step-based approvals (next N steps, or until task/goal completes)
  - Daily spend cap with smart budget allocation
  - Priority-based budget distribution

Env vars:
  PERMANENCE_PREPAID_CREDIT_USD       — Total prepaid credits (default: 0)
  PERMANENCE_ANTHROPIC_CREDIT_USD     — Anthropic-specific credits
  PERMANENCE_OPENAI_CREDIT_USD        — OpenAI-specific credits
  PERMANENCE_XAI_CREDIT_USD           — xAI-specific credits
  PERMANENCE_SPENDING_APPROVAL_MODE   — "gate" (default), "auto" (no gate), "block" (block all)
  PERMANENCE_SPENDING_GATE_LOG        — Path to approval request log
  PERMANENCE_DAILY_SPEND_CAP_USD      — Daily spend cap across all providers (default: 0 = no cap)

Usage:
  from core.spending_gate import spending_gate

  # Before making an API call:
  decision = spending_gate.check(provider="anthropic", estimated_cost_usd=0.05)
  if decision["allowed"]:
      # proceed with API call
      ...
      spending_gate.record_spend(provider="anthropic", actual_cost_usd=0.04)
  else:
      # fall back to Ollama or queue for approval
      print(decision["reason"])

  # Time-limited approval (human approves for 1 hour):
  spending_gate.approve_timed(provider="anthropic", amount_usd=20.00, duration_minutes=60)

  # Step-based approval (human approves next 10 steps):
  spending_gate.approve_steps(provider="anthropic", amount_usd=10.00, max_steps=10)

  # Check remaining credits:
  status = spending_gate.status()
"""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DEFAULT_GATE_LOG = os.path.join(BASE_DIR, "logs", "spending_gate.jsonl")
DEFAULT_GATE_STATE = os.path.join(BASE_DIR, "memory", "working", "spending_gate_state.json")

# Provider list
PAID_PROVIDERS = ("anthropic", "openai", "xai")

# Approval type constants
APPROVAL_TYPE_CREDITS = "credits"           # Basic credit-based (original)
APPROVAL_TYPE_TIMED = "timed"               # Time-limited window
APPROVAL_TYPE_STEPS = "steps"               # Step-count limited
APPROVAL_TYPE_TASK = "task"                 # Until task/goal completes
APPROVAL_TYPE_DAILY_CAP = "daily_cap"       # Daily budget cap

# Priority tiers for smart budget allocation
PRIORITY_CRITICAL = "critical"    # Must-complete tasks — gets largest share
PRIORITY_HIGH = "high"            # Important tasks — significant share
PRIORITY_NORMAL = "normal"        # Regular tasks — fair share
PRIORITY_LOW = "low"              # Nice-to-have — smallest share

PRIORITY_WEIGHTS = {
    PRIORITY_CRITICAL: 4.0,
    PRIORITY_HIGH: 2.5,
    PRIORITY_NORMAL: 1.0,
    PRIORITY_LOW: 0.4,
}


class TimedApproval:
    """A time-limited spending approval window."""

    def __init__(
        self,
        provider: str,
        amount_usd: float,
        expires_at: datetime,
        approved_by: str = "human",
        task_id: str = "",
    ):
        self.provider = provider
        self.amount_usd = amount_usd
        self.spent_usd = 0.0
        self.expires_at = expires_at
        self.approved_by = approved_by
        self.task_id = task_id
        self.created_at = datetime.now(timezone.utc)

    @property
    def remaining_usd(self) -> float:
        return max(0.0, self.amount_usd - self.spent_usd)

    @property
    def is_expired(self) -> bool:
        return datetime.now(timezone.utc) >= self.expires_at

    @property
    def is_active(self) -> bool:
        return not self.is_expired and self.remaining_usd > 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": APPROVAL_TYPE_TIMED,
            "provider": self.provider,
            "amount_usd": round(self.amount_usd, 6),
            "spent_usd": round(self.spent_usd, 6),
            "remaining_usd": round(self.remaining_usd, 6),
            "expires_at": self.expires_at.isoformat(),
            "created_at": self.created_at.isoformat(),
            "approved_by": self.approved_by,
            "task_id": self.task_id,
            "is_active": self.is_active,
        }


class StepApproval:
    """A step-count-limited spending approval."""

    def __init__(
        self,
        provider: str,
        amount_usd: float,
        max_steps: int,
        approved_by: str = "human",
        task_id: str = "",
    ):
        self.provider = provider
        self.amount_usd = amount_usd
        self.spent_usd = 0.0
        self.max_steps = max_steps
        self.steps_used = 0
        self.approved_by = approved_by
        self.task_id = task_id
        self.created_at = datetime.now(timezone.utc)

    @property
    def remaining_usd(self) -> float:
        return max(0.0, self.amount_usd - self.spent_usd)

    @property
    def steps_remaining(self) -> int:
        return max(0, self.max_steps - self.steps_used)

    @property
    def is_active(self) -> bool:
        return self.steps_remaining > 0 and self.remaining_usd > 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": APPROVAL_TYPE_STEPS,
            "provider": self.provider,
            "amount_usd": round(self.amount_usd, 6),
            "spent_usd": round(self.spent_usd, 6),
            "remaining_usd": round(self.remaining_usd, 6),
            "max_steps": self.max_steps,
            "steps_used": self.steps_used,
            "steps_remaining": self.steps_remaining,
            "created_at": self.created_at.isoformat(),
            "approved_by": self.approved_by,
            "task_id": self.task_id,
            "is_active": self.is_active,
        }


class TaskApproval:
    """Approval that lasts until a specific task/goal completes."""

    def __init__(
        self,
        provider: str,
        amount_usd: float,
        task_id: str,
        approved_by: str = "human",
    ):
        self.provider = provider
        self.amount_usd = amount_usd
        self.spent_usd = 0.0
        self.task_id = task_id
        self.approved_by = approved_by
        self.created_at = datetime.now(timezone.utc)
        self.completed = False

    @property
    def remaining_usd(self) -> float:
        return max(0.0, self.amount_usd - self.spent_usd)

    @property
    def is_active(self) -> bool:
        return not self.completed and self.remaining_usd > 0

    def complete(self) -> None:
        self.completed = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": APPROVAL_TYPE_TASK,
            "provider": self.provider,
            "amount_usd": round(self.amount_usd, 6),
            "spent_usd": round(self.spent_usd, 6),
            "remaining_usd": round(self.remaining_usd, 6),
            "task_id": self.task_id,
            "created_at": self.created_at.isoformat(),
            "approved_by": self.approved_by,
            "completed": self.completed,
            "is_active": self.is_active,
        }


class DailyBudget:
    """Tracks daily spend cap with smart allocation."""

    def __init__(self, cap_usd: float = 0.0):
        self.cap_usd = cap_usd
        self._daily_spend: Dict[str, float] = {}   # provider -> amount spent today
        self._date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        self._priorities: Dict[str, str] = {}       # task_type -> priority level

    def _reset_if_new_day(self) -> None:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if today != self._date:
            self._daily_spend = {}
            self._date = today

    @property
    def total_spent_today(self) -> float:
        self._reset_if_new_day()
        return sum(self._daily_spend.values())

    @property
    def remaining_today(self) -> float:
        if self.cap_usd <= 0:
            return float("inf")
        return max(0.0, self.cap_usd - self.total_spent_today)

    def provider_spent_today(self, provider: str) -> float:
        self._reset_if_new_day()
        return self._daily_spend.get(provider, 0.0)

    def record_daily_spend(self, provider: str, amount_usd: float) -> None:
        self._reset_if_new_day()
        current = self._daily_spend.get(provider, 0.0)
        self._daily_spend[provider] = current + amount_usd

    def set_priority(self, task_type: str, priority: str) -> None:
        if priority in PRIORITY_WEIGHTS:
            self._priorities[task_type] = priority

    def get_budget_allocation(self, task_type: str = "") -> float:
        """Get how much budget a task type should get based on priority."""
        if self.cap_usd <= 0:
            return float("inf")

        priority = self._priorities.get(task_type, PRIORITY_NORMAL)
        weight = PRIORITY_WEIGHTS.get(priority, 1.0)

        # Total weight across all registered priorities
        total_weight = sum(
            PRIORITY_WEIGHTS.get(p, 1.0) for p in self._priorities.values()
        )
        if total_weight <= 0:
            total_weight = 1.0

        # This task's share of the remaining daily budget
        share = (weight / total_weight) * self.remaining_today
        return round(share, 6)

    def would_exceed_cap(self, amount_usd: float) -> bool:
        if self.cap_usd <= 0:
            return False
        return (self.total_spent_today + amount_usd) > self.cap_usd

    def to_dict(self) -> Dict[str, Any]:
        self._reset_if_new_day()
        return {
            "cap_usd": round(self.cap_usd, 6),
            "date": self._date,
            "total_spent_today": round(self.total_spent_today, 6),
            "remaining_today": round(self.remaining_today, 6),
            "spend_by_provider": {k: round(v, 6) for k, v in self._daily_spend.items()},
            "priorities": dict(self._priorities),
        }


class SpendingGate:
    """
    Human-approval-required gate for real-money LLM spending.

    Modes:
      - "gate" (default): Use credits freely, block when exhausted, fall back to Ollama
      - "auto": No gate, spend freely up to budget (use with caution)
      - "block": Block ALL paid API calls (Ollama only)

    Approval types:
      - credits: Basic — add credits to a provider's balance
      - timed: Time-limited — approve spending for N minutes
      - steps: Step-limited — approve next N API calls
      - task: Task-scoped — approve spending until a task completes
      - daily_cap: Daily budget — auto-distribute across priorities
    """

    def __init__(
        self,
        state_path: Optional[str] = None,
        log_path: Optional[str] = None,
    ):
        self.state_path = Path(state_path or os.getenv("PERMANENCE_SPENDING_GATE_STATE", DEFAULT_GATE_STATE))
        self.log_path = Path(log_path or os.getenv("PERMANENCE_SPENDING_GATE_LOG", DEFAULT_GATE_LOG))
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

        # Mode
        self.mode = os.getenv("PERMANENCE_SPENDING_APPROVAL_MODE", "gate").strip().lower()
        if self.mode not in ("gate", "auto", "block"):
            self.mode = "gate"

        # Load or initialize credit balances
        self._credits = self._load_state()

        # Active approval windows (in-memory, not persisted — expire naturally)
        self._timed_approvals: List[TimedApproval] = []
        self._step_approvals: List[StepApproval] = []
        self._task_approvals: List[TaskApproval] = []

        # Daily budget — prefer saved state, fall back to env var
        saved_db = getattr(self, "_saved_daily_budget", {})
        saved_cap = _safe_float(str(saved_db.get("cap_usd", 0)))
        env_cap = _safe_float(os.getenv("PERMANENCE_DAILY_SPEND_CAP_USD", "0"))
        daily_cap = saved_cap if saved_cap > 0 else env_cap
        self._daily_budget = DailyBudget(cap_usd=daily_cap)

        # Restore priorities from saved state
        if saved_db.get("priorities"):
            for task_type, priority in saved_db["priorities"].items():
                self._daily_budget.set_priority(task_type, priority)

    def _default_credits(self) -> Dict[str, float]:
        """Load credit balances from env vars."""
        # Global prepaid pool
        global_credit = _safe_float(os.getenv("PERMANENCE_PREPAID_CREDIT_USD", "0"))

        credits: Dict[str, float] = {}
        for provider in PAID_PROVIDERS:
            env_key = f"PERMANENCE_{provider.upper()}_CREDIT_USD"
            provider_credit = _safe_float(os.getenv(env_key, "0"))
            # Provider-specific credit OR share of global pool
            credits[provider] = provider_credit if provider_credit > 0 else global_credit / max(1, len(PAID_PROVIDERS))

        return credits

    def _load_state(self) -> Dict[str, float]:
        """Load persisted credit state, or initialize from env vars.

        Also restores mode and daily_budget from state file if present.
        """
        if self.state_path.exists():
            try:
                data = json.loads(self.state_path.read_text(encoding="utf-8"))
                if isinstance(data, dict) and "credits" in data:
                    # Restore mode from state if not overridden by env
                    if "mode" in data and not os.getenv("PERMANENCE_SPENDING_APPROVAL_MODE"):
                        saved_mode = data["mode"].lower().strip()
                        if saved_mode in ("gate", "auto", "block"):
                            self.mode = saved_mode
                    # Store daily_budget data for post-init restoration
                    self._saved_daily_budget = data.get("daily_budget", {})
                    return {k: float(v) for k, v in data["credits"].items()}
            except (json.JSONDecodeError, OSError, TypeError, ValueError):
                pass
        self._saved_daily_budget = {}
        return self._default_credits()

    def _save_state(self) -> None:
        """Persist credit state to disk."""
        try:
            data = {
                "credits": {k: round(v, 6) for k, v in self._credits.items()},
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "mode": self.mode,
                "daily_budget": self._daily_budget.to_dict(),
            }
            self.state_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except OSError:
            pass

    def _log_event(self, event_type: str, details: Dict[str, Any]) -> None:
        """Append event to spending gate log."""
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event": event_type,
            **details,
        }
        try:
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
        except OSError:
            pass

    def _cleanup_expired(self) -> None:
        """Remove expired/exhausted approvals."""
        self._timed_approvals = [a for a in self._timed_approvals if a.is_active]
        self._step_approvals = [a for a in self._step_approvals if a.is_active]
        self._task_approvals = [a for a in self._task_approvals if a.is_active]

    def _check_timed_approvals(self, provider: str, estimated_cost_usd: float) -> Optional[TimedApproval]:
        """Find an active timed approval covering this request."""
        for approval in self._timed_approvals:
            if (
                approval.provider == provider
                and approval.is_active
                and estimated_cost_usd <= approval.remaining_usd
            ):
                return approval
        return None

    def _check_step_approvals(self, provider: str, estimated_cost_usd: float) -> Optional[StepApproval]:
        """Find an active step approval covering this request."""
        for approval in self._step_approvals:
            if (
                approval.provider == provider
                and approval.is_active
                and estimated_cost_usd <= approval.remaining_usd
            ):
                return approval
        return None

    def _check_task_approvals(self, provider: str, estimated_cost_usd: float, task_id: str = "") -> Optional[TaskApproval]:
        """Find an active task approval covering this request."""
        for approval in self._task_approvals:
            if (
                approval.provider == provider
                and approval.is_active
                and estimated_cost_usd <= approval.remaining_usd
                and (not task_id or approval.task_id == task_id)
            ):
                return approval
        return None

    def check(
        self,
        provider: str,
        estimated_cost_usd: float,
        task_type: str = "",
        model: str = "",
        task_id: str = "",
    ) -> Dict[str, Any]:
        """
        Check if a paid API call is allowed.

        Checks in order:
          1. Free providers (Ollama) — always allowed
          2. Block mode — always blocked
          3. Auto mode — always allowed
          4. Daily cap — blocked if would exceed
          5. Gate mode — check credits, then timed/step/task approvals

        Returns:
          {
            "allowed": True/False,
            "reason": "...",
            "fallback": "ollama" or None,
            "remaining_credit": float,
            "approval_type": str or None,
          }
        """
        provider = provider.lower().strip()

        # Ollama is always free — always allowed
        if provider == "ollama" or provider not in PAID_PROVIDERS:
            return {
                "allowed": True,
                "reason": "free_provider",
                "fallback": None,
                "remaining_credit": float("inf"),
                "approval_type": None,
            }

        # Block mode — no paid calls ever
        if self.mode == "block":
            self._log_event("blocked", {
                "provider": provider,
                "estimated_cost": estimated_cost_usd,
                "task_type": task_type,
                "model": model,
                "reason": "block_mode",
            })
            return {
                "allowed": False,
                "reason": "Spending mode is 'block' — all paid API calls are disabled. Using Ollama instead.",
                "fallback": "ollama",
                "remaining_credit": 0.0,
                "approval_type": None,
            }

        # Auto mode — allow everything (respects budget limits in model_router)
        if self.mode == "auto":
            return {
                "allowed": True,
                "reason": "auto_mode",
                "fallback": None,
                "remaining_credit": self._credits.get(provider, 0.0),
                "approval_type": None,
            }

        # ── Gate mode checks ─────────────────────────────────────────

        # Clean up expired approvals
        self._cleanup_expired()

        # Daily cap check (if configured)
        if self._daily_budget.cap_usd > 0 and self._daily_budget.would_exceed_cap(estimated_cost_usd):
            self._log_event("daily_cap_exceeded", {
                "provider": provider,
                "estimated_cost": estimated_cost_usd,
                "daily_spent": self._daily_budget.total_spent_today,
                "daily_cap": self._daily_budget.cap_usd,
                "task_type": task_type,
                "model": model,
            })
            return {
                "allowed": False,
                "reason": f"Daily spend cap ${self._daily_budget.cap_usd:.2f} would be exceeded. "
                          f"Spent today: ${self._daily_budget.total_spent_today:.4f}. "
                          f"Remaining: ${self._daily_budget.remaining_today:.4f}. "
                          f"Falling back to Ollama.",
                "fallback": "ollama",
                "remaining_credit": round(self._daily_budget.remaining_today, 6),
                "approval_type": "daily_cap_block",
            }

        with self._lock:
            available = self._credits.get(provider, 0.0)

            # 1. Check basic credits first
            if estimated_cost_usd <= available:
                return {
                    "allowed": True,
                    "reason": "within_credits",
                    "fallback": None,
                    "remaining_credit": round(available, 6),
                    "approval_type": APPROVAL_TYPE_CREDITS,
                }

            # 2. Check timed approvals
            timed = self._check_timed_approvals(provider, estimated_cost_usd)
            if timed:
                return {
                    "allowed": True,
                    "reason": f"timed_approval (expires {timed.expires_at.strftime('%H:%M UTC')})",
                    "fallback": None,
                    "remaining_credit": round(timed.remaining_usd, 6),
                    "approval_type": APPROVAL_TYPE_TIMED,
                }

            # 3. Check step approvals
            step = self._check_step_approvals(provider, estimated_cost_usd)
            if step:
                return {
                    "allowed": True,
                    "reason": f"step_approval ({step.steps_remaining} steps left)",
                    "fallback": None,
                    "remaining_credit": round(step.remaining_usd, 6),
                    "approval_type": APPROVAL_TYPE_STEPS,
                }

            # 4. Check task approvals
            task_appr = self._check_task_approvals(provider, estimated_cost_usd, task_id)
            if task_appr:
                return {
                    "allowed": True,
                    "reason": f"task_approval (task: {task_appr.task_id})",
                    "fallback": None,
                    "remaining_credit": round(task_appr.remaining_usd, 6),
                    "approval_type": APPROVAL_TYPE_TASK,
                }

            # Nothing covers this — BLOCK and request approval
            self._log_event("approval_needed", {
                "provider": provider,
                "estimated_cost": estimated_cost_usd,
                "available_credit": available,
                "shortfall": round(estimated_cost_usd - available, 6),
                "task_type": task_type,
                "model": model,
                "task_id": task_id,
                "message": f"Need ${estimated_cost_usd:.4f} but only ${available:.4f} credit remaining for {provider}. Approve more spending or use Ollama.",
            })
            return {
                "allowed": False,
                "reason": f"Credit exhausted for {provider}: need ${estimated_cost_usd:.4f}, have ${available:.4f}. Falling back to Ollama. Run `python cli.py spending approve {provider} <amount>` to add credits.",
                "fallback": "ollama",
                "remaining_credit": round(available, 6),
                "approval_type": None,
            }

    def record_spend(
        self,
        provider: str,
        actual_cost_usd: float,
        model: str = "",
        task_type: str = "",
        task_id: str = "",
    ) -> Dict[str, Any]:
        """
        Record actual spend after a successful API call.
        Deducts from the approval source that authorized the call.
        Also tracks daily spend.
        """
        provider = provider.lower().strip()
        if provider == "ollama" or provider not in PAID_PROVIDERS:
            return {"provider": provider, "cost": 0.0, "remaining": float("inf")}

        with self._lock:
            # Track daily spending
            self._daily_budget.record_daily_spend(provider, actual_cost_usd)

            # Try to deduct from approval sources in order
            deducted_from = "credits"

            # 1. Check timed approvals
            timed = self._check_timed_approvals(provider, actual_cost_usd)
            if timed and self._credits.get(provider, 0.0) < actual_cost_usd:
                timed.spent_usd += actual_cost_usd
                deducted_from = "timed_approval"
                remaining = timed.remaining_usd
            # 2. Check step approvals
            elif (step := self._check_step_approvals(provider, actual_cost_usd)) and self._credits.get(provider, 0.0) < actual_cost_usd:
                step.spent_usd += actual_cost_usd
                step.steps_used += 1
                deducted_from = "step_approval"
                remaining = step.remaining_usd
            # 3. Check task approvals
            elif (task_appr := self._check_task_approvals(provider, actual_cost_usd, task_id)) and self._credits.get(provider, 0.0) < actual_cost_usd:
                task_appr.spent_usd += actual_cost_usd
                deducted_from = "task_approval"
                remaining = task_appr.remaining_usd
            else:
                # Deduct from basic credits
                old_balance = self._credits.get(provider, 0.0)
                new_balance = max(0.0, old_balance - actual_cost_usd)
                self._credits[provider] = new_balance
                remaining = new_balance

            self._save_state()

        # If it was a step approval, count step even if deducted from credits
        for sa in self._step_approvals:
            if sa.provider == provider and sa.is_active and deducted_from != "step_approval":
                sa.steps_used += 1
                break

        self._log_event("spend_recorded", {
            "provider": provider,
            "cost_usd": round(actual_cost_usd, 6),
            "remaining": round(remaining, 6),
            "deducted_from": deducted_from,
            "model": model,
            "task_type": task_type,
            "task_id": task_id,
            "daily_total": round(self._daily_budget.total_spent_today, 6),
        })

        return {
            "provider": provider,
            "cost": round(actual_cost_usd, 6),
            "remaining": round(remaining, 6),
            "deducted_from": deducted_from,
        }

    # ── Approval Methods ────────────────────────────────────────────────

    def approve_spending(
        self,
        provider: str,
        amount_usd: float,
        approved_by: str = "human",
    ) -> Dict[str, Any]:
        """
        Human approves additional spending for a provider.
        Adds credits to the balance (permanent until spent).
        """
        provider = provider.lower().strip()
        if provider not in PAID_PROVIDERS:
            return {"ok": False, "error": f"Unknown provider: {provider}"}

        with self._lock:
            old_balance = self._credits.get(provider, 0.0)
            new_balance = old_balance + amount_usd
            self._credits[provider] = new_balance
            self._save_state()

        self._log_event("spending_approved", {
            "provider": provider,
            "amount_usd": round(amount_usd, 6),
            "old_balance": round(old_balance, 6),
            "new_balance": round(new_balance, 6),
            "approved_by": approved_by,
            "approval_type": APPROVAL_TYPE_CREDITS,
        })

        return {
            "ok": True,
            "provider": provider,
            "added_usd": round(amount_usd, 6),
            "new_balance": round(new_balance, 6),
        }

    def approve_timed(
        self,
        provider: str,
        amount_usd: float,
        duration_minutes: int = 60,
        approved_by: str = "human",
        task_id: str = "",
    ) -> Dict[str, Any]:
        """
        Approve spending for a time window.
        Duration presets: 30 (half hour), 60 (1 hour), "eod" (end of day).
        """
        provider = provider.lower().strip()
        if provider not in PAID_PROVIDERS:
            return {"ok": False, "error": f"Unknown provider: {provider}"}
        if duration_minutes <= 0:
            return {"ok": False, "error": "Duration must be positive"}

        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(minutes=duration_minutes)

        approval = TimedApproval(
            provider=provider,
            amount_usd=amount_usd,
            expires_at=expires_at,
            approved_by=approved_by,
            task_id=task_id,
        )

        with self._lock:
            self._timed_approvals.append(approval)

        self._log_event("timed_approval_granted", {
            "provider": provider,
            "amount_usd": round(amount_usd, 6),
            "duration_minutes": duration_minutes,
            "expires_at": expires_at.isoformat(),
            "approved_by": approved_by,
            "task_id": task_id,
        })

        return {
            "ok": True,
            "provider": provider,
            "amount_usd": round(amount_usd, 6),
            "duration_minutes": duration_minutes,
            "expires_at": expires_at.isoformat(),
        }

    def approve_timed_eod(
        self,
        provider: str,
        amount_usd: float,
        approved_by: str = "human",
    ) -> Dict[str, Any]:
        """Approve spending until end of day (23:59 UTC)."""
        now = datetime.now(timezone.utc)
        eod = now.replace(hour=23, minute=59, second=59, microsecond=0)
        if eod <= now:
            # Already past EOD — extend to next day
            eod += timedelta(days=1)
        remaining_minutes = int((eod - now).total_seconds() / 60)
        return self.approve_timed(
            provider=provider,
            amount_usd=amount_usd,
            duration_minutes=max(1, remaining_minutes),
            approved_by=approved_by,
        )

    def approve_steps(
        self,
        provider: str,
        amount_usd: float,
        max_steps: int = 10,
        approved_by: str = "human",
        task_id: str = "",
    ) -> Dict[str, Any]:
        """
        Approve spending for the next N API calls (steps).
        Once max_steps reached OR amount_usd spent, approval expires.
        """
        provider = provider.lower().strip()
        if provider not in PAID_PROVIDERS:
            return {"ok": False, "error": f"Unknown provider: {provider}"}
        if max_steps <= 0:
            return {"ok": False, "error": "max_steps must be positive"}

        approval = StepApproval(
            provider=provider,
            amount_usd=amount_usd,
            max_steps=max_steps,
            approved_by=approved_by,
            task_id=task_id,
        )

        with self._lock:
            self._step_approvals.append(approval)

        self._log_event("step_approval_granted", {
            "provider": provider,
            "amount_usd": round(amount_usd, 6),
            "max_steps": max_steps,
            "approved_by": approved_by,
            "task_id": task_id,
        })

        return {
            "ok": True,
            "provider": provider,
            "amount_usd": round(amount_usd, 6),
            "max_steps": max_steps,
        }

    def approve_task(
        self,
        provider: str,
        amount_usd: float,
        task_id: str,
        approved_by: str = "human",
    ) -> Dict[str, Any]:
        """
        Approve spending until a specific task/goal completes.
        Call complete_task() when the task is done to revoke the approval.
        """
        provider = provider.lower().strip()
        if provider not in PAID_PROVIDERS:
            return {"ok": False, "error": f"Unknown provider: {provider}"}
        if not task_id:
            return {"ok": False, "error": "task_id is required"}

        approval = TaskApproval(
            provider=provider,
            amount_usd=amount_usd,
            task_id=task_id,
            approved_by=approved_by,
        )

        with self._lock:
            self._task_approvals.append(approval)

        self._log_event("task_approval_granted", {
            "provider": provider,
            "amount_usd": round(amount_usd, 6),
            "task_id": task_id,
            "approved_by": approved_by,
        })

        return {
            "ok": True,
            "provider": provider,
            "amount_usd": round(amount_usd, 6),
            "task_id": task_id,
        }

    def complete_task(self, task_id: str) -> Dict[str, Any]:
        """Mark a task as complete — revokes any task-scoped approvals."""
        revoked = 0
        total_unspent = 0.0
        for approval in self._task_approvals:
            if approval.task_id == task_id and not approval.completed:
                total_unspent += approval.remaining_usd
                approval.complete()
                revoked += 1

        if revoked > 0:
            self._log_event("task_completed", {
                "task_id": task_id,
                "approvals_revoked": revoked,
                "unspent_returned": round(total_unspent, 6),
            })

        return {
            "ok": True,
            "task_id": task_id,
            "approvals_revoked": revoked,
            "unspent_returned": round(total_unspent, 6),
        }

    # ── Daily Budget ────────────────────────────────────────────────────

    def set_daily_cap(self, cap_usd: float) -> Dict[str, Any]:
        """Set or update the daily spend cap."""
        old_cap = self._daily_budget.cap_usd
        self._daily_budget.cap_usd = max(0.0, cap_usd)
        self._save_state()

        self._log_event("daily_cap_set", {
            "old_cap": round(old_cap, 6),
            "new_cap": round(self._daily_budget.cap_usd, 6),
        })

        return {
            "ok": True,
            "old_cap": round(old_cap, 6),
            "new_cap": round(self._daily_budget.cap_usd, 6),
            "remaining_today": round(self._daily_budget.remaining_today, 6),
        }

    def set_task_priority(self, task_type: str, priority: str) -> Dict[str, Any]:
        """Set priority for a task type (affects budget allocation)."""
        if priority not in PRIORITY_WEIGHTS:
            return {"ok": False, "error": f"Invalid priority: {priority}. Use: critical, high, normal, low"}
        self._daily_budget.set_priority(task_type, priority)
        self._save_state()
        return {"ok": True, "task_type": task_type, "priority": priority}

    def get_budget_plan(self, task_types: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Pre-planning analysis: show how budget would be allocated across tasks.
        Call this BEFORE spending to see the optimal allocation.
        """
        if self._daily_budget.cap_usd <= 0:
            return {"ok": True, "message": "No daily cap set — unlimited spending", "allocations": {}}

        if not task_types:
            task_types = list(self._daily_budget._priorities.keys()) or ["default"]

        allocations = {}
        for task_type in task_types:
            allocation = self._daily_budget.get_budget_allocation(task_type)
            priority = self._daily_budget._priorities.get(task_type, PRIORITY_NORMAL)
            allocations[task_type] = {
                "priority": priority,
                "weight": PRIORITY_WEIGHTS.get(priority, 1.0),
                "allocated_usd": round(allocation, 6),
            }

        return {
            "ok": True,
            "daily_cap": round(self._daily_budget.cap_usd, 6),
            "remaining_today": round(self._daily_budget.remaining_today, 6),
            "total_spent_today": round(self._daily_budget.total_spent_today, 6),
            "allocations": allocations,
        }

    # ── Mode & State ────────────────────────────────────────────────────

    def set_mode(self, mode: str) -> Dict[str, Any]:
        """Change spending gate mode."""
        mode = mode.lower().strip()
        if mode not in ("gate", "auto", "block"):
            return {"ok": False, "error": f"Invalid mode: {mode}. Use gate/auto/block"}

        old_mode = self.mode
        self.mode = mode
        self._save_state()

        self._log_event("mode_changed", {
            "old_mode": old_mode,
            "new_mode": mode,
        })

        return {"ok": True, "old_mode": old_mode, "new_mode": mode}

    def reset_credits(self) -> Dict[str, Any]:
        """Reset credits to env var defaults."""
        with self._lock:
            self._credits = self._default_credits()
            self._save_state()

        self._log_event("credits_reset", {"credits": dict(self._credits)})
        return {"ok": True, "credits": dict(self._credits)}

    def revoke_all_approvals(self) -> Dict[str, Any]:
        """Emergency: revoke all active timed/step/task approvals."""
        count = len(self._timed_approvals) + len(self._step_approvals) + len(self._task_approvals)
        self._timed_approvals.clear()
        self._step_approvals.clear()
        for ta in self._task_approvals:
            ta.complete()
        self._task_approvals.clear()

        self._log_event("all_approvals_revoked", {"count": count})
        return {"ok": True, "revoked": count}

    def status(self) -> Dict[str, Any]:
        """Return full spending gate status."""
        self._cleanup_expired()
        pending_approvals = self._count_pending_approvals()

        return {
            "mode": self.mode,
            "credits": {k: round(v, 6) for k, v in self._credits.items()},
            "total_credit_remaining": round(sum(self._credits.values()), 6),
            "pending_approvals": pending_approvals,
            "active_timed_approvals": [a.to_dict() for a in self._timed_approvals if a.is_active],
            "active_step_approvals": [a.to_dict() for a in self._step_approvals if a.is_active],
            "active_task_approvals": [a.to_dict() for a in self._task_approvals if a.is_active],
            "daily_budget": self._daily_budget.to_dict(),
            "state_path": str(self.state_path),
            "log_path": str(self.log_path),
        }

    def _count_pending_approvals(self) -> int:
        """Count unresolved approval requests."""
        if not self.log_path.exists():
            return 0
        count = 0
        approvals = set()
        try:
            with open(self.log_path) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    event = entry.get("event", "")
                    provider = entry.get("provider", "")
                    if event == "approval_needed":
                        count += 1
                    elif event == "spending_approved" and provider:
                        approvals.add(provider)
            # Subtract providers that have been approved since
            # (simplified — just tracks if any approval happened)
        except OSError:
            pass
        return max(0, count - len(approvals))

    def get_approval_requests(self, limit: int = 20) -> list[Dict[str, Any]]:
        """Get recent approval requests for the dashboard."""
        if not self.log_path.exists():
            return []

        requests = []
        try:
            with open(self.log_path) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if entry.get("event") == "approval_needed":
                        requests.append(entry)
        except OSError:
            pass

        return requests[-limit:]


def _safe_float(val: Any, default: float = 0.0) -> float:
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


# ── Module singleton ──────────────────────────────────────────────────

_gate: Optional[SpendingGate] = None


def get_spending_gate() -> SpendingGate:
    """Get the global SpendingGate singleton."""
    global _gate
    if _gate is None:
        _gate = SpendingGate()
    return _gate


# Convenience alias
spending_gate = None


def _ensure_gate() -> SpendingGate:
    global spending_gate
    if spending_gate is None:
        spending_gate = get_spending_gate()
    return spending_gate
