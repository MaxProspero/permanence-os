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
    from core.model_router import ModelRouter
except Exception:  # pragma: no cover - optional dependency
    ModelRouter = None
try:
    from context_loader import (
        inject_brand_context_if_needed,
        inject_chronicle_context_if_needed,
    )
except Exception:  # pragma: no cover - fallback when brand context is unavailable
    def inject_brand_context_if_needed(task_goal: str, base_system_prompt: str, level: str = "voice") -> str:
        return base_system_prompt

    def inject_chronicle_context_if_needed(
        task_goal: str,
        base_system_prompt: str,
        max_direction_events: int = 3,
        max_issue_events: int = 3,
    ) -> str:
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

    def __init__(self, model_router: Optional["ModelRouter"] = None):
        self.model_router = model_router or (ModelRouter() if ModelRouter else None)
        self.enable_model_assist = os.getenv("PERMANENCE_ENABLE_MODEL_ASSIST", "").lower() in {
            "1",
            "true",
            "yes",
            "on",
        }

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
        brand_context_loaded = "BRAND VOICE" in executor_prompt
        chronicle_context_loaded = "CHRONICLE CONTEXT" in executor_prompt
        if brand_context_loaded:
            log("Executor loaded brand voice context (CA-013)", level="INFO")
        if chronicle_context_loaded:
            log("Executor loaded chronicle context (self-improvement signals)", level="INFO")

        sources = inputs.get("sources", [])
        draft_text = self._load_draft(inputs)
        model_drafted = False
        if not draft_text and self.enable_model_assist:
            draft_text = self._generate_draft_with_model(spec=spec, sources=sources, system_prompt=executor_prompt)
            model_drafted = bool(draft_text)

        if draft_text:
            artifact_path = self._write_final(spec, sources, draft_text)
            log(f"Executor created final artifact: {artifact_path}", level="INFO")
            notes = ["Final output created from provided draft."]
            status = "FINAL_CREATED"
            if model_drafted:
                status = "MODEL_COMPOSED"
                notes = ["Final output created from model draft."]
            if brand_context_loaded:
                notes.append("Brand voice context applied for this task.")
            if chronicle_context_loaded:
                notes.append("Chronicle context applied for this task.")
            return ExecutionResult(
                status=status,
                artifact=artifact_path,
                notes=notes,
                created_at=datetime.now(timezone.utc).isoformat(),
            )

        artifact_path = self._write_compiled(spec, sources)
        log(f"Executor created compiled artifact: {artifact_path}", level="INFO")
        notes = ["Compiled output created from sources without additional claims."]
        if brand_context_loaded:
            notes.append("Brand voice context applied for this task.")
        if chronicle_context_loaded:
            notes.append("Chronicle context applied for this task.")
        return ExecutionResult(
            status="AUTO_COMPOSED",
            artifact=artifact_path,
            notes=notes,
            created_at=datetime.now(timezone.utc).isoformat(),
        )

    def _generate_draft_with_model(
        self,
        spec: Dict[str, Any],
        sources: List[Dict[str, Any]],
        system_prompt: str,
    ) -> Optional[str]:
        if not self.model_router:
            return None
        model = self.model_router.get_model("execution")
        if not model:
            return None

        goal = str(spec.get("goal", "")).strip()
        deliverables = [str(d).strip() for d in spec.get("deliverables", []) if str(d).strip()]
        constraints = [str(c).strip() for c in spec.get("constraints", []) if str(c).strip()]
        evidence_lines: List[str] = []
        for src in sources[:12]:
            source = str(src.get("source", "unknown")).strip()
            ts = str(src.get("timestamp", "unknown")).strip()
            conf = str(src.get("confidence", "unknown")).strip()
            notes = str(src.get("notes", "")).strip()
            evidence_lines.append(f"- {source} | {ts} | {conf} | {notes}")

        prompt_lines = [
            "Task: Produce final markdown output only from evidence provided.",
            f"Goal: {goal}",
            "Deliverables:",
            *([f"- {d}" for d in deliverables] or ["- Structured response"]),
            "Constraints:",
            *([f"- {c}" for c in constraints] or ["- Respect Canon constraints"]),
            "",
            "Evidence:",
            *evidence_lines,
            "",
            "Requirements:",
            "- Include a '## Sources (Provenance)' section with source|timestamp|confidence.",
            "- Do not invent facts beyond evidence lines.",
            "- Keep output concise and spec-bound.",
        ]
        prompt = "\n".join(prompt_lines)
        try:
            response = model.generate(prompt=prompt, system=system_prompt)
            text = response.text.strip()
            return text or None
        except Exception as exc:
            log(f"Executor model assist failed: {exc}", level="WARNING")
            return None

    def _build_system_prompt(self, task_goal: str) -> str:
        """Build the Executor prompt and inject brand voice context when task semantics require it."""
        prompt = EXECUTOR_BASE_PROMPT
        try:
            prompt = inject_brand_context_if_needed(
                task_goal=task_goal,
                base_system_prompt=prompt,
                level="voice",
            )
        except Exception as exc:  # pragma: no cover - keep executor alive on loader failure
            log(f"Executor brand context loader fallback: {exc}", level="WARNING")
            prompt = EXECUTOR_BASE_PROMPT

        try:
            prompt = inject_chronicle_context_if_needed(
                task_goal=task_goal,
                base_system_prompt=prompt,
            )
        except Exception as exc:  # pragma: no cover - keep executor alive on loader failure
            log(f"Executor chronicle context loader fallback: {exc}", level="WARNING")

        return prompt

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
