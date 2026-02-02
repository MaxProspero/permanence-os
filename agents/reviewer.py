#!/usr/bin/env python3
"""
REVIEWER AGENT
Evaluates outputs against a spec/rubric. Does not create content.
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
import os

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
        content: Optional[str] = None

        if not output or (isinstance(output, str) and not output.strip()):
            issues.append("Output is empty.")
        elif isinstance(output, str) and os.path.exists(output):
            with open(output, "r") as f:
                content = f.read()
        elif isinstance(output, str):
            content = output

        if content is not None:
            if "DRAFT PLACEHOLDER" in content or "TODO:" in content:
                issues.append("Output contains placeholders and is not final.")

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
