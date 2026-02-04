#!/usr/bin/env python3
"""
SOCIAL MEDIA AGENT
Drafting, scheduling, engagement monitoring, and revenue tracking.
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


class SocialAgent:
    """
    ROLE: Draft content and monitor engagement. No auto-publishing.

    CONSTRAINTS:
    - All public posts require human approval
    - No automated replies or DMs
    """

    legal_exposure_domains = [
        "public_statements",
        "copyright",
        "ftc_disclosure",
        "defamation",
        "platform_tos",
    ]

    allowed_tools = ["social_read", "analytics"]

    forbidden_actions = [
        "publish_without_approval",
        "automated_replies",
        "automated_dms",
        "follow_unfollow_automation",
    ]

    def execute(self, task: Dict[str, Any]) -> AgentResult:
        """
        Manage local social drafts/queue and summary.
        Expected inputs (optional):
          - queue_dir: override queue directory
          - max_items: limit report entries
          - action: "draft" to append a new draft
          - draft: dict with title/body/platform tags
        """
        queue_dir = task.get("queue_dir") or os.getenv(
            "PERMANENCE_SOCIAL_QUEUE_DIR",
            os.path.join(os.path.dirname(__file__), "..", "..", "memory", "working", "social"),
        )
        queue_dir = os.path.abspath(queue_dir)
        os.makedirs(queue_dir, exist_ok=True)

        action = task.get("action")
        if action == "draft":
            draft = task.get("draft") or {}
            saved = self._append_draft(queue_dir, draft)
            return AgentResult(
                status="DRAFT_SAVED",
                notes=[f"Draft saved: {saved}"],
                artifact=saved,
            )

        max_items = int(task.get("max_items") or 20)
        drafts = self._load_drafts(queue_dir)
        if not drafts:
            return AgentResult(
                status="NO_DRAFTS",
                notes=[f"No drafts found in {queue_dir}"],
            )

        report, payload = self._format_report(drafts[:max_items], queue_dir)
        output_path, tool_path = self._write_report(report, payload)
        log(f"Social summary written: {output_path}", level="INFO")
        return AgentResult(
            status="SUMMARY",
            notes=[f"Social summary written: {output_path}", f"Tool memory: {tool_path}"],
            artifact=output_path,
        )

    def _load_drafts(self, queue_dir: str) -> List[Dict[str, Any]]:
        drafts: List[Dict[str, Any]] = []
        for file in sorted(Path(queue_dir).glob("*.json*")):
            drafts.extend(self._load_json_entries(file))
        drafts.sort(key=lambda d: d.get("created_at", ""), reverse=True)
        return drafts

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

    def _append_draft(self, queue_dir: str, draft: Dict[str, Any]) -> str:
        os.makedirs(queue_dir, exist_ok=True)
        payload = {
            "title": draft.get("title"),
            "body": draft.get("body"),
            "platform": draft.get("platform"),
            "tags": draft.get("tags", []),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        path = os.path.join(queue_dir, "drafts.jsonl")
        with open(path, "a") as f:
            f.write(json.dumps(payload) + "\n")
        return path

    def _format_report(self, drafts: List[Dict[str, Any]], queue_dir: str) -> tuple[str, Dict[str, Any]]:
        lines = [
            "# Social Draft Summary",
            "",
            f"Queue: {queue_dir}",
            f"Drafts listed: {len(drafts)}",
            "",
        ]
        for draft in drafts:
            title = draft.get("title") or "(no title)"
            platform = draft.get("platform") or "unspecified"
            created = draft.get("created_at") or "unknown"
            lines.append(f"- {title} [{platform}] ({created})")
        report = "\n".join(lines).rstrip() + "\n"
        return report, {"queue_dir": queue_dir, "count": len(drafts), "drafts": drafts}

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
        output_path = os.path.join(output_dir, f"social_summary_{stamp}.md")
        tool_path = os.path.join(tool_dir, f"social_summary_{stamp}.json")
        with open(output_path, "w") as f:
            f.write(report)
        with open(tool_path, "w") as f:
            json.dump(payload, f, indent=2)
        return output_path, tool_path
