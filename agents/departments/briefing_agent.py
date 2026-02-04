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
import json

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
        log("BriefingAgent execute called", level="INFO")
        now = datetime.now(timezone.utc).isoformat()
        notes: List[str] = [
            "# Daily Briefing",
            "",
            f"Generated (UTC): {now}",
            "",
        ]

        notes.extend(self._section_system_status())
        notes.extend(self._section_openclaw())
        notes.extend(self._section_email_triage())
        notes.extend(self._section_health_summary())
        notes.extend(self._section_hr_report())
        notes.extend(self._section_outputs())

        return AgentResult(
            status="COMPILED",
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

    @staticmethod
    def _latest_openclaw_health() -> Optional[str]:
        output_dir = os.getenv(
            "PERMANENCE_OUTPUT_DIR",
            os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "outputs")),
        )
        try:
            candidates = sorted(
                Path(output_dir).glob("openclaw_health_*.txt"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
        except FileNotFoundError:
            return None
        if not candidates:
            return None
        latest = candidates[0]
        excerpt = BriefingAgent._read_excerpt(latest, max_lines=6)
        if excerpt:
            return f"OpenClaw health: {excerpt}"
        return f"OpenClaw health captured: {latest}"

    @staticmethod
    def _latest_hr_report() -> Optional[str]:
        output_dir = os.getenv(
            "PERMANENCE_OUTPUT_DIR",
            os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "outputs")),
        )
        path = Path(output_dir) / "weekly_system_health_report.md"
        if not path.exists():
            return None
        latest = path
        excerpt = BriefingAgent._read_excerpt(latest, max_lines=12)
        if excerpt:
            return f"HR report excerpt: {excerpt}"
        return f"HR report captured: {latest}"

    @staticmethod
    def _latest_status_snapshot() -> Optional[Dict[str, Any]]:
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        memory_dir = os.getenv("PERMANENCE_MEMORY_DIR", os.path.join(base_dir, "memory"))
        log_dir = os.getenv("PERMANENCE_LOG_DIR", os.path.join(base_dir, "logs"))
        output_dir = os.getenv("PERMANENCE_OUTPUT_DIR", os.path.join(base_dir, "outputs"))
        episodic_dir = os.path.join(memory_dir, "episodic")

        def _latest_file(path: str, ext: str) -> Optional[str]:
            if not os.path.isdir(path):
                return None
            files = [f for f in os.listdir(path) if f.endswith(ext)]
            if not files:
                return None
            files.sort(key=lambda f: os.path.getmtime(os.path.join(path, f)), reverse=True)
            return os.path.join(path, files[0])

        latest_state = _latest_file(episodic_dir, ".json")
        latest_log = _latest_file(log_dir, ".log")
        output_count = len([f for f in os.listdir(output_dir) if f.endswith(".md")]) if os.path.isdir(output_dir) else 0

        if not latest_state:
            return {
                "task_id": None,
                "stage": None,
                "status": None,
                "risk_tier": None,
                "goal": None,
                "latest_log": os.path.basename(latest_log) if latest_log else None,
                "outputs": output_count,
            }

        try:
            with open(latest_state, "r") as f:
                state = json.load(f)
        except (OSError, json.JSONDecodeError):
            state = {}

        return {
            "task_id": state.get("task_id"),
            "stage": state.get("stage"),
            "status": state.get("status"),
            "risk_tier": state.get("risk_tier"),
            "goal": state.get("task_goal"),
            "latest_log": os.path.basename(latest_log) if latest_log else None,
            "outputs": output_count,
        }

    @staticmethod
    def _read_excerpt(path: Path, max_lines: int = 6) -> str:
        try:
            with open(path, "r") as f:
                lines = []
                for _ in range(max_lines):
                    line = f.readline()
                    if not line:
                        break
                    line = line.rstrip()
                    if line:
                        lines.append(line)
            return " | ".join(lines)
        except OSError:
            return ""

    def _section_system_status(self) -> List[str]:
        snapshot = self._latest_status_snapshot()
        lines = ["## System Status"]
        if not snapshot:
            lines.append("- No status snapshot available")
            lines.append("")
            return lines
        lines.append(f"- Latest Task: {snapshot.get('task_id') or 'none'}")
        if snapshot.get("stage") or snapshot.get("status"):
            lines.append(f"- Stage/Status: {snapshot.get('stage')} / {snapshot.get('status')}")
        if snapshot.get("risk_tier"):
            lines.append(f"- Risk Tier: {snapshot.get('risk_tier')}")
        if snapshot.get("goal"):
            lines.append(f"- Goal: {snapshot.get('goal')}")
        lines.append(f"- Outputs (md): {snapshot.get('outputs')}")
        if snapshot.get("latest_log"):
            lines.append(f"- Latest Log: {snapshot.get('latest_log')}")
        lines.append("")
        return lines

    def _section_openclaw(self) -> List[str]:
        lines = ["## OpenClaw"]
        status = self._latest_openclaw_status()
        health = self._latest_openclaw_health()
        if status:
            lines.append(f"- {status}")
        if health:
            lines.append(f"- {health}")
        if not status and not health:
            lines.append("- No OpenClaw status captured")
        lines.append("")
        return lines

    def _section_email_triage(self) -> List[str]:
        lines = ["## Email Triage"]
        email_note = self._latest_email_triage()
        if email_note:
            lines.append(f"- {email_note}")
        else:
            lines.append("- No email triage report found")
        lines.append("")
        return lines

    def _section_hr_report(self) -> List[str]:
        lines = ["## HR Health"]
        hr_note = self._latest_hr_report()
        if hr_note:
            lines.append(f"- {hr_note}")
        else:
            lines.append("- No HR report found")
        lines.append("")
        return lines

    def _section_health_summary(self) -> List[str]:
        lines = ["## Health Summary"]
        note = self._latest_health_summary()
        if note:
            lines.append(f"- {note}")
        else:
            lines.append("- No health summary found")
        lines.append("")
        return lines

    def _section_outputs(self) -> List[str]:
        output_dir = os.getenv(
            "PERMANENCE_OUTPUT_DIR",
            os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "outputs")),
        )
        lines = ["## Recent Outputs"]
        try:
            candidates = sorted(
                Path(output_dir).glob("*.md"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
        except FileNotFoundError:
            candidates = []
        if not candidates:
            lines.append("- (none)")
            lines.append("")
            return lines
        for path in candidates[:5]:
            lines.append(f"- {path.name}")
        lines.append("")
        return lines

    @staticmethod
    def _latest_health_summary() -> Optional[str]:
        output_dir = os.getenv(
            "PERMANENCE_OUTPUT_DIR",
            os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "outputs")),
        )
        try:
            candidates = sorted(
                Path(output_dir).glob("health_summary_*.md"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
        except FileNotFoundError:
            return None
        if not candidates:
            return None
        latest = candidates[0]
        excerpt = BriefingAgent._read_excerpt(latest, max_lines=6)
        if excerpt:
            return f"Health summary: {excerpt}"
        return f"Health summary captured: {latest}"
