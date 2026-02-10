"""
Permanence OS — Interface Agent v0.4
Network intake gateway. Routes external input into governed intake records.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, Tuple

from agents.base import BaseAgent
from memory.zero_point import ConfidenceLevel, MemoryType, ZeroPoint
from core.polemarch import Polemarch


class InterfaceAgent(BaseAgent):
    ROLE = "INTERFACE_AGENT"
    ROLE_DESCRIPTION = "External intake router and provenance normalizer"
    ALLOWED_TOOLS = ["write_zero_point", "route_to_polemarch"]
    FORBIDDEN_ACTIONS = ["content_generation", "chat_response", "modify_canon"]
    DEPARTMENT = "CORE"

    def __init__(
        self,
        zero_point: ZeroPoint | None = None,
        polemarch: Polemarch | None = None,
        max_payload_bytes: int = 64_000,
        canon_path: str = "canon/",
    ):
        super().__init__(canon_path=canon_path)
        self.zero_point = zero_point or ZeroPoint()
        self.polemarch = polemarch or Polemarch()
        self.max_payload_bytes = max_payload_bytes

    def _do_work(self, task: Dict) -> Dict:
        return {"status": "NOOP"}

    @staticmethod
    def _ticket_id() -> str:
        return f"TKT-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}"

    @staticmethod
    def sanitize_content(content: str) -> Tuple[str, list[str]]:
        flags: list[str] = []
        cleaned = content or ""

        # Remove script tags.
        cleaned_2 = re.sub(r"<\s*script[^>]*>.*?<\s*/\s*script\s*>", "", cleaned, flags=re.I | re.S)
        if cleaned_2 != cleaned:
            flags.append("script_tag_removed")
        cleaned = cleaned_2

        # Remove obvious SQL injection fragments.
        sql_patterns = [
            r"(?i)\bunion\s+select\b",
            r"(?i)\bdrop\s+table\b",
            r"(?i)\bor\s+1\s*=\s*1\b",
            r"(?i)\b--\b",
        ]
        for pattern in sql_patterns:
            cleaned_2 = re.sub(pattern, "", cleaned)
            if cleaned_2 != cleaned:
                flags.append("sql_pattern_removed")
            cleaned = cleaned_2

        # Remove shell command separators commonly used in payload injection.
        shell_cleaned = cleaned.replace("`", "").replace("$(", "").replace(");", ")")
        if shell_cleaned != cleaned:
            flags.append("shell_pattern_removed")
        cleaned = shell_cleaned.strip()

        return cleaned, flags

    def process_intake(self, payload: Any, source_type: str | None = None) -> Dict[str, str]:
        ticket_id = self._ticket_id()
        now = datetime.now(timezone.utc).isoformat()

        malformed = False
        flags: list[str] = []
        source = "unknown"
        content = ""
        payload_size = 0

        if isinstance(payload, dict):
            source = str(payload.get("source", source))
            content = str(payload.get("content", ""))
            payload_size = len(json.dumps(payload).encode("utf-8"))
        else:
            malformed = True
            flags.append("non_json_payload")
            content = str(payload)
            payload_size = len(content.encode("utf-8"))

        if payload_size > self.max_payload_bytes:
            malformed = True
            flags.append("payload_truncated")
            content = content[: self.max_payload_bytes]

        sanitized, sanitize_flags = self.sanitize_content(content)
        flags.extend(sanitize_flags)
        if sanitized != content:
            malformed = True

        intake_record = {
            "ticket_id": ticket_id,
            "source": source,
            "source_type": source_type or source,
            "content": sanitized,
            "timestamp": now,
            "raw_timestamp": payload.get("timestamp") if isinstance(payload, dict) else None,
            "malformed": malformed,
            "flags": sorted(set(flags)),
            "provenance": "external_interface",
            "intake_timestamp": now,
        }

        self.zero_point.write(
            content=json.dumps(intake_record),
            memory_type=MemoryType.INTAKE,
            tags=["intake", "external", intake_record["source_type"]],
            source="external_interface",
            author_agent=self.ROLE,
            confidence=ConfidenceLevel.LOW if malformed else ConfidenceLevel.MEDIUM,
            evidence_count=1,
            limitations="Sanitized interface payload.",
            emergency=False,
        )

        self.polemarch.assess_risk(intake_record)
        return {"ticket_id": ticket_id}

    def listen(self, host: str = "127.0.0.1", port: int = 8000) -> None:
        agent = self

        class IntakeHandler(BaseHTTPRequestHandler):
            def _write_json(self, body: Dict[str, str], status: int = 200) -> None:
                payload = json.dumps(body).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def do_POST(self):  # noqa: N802
                if self.path != "/intake":
                    self._write_json({"ticket_id": "TKT-NOTFOUND"}, status=404)
                    return

                length = int(self.headers.get("Content-Length", "0"))
                body = self.rfile.read(max(0, length))
                try:
                    payload = json.loads(body.decode("utf-8"))
                except Exception:
                    payload = body.decode("utf-8", errors="ignore")

                result = agent.process_intake(payload, source_type="webhook")
                self._write_json(result, status=200)

            def log_message(self, *_args) -> None:  # pragma: no cover
                return

        server = ThreadingHTTPServer((host, port), IntakeHandler)
        try:
            server.serve_forever()
        finally:  # pragma: no cover
            server.server_close()
