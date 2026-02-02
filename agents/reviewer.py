#!/usr/bin/env python3
"""
REVIEWER AGENT
Evaluates outputs against a spec/rubric. Does not create content.
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

from agents.utils import log


@dataclass
class ReviewResult:
    approved: bool
    notes: List[str]
    required_changes: List[str]
    created_at: str


class ReviewerAgent:
    """
    ROLE: Evaluate outputs against specifications.

    CONSTRAINTS:
    - Cannot generate or modify outputs
    - Must provide explicit pass/fail and reasons
    """

    def review(self, output: Optional[str], spec: Optional[Dict[str, Any]]) -> ReviewResult:
        issues: List[str] = []

        if not output or not output.strip():
            issues.append("Output is empty.")

        if not spec or not spec.get("deliverables"):
            issues.append("Missing or incomplete task specification (deliverables).")

        approved = len(issues) == 0
        log("Reviewer completed evaluation", level="INFO")
        return ReviewResult(
            approved=approved,
            notes=issues if issues else ["Meets minimal rubric."],
            required_changes=issues,
            created_at=datetime.now(timezone.utc).isoformat(),
        )


if __name__ == "__main__":
    ra = ReviewerAgent()
    print(ra.review("sample", {"deliverables": ["x"]}))
