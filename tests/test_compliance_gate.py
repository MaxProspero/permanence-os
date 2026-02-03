#!/usr/bin/env python3
"""Tests for Compliance Gate agent."""

import os
import sys

os.environ.setdefault("PERMANENCE_LOG_DIR", "/tmp/permanence-os-test-logs")

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from agents.compliance_gate import ComplianceGate
from agents.identity import public_name, internal_name


def test_reject_missing_identity():
    gate = ComplianceGate()
    decision = gate.review({"goal": "internal note"})
    assert decision.verdict == "REJECT"


def test_hold_public_statement():
    gate = ComplianceGate()
    decision = gate.review({"goal": "publish announcement", "identity_used": public_name()})
    assert decision.verdict == "HOLD"


def test_approve_internal_note():
    gate = ComplianceGate()
    decision = gate.review({"goal": "internal note", "identity_used": internal_name()})
    assert decision.verdict == "APPROVE"


if __name__ == "__main__":
    test_reject_missing_identity()
    test_hold_public_statement()
    test_approve_internal_note()
    print("✓ Compliance Gate tests passed")
