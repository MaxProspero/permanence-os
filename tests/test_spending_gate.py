"""Tests for the Spending Gate — human-approval-required spending control."""

import json
import os
import tempfile
import time
from datetime import datetime, timezone, timedelta
from unittest.mock import patch
import pytest
from core.spending_gate import (
    SpendingGate,
    TimedApproval,
    StepApproval,
    TaskApproval,
    DailyBudget,
    APPROVAL_TYPE_CREDITS,
    APPROVAL_TYPE_TIMED,
    APPROVAL_TYPE_STEPS,
    APPROVAL_TYPE_TASK,
    PRIORITY_CRITICAL,
    PRIORITY_HIGH,
    PRIORITY_NORMAL,
    PRIORITY_LOW,
    PRIORITY_WEIGHTS,
)


_PROVIDER_CREDIT_KEYS = [
    "PERMANENCE_ANTHROPIC_CREDIT_USD",
    "PERMANENCE_OPENAI_CREDIT_USD",
    "PERMANENCE_XAI_CREDIT_USD",
    "PERMANENCE_OPENCLAW_CREDIT_USD",
]


@pytest.fixture
def gate(tmp_path):
    """Create a SpendingGate with temp paths and some initial credits."""
    state_path = str(tmp_path / "spending_state.json")
    log_path = str(tmp_path / "spending_gate.jsonl")

    # Save any existing env state that might pollute
    saved = {k: os.environ.pop(k, None) for k in _PROVIDER_CREDIT_KEYS}

    # Set env vars for credits -- $5 per provider explicitly
    os.environ["PERMANENCE_PREPAID_CREDIT_USD"] = "20.00"
    os.environ["PERMANENCE_SPENDING_APPROVAL_MODE"] = "gate"

    g = SpendingGate(state_path=state_path, log_path=log_path)

    yield g

    # Cleanup
    os.environ.pop("PERMANENCE_PREPAID_CREDIT_USD", None)
    os.environ.pop("PERMANENCE_SPENDING_APPROVAL_MODE", None)
    os.environ.pop("PERMANENCE_DAILY_SPEND_CAP_USD", None)
    # Restore any saved provider-specific env vars
    for k, v in saved.items():
        if v is not None:
            os.environ[k] = v
        else:
            os.environ.pop(k, None)


@pytest.fixture
def block_gate(tmp_path):
    """Create a SpendingGate in block mode."""
    saved = {k: os.environ.pop(k, None) for k in _PROVIDER_CREDIT_KEYS}
    os.environ["PERMANENCE_SPENDING_APPROVAL_MODE"] = "block"
    g = SpendingGate(
        state_path=str(tmp_path / "state.json"),
        log_path=str(tmp_path / "log.jsonl"),
    )
    yield g
    os.environ.pop("PERMANENCE_SPENDING_APPROVAL_MODE", None)
    for k, v in saved.items():
        if v is not None:
            os.environ[k] = v
        else:
            os.environ.pop(k, None)


@pytest.fixture
def auto_gate(tmp_path):
    """Create a SpendingGate in auto mode."""
    saved = {k: os.environ.pop(k, None) for k in _PROVIDER_CREDIT_KEYS}
    os.environ["PERMANENCE_SPENDING_APPROVAL_MODE"] = "auto"
    os.environ["PERMANENCE_PREPAID_CREDIT_USD"] = "10.00"
    g = SpendingGate(
        state_path=str(tmp_path / "state.json"),
        log_path=str(tmp_path / "log.jsonl"),
    )
    yield g
    os.environ.pop("PERMANENCE_SPENDING_APPROVAL_MODE", None)
    os.environ.pop("PERMANENCE_PREPAID_CREDIT_USD", None)
    for k, v in saved.items():
        if v is not None:
            os.environ[k] = v
        else:
            os.environ.pop(k, None)


