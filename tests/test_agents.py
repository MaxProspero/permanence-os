#!/usr/bin/env python3
"""
Basic evaluation harness for agent boundaries.
"""

import os
import sys
from datetime import datetime, timezone

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from agents.researcher import ResearcherAgent
from agents.executor import ExecutorAgent
from agents.reviewer import ReviewerAgent, ReviewResult
from agents.conciliator import ConciliatorAgent


def test_researcher_provenance_validation():
    ra = ResearcherAgent()
    result = ra.validate_sources([
        {"source": "doc", "timestamp": datetime.now(timezone.utc).isoformat(), "confidence": 0.6},
        {"source": "doc2", "confidence": 0.9},
    ])
    assert result["ok"] is False
    assert len(result["errors"]) == 1


def test_researcher_provenance_ok():
    ra = ResearcherAgent()
    result = ra.validate_sources([
        {"source": "doc", "timestamp": datetime.now(timezone.utc).isoformat(), "confidence": 0.8}
    ])
    assert result["ok"] is True


def test_executor_requires_spec():
    ea = ExecutorAgent()
    res = ea.execute(spec=None)
    assert res.status == "REFUSED"


def test_reviewer_minimal_rubric():
    rv = ReviewerAgent()
    res = rv.review("output", {"deliverables": ["x"]})
    assert res.approved is True


def test_conciliator_escalates_after_retries():
    ca = ConciliatorAgent()
    rr = ReviewResult(approved=False, notes=["x"], required_changes=["x"], created_at=datetime.now(timezone.utc).isoformat())
    decision = ca.decide(rr, retry_count=2, max_retries=2)
    assert decision.decision == "ESCALATE"


if __name__ == "__main__":
    test_researcher_provenance_validation()
    test_researcher_provenance_ok()
    test_executor_requires_spec()
    test_reviewer_minimal_rubric()
    test_conciliator_escalates_after_retries()
    print("✓ Agent boundary tests passed")
