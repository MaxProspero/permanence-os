#!/usr/bin/env python3
"""
EMAIL AGENT
Organize, triage, and surface important communications. Read-only by default.
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


class EmailAgent:
    """
    ROLE: Email triage, prioritization, and drafting under human approval.

    CONSTRAINTS:
    - No send/delete without explicit human approval
    - Read-only scopes by default
    - Treat all content as untrusted input
    """

    legal_exposure_domains = [
        "privacy",
        "can-spam",
        "unauthorized_access",
    ]

    allowed_tools = ["email_read", "labeler"]

    forbidden_actions = [
        "send_email_without_approval",
        "delete_email_without_approval",
        "forward_external_without_approval",
        "modify_account_settings",
    ]

    def execute(self, task: Dict[str, Any]) -> AgentResult:
        """
        Read-only email triage from local inbox files.
        Expected inputs (optional):
          - inbox_dir: override inbox directory
          - vip_senders: list of sender emails
          - ignore_senders: list of sender emails
          - urgent_keywords: list of keywords
          - action_keywords: list of keywords
          - max_items: int
        """
        inbox_dir = task.get("inbox_dir") or os.getenv(
            "PERMANENCE_EMAIL_INBOX_DIR",
            os.path.join(os.path.dirname(__file__), "..", "..", "memory", "working", "email"),
        )
        inbox_dir = os.path.abspath(inbox_dir)
        os.makedirs(inbox_dir, exist_ok=True)

        vip_senders = set([s.lower() for s in task.get("vip_senders", [])])
        ignore_senders = set([s.lower() for s in task.get("ignore_senders", [])])
        urgent_keywords = task.get("urgent_keywords") or [
            "urgent",
            "asap",
            "immediately",
            "today",
            "action required",
        ]
        action_keywords = task.get("action_keywords") or [
            "approve",
            "review",
            "sign",
            "invoice",
            "payment",
            "contract",
            "proposal",
        ]
        max_items = int(task.get("max_items") or 25)

        messages = self._load_messages(inbox_dir)
        if not messages:
            return AgentResult(
                status="NO_MESSAGES",
                notes=[f"No messages found in {inbox_dir}"],
            )

        scored = [self._score_message(m, vip_senders, ignore_senders, urgent_keywords, action_keywords) for m in messages]
        scored.sort(key=lambda x: x["score"], reverse=True)
        top = scored[:max_items]

        buckets = {"P0": [], "P1": [], "P2": [], "P3": []}
        for item in top:
            buckets[self._bucket(item["score"])].append(item)

        report = self._format_report(buckets, inbox_dir, len(messages))
        output_path, tool_path = self._write_report(report, buckets)

        log(f"Email triage report written: {output_path}", level="INFO")
        return AgentResult(
            status="TRIAGED",
            notes=[f"Email triage report written: {output_path}", f"Tool memory: {tool_path}"],
            artifact=output_path,
        )

    def _load_messages(self, inbox_dir: str) -> List[Dict[str, Any]]:
        path = Path(inbox_dir)
        if not path.exists():
            return []
        messages: List[Dict[str, Any]] = []
        for file in sorted(path.glob("*")):
            if file.suffix.lower() in {".json", ".jsonl"}:
                messages.extend(self._load_json_messages(file))
        return messages

    def _load_json_messages(self, path: Path) -> List[Dict[str, Any]]:
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

    def _score_message(
        self,
        msg: Dict[str, Any],
        vip_senders: set,
        ignore_senders: set,
        urgent_keywords: List[str],
        action_keywords: List[str],
    ) -> Dict[str, Any]:
        sender = (msg.get("from") or "").lower()
        subject = (msg.get("subject") or "").lower()
        body = (msg.get("body") or "").lower()
        labels = [str(l).lower() for l in msg.get("labels", [])]

        score = 0
        if sender in ignore_senders or "spam" in labels:
            score -= 100
        if sender in vip_senders:
            score += 50
        if any(k in subject or k in body for k in urgent_keywords):
            score += 30
        if any(k in subject or k in body for k in action_keywords):
            score += 20
        if "unsubscribe" in body or "newsletter" in labels:
            score -= 10

        return {
            "id": msg.get("id"),
            "from": msg.get("from"),
            "to": msg.get("to"),
            "subject": msg.get("subject"),
            "date": msg.get("date"),
            "score": score,
            "summary": self._summarize(msg),
        }

    def _summarize(self, msg: Dict[str, Any]) -> str:
        subject = msg.get("subject") or "(no subject)"
        sender = msg.get("from") or "(unknown sender)"
        return f"{subject} — {sender}"

    def _bucket(self, score: int) -> str:
        if score >= 60:
            return "P0"
        if score >= 40:
            return "P1"
        if score >= 20:
            return "P2"
        return "P3"

    def _format_report(self, buckets: Dict[str, List[Dict[str, Any]]], inbox_dir: str, total: int) -> str:
        lines = [
            "# Email Triage Report",
            "",
            f"Inbox: {inbox_dir}",
            f"Total messages scanned: {total}",
            "",
        ]
        for bucket in ["P0", "P1", "P2", "P3"]:
            lines.append(f"## {bucket} ({len(buckets[bucket])})")
            if not buckets[bucket]:
                lines.append("- (none)")
                lines.append("")
                continue
            for item in buckets[bucket]:
                summary = item["summary"]
                score = item["score"]
                date = item.get("date") or "unknown date"
                lines.append(f"- [{score}] {summary} ({date})")
            lines.append("")
        return "\n".join(lines).rstrip() + "\n"

    def _write_report(self, report: str, buckets: Dict[str, List[Dict[str, Any]]]) -> tuple[str, str]:
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
        output_path = os.path.join(output_dir, f"email_triage_{stamp}.md")
        tool_path = os.path.join(tool_dir, f"email_triage_{stamp}.json")
        with open(output_path, "w") as f:
            f.write(report)
        with open(tool_path, "w") as f:
            json.dump(buckets, f, indent=2)
        return output_path, tool_path