@pytest.fixture
def capped_gate(tmp_path):
    """Create a SpendingGate with a daily cap."""
    saved = {k: os.environ.pop(k, None) for k in _PROVIDER_CREDIT_KEYS}
    os.environ["PERMANENCE_SPENDING_APPROVAL_MODE"] = "gate"
    os.environ["PERMANENCE_PREPAID_CREDIT_USD"] = "100.00"
    os.environ["PERMANENCE_DAILY_SPEND_CAP_USD"] = "10.00"
    g = SpendingGate(
        state_path=str(tmp_path / "state.json"),
        log_path=str(tmp_path / "log.jsonl"),
    )
    yield g
    os.environ.pop("PERMANENCE_SPENDING_APPROVAL_MODE", None)
    os.environ.pop("PERMANENCE_PREPAID_CREDIT_USD", None)
    os.environ.pop("PERMANENCE_DAILY_SPEND_CAP_USD", None)
    for k, v in saved.items():
        if v is not None:
            os.environ[k] = v
        else:
            os.environ.pop(k, None)


# ── Check (Gate Mode) ────────────────────────────────────────────────────

class TestGateMode:
    def test_ollama_always_allowed(self, gate):
        result = gate.check(provider="ollama", estimated_cost_usd=0.0)
        assert result["allowed"] is True
        assert result["reason"] == "free_provider"

    def test_within_credits_allowed(self, gate):
        result = gate.check(provider="anthropic", estimated_cost_usd=1.00)
        assert result["allowed"] is True
        assert result["reason"] == "within_credits"

    def test_exceeds_credits_blocked(self, gate):
        # Default credits = 20 / 4 providers = 5 each
        result = gate.check(provider="anthropic", estimated_cost_usd=10.00)
        assert result["allowed"] is False
        assert result["fallback"] == "ollama"
        assert "Credit exhausted" in result["reason"]

    def test_exactly_at_credit_limit_allowed(self, gate):
        # Credits = $5 per provider
        result = gate.check(provider="anthropic", estimated_cost_usd=5.00)
        assert result["allowed"] is True

    def test_spend_deducts_credits(self, gate):
        # Start with $5 credit for anthropic
        gate.record_spend(provider="anthropic", actual_cost_usd=3.00)
        result = gate.check(provider="anthropic", estimated_cost_usd=3.00)
        assert result["allowed"] is False  # only $2 left

    def test_spend_then_approve_then_spend(self, gate):
        # Spend down credits
        gate.record_spend(provider="anthropic", actual_cost_usd=5.00)
        assert gate.check(provider="anthropic", estimated_cost_usd=1.00)["allowed"] is False

        # Human approves $10 more
        result = gate.approve_spending(provider="anthropic", amount_usd=10.00)
        assert result["ok"] is True
        assert result["new_balance"] == 10.00

        # Now spending works again
        assert gate.check(provider="anthropic", estimated_cost_usd=5.00)["allowed"] is True

    def test_different_providers_independent(self, gate):
        # Exhaust anthropic credits
        gate.record_spend(provider="anthropic", actual_cost_usd=5.00)
        assert gate.check(provider="anthropic", estimated_cost_usd=1.00)["allowed"] is False

        # OpenAI still has credits
        assert gate.check(provider="openai", estimated_cost_usd=3.00)["allowed"] is True

    def test_check_includes_approval_type(self, gate):
        result = gate.check(provider="anthropic", estimated_cost_usd=1.00)
        assert "approval_type" in result
        assert result["approval_type"] == APPROVAL_TYPE_CREDITS


# ── Block Mode ────────────────────────────────────────────────────────────

class TestBlockMode:
    def test_block_mode_blocks_all_paid(self, block_gate):
        result = block_gate.check(provider="anthropic", estimated_cost_usd=0.01)
        assert result["allowed"] is False
        assert result["fallback"] == "ollama"

    def test_block_mode_allows_ollama(self, block_gate):
        result = block_gate.check(provider="ollama", estimated_cost_usd=0.0)
        assert result["allowed"] is True


# ── Auto Mode ─────────────────────────────────────────────────────────────

class TestAutoMode:
    def test_auto_mode_allows_everything(self, auto_gate):
        result = auto_gate.check(provider="anthropic", estimated_cost_usd=100.00)
        assert result["allowed"] is True
        assert result["reason"] == "auto_mode"


