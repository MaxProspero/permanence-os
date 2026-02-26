#!/usr/bin/env python3
"""
Integration readiness checks for external dependencies and credentials.
"""

from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parents[1]
WORKING_DIR = Path(os.getenv("PERMANENCE_WORKING_DIR", str(BASE_DIR / "memory" / "working")))
OUTPUT_DIR = Path(os.getenv("PERMANENCE_OUTPUT_DIR", str(BASE_DIR / "outputs")))
TOOL_DIR = Path(os.getenv("PERMANENCE_TOOL_DIR", str(BASE_DIR / "memory" / "tool")))


@dataclass(frozen=True)
class Check:
    key: str
    required: bool
    kind: str
    help_text: str


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _default_env(name: str) -> str:
    defaults = {
        "PERMANENCE_GMAIL_CREDENTIALS": str(WORKING_DIR / "google" / "credentials.json"),
        "PERMANENCE_GMAIL_TOKEN": str(WORKING_DIR / "google" / "token.json"),
    }
    return defaults.get(name, "")


def _normalize_value(raw: str, key: str) -> str:
    value = (raw or "").strip()
    if value:
        return value
    return _default_env(key)


def _check_item(check: Check) -> dict[str, Any]:
    raw = os.environ.get(check.key, "")
    value = _normalize_value(raw, check.key)
    exists = False
    if check.kind == "path":
        exists = bool(value) and Path(os.path.expanduser(value)).exists()
    elif check.kind == "command":
        exists = bool(value) and shutil.which(value) is not None
    elif check.kind == "url":
        exists = value.startswith("http://") or value.startswith("https://")
    else:
        exists = bool(value)

    status = "ready" if exists else ("missing" if check.required else "optional_missing")
    return {
        "key": check.key,
        "required": check.required,
        "kind": check.kind,
        "status": status,
        "exists": exists,
        "value_present": bool(value),
        "value_preview": value[:120] if value else "",
        "help": check.help_text,
    }


def _checks() -> list[Check]:
    return [
        Check("ANTHROPIC_API_KEY", True, "secret", "Required for live Claude model calls."),
        Check("PERMANENCE_GMAIL_CREDENTIALS", True, "path", "Google OAuth client credentials JSON."),
        Check("PERMANENCE_GMAIL_TOKEN", True, "path", "Google OAuth token JSON (run gmail-ingest once to authorize)."),
        Check("PERMANENCE_BOOKING_LINK", True, "url", "Booking link used in outreach and offers."),
        Check("PERMANENCE_PAYMENT_LINK", True, "url", "Payment link used in proposals and close flow."),
        Check("PERMANENCE_SLACK_WEBHOOK_URL", False, "url", "Optional Slack notifications."),
        Check("OPENAI_API_KEY", False, "secret", "Optional for OpenAI skills."),
        Check("GH_TOKEN", False, "secret", "Optional for GitHub automation."),
        Check("claude", False, "command", "Optional Claude CLI for terminal workflows."),
    ]


def _write_report(results: list[dict[str, Any]]) -> tuple[Path, Path]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    TOOL_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    md_path = OUTPUT_DIR / f"integration_readiness_{stamp}.md"
    latest_md = OUTPUT_DIR / "integration_readiness_latest.md"
    json_path = TOOL_DIR / f"integration_readiness_{stamp}.json"

    required_total = sum(1 for r in results if r["required"])
    required_ready = sum(1 for r in results if r["required"] and r["exists"])
    missing_required = [r for r in results if r["required"] and not r["exists"]]

    lines = [
        "# Integration Readiness",
        "",
        f"Generated (UTC): {_now_utc()}",
        "",
        "## Summary",
        f"- Required ready: {required_ready}/{required_total}",
        f"- Overall status: {'READY' if not missing_required else 'BLOCKED'}",
        "",
        "## Checks",
    ]
    for row in results:
        status = str(row["status"]).upper()
        req = "required" if row["required"] else "optional"
        detail = row["value_preview"] or "(empty)"
        lines.append(f"- {row['key']} | {req} | {status} | {detail}")

    if missing_required:
        lines.extend(["", "## Actions Needed"])
        for row in missing_required:
            lines.append(f"- Set `{row['key']}`: {row['help']}")

    payload = {
        "generated_at": _now_utc(),
        "required_total": required_total,
        "required_ready": required_ready,
        "blocked": bool(missing_required),
        "checks": results,
        "latest_markdown": str(latest_md),
    }
    report = "\n".join(lines) + "\n"
    md_path.write_text(report, encoding="utf-8")
    latest_md.write_text(report, encoding="utf-8")
    json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return md_path, json_path


def main() -> int:
    results = [_check_item(check) for check in _checks()]
    md_path, json_path = _write_report(results)
    blocked = any(row["required"] and not row["exists"] for row in results)
    print(f"Integration readiness written: {md_path}")
    print(f"Integration readiness latest: {OUTPUT_DIR / 'integration_readiness_latest.md'}")
    print(f"Tool payload written: {json_path}")
    print("Status: BLOCKED" if blocked else "Status: READY")
    return 1 if blocked else 0


if __name__ == "__main__":
    raise SystemExit(main())
