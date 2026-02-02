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

OUTPUT_DIR = os.getenv("PERMANENCE_OUTPUT_DIR", os.path.join(BASE_DIR, "outputs"))


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
        sources = inputs.get("sources", [])
        draft_text = self._load_draft(inputs)

        if draft_text:
            artifact_path = self._write_final(spec, sources, draft_text)
            log(f"Executor created final artifact: {artifact_path}", level="INFO")
            return ExecutionResult(
                status="FINAL_CREATED",
                artifact=artifact_path,
                notes=["Final output created from provided draft."],
                created_at=datetime.now(timezone.utc).isoformat(),
            )

        artifact_path = self._write_skeleton(spec, sources)
        log(f"Executor created skeleton artifact: {artifact_path}", level="INFO")
        return ExecutionResult(
            status="SKELETON_CREATED",
            artifact=artifact_path,
            notes=["Skeleton created; requires real execution to replace placeholders."],
            created_at=datetime.now(timezone.utc).isoformat(),
        )

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

    def _slugify(self, text: str) -> str:
        lowered = text.lower().strip()
        cleaned = re.sub(r"[^a-z0-9]+", "-", lowered).strip("-")
        return cleaned


if __name__ == "__main__":
    ea = ExecutorAgent()
    print(ea.execute(spec=None))