# ── Approval Flow ─────────────────────────────────────────────────────────

class TestApprovalFlow:
    def test_approve_adds_credits(self, gate):
        result = gate.approve_spending(provider="anthropic", amount_usd=20.00)
        assert result["ok"] is True
        assert result["new_balance"] == 25.00  # 5 initial + 20 approved

    def test_approve_invalid_provider(self, gate):
        result = gate.approve_spending(provider="fake", amount_usd=10.00)
        assert result["ok"] is False

    def test_approval_logged(self, gate):
        gate.approve_spending(provider="openai", amount_usd=5.00)
        with open(gate.log_path) as f:
            lines = [json.loads(l) for l in f if l.strip()]
        assert any(e["event"] == "spending_approved" for e in lines)

    def test_blocked_call_logged(self, gate):
        gate.record_spend(provider="anthropic", actual_cost_usd=5.00)
        gate.check(provider="anthropic", estimated_cost_usd=10.00)
        with open(gate.log_path) as f:
            lines = [json.loads(l) for l in f if l.strip()]
        assert any(e["event"] == "approval_needed" for e in lines)


# ── Timed Approvals ──────────────────────────────────────────────────────

class TestTimedApprovals:
    def test_timed_approval_allows_spending(self, gate):
        # Exhaust credits
        gate.record_spend(provider="anthropic", actual_cost_usd=5.00)
        assert gate.check(provider="anthropic", estimated_cost_usd=1.00)["allowed"] is False

        # Approve for 60 minutes
        result = gate.approve_timed(provider="anthropic", amount_usd=10.00, duration_minutes=60)
        assert result["ok"] is True
        assert result["duration_minutes"] == 60

        # Now spending works
        check = gate.check(provider="anthropic", estimated_cost_usd=5.00)
        assert check["allowed"] is True
        assert check["approval_type"] == APPROVAL_TYPE_TIMED

    def test_timed_approval_expires(self, gate):
        gate.record_spend(provider="anthropic", actual_cost_usd=5.00)

        # Create an approval that's already expired
        now = datetime.now(timezone.utc)
        expired = TimedApproval(
            provider="anthropic",
            amount_usd=10.00,
            expires_at=now - timedelta(minutes=1),
        )
        gate._timed_approvals.append(expired)

        # Should still be blocked (expired)
        assert gate.check(provider="anthropic", estimated_cost_usd=1.00)["allowed"] is False

    def test_timed_approval_budget_limited(self, gate):
        gate.record_spend(provider="anthropic", actual_cost_usd=5.00)

        # Approve $2 for 60 minutes
        gate.approve_timed(provider="anthropic", amount_usd=2.00, duration_minutes=60)

        # $1 should work
        assert gate.check(provider="anthropic", estimated_cost_usd=1.00)["allowed"] is True
        # $5 should fail (only $2 approved)
        assert gate.check(provider="anthropic", estimated_cost_usd=5.00)["allowed"] is False

    def test_timed_approval_invalid_provider(self, gate):
        result = gate.approve_timed(provider="fake", amount_usd=10.00)
        assert result["ok"] is False

    def test_timed_approval_invalid_duration(self, gate):
        result = gate.approve_timed(provider="anthropic", amount_usd=10.00, duration_minutes=0)
        assert result["ok"] is False

    def test_timed_approval_eod(self, gate):
        gate.record_spend(provider="anthropic", actual_cost_usd=5.00)
        result = gate.approve_timed_eod(provider="anthropic", amount_usd=20.00)
        assert result["ok"] is True
        assert gate.check(provider="anthropic", estimated_cost_usd=10.00)["allowed"] is True

    def test_timed_approval_logged(self, gate):
        gate.approve_timed(provider="anthropic", amount_usd=10.00, duration_minutes=30)
        with open(gate.log_path) as f:
            lines = [json.loads(l) for l in f if l.strip()]
        assert any(e["event"] == "timed_approval_granted" for e in lines)

    def test_timed_approval_spend_deducts(self, gate):
        gate.record_spend(provider="anthropic", actual_cost_usd=5.00)
        gate.approve_timed(provider="anthropic", amount_usd=10.00, duration_minutes=60)

        # Record spend against timed approval
        result = gate.record_spend(provider="anthropic", actual_cost_usd=3.00)
        assert result["deducted_from"] == "timed_approval"
        assert result["remaining"] == 7.00  # 10 - 3


