#!/usr/bin/env python3
"""
CONCILIATOR AGENT
Rule-based accept/retry/escalate after retries.
"""

from dataclasses import dataclass
from typing import Optional
from datetime import datetime, timezone

from agents.utils import log
from agents.reviewer import ReviewResult


@dataclass
class ConciliationDecision:
    decision: str  # ACCEPT | RETRY | ESCALATE
    reason: str
    created_at: str


class ConciliatorAgent:
    """
    ROLE: Determine accept/retry/escalate based on review outcomes.

    CONSTRAINTS:
    - No content generation
    - Follows retry limits before escalation
    """

    def decide(
        self,
        review_result: ReviewResult,
        retry_count: int,
        max_retries: int = 2,
        reason: Optional[str] = None,
    ) -> ConciliationDecision:
        if review_result.approved:
            log("Conciliator decision: ACCEPT", level="INFO")
            return ConciliationDecision(
                decision="ACCEPT",
                reason=reason or "Review approved output.",
                created_at=datetime.now(timezone.utc).isoformat(),
            )

        if retry_count >= max_retries:
            log("Conciliator decision: ESCALATE", level="WARNING")
            return ConciliationDecision(
                decision="ESCALATE",
                reason=reason or "Retry limit reached; escalate to human.",
                created_at=datetime.now(timezone.utc).isoformat(),
            )

        log("Conciliator decision: RETRY", level="INFO")
        return ConciliationDecision(
            decision="RETRY",
            reason=reason or "Review failed; retry allowed.",
            created_at=datetime.now(timezone.utc).isoformat(),
        )


if __name__ == "__main__":
    ca = ConciliatorAgent()
    rr = ReviewResult(approved=False, notes=["x"], required_changes=["x"], created_at=datetime.now(timezone.utc).isoformat())
    print(ca.decide(rr, retry_count=2))
