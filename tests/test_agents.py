#!/usr/bin/env python3
"""
Basic evaluation harness for agent boundaries.
"""

import os
import sys
from datetime import datetime, timezone

os.environ.setdefault("PERMANENCE_LOG_DIR", "/tmp/permanence-os-test-logs")
os.environ.setdefault("PERMANENCE_OUTPUT_DIR", "/tmp/permanence-os-test-outputs")

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


def test_researcher_safe_url():
    ra = ResearcherAgent()
    assert ra._safe_url("https://example.com") is True
    assert ra._safe_url("http://127.0.0.1:8080") is False


def test_executor_requires_spec():
    ea = ExecutorAgent()
    res = ea.execute(spec=None)
    assert res.status == "REFUSED"

def test_executor_auto_compose_and_reviewer_approves():
    ea = ExecutorAgent()
    spec = {"goal": "Test goal", "deliverables": ["x"], "constraints": ["y"]}
    sources = [{"source": "s1", "timestamp": "2026-02-02T00:00:00+00:00", "confidence": 0.7}]
    res = ea.execute(spec=spec, inputs={"sources": sources})
    assert res.status == "AUTO_COMPOSED"
    assert res.artifact is not None

    rv = ReviewerAgent()
    review = rv.review(res.artifact, spec)
    assert review.approved is True

    if res.artifact and os.path.exists(res.artifact):
        os.remove(res.artifact)
def test_executor_packages_draft_and_reviewer_approves():
    ea = ExecutorAgent()
    spec = {"goal": "Final goal", "deliverables": ["x"], "constraints": ["y"]}
    draft = "# Title\n\nFinal content.\n"
    res = ea.execute(spec=spec, inputs={"sources": [], "draft_text": draft})
    assert res.status == "FINAL_CREATED"
    assert res.artifact is not None

    rv = ReviewerAgent()
    review = rv.review(res.artifact, spec)
    assert review.approved is True

    if res.artifact and os.path.exists(res.artifact):
        os.remove(res.artifact)

def test_reviewer_minimal_rubric():
    rv = ReviewerAgent()
    res = rv.review("output\n\n## Sources\n- x", {"deliverables": ["x"]})
    assert res.approved is True


def test_reviewer_requires_evidence_for_deliverables():
    rv = ReviewerAgent()
    content = "\n".join(
        [
            "# Report",
            "",
            "## Output (Spec-Bound)",
            "",
            "### Deliverable A",
            "",
            "Evidence (verbatim or excerpted from sources):",
            "",
            "## Sources (Provenance)",
            "- s1 | 2026-02-02T00:00:00+00:00 | 0.7",
        ]
    )
    res = rv.review(content, {"deliverables": ["Deliverable A"]})
    assert res.approved is False


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