# ── Step Approvals ────────────────────────────────────────────────────────

class TestStepApprovals:
    def test_step_approval_allows_spending(self, gate):
        gate.record_spend(provider="anthropic", actual_cost_usd=5.00)
        assert gate.check(provider="anthropic", estimated_cost_usd=1.00)["allowed"] is False

        # Approve next 5 steps
        result = gate.approve_steps(provider="anthropic", amount_usd=10.00, max_steps=5)
        assert result["ok"] is True
        assert result["max_steps"] == 5

        check = gate.check(provider="anthropic", estimated_cost_usd=1.00)
        assert check["allowed"] is True
        assert check["approval_type"] == APPROVAL_TYPE_STEPS

    def test_step_approval_counts_down(self, gate):
        gate.record_spend(provider="anthropic", actual_cost_usd=5.00)
        gate.approve_steps(provider="anthropic", amount_usd=50.00, max_steps=3)

        # Use 3 steps
        for i in range(3):
            gate.record_spend(provider="anthropic", actual_cost_usd=0.10)

        # Step approval should be exhausted now
        assert gate._step_approvals[0].steps_remaining == 0
        assert gate._step_approvals[0].is_active is False

    def test_step_approval_budget_limited(self, gate):
        gate.record_spend(provider="anthropic", actual_cost_usd=5.00)
        gate.approve_steps(provider="anthropic", amount_usd=1.00, max_steps=100)

        # Within budget
        assert gate.check(provider="anthropic", estimated_cost_usd=0.50)["allowed"] is True
        # Over budget
        assert gate.check(provider="anthropic", estimated_cost_usd=5.00)["allowed"] is False

    def test_step_approval_invalid_provider(self, gate):
        result = gate.approve_steps(provider="fake", amount_usd=10.00)
        assert result["ok"] is False

    def test_step_approval_invalid_steps(self, gate):
        result = gate.approve_steps(provider="anthropic", amount_usd=10.00, max_steps=0)
        assert result["ok"] is False

    def test_step_approval_logged(self, gate):
        gate.approve_steps(provider="anthropic", amount_usd=10.00, max_steps=5)
        with open(gate.log_path) as f:
            lines = [json.loads(l) for l in f if l.strip()]
        assert any(e["event"] == "step_approval_granted" for e in lines)


# ── Task Approvals ────────────────────────────────────────────────────────

class TestTaskApprovals:
    def test_task_approval_allows_spending(self, gate):
        gate.record_spend(provider="anthropic", actual_cost_usd=5.00)
        assert gate.check(provider="anthropic", estimated_cost_usd=1.00)["allowed"] is False

        result = gate.approve_task(provider="anthropic", amount_usd=20.00, task_id="build-feature-x")
        assert result["ok"] is True
        assert result["task_id"] == "build-feature-x"

        check = gate.check(provider="anthropic", estimated_cost_usd=5.00, task_id="build-feature-x")
        assert check["allowed"] is True
        assert check["approval_type"] == APPROVAL_TYPE_TASK

    def test_task_approval_revoked_on_complete(self, gate):
        gate.record_spend(provider="anthropic", actual_cost_usd=5.00)
        gate.approve_task(provider="anthropic", amount_usd=20.00, task_id="my-task")

        # Complete the task
        result = gate.complete_task("my-task")
        assert result["ok"] is True
        assert result["approvals_revoked"] == 1

        # No longer approved
        assert gate.check(provider="anthropic", estimated_cost_usd=1.00, task_id="my-task")["allowed"] is False

    def test_task_approval_tracks_unspent(self, gate):
        gate.record_spend(provider="anthropic", actual_cost_usd=5.00)
        gate.approve_task(provider="anthropic", amount_usd=20.00, task_id="my-task")

        # Spend $5 of the $20
        gate.record_spend(provider="anthropic", actual_cost_usd=5.00, task_id="my-task")

        # Complete — should report $15 unspent
        result = gate.complete_task("my-task")
        assert result["unspent_returned"] == 15.00

    def test_task_approval_invalid_provider(self, gate):
        result = gate.approve_task(provider="fake", amount_usd=10.00, task_id="t")
        assert result["ok"] is False

    def test_task_approval_requires_task_id(self, gate):
        result = gate.approve_task(provider="anthropic", amount_usd=10.00, task_id="")
        assert result["ok"] is False

    def test_task_approval_logged(self, gate):
        gate.approve_task(provider="anthropic", amount_usd=10.00, task_id="test-task")
        with open(gate.log_path) as f:
            lines = [json.loads(l) for l in f if l.strip()]
        assert any(e["event"] == "task_approval_granted" for e in lines)

    def test_complete_nonexistent_task(self, gate):
        result = gate.complete_task("nonexistent")
        assert result["ok"] is True
        assert result["approvals_revoked"] == 0


