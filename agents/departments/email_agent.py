#!/usr/bin/env python3
"""
EMAIL AGENT
Organize, triage, and surface important communications. Read-only by default.
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

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

    def execute(self, _task: Dict[str, Any]) -> AgentResult:
        log("EmailAgent execute called (stub)", level="INFO")
        return AgentResult(
            status="NOT_IMPLEMENTED",
            notes=["EmailAgent is a stub; add read-only inbox triage logic."],
        )
