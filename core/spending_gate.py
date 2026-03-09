#!/usr/bin/env python3
"""
Permanence OS — Spending Gate

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

Env vars:
  PERMANENCE_PREPAID_CREDIT_USD       — Total prepaid credits (default: 0)
  PERMANENCE_ANTHROPIC_CREDIT_USD     — Anthropic-specific credits
  PERMANENCE_OPENAI_CREDIT_USD        — OpenAI-specific credits
  PERMANENCE_XAI_CREDIT_USD           — xAI-specific credits
  PERMANENCE_SPENDING_APPROVAL_MODE   — "gate" (default), "auto" (no gate), "block" (block all)
  PERMANENCE_SPENDING_GATE_LOG        — Path to approval request log

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

  # Check remaining credits:
  status = spending_gate.status()
"""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DEFAULT_GATE_LOG = os.path.join(BASE_DIR, "logs", "spending_gate.jsonl")
DEFAULT_GATE_STATE = os.path.join(BASE_DIR, "memory", "working", "spending_gate_state.json")

# Provider list
PAID_PROVIDERS = ("anthropic", "openai", "xai")


class SpendingGate:
    """
    Human-approval-required gate for real-money LLM spending.

    Modes:
      - "gate" (default): Use credits freely, block when exhausted, fall back to Ollama
      - "auto": No gate, spend freely up to budget (use with caution)
      - "block": Block ALL paid API calls (Ollama only)
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
        """Load persisted credit state, or initialize from env vars."""
        if self.state_path.exists():
            try:
                data = json.loads(self.state_path.read_text(encoding="utf-8"))
                if isinstance(data, dict) and "credits" in data:
                    return {k: float(v) for k, v in data["credits"].items()}
            except (json.JSONDecodeError, OSError, TypeError, ValueError):
                pass
        return self._default_credits()

    def _save_state(self) -> None:
        """Persist credit state to disk."""
        try:
            data = {
                "credits": {k: round(v, 6) for k, v in self._credits.items()},
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "mode": self.mode,
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

    def check(
        self,
        provider: str,
        estimated_cost_usd: float,
        task_type: str = "",
        model: str = "",
    ) -> Dict[str, Any]:
        """
        Check if a paid API call is allowed.

        Returns:
          {
            "allowed": True/False,
            "reason": "...",
            "fallback": "ollama" or None,
            "remaining_credit": float,
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
            }

        # Auto mode — allow everything (respects budget limits in model_router)
        if self.mode == "auto":
            return {
                "allowed": True,
                "reason": "auto_mode",
                "fallback": None,
                "remaining_credit": self._credits.get(provider, 0.0),
            }

        # Gate mode — check credits
        with self._lock:
            available = self._credits.get(provider, 0.0)

            if estimated_cost_usd <= available:
                # Within credits — allowed
                return {
                    "allowed": True,
                    "reason": "within_credits",
                    "fallback": None,
                    "remaining_credit": round(available, 6),
                }
            else:
                # Would exceed credits — BLOCK and request approval
                self._log_event("approval_needed", {
                    "provider": provider,
                    "estimated_cost": estimated_cost_usd,
                    "available_credit": available,
                    "shortfall": round(estimated_cost_usd - available, 6),
                    "task_type": task_type,
                    "model": model,
                    "message": f"Need ${estimated_cost_usd:.4f} but only ${available:.4f} credit remaining for {provider}. Approve more spending or use Ollama.",
                })
                return {
                    "allowed": False,
                    "reason": f"Credit exhausted for {provider}: need ${estimated_cost_usd:.4f}, have ${available:.4f}. Falling back to Ollama. Run `python cli.py spending approve {provider} <amount>` to add credits.",
                    "fallback": "ollama",
                    "remaining_credit": round(available, 6),
                }

    def record_spend(
        self,
        provider: str,
        actual_cost_usd: float,
        model: str = "",
        task_type: str = "",
    ) -> Dict[str, Any]:
        """
        Record actual spend after a successful API call.
        Deducts from credit balance.
        """
        provider = provider.lower().strip()
        if provider == "ollama" or provider not in PAID_PROVIDERS:
            return {"provider": provider, "cost": 0.0, "remaining": float("inf")}

        with self._lock:
            old_balance = self._credits.get(provider, 0.0)
            new_balance = max(0.0, old_balance - actual_cost_usd)
            self._credits[provider] = new_balance
            self._save_state()

        self._log_event("spend_recorded", {
            "provider": provider,
            "cost_usd": round(actual_cost_usd, 6),
            "old_balance": round(old_balance, 6),
            "new_balance": round(new_balance, 6),
            "model": model,
            "task_type": task_type,
        })

        return {
            "provider": provider,
            "cost": round(actual_cost_usd, 6),
            "remaining": round(new_balance, 6),
        }

    def approve_spending(
        self,
        provider: str,
        amount_usd: float,
        approved_by: str = "human",
    ) -> Dict[str, Any]:
        """
        Human approves additional spending for a provider.
        Adds credits to the balance.
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
        })

        return {
            "ok": True,
            "provider": provider,
            "added_usd": round(amount_usd, 6),
            "new_balance": round(new_balance, 6),
        }

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

    def status(self) -> Dict[str, Any]:
        """Return full spending gate status."""
        pending_approvals = self._count_pending_approvals()

        return {
            "mode": self.mode,
            "credits": {k: round(v, 6) for k, v in self._credits.items()},
            "total_credit_remaining": round(sum(self._credits.values()), 6),
            "pending_approvals": pending_approvals,
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


# ── Module singleton ──────────────────────────────────────────────────────

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
