#!/usr/bin/env python3
"""
HEALTH AGENT
Ingest wearable data, track protocols, surface trends.
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
import os
import json
from pathlib import Path

from agents.utils import log


@dataclass
class AgentResult:
    status: str
    notes: List[str]
    artifact: Optional[Any] = None
    created_at: str = datetime.now(timezone.utc).isoformat()


class HealthAgent:
    """
    ROLE: Aggregate health data and protocol adherence.

    CONSTRAINTS:
    - No diagnosis or medical advice
    - No sharing of health data externally
    """

    legal_exposure_domains = ["medical_privacy", "health_claims"]

    allowed_tools = ["wearable_read", "health_logs"]

    forbidden_actions = [
        "diagnosis",
        "medical_advice",
        "external_data_sharing",
    ]

    def execute(self, task: Dict[str, Any]) -> AgentResult:
        """
        Read-only health summary from local files.
        Expected inputs (optional):
          - data_dir: override health data directory
          - max_days: limit entries
        """
        data_dir = task.get("data_dir") or os.getenv(
            "PERMANENCE_HEALTH_DATA_DIR",
            os.path.join(os.path.dirname(__file__), "..", "..", "memory", "working", "health"),
        )
        data_dir = os.path.abspath(data_dir)
        os.makedirs(data_dir, exist_ok=True)
        max_days = int(task.get("max_days") or 14)

        entries = self._load_entries(data_dir)
        if not entries:
            return AgentResult(
                status="NO_DATA",
                notes=[f"No health data found in {data_dir}"],
            )

        summary = self._summarize(entries, max_days)
        report, tool_payload = self._format_report(summary)
        output_path, tool_path = self._write_report(report, tool_payload)

        log(f"Health summary written: {output_path}", level="INFO")
        return AgentResult(
            status="SUMMARIZED",
            notes=[f"Health summary written: {output_path}", f"Tool memory: {tool_path}"],
            artifact=output_path,
        )

    def _load_entries(self, data_dir: str) -> List[Dict[str, Any]]:
        entries: List[Dict[str, Any]] = []
        for file in sorted(Path(data_dir).glob("*.json*")):
            entries.extend(self._load_json_entries(file))
        return entries

    def _load_json_entries(self, path: Path) -> List[Dict[str, Any]]:
        try:
            content = path.read_text()
        except OSError:
            return []
        if not content.strip():
            return []
        if path.suffix.lower() == ".jsonl":
            items: List[Dict[str, Any]] = []
            for line in content.splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    items.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
            return items
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            return []
        return data if isinstance(data, list) else [data]

    def _summarize(self, entries: List[Dict[str, Any]], max_days: int) -> Dict[str, Any]:
        # Expect entries with fields: date, sleep_hours, hrv, recovery_score, strain
        sorted_entries = sorted(entries, key=lambda e: e.get("date", ""), reverse=True)
        recent = sorted_entries[:max_days]
        def _avg(key: str) -> Optional[float]:
            vals = [e.get(key) for e in recent if isinstance(e.get(key), (int, float))]
            return round(sum(vals) / len(vals), 2) if vals else None

        return {
            "days": len(recent),
            "avg_sleep_hours": _avg("sleep_hours"),
            "avg_hrv": _avg("hrv"),
            "avg_recovery": _avg("recovery_score"),
            "avg_strain": _avg("strain"),
            "latest": recent[0] if recent else None,
        }

    def _format_report(self, summary: Dict[str, Any]) -> tuple[str, Dict[str, Any]]:
        lines = [
            "# Health Summary",
            "",
            f"Days analyzed: {summary.get('days')}",
            "",
            "## Averages",
            f"- Sleep hours: {summary.get('avg_sleep_hours')}",
            f"- HRV: {summary.get('avg_hrv')}",
            f"- Recovery: {summary.get('avg_recovery')}",
            f"- Strain: {summary.get('avg_strain')}",
            "",
            "## Latest Entry",
        ]
        latest = summary.get("latest") or {}
        if latest:
            for key, value in latest.items():
                lines.append(f"- {key}: {value}")
        else:
            lines.append("- (none)")

        report = "\n".join(lines).rstrip() + "\n"
        return report, summary

    def _write_report(self, report: str, payload: Dict[str, Any]) -> tuple[str, str]:
        output_dir = os.getenv(
            "PERMANENCE_OUTPUT_DIR",
            os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "outputs")),
        )
        tool_dir = os.getenv(
            "PERMANENCE_TOOL_DIR",
            os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "memory", "tool")),
        )
        os.makedirs(output_dir, exist_ok=True)
        os.makedirs(tool_dir, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        output_path = os.path.join(output_dir, f"health_summary_{stamp}.md")
        tool_path = os.path.join(tool_dir, f"health_summary_{stamp}.json")
        with open(output_path, "w") as f:
            f.write(report)
        with open(tool_path, "w") as f:
            json.dump(payload, f, indent=2)
        return output_path, tool_path
