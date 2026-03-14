#!/usr/bin/env python3
"""Tests for the Cost Tracker (core/cost_tracker.py).

Covers:
  - Cost estimation from known pricing
  - Session/task/daily/monthly totals
  - Budget status and warnings
  - Ollama calls are free
  - Unknown models return $0 cost
  - CostTracker.record() integration
"""

import os
import sys
import tempfile

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.cost_tracker import estimate_cost, CostTracker  # noqa: E402


# ---------------------------------------------------------------------------
# estimate_cost
# ---------------------------------------------------------------------------

def test_estimate_cost_anthropic_sonnet():
    cost = estimate_cost("claude-sonnet-4-6", "anthropic", 1_000_000, 1_000_000)
    # $3/M input + $15/M output = $18
    assert abs(cost - 18.0) < 0.01


def test_estimate_cost_anthropic_haiku():
    cost = estimate_cost("claude-haiku-4-5-20251001", "anthropic", 1_000_000, 1_000_000)
    # $0.80/M input + $4/M output = $4.80
    assert abs(cost - 4.80) < 0.01


def test_estimate_cost_openai_mini():
    cost = estimate_cost("gpt-4o-mini", "openai", 1_000_000, 1_000_000)
    # $0.15/M input + $0.60/M output = $0.75
    assert abs(cost - 0.75) < 0.01


def test_estimate_cost_ollama_is_free():
    cost = estimate_cost("qwen3:8b", "ollama", 1_000_000, 1_000_000)
    assert cost == 0.0


def test_estimate_cost_unknown_model():
    cost = estimate_cost("some-unknown-model", "unknown_provider", 1000, 500)
    assert cost == 0.0


def test_estimate_cost_zero_tokens():
    cost = estimate_cost("claude-sonnet-4-6", "anthropic", 0, 0)
    assert cost == 0.0


def test_estimate_cost_small_call():
    # 100 input + 50 output tokens for Sonnet
    cost = estimate_cost("claude-sonnet-4-6", "anthropic", 100, 50)
    # (100/1M) * 3 + (50/1M) * 15 = 0.0003 + 0.00075 = 0.00105
    assert abs(cost - 0.00105) < 0.0001


# ---------------------------------------------------------------------------
# CostTracker integration
# ---------------------------------------------------------------------------

def test_tracker_record_returns_cost():
    with tempfile.TemporaryDirectory() as tmp:
        db_path = os.path.join(tmp, "cost_test.db")
        os.environ["PERMANENCE_SYNTHESIS_DB"] = db_path
        tracker = CostTracker(session_id="test_session")
        tracker._db = None  # Force re-init

        metadata = {
            "model": "claude-sonnet-4-6",
            "tier": "sonnet",
            "provider": "anthropic",
            "input_tokens": 1000,
            "output_tokens": 500,
        }
        cost = tracker.record(metadata)
        assert cost is not None
        assert cost > 0
        os.environ.pop("PERMANENCE_SYNTHESIS_DB", None)


def test_tracker_session_total():
    with tempfile.TemporaryDirectory() as tmp:
        db_path = os.path.join(tmp, "session_test.db")
        from core.synthesis_db import SynthesisDB

        db = SynthesisDB(db_path=db_path)
        tracker = CostTracker(session_id="sess_test")
        tracker._db = db

        metadata1 = {
            "model": "claude-sonnet-4-6",
            "tier": "sonnet",
            "provider": "anthropic",
            "input_tokens": 1000,
            "output_tokens": 500,
        }
        metadata2 = {
            "model": "gpt-4o-mini",
            "tier": "haiku",
            "provider": "openai",
            "input_tokens": 2000,
            "output_tokens": 1000,
        }
        c1 = tracker.record(metadata1)
        c2 = tracker.record(metadata2)

        total = tracker.session_total()
        assert total > 0
        assert abs(total - (c1 + c2)) < 0.0001
        db.close()


