#!/usr/bin/env python3
"""
ARI RECEPTION AGENT
Queue and summarize inbound operator requests/messages.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
import hashlib
import json
import os

from agents.utils import log


@dataclass
class AgentResult:
    status: str
    notes: List[str]
    artifact: Optional[Any] = None
    created_at: str = datetime.now(timezone.utc).isoformat()


class ReceptionAgent:
    """
    Role:
      - Intake inbound messages to a governed local queue.
      - Produce a concise daily receptionist summary for review.

    Constraints:
      - Read/write only local queue and report artifacts.
      - No external posting/DM actions.
    """

    legal_exposure_domains = ["privacy", "public_communications"]
    allowed_tools = ["local_queue"]
    forbidden_actions = ["external_send", "auto_reply"]

    def execute(self, task: Dict[str, Any]) -> AgentResult:
        name = self._display_name(task)
        action = (task.get("action") or "summary").strip().lower()
        queue_dir = task.get("queue_dir") or os.getenv(
            "PERMANENCE_RECEPTION_QUEUE_DIR",
            os.path.join(os.path.dirname(__file__), "..", "..", "memory", "working", "reception"),
        )
        queue_path = Path(os.path.abspath(queue_dir))
        queue_path.mkdir(parents=True, exist_ok=True)

        if action == "intake":
            return self._intake(queue_path, task, name)
        if action == "summary":
            return self._summary(queue_path, int(task.get("max_items") or 20), name)
        return AgentResult(status="INVALID_ACTION", notes=[f"Unsupported action: {action}"])

    def _intake(self, queue_dir: Path, task: Dict[str, Any], name: str) -> AgentResult:
        sender = (task.get("sender") or "").strip()
        message = (task.get("message") or "").strip()
        if not sender or not message:
            return AgentResult(
                status="INVALID_INPUT",
                notes=["Intake requires both sender and message."],
            )

        now = datetime.now(timezone.utc).isoformat()
        payload = {
            "id": self._entry_id(sender, message, now),
            "created_at": now,
            "sender": sender,
            "message": message,
            "channel": task.get("channel") or "unspecified",
            "source": task.get("source") or "manual",
            "priority": self._priority(message, task.get("priority")),
            "status": "open",
        }

        inbox = queue_dir / "ari_inbox.jsonl"
        with inbox.open("a") as f:
            f.write(json.dumps(payload) + "\n")

        log(f"{name} intake saved: {payload['id']}", level="INFO")
        return AgentResult(
            status="INTAKE_SAVED",
            notes=[f"{name} intake saved: {inbox}", f"Entry ID: {payload['id']}"],
            artifact=str(inbox),
        )

    def _summary(self, queue_dir: Path, max_items: int, name: str) -> AgentResult:
        entries = self._load_entries(queue_dir)
        if not entries:
            return AgentResult(status="NO_ENTRIES", notes=[f"No {name} entries found in {queue_dir}"])

        entries.sort(key=lambda e: e.get("created_at", ""), reverse=True)
        open_items = [e for e in entries if e.get("status", "open") == "open"]
        urgent = [e for e in open_items if e.get("priority") == "urgent"]
        latest = open_items[:max_items]

        report = self._format_report(queue_dir, entries, open_items, urgent, latest, name)
        output_path, tool_path = self._write_report(report, entries, open_items, urgent, latest)
        log(f"{name} summary written: {output_path}", level="INFO")
        return AgentResult(
            status="SUMMARY",
            notes=[f"{name} summary written: {output_path}", f"Tool memory: {tool_path}"],
            artifact=output_path,
        )

    @staticmethod
    def _priority(message: str, explicit: Any) -> str:
        if explicit:
            value = str(explicit).strip().lower()
            if value in {"urgent", "high", "normal", "low"}:
                return "urgent" if value in {"urgent", "high"} else value
        lower = message.lower()
        for keyword in ("urgent", "asap", "today", "immediately", "critical"):
            if keyword in lower:
                return "urgent"
        return "normal"

    @staticmethod
    def _entry_id(sender: str, message: str, now_iso: str) -> str:
        basis = f"{sender}|{message}|{now_iso}".encode("utf-8")
        return "ari_" + hashlib.sha256(basis).hexdigest()[:12]

    @staticmethod
    def _load_entries(queue_dir: Path) -> List[Dict[str, Any]]:
        entries: List[Dict[str, Any]] = []
        for path in sorted(queue_dir.glob("*.json*")):
            try:
                content = path.read_text()
            except OSError:
                continue
            if not content.strip():
                continue
            if path.suffix.lower() == ".jsonl":
                for line in content.splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
            else:
                try:
                    data = json.loads(content)
                except json.JSONDecodeError:
                    continue
                if isinstance(data, list):
                    entries.extend(data)
                elif isinstance(data, dict):
                    entries.append(data)
        return entries

    @staticmethod
    def _format_report(
        queue_dir: Path,
        entries: List[Dict[str, Any]],
        open_items: List[Dict[str, Any]],
        urgent: List[Dict[str, Any]],
        latest: List[Dict[str, Any]],
        name: str,
    ) -> str:
        lines = [
            f"# {name} Reception Summary",
            "",
            f"Queue: {queue_dir}",
            f"Total entries: {len(entries)}",
            f"Open entries: {len(open_items)}",
            f"Urgent open entries: {len(urgent)}",
            "",
            "## Open Queue",
        ]
        if not latest:
            lines.append("- (none)")
        else:
            for item in latest:
                created = item.get("created_at") or "unknown"
                sender = item.get("sender") or "unknown"
                channel = item.get("channel") or "unspecified"
                priority = item.get("priority") or "normal"
                message = (item.get("message") or "").replace("\n", " ").strip()
                lines.append(f"- [{priority}] {sender} via {channel} ({created}): {message}")
        lines.append("")
        return "\n".join(lines)

    @staticmethod
    def _write_report(
        report: str,
        entries: List[Dict[str, Any]],
        open_items: List[Dict[str, Any]],
        urgent: List[Dict[str, Any]],
        latest: List[Dict[str, Any]],
    ) -> tuple[str, str]:
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
        output_path = os.path.join(output_dir, f"ari_reception_{stamp}.md")
        tool_path = os.path.join(tool_dir, f"ari_reception_{stamp}.json")
        with open(output_path, "w") as f:
            f.write(report)
        with open(tool_path, "w") as f:
            json.dump(
                {
                    "total_entries": len(entries),
                    "open_entries": len(open_items),
                    "urgent_open_entries": len(urgent),
                    "open_queue": latest,
                },
                f,
                indent=2,
            )
        return output_path, tool_path

    @staticmethod
    def _display_name(task: Dict[str, Any]) -> str:
        value = str(task.get("name") or os.getenv("PERMANENCE_RECEPTIONIST_NAME") or "Ari").strip()
        return value if value else "Ari"
