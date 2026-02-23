#!/usr/bin/env python3
"""
EXECUTOR AGENT
Produces outputs strictly from approved plans. No scope changes.
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
import os
import re

from agents.utils import log, BASE_DIR
try:
    from context_loader import inject_brand_context_if_needed
except Exception:  # pragma: no cover - fallback when brand context is unavailable
    def inject_brand_context_if_needed(task_goal: str, base_system_prompt: str, level: str = "voice") -> str:
        return base_system_prompt

OUTPUT_DIR = os.getenv("PERMANENCE_OUTPUT_DIR", os.path.join(BASE_DIR, "outputs"))
EXECUTOR_BASE_PROMPT = (
    "You are the Permanence Executor Agent. Produce outputs strictly from approved plans "
    "and validated sources. Never improvise scope and never alter governance rules."
)


@dataclass
class ExecutionResult:
    status: str
    artifact: Optional[Any]
    notes: List[str]
    created_at: str


class ExecutorAgent:
    """
    ROLE: Produce outputs per an approved task specification.

    CONSTRAINTS:
    - Cannot improvise scope
    - Cannot execute without a plan/spec
    - Cannot alter Canon or governance rules
    """

    def execute(self, spec: Optional[Dict[str, Any]], inputs: Optional[Dict[str, Any]] = None) -> ExecutionResult:
        if not spec:
            log("Executor refused: missing task specification", level="WARNING")
            return ExecutionResult(
                status="REFUSED",
                artifact=None,
                notes=["Execution requires an approved task specification."],
                created_at=datetime.now(timezone.utc).isoformat(),
            )

        inputs = inputs or {}
        task_goal = str(spec.get("goal", ""))
        executor_prompt = self._build_system_prompt(task_goal)
        brand_context_loaded = executor_prompt != EXECUTOR_BASE_PROMPT
        if brand_context_loaded:
            log("Executor loaded brand voice context (CA-013)", level="INFO")

        sources = inputs.get("sources", [])
        draft_text = self._load_draft(inputs)

        if draft_text:
            artifact_path = self._write_final(spec, sources, draft_text)
            log(f"Executor created final artifact: {artifact_path}", level="INFO")
            notes = ["Final output created from provided draft."]
            if brand_context_loaded:
                notes.append("Brand voice context applied for this task.")
            return ExecutionResult(
                status="FINAL_CREATED",
                artifact=artifact_path,
                notes=notes,
                created_at=datetime.now(timezone.utc).isoformat(),
            )

        artifact_path = self._write_compiled(spec, sources)
        log(f"Executor created compiled artifact: {artifact_path}", level="INFO")
        notes = ["Compiled output created from sources without additional claims."]
        if brand_context_loaded:
            notes.append("Brand voice context applied for this task.")
        return ExecutionResult(
            status="AUTO_COMPOSED",
            artifact=artifact_path,
            notes=notes,
            created_at=datetime.now(timezone.utc).isoformat(),
        )

    def _build_system_prompt(self, task_goal: str) -> str:
        """Build the Executor prompt and inject brand voice context when task semantics require it."""
        try:
            return inject_brand_context_if_needed(
                task_goal=task_goal,
                base_system_prompt=EXECUTOR_BASE_PROMPT,
                level="voice",
            )
        except Exception as exc:  # pragma: no cover - keep executor alive on loader failure
            log(f"Executor brand context loader fallback: {exc}", level="WARNING")
            return EXECUTOR_BASE_PROMPT

    def _load_draft(self, inputs: Dict[str, Any]) -> Optional[str]:
        draft_text = inputs.get("draft_text")
        if isinstance(draft_text, str) and draft_text.strip():
            return draft_text

        draft_path = inputs.get("draft_path")
        if isinstance(draft_path, str) and os.path.exists(draft_path):
            with open(draft_path, "r") as f:
                text = f.read()
            return text if text.strip() else None

        return None

    def _write_skeleton(self, spec: Dict[str, Any], sources: List[Dict[str, Any]]) -> str:
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        goal = spec.get("goal", "Unknown goal")
        slug = self._slugify(goal)[:40] or "task"
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        filename = f"{timestamp}-{slug}.md"
        path = os.path.join(OUTPUT_DIR, filename)

        deliverables = spec.get("deliverables", [])
        constraints = spec.get("constraints", [])

        lines = [
            "# DRAFT PLACEHOLDER - DO NOT PUBLISH",
            "",
            "## Goal",
            goal,
            "",
            "## Deliverables",
        ]
        if deliverables:
            lines.extend([f"- {d}" for d in deliverables])
        else:
            lines.append("- (none)")

        lines.extend(["", "## Constraints"])
        if constraints:
            lines.extend([f"- {c}" for c in constraints])
        else:
            lines.append("- (none)")

        lines.extend(["", "## Sources (Provenance)"])
        if sources:
            for src in sources:
                source = src.get("source", "unknown")
                ts = src.get("timestamp", "unknown")
                conf = src.get("confidence", "unknown")
                note = src.get("notes", "")
                note_part = f" — {note}" if note else ""
                lines.append(f"- {source} | {ts} | {conf}{note_part}")
        else:
            lines.append("- (no sources provided)")

        lines.extend(
            [
                "",
                "## Draft",
                "[TODO: Replace placeholders with real content produced from verified sources.]",
            ]
        )

        with open(path, "w") as f:
            f.write("\n".join(lines) + "\n")

        return path

    def _write_compiled(self, spec: Dict[str, Any], sources: List[Dict[str, Any]]) -> str:
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        goal = spec.get("goal", "Unknown goal")
        slug = self._slugify(goal)[:40] or "task"
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        filename = f"{timestamp}-{slug}.md"
        path = os.path.join(OUTPUT_DIR, filename)

        deliverables = spec.get("deliverables", [])
        constraints = spec.get("constraints", [])

        lines = [
            "# Report",
            "",
            "## Goal",
            goal,
            "",
            "## Deliverables",
        ]
        if deliverables:
            lines.extend([f"- {d}" for d in deliverables])
        else:
            lines.append("- (none)")

        lines.extend(["", "## Constraints"])
        if constraints:
            lines.extend([f"- {c}" for c in constraints])
        else:
            lines.append("- (none)")

        lines.extend(["", "## Output (Spec-Bound)"])
        if deliverables:
            for d in deliverables:
                lines.extend(
                    [
                        "",
                        f"### {d}",
                        "",
                        "Evidence (verbatim or excerpted from sources):",
                    ]
                )
                evidence = self._select_evidence_for_deliverable(d, sources)
                if evidence:
                    for src, note in evidence:
                        label = src.get("source", "unknown")
                        if note:
                            lines.append(f"- [{label}] {note}")
                        else:
                            lines.append(f"- [{label}] (no excerpt provided)")
                else:
                    lines.append("- (no sources available)")
        else:
            lines.append("- No deliverables specified; output limited to provenance summary.")

        lines.extend(["", "## Sources (Provenance)"])
        if sources:
            for src in sources:
                source = src.get("source", "unknown")
                ts = src.get("timestamp", "unknown")
                conf = src.get("confidence", "unknown")
                note = src.get("notes", "")
                note_part = f" - {note}" if note else ""
                lines.append(f"- {source} | {ts} | {conf}{note_part}")
        else:
            lines.append("- (no sources provided)")

        with open(path, "w") as f:
            f.write("\n".join(lines) + "\n")

        return path

    def _write_final(
        self, spec: Dict[str, Any], sources: List[Dict[str, Any]], draft_text: str
    ) -> str:
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        goal = spec.get("goal", "Unknown goal")
        slug = self._slugify(goal)[:40] or "task"
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        filename = f"{timestamp}-{slug}.md"
        path = os.path.join(OUTPUT_DIR, filename)

        content = draft_text
        if "## Sources" not in content:
            content = content.rstrip() + "\n\n## Sources (Provenance)\n"
            if sources:
                for src in sources:
                    source = src.get("source", "unknown")
                    ts = src.get("timestamp", "unknown")
                    conf = src.get("confidence", "unknown")
                    note = src.get("notes", "")
                    note_part = f" - {note}" if note else ""
                    content += f"- {source} | {ts} | {conf}{note_part}\n"
            else:
                content += "- (no sources provided)\n"

        with open(path, "w") as f:
            f.write(content.rstrip() + "\n")

        return path

    def _select_evidence_for_deliverable(
        self, deliverable: str, sources: List[Dict[str, Any]]
    ) -> List[tuple[Dict[str, Any], str]]:
        keywords = self._extract_keywords(deliverable)
        matched: List[tuple[Dict[str, Any], str]] = []

        for src in sources:
            note = src.get("notes") or ""
            if keywords and any(k in note.lower() for k in keywords):
                matched.append((src, note))

        if not matched:
            matched = [(src, src.get("notes") or "") for src in sources if src.get("notes")]

        if not matched:
            matched = [(src, "") for src in sources]

        return matched

    def _extract_keywords(self, text: str) -> List[str]:
        tokens = re.findall(r"[a-zA-Z0-9]+", text.lower())
        return [t for t in tokens if len(t) >= 4]

    def _slugify(self, text: str) -> str:
        lowered = text.lower().strip()
        cleaned = re.sub(r"[^a-z0-9]+", "-", lowered).strip("-")
        return cleaned


if __name__ == "__main__":
    ea = ExecutorAgent()
    print(ea.execute(spec=None))
