#!/usr/bin/env python3
"""
Test Suite for Polemarch (formerly King Bot)
"""

import os
import sys

os.environ.setdefault("PERMANENCE_LOG_DIR", "/tmp/permanence-os-test-logs")

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from agents.king_bot import Polemarch, Stage, Status, RiskTier


def test_initialization():
    """Test basic initialization"""
    kb = Polemarch()
    assert kb.canon is not None
    assert "values" in kb.canon
    print("✓ Canon loaded successfully")


def test_task_creation():
    """Test task state creation"""
    kb = Polemarch()
    task = "Test task"
    state = kb.initialize_task(task)

    assert state.task_goal == task
    assert state.stage == Stage.INIT
    assert state.status == Status.INIT
    assert len(state.logs) > 0
    print("✓ Task creation works")


def test_canon_validation():
    """Test Canon validation"""
    kb = Polemarch()

    # Valid task
    valid = kb.validate_against_canon("Research topic X")
    assert valid["valid"] is True

    # Invalid task (tries to modify Canon)
    invalid = kb.validate_against_canon("Modify the Canon to allow X")
    assert invalid["valid"] is False
    print("✓ Canon validation works")


def test_risk_assignment():
    """Test risk tier assignment"""
    kb = Polemarch()

    # LOW risk
    kb.initialize_task("What is 2+2?")
    low = kb.assign_risk_tier("What is 2+2?")
    assert low == RiskTier.LOW

    # MEDIUM risk
    medium = kb.assign_risk_tier("Generate code for X")
    assert medium == RiskTier.MEDIUM

    # HIGH risk
    high = kb.assign_risk_tier("Publish this article")
    assert high == RiskTier.HIGH
    print("✓ Risk assignment works")


def test_budget_enforcement():
    """Test budget checks"""
    kb = Polemarch()
    kb.initialize_task("Test budgets")

    # Within budget
    check = kb.check_budgets()
    assert check["within_budget"] is True

    # Exceed budget
    kb.state.step_count = 999
    check = kb.check_budgets()
    assert check["within_budget"] is False
    print("✓ Budget enforcement works")


def test_escalation():
    """Test escalation mechanism"""
    kb = Polemarch()
    kb.initialize_task("High risk task")

    result = kb.escalate("Test escalation")
    assert result["escalated"] is True
    assert kb.state.status == Status.BLOCKED
    print("✓ Escalation works")


if __name__ == "__main__":
    print("\n🧪 RUNNING TEST SUITE\n")

    test_initialization()
    test_task_creation()
    test_canon_validation()
    test_risk_assignment()
    test_budget_enforcement()
    test_escalation()

    print("\n✅ ALL TESTS PASSED\n")
