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
try:
    from core.model_router import ModelRouter
except Exception:  # pragma: no cover - optional dependency
    ModelRouter = None


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

    def __init__(self, model_router: Optional["ModelRouter"] = None):
        self.model_router = model_router or (ModelRouter() if ModelRouter else None)
        self.enable_model_assist = os.getenv("PERMANENCE_ENABLE_MODEL_ASSIST", "").lower() in {
            "1",
            "true",
            "yes",
            "on",
        }

    def review(self, output: Optional[str], spec: Optional[Dict[str, Any]]) -> ReviewResult:
        issues: List[str] = []
        audit_notes: List[str] = []
        content: Optional[str] = None
        sources_data: List[Dict[str, Any]] = []

        if not output or (isinstance(output, str) and not output.strip()):
            issues.append("Output is empty.")
        elif isinstance(output, str) and os.path.exists(output):
            with open(output, "r") as f:
                content = f.read()
        elif isinstance(output, str):
            content = output

        if spec and isinstance(spec.get("sources"), list):
            sources_data = spec.get("sources") or []

        if content is not None:
            if "DRAFT PLACEHOLDER" in content or "TODO:" in content:
                issues.append("Output contains placeholders and is not final.")
            if "## Sources" not in content:
                issues.append("Output is missing a sources/provenance section.")
            if "Output (Spec-Bound)" in content:
                missing = self._missing_evidence_sections(content, spec)
                if missing:
                    issues.append(
                        "Spec-bound output missing evidence for deliverables: " + ", ".join(missing)
                    )
            dominance_issue = self._detect_source_dominance(content, sources_data)
            if dominance_issue:
                issues.append(dominance_issue)

        if not spec or not spec.get("deliverables"):
            issues.append("Missing or incomplete task specification (deliverables).")

        if self.enable_model_assist and content:
            observation = self._model_secondary_observation(content=content, spec=spec)
            if observation:
                audit_notes.append(f"Model audit note: {observation}")

        approved = len(issues) == 0
        log("Reviewer completed evaluation", level="INFO")
        notes = issues if issues else ["Meets minimal rubric."]
        if audit_notes:
            notes.extend(audit_notes)
        return ReviewResult(
            approved=approved,
            notes=notes,
            required_changes=issues,
            created_at=datetime.now(timezone.utc).isoformat(),
        )

    def _model_secondary_observation(self, content: str, spec: Optional[Dict[str, Any]]) -> Optional[str]:
        if not self.model_router:
            return None
        model = self.model_router.get_model("review")
        if not model:
            return None

        prompt = "\n".join(
            [
                "Review this output for governance and evidence quality.",
                "Respond with one short line: either 'OK' or a concise issue.",
                f"Deliverables: {spec.get('deliverables', []) if isinstance(spec, dict) else []}",
                "",
                "Output:",
                content[:5000],
            ]
        )
        try:
            response = model.generate(prompt=prompt)
            text = response.text.strip()
            if not text or text.upper() == "OK":
                return None
            return text
        except Exception as exc:
            log(f"Reviewer model assist failed: {exc}", level="WARNING")
            return None

    def _missing_evidence_sections(self, content: str, spec: Optional[Dict[str, Any]]) -> List[str]:
        deliverables = (spec or {}).get("deliverables", [])
        if not deliverables:
            return []
        missing: List[str] = []
        lines = content.splitlines()
        for deliverable in deliverables:
            marker = f"### {deliverable}"
            try:
                idx = lines.index(marker)
            except ValueError:
                missing.append(deliverable)
                continue
            # Search until next section header
            has_evidence = False
            for line in lines[idx + 1 :]:
                if line.startswith("### ") or line.startswith("## "):
                    break
                if line.strip().startswith("- ["):
                    has_evidence = True
                    break
            if not has_evidence:
                missing.append(deliverable)
        return missing

    def _detect_source_dominance(
        self, content: str, sources: List[Dict[str, Any]], threshold: float = 0.7
    ) -> Optional[str]:
        """
        Detect if a single source dominates evidence lines.
        Evidence lines are counted by prefix "- [source]".
        """
        if not sources:
            return None
        counts: Dict[str, int] = {}
        total = 0
        for line in content.splitlines():
            line = line.strip()
            if line.startswith("- [") and "]" in line:
                label = line[3:].split("]")[0].strip()
                counts[label] = counts.get(label, 0) + 1
                total += 1
        if total == 0:
            return None
        top_label, top_count = max(counts.items(), key=lambda x: x[1])
        if total > 0 and (top_count / total) >= threshold:
            return f"Source dominance detected: {top_label} accounts for {top_count}/{total} evidence lines."
        return None


if __name__ == "__main__":
    ra = ReviewerAgent()
    print(ra.review("sample", {"deliverables": ["x"]}))
