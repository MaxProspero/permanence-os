#!/usr/bin/env python3
"""
BRIEFING AGENT
Aggregate intelligence from departments into a daily report.
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
import os
from pathlib import Path

from agents.utils import log


@dataclass
class AgentResult:
    status: str
    notes: List[str]
    artifact: Optional[Any] = None
    created_at: str = datetime.now(timezone.utc).isoformat()


class BriefingAgent:
    """
    ROLE: Aggregate read-only summaries across departments.

    CONSTRAINTS:
    - Read-only aggregation
    - No cross-department writes
    """

    legal_exposure_domains = ["sensitive_data_aggregation"]

    allowed_tools = ["read_reports"]

    source_agents = [
        "email_agent",
        "device_agent",
        "social_agent",
        "health_agent",
        "trainer_agent",
        "therapist_agent",
        "hr_agent",
        "openclaw_status",
    ]

    forbidden_actions = ["write_back_to_departments", "publish_without_approval"]

    def execute(self, _task: Dict[str, Any]) -> AgentResult:
        log("BriefingAgent execute called (stub)", level="INFO")
        openclaw_note = self._latest_openclaw_status()
        email_note = self._latest_email_triage()
        notes = ["BriefingAgent is a stub; add aggregation pipeline."]
        if openclaw_note:
            notes.append(openclaw_note)
        if email_note:
            notes.append(email_note)
        return AgentResult(
            status="NOT_IMPLEMENTED",
            notes=notes,
        )

    @staticmethod
    def _latest_openclaw_status() -> Optional[str]:
        output_dir = os.getenv(
            "PERMANENCE_OUTPUT_DIR",
            os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "outputs")),
        )
        try:
            candidates = sorted(
                Path(output_dir).glob("openclaw_status_*.txt"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
        except FileNotFoundError:
            return None
        if not candidates:
            return None
        latest = candidates[0]
        excerpt = ""
        try:
            with open(latest, "r") as f:
                lines = [next(f).rstrip() for _ in range(6)]
            excerpt = " | ".join([l for l in lines if l])
        except (OSError, StopIteration):
            excerpt = ""
        if excerpt:
            return f"OpenClaw status: {excerpt}"
        return f"OpenClaw status captured: {latest}"

    @staticmethod
    def _latest_email_triage() -> Optional[str]:
        output_dir = os.getenv(
            "PERMANENCE_OUTPUT_DIR",
            os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "outputs")),
        )
        try:
            candidates = sorted(
                Path(output_dir).glob("email_triage_*.md"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
        except FileNotFoundError:
            return None
        if not candidates:
            return None
        latest = candidates[0]
        excerpt = ""
        try:
            with open(latest, "r") as f:
                lines = [next(f).rstrip() for _ in range(6)]
            excerpt = " | ".join([l for l in lines if l])
        except (OSError, StopIteration):
            excerpt = ""
        if excerpt:
            return f"Email triage: {excerpt}"
        return f"Email triage captured: {latest}"