# ── Daily Budget Cap ──────────────────────────────────────────────────────

class TestDailyBudget:
    def test_daily_cap_blocks_when_exceeded(self, capped_gate):
        # Cap is $10/day, credits are high ($33/provider)
        # Spend $9 — should still work
        capped_gate.record_spend(provider="anthropic", actual_cost_usd=9.00)
        result = capped_gate.check(provider="anthropic", estimated_cost_usd=0.50)
        assert result["allowed"] is True

        # Spend $2 more — should push past cap
        result = capped_gate.check(provider="anthropic", estimated_cost_usd=2.00)
        assert result["allowed"] is False
        assert "Daily spend cap" in result["reason"]

    def test_daily_cap_allows_within_budget(self, capped_gate):
        result = capped_gate.check(provider="anthropic", estimated_cost_usd=5.00)
        assert result["allowed"] is True

    def test_set_daily_cap(self, gate):
        result = gate.set_daily_cap(25.00)
        assert result["ok"] is True
        assert result["new_cap"] == 25.00

    def test_daily_budget_resets_on_new_day(self):
        budget = DailyBudget(cap_usd=50.00)
        budget.record_daily_spend("anthropic", 30.00)
        assert budget.total_spent_today == 30.00

        # Simulate next day
        budget._date = "2020-01-01"
        assert budget.total_spent_today == 0.0

    def test_daily_budget_no_cap_is_unlimited(self):
        budget = DailyBudget(cap_usd=0.0)
        assert budget.remaining_today == float("inf")
        assert budget.would_exceed_cap(999999) is False

    def test_daily_budget_tracks_by_provider(self, capped_gate):
        capped_gate.record_spend(provider="anthropic", actual_cost_usd=3.00)
        capped_gate.record_spend(provider="openai", actual_cost_usd=2.00)
        status = capped_gate.status()
        assert status["daily_budget"]["total_spent_today"] == 5.00
        assert status["daily_budget"]["spend_by_provider"]["anthropic"] == 3.00
        assert status["daily_budget"]["spend_by_provider"]["openai"] == 2.00

    def test_daily_cap_logged(self, capped_gate):
        # Spend up to the cap
        capped_gate.record_spend(provider="anthropic", actual_cost_usd=10.00)
        capped_gate.check(provider="anthropic", estimated_cost_usd=1.00)
        with open(capped_gate.log_path) as f:
            lines = [json.loads(l) for l in f if l.strip()]
        assert any(e["event"] == "daily_cap_exceeded" for e in lines)


# ── Priority-Based Budget Allocation ─────────────────────────────────────

