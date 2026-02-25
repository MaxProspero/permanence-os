#!/usr/bin/env python3
"""
CONCILIATOR AGENT
Rule-based accept/retry/escalate after retries.
"""

from dataclasses import dataclass
from typing import Optional
from datetime import datetime, timezone
import os

from agents.utils import log
from agents.reviewer import ReviewResult
try:
    from core.model_router import ModelRouter
except Exception:  # pragma: no cover - optional dependency
    ModelRouter = None


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

    def __init__(self, model_router: Optional["ModelRouter"] = None):
        self.model_router = model_router or (ModelRouter() if ModelRouter else None)
        self.enable_model_assist = os.getenv("PERMANENCE_ENABLE_MODEL_ASSIST", "").lower() in {
            "1",
            "true",
            "yes",
            "on",
        }

    def decide(
        self,
        review_result: ReviewResult,
        retry_count: int,
        max_retries: int = 2,
        reason: Optional[str] = None,
    ) -> ConciliationDecision:
        if self.enable_model_assist:
            model_reason = self._model_advisory_reason(review_result, retry_count, max_retries)
            if model_reason:
                reason = f"{reason}; {model_reason}" if reason else model_reason

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

    def _model_advisory_reason(
        self,
        review_result: ReviewResult,
        retry_count: int,
        max_retries: int,
    ) -> Optional[str]:
        if not self.model_router:
            return None
        model = self.model_router.get_model("conciliation")
        if not model:
            return None
        prompt = "\n".join(
            [
                "Conciliation advisory only. Do not create content.",
                f"Review approved: {review_result.approved}",
                f"Retry count: {retry_count}",
                f"Max retries: {max_retries}",
                f"Issues: {review_result.required_changes}",
                "Respond in one short sentence with recommendation rationale.",
            ]
        )
        try:
            response = model.generate(prompt=prompt)
            text = response.text.strip()
            return text or None
        except Exception as exc:
            log(f"Conciliator model assist failed: {exc}", level="WARNING")
            return None


if __name__ == "__main__":
    ca = ConciliatorAgent()
    rr = ReviewResult(approved=False, notes=["x"], required_changes=["x"], created_at=datetime.now(timezone.utc).isoformat())
    print(ca.decide(rr, retry_count=2))