def test_tracker_task_total():
    with tempfile.TemporaryDirectory() as tmp:
        db_path = os.path.join(tmp, "task_test.db")
        from core.synthesis_db import SynthesisDB

        db = SynthesisDB(db_path=db_path)
        tracker = CostTracker(session_id="sess_task")
        tracker._db = db

        metadata = {
            "model": "claude-sonnet-4-6",
            "tier": "sonnet",
            "provider": "anthropic",
            "input_tokens": 500,
            "output_tokens": 200,
        }
        tracker.record(metadata, task_id="task_A")
        tracker.record(metadata, task_id="task_B")

        a_total = tracker.task_total("task_A")
        b_total = tracker.task_total("task_B")
        assert a_total > 0
        assert b_total > 0
        assert abs(a_total - b_total) < 0.0001  # Same metadata → same cost
        db.close()


def test_tracker_daily_total():
    with tempfile.TemporaryDirectory() as tmp:
        db_path = os.path.join(tmp, "daily_test.db")
        from core.synthesis_db import SynthesisDB

        db = SynthesisDB(db_path=db_path)
        tracker = CostTracker(session_id="sess_daily")
        tracker._db = db

        metadata = {
            "model": "claude-sonnet-4-6",
            "tier": "sonnet",
            "provider": "anthropic",
            "input_tokens": 100,
            "output_tokens": 50,
        }
        tracker.record(metadata)

        daily = tracker.daily_total()
        assert daily > 0
        db.close()


def test_tracker_budget_status():
    with tempfile.TemporaryDirectory() as tmp:
        db_path = os.path.join(tmp, "budget_test.db")
        from core.synthesis_db import SynthesisDB

        db = SynthesisDB(db_path=db_path)
        tracker = CostTracker(session_id="sess_budget")
        tracker._db = db
        tracker._budget_usd = 10.0

        status = tracker.budget_status()
        assert "monthly_spend_usd" in status
        assert "budget_usd" in status
        assert status["budget_usd"] == 10.0
        assert status["over_budget"] is False
        db.close()


def test_tracker_budget_no_budget_set():
    with tempfile.TemporaryDirectory() as tmp:
        db_path = os.path.join(tmp, "nobudget_test.db")
        from core.synthesis_db import SynthesisDB

        db = SynthesisDB(db_path=db_path)
        tracker = CostTracker(session_id="sess_nb")
        tracker._db = db
        tracker._budget_usd = None

        status = tracker.budget_status()
        assert status["budget_usd"] == 0.0
        assert status["utilization_pct"] == 0.0
        db.close()


def test_tracker_by_provider():
    with tempfile.TemporaryDirectory() as tmp:
        db_path = os.path.join(tmp, "provider_test.db")
        from core.synthesis_db import SynthesisDB

        db = SynthesisDB(db_path=db_path)
        tracker = CostTracker(session_id="sess_prov")
        tracker._db = db

        tracker.record({
            "model": "claude-sonnet-4-6", "tier": "sonnet",
            "provider": "anthropic", "input_tokens": 100, "output_tokens": 50,
        })
        tracker.record({
            "model": "qwen3:4b", "tier": "sonnet",
            "provider": "ollama", "input_tokens": 100, "output_tokens": 50,
        })

        breakdown = tracker.by_provider()
        providers = {r["provider"] for r in breakdown}
        assert "anthropic" in providers
        assert "ollama" in providers
        db.close()


def test_ollama_cost_is_zero():
    """Verify that Ollama calls cost nothing."""
    with tempfile.TemporaryDirectory() as tmp:
        db_path = os.path.join(tmp, "ollama_cost.db")
        from core.synthesis_db import SynthesisDB

        db = SynthesisDB(db_path=db_path)
        tracker = CostTracker(session_id="sess_ollama")
        tracker._db = db

        cost = tracker.record({
            "model": "qwen3:8b",
            "tier": "opus",
            "provider": "ollama",
            "input_tokens": 10000,
            "output_tokens": 5000,
        })
        assert cost == 0.0
        assert tracker.session_total() == 0.0
        db.close()