class TestPriorityAllocation:
    def test_set_task_priority(self, gate):
        result = gate.set_task_priority("research", PRIORITY_HIGH)
        assert result["ok"] is True
        assert result["priority"] == PRIORITY_HIGH

    def test_set_invalid_priority(self, gate):
        result = gate.set_task_priority("research", "yolo")
        assert result["ok"] is False

    def test_budget_plan_with_priorities(self, gate):
        gate.set_daily_cap(30.00)
        gate.set_task_priority("research", PRIORITY_CRITICAL)
        gate.set_task_priority("classification", PRIORITY_LOW)
        gate.set_task_priority("execution", PRIORITY_NORMAL)

        plan = gate.get_budget_plan()
        assert plan["ok"] is True
        assert plan["daily_cap"] == 30.00

        # Critical should get more than normal, which gets more than low
        allocs = plan["allocations"]
        assert allocs["research"]["allocated_usd"] > allocs["execution"]["allocated_usd"]
        assert allocs["execution"]["allocated_usd"] > allocs["classification"]["allocated_usd"]

    def test_budget_plan_no_cap(self, gate):
        plan = gate.get_budget_plan()
        assert plan["ok"] is True
        assert plan["message"] == "No daily cap set — unlimited spending"

    def test_priority_weights_correct(self):
        assert PRIORITY_WEIGHTS[PRIORITY_CRITICAL] > PRIORITY_WEIGHTS[PRIORITY_HIGH]
        assert PRIORITY_WEIGHTS[PRIORITY_HIGH] > PRIORITY_WEIGHTS[PRIORITY_NORMAL]
        assert PRIORITY_WEIGHTS[PRIORITY_NORMAL] > PRIORITY_WEIGHTS[PRIORITY_LOW]


# ── Status and State ──────────────────────────────────────────────────────

class TestStatus:
    def test_status_returns_all_fields(self, gate):
        status = gate.status()
        assert "mode" in status
        assert "credits" in status
        assert "total_credit_remaining" in status
        assert "active_timed_approvals" in status
        assert "active_step_approvals" in status
        assert "active_task_approvals" in status
        assert "daily_budget" in status
        assert status["mode"] == "gate"

    def test_status_reflects_spending(self, gate):
        gate.record_spend(provider="anthropic", actual_cost_usd=2.00)
        status = gate.status()
        assert status["credits"]["anthropic"] < 5.00

    def test_state_persists(self, gate):
        gate.record_spend(provider="anthropic", actual_cost_usd=3.00)

        # Create new gate with same paths
        gate2 = SpendingGate(
            state_path=str(gate.state_path),
            log_path=str(gate.log_path),
        )
        assert gate2._credits["anthropic"] == gate._credits["anthropic"]

    def test_reset_credits(self, gate):
        gate.record_spend(provider="anthropic", actual_cost_usd=5.00)
        gate.reset_credits()
        assert gate._credits["anthropic"] == 5.00  # back to default

    def test_status_shows_active_approvals(self, gate):
        gate.approve_timed(provider="anthropic", amount_usd=10.00, duration_minutes=60)
        gate.approve_steps(provider="openai", amount_usd=5.00, max_steps=10)
        gate.approve_task(provider="xai", amount_usd=15.00, task_id="my-task")

        status = gate.status()
        assert len(status["active_timed_approvals"]) == 1
        assert len(status["active_step_approvals"]) == 1
        assert len(status["active_task_approvals"]) == 1


# ── Mode Changes ──────────────────────────────────────────────────────────

class TestModeChanges:
    def test_set_mode_valid(self, gate):
        result = gate.set_mode("block")
        assert result["ok"] is True
        assert gate.mode == "block"

    def test_set_mode_invalid(self, gate):
        result = gate.set_mode("yolo")
        assert result["ok"] is False

    def test_mode_change_logged(self, gate):
        gate.set_mode("auto")
        with open(gate.log_path) as f:
            lines = [json.loads(l) for l in f if l.strip()]
        assert any(e["event"] == "mode_changed" for e in lines)


# ── Record Spend ──────────────────────────────────────────────────────────

