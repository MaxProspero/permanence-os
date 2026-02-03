#!/usr/bin/env python3
"""
COMPLIANCE GATE
Review outbound actions for legal, ethical, and identity compliance.
"""

from dataclasses import dataclass
from typing import Any, Dict, List
from datetime import datetime, timezone

from agents.utils import log
from agents.identity import public_name, public_legal_name, internal_name


@dataclass
class ComplianceDecision:
    verdict: str  # APPROVE | HOLD | REJECT
    reasons: List[str]
    created_at: str


class ComplianceGate:
    """
    ROLE: Approve, hold, or reject outbound actions.
    """

    def review(self, action: Dict[str, Any]) -> ComplianceDecision:
        hold_reasons: List[str] = []
        reject_reasons: List[str] = []

        goal = str(action.get("goal", "")).lower()
        identity_used = action.get("identity_used")
        irreversible = bool(action.get("irreversible"))

        allowed_identities = {public_name(), public_legal_name(), internal_name()}
        if not identity_used:
            reject_reasons.append("Identity missing for outbound action")
        elif identity_used not in allowed_identities:
            reject_reasons.append("Identity mismatch for outbound action")

        if self._legal_exposure(goal):
            hold_reasons.append("Legal exposure detected")

        if self._financial_exposure(goal):
            hold_reasons.append("Financial action requires explicit human approval")

        if self._contractual_exposure(goal):
            hold_reasons.append("Contractual commitment requires explicit human approval")

        if self._public_statement(goal):
            hold_reasons.append("Public statement requires explicit human approval")

        if irreversible:
            hold_reasons.append("Irreversible action requires explicit human approval")

        if reject_reasons:
            verdict = "REJECT"
            reasons = reject_reasons + hold_reasons
        elif hold_reasons:
            verdict = "HOLD"
            reasons = hold_reasons
        else:
            verdict = "APPROVE"
            reasons = ["All compliance checks passed"]

        log(f"Compliance Gate verdict: {verdict}", level="INFO")
        return ComplianceDecision(
            verdict=verdict,
            reasons=reasons,
            created_at=datetime.now(timezone.utc).isoformat(),
        )

    def _legal_exposure(self, goal: str) -> bool:
        markers = [
            "legal",
            "lawsuit",
            "regulation",
            "compliance",
            "gdpr",
            "hipaa",
            "privacy",
            "pii",
        ]
        return any(m in goal for m in markers)

    def _financial_exposure(self, goal: str) -> bool:
        markers = ["money", "payment", "invoice", "tax", "bank", "wire", "transfer"]
        return any(m in goal for m in markers)

    def _contractual_exposure(self, goal: str) -> bool:
        markers = ["contract", "agreement", "terms", "sign", "commitment"]
        return any(m in goal for m in markers)

    def _public_statement(self, goal: str) -> bool:
        markers = ["publish", "post", "tweet", "announce", "press", "public"]
        return any(m in goal for m in markers)


if __name__ == "__main__":
    gate = ComplianceGate()
    sample = {"goal": "Publish announcement", "identity_used": public_name(), "irreversible": True}
    print(gate.review(sample))
