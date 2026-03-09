"""Tests for the Spending Gate — human-approval-required spending control."""

import json
import os
import tempfile
import pytest
from core.spending_gate import SpendingGate


@pytest.fixture
def gate(tmp_path):
    """Create a SpendingGate with temp paths and some initial credits."""
    state_path = str(tmp_path / "spending_state.json")
    log_path = str(tmp_path / "spending_gate.jsonl")

    # Set env vars for credits
    os.environ["PERMANENCE_PREPAID_CREDIT_USD"] = "15.00"
    os.environ["PERMANENCE_SPENDING_APPROVAL_MODE"] = "gate"

    g = SpendingGate(state_path=state_path, log_path=log_path)

    yield g

    # Cleanup
    os.environ.pop("PERMANENCE_PREPAID_CREDIT_USD", None)
    os.environ.pop("PERMANENCE_SPENDING_APPROVAL_MODE", None)


@pytest.fixture
def block_gate(tmp_path):
    """Create a SpendingGate in block mode."""
    os.environ["PERMANENCE_SPENDING_APPROVAL_MODE"] = "block"
    g = SpendingGate(
        state_path=str(tmp_path / "state.json"),
        log_path=str(tmp_path / "log.jsonl"),
    )
    yield g
    os.environ.pop("PERMANENCE_SPENDING_APPROVAL_MODE", None)


@pytest.fixture
def auto_gate(tmp_path):
    """Create a SpendingGate in auto mode."""
    os.environ["PERMANENCE_SPENDING_APPROVAL_MODE"] = "auto"
    os.environ["PERMANENCE_PREPAID_CREDIT_USD"] = "10.00"
    g = SpendingGate(
        state_path=str(tmp_path / "state.json"),
        log_path=str(tmp_path / "log.jsonl"),
    )
    yield g
    os.environ.pop("PERMANENCE_SPENDING_APPROVAL_MODE", None)
    os.environ.pop("PERMANENCE_PREPAID_CREDIT_USD", None)


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
        # Default credits = 15 / 3 providers = 5 each
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


# ── Status and State ──────────────────────────────────────────────────────

class TestStatus:
    def test_status_returns_all_fields(self, gate):
        status = gate.status()
        assert "mode" in status
        assert "credits" in status
        assert "total_credit_remaining" in status
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