class TestRecordSpend:
    def test_record_spend_returns_remaining(self, gate):
        result = gate.record_spend(provider="anthropic", actual_cost_usd=1.00)
        assert result["remaining"] == 4.00

    def test_record_spend_ollama_free(self, gate):
        result = gate.record_spend(provider="ollama", actual_cost_usd=0.0)
        assert result["cost"] == 0.0

    def test_record_spend_cannot_go_negative(self, gate):
        result = gate.record_spend(provider="anthropic", actual_cost_usd=100.00)
        assert result["remaining"] == 0.0  # clamped to 0, not negative

    def test_record_spend_tracks_daily(self, gate):
        gate.record_spend(provider="anthropic", actual_cost_usd=1.00)
        gate.record_spend(provider="anthropic", actual_cost_usd=2.00)
        assert gate._daily_budget.total_spent_today == 3.00

    def test_record_spend_includes_deducted_from(self, gate):
        result = gate.record_spend(provider="anthropic", actual_cost_usd=1.00)
        assert "deducted_from" in result


# ── Revoke All Approvals ─────────────────────────────────────────────────

class TestRevokeAll:
    def test_revoke_all_clears_everything(self, gate):
        gate.approve_timed(provider="anthropic", amount_usd=10.00, duration_minutes=60)
        gate.approve_steps(provider="openai", amount_usd=5.00, max_steps=10)
        gate.approve_task(provider="xai", amount_usd=15.00, task_id="t1")

        result = gate.revoke_all_approvals()
        assert result["ok"] is True
        assert result["revoked"] == 3

        status = gate.status()
        assert len(status["active_timed_approvals"]) == 0
        assert len(status["active_step_approvals"]) == 0
        assert len(status["active_task_approvals"]) == 0

    def test_revoke_all_empty(self, gate):
        result = gate.revoke_all_approvals()
        assert result["ok"] is True
        assert result["revoked"] == 0

    def test_revoke_all_logged(self, gate):
        gate.approve_timed(provider="anthropic", amount_usd=10.00, duration_minutes=60)
        gate.revoke_all_approvals()
        with open(gate.log_path) as f:
            lines = [json.loads(l) for l in f if l.strip()]
        assert any(e["event"] == "all_approvals_revoked" for e in lines)


# ── Approval Data Classes ────────────────────────────────────────────────

class TestApprovalDataClasses:
    def test_timed_approval_to_dict(self):
        now = datetime.now(timezone.utc)
        approval = TimedApproval(
            provider="anthropic",
            amount_usd=10.00,
            expires_at=now + timedelta(hours=1),
        )
        d = approval.to_dict()
        assert d["type"] == APPROVAL_TYPE_TIMED
        assert d["provider"] == "anthropic"
        assert d["amount_usd"] == 10.00
        assert d["is_active"] is True

    def test_timed_approval_expired(self):
        approval = TimedApproval(
            provider="anthropic",
            amount_usd=10.00,
            expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
        )
        assert approval.is_expired is True
        assert approval.is_active is False

    def test_step_approval_to_dict(self):
        approval = StepApproval(
            provider="openai",
            amount_usd=5.00,
            max_steps=10,
        )
        d = approval.to_dict()
        assert d["type"] == APPROVAL_TYPE_STEPS
        assert d["steps_remaining"] == 10
        assert d["is_active"] is True

    def test_step_approval_exhausted(self):
        approval = StepApproval(
            provider="openai",
            amount_usd=100.00,
            max_steps=2,
        )
        approval.steps_used = 2
        assert approval.steps_remaining == 0
        assert approval.is_active is False

    def test_task_approval_to_dict(self):
        approval = TaskApproval(
            provider="xai",
            amount_usd=15.00,
            task_id="feature-x",
        )
        d = approval.to_dict()
        assert d["type"] == APPROVAL_TYPE_TASK
        assert d["task_id"] == "feature-x"
        assert d["is_active"] is True

    def test_task_approval_completed(self):
        approval = TaskApproval(
            provider="xai",
            amount_usd=15.00,
            task_id="feature-x",
        )
        approval.complete()
        assert approval.completed is True
        assert approval.is_active is False

    def test_daily_budget_to_dict(self):
        budget = DailyBudget(cap_usd=30.00)
        budget.record_daily_spend("anthropic", 5.00)
        d = budget.to_dict()
        assert d["cap_usd"] == 30.00
        assert d["total_spent_today"] == 5.00
        assert d["remaining_today"] == 25.00
