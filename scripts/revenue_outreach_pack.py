#!/usr/bin/env python3
"""
Generate a revenue outreach message pack from live pipeline rows.

This is draft-only output for human review before sending.
"""

from __future__ import annotations

import json
import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parents[1]
WORKING_DIR = Path(os.getenv("PERMANENCE_WORKING_DIR", str(BASE_DIR / "memory" / "working")))
OUTPUT_DIR = Path(os.getenv("PERMANENCE_OUTPUT_DIR", str(BASE_DIR / "outputs")))
TOOL_DIR = Path(os.getenv("PERMANENCE_TOOL_DIR", str(BASE_DIR / "memory" / "tool")))
PIPELINE_PATH = Path(os.getenv("PERMANENCE_SALES_PIPELINE_PATH", str(WORKING_DIR / "sales_pipeline.json")))

OPEN_STAGES = {"lead", "qualified", "call_scheduled", "proposal_sent", "negotiation"}
STAGE_PRIORITY = {
    "negotiation": 5,
    "proposal_sent": 4,
    "call_scheduled": 3,
    "qualified": 2,
    "lead": 1,
}
CTA_BY_STAGE = {
    "lead": "book a 15-minute fit call this week",
    "qualified": "lock a discovery call and confirm your top blocker",
    "call_scheduled": "confirm call agenda and desired outcome before the call",
    "proposal_sent": "reply yes/no on proposal fit and choose a kickoff date",
    "negotiation": "finalize kickoff this week and secure invoice approval",
}
OPEN_LINE_BY_STAGE = {
    "lead": "quick follow-up to keep momentum.",
    "qualified": "wanted to move this forward while it's hot.",
    "call_scheduled": "before we meet, I want to make this call high-leverage.",
    "proposal_sent": "checking in on the proposal and next decision step.",
    "negotiation": "one step away from getting this live.",
}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def _load_pipeline_rows() -> list[dict[str, Any]]:
    payload = _read_json(PIPELINE_PATH, [])
    if not isinstance(payload, list):
        return []
    return [row for row in payload if isinstance(row, dict)]


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _suggest_channel(source: str) -> str:
    text = str(source or "").lower()
    if any(token in text for token in {"dm", "x", "twitter", "linkedin", "social"}):
        return "dm"
    return "email"


def _rank_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    today = date.today()
    tomorrow = today + timedelta(days=1)

    def key(row: dict[str, Any]) -> tuple[int, int, float, str]:
        stage = str(row.get("stage") or "lead")
        due = str(row.get("next_action_due") or "")
        urgent = 1 if due and due <= tomorrow.isoformat() else 0
        return (
            urgent,
            STAGE_PRIORITY.get(stage, 0),
            _as_float(row.get("est_value"), 0.0),
            str(row.get("updated_at") or ""),
        )

    ranked = [row for row in rows if str(row.get("stage") or "lead") in OPEN_STAGES]
    ranked.sort(key=key, reverse=True)
    return ranked


def _build_message(row: dict[str, Any]) -> dict[str, Any]:
    lead_id = str(row.get("lead_id") or "unknown")
    name = str(row.get("name") or "there")
    stage = str(row.get("stage") or "lead")
    source = str(row.get("source") or "pipeline")
    next_action = str(row.get("next_action") or "move to next stage")
    due = str(row.get("next_action_due") or "")
    est_value = _as_float(row.get("est_value"), 0.0)

    channel = _suggest_channel(source)
    cta = CTA_BY_STAGE.get(stage, CTA_BY_STAGE["lead"])
    open_line = OPEN_LINE_BY_STAGE.get(stage, OPEN_LINE_BY_STAGE["lead"])
    subject = f"{name} — next step for FOUNDATION setup"
    body = (
        f"Hey {name}, {open_line} "
        f"Current next step on my side is: {next_action}. "
        f"If this is still a priority, let's {cta}. "
        f"I can send the intake + calendar link right now."
    )
    if stage in {"proposal_sent", "negotiation"}:
        body += " If helpful, I can also walk through scope line-by-line in one quick call."

    return {
        "lead_id": lead_id,
        "lead_name": name,
        "stage": stage,
        "source": source,
        "channel": channel,
        "subject": subject,
        "body": body,
        "next_action_due": due,
        "est_value": est_value,
    }


def _write_outputs(messages: list[dict[str, Any]]) -> tuple[Path, Path]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    TOOL_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _utc_now().strftime("%Y%m%d-%H%M%S")

    md_path = OUTPUT_DIR / f"revenue_outreach_pack_{stamp}.md"
    latest_path = OUTPUT_DIR / "revenue_outreach_pack_latest.md"
    json_path = TOOL_DIR / f"revenue_outreach_pack_{stamp}.json"

    lines = [
        "# Revenue Outreach Pack",
        "",
        f"Generated (UTC): {_utc_now().isoformat()}",
        f"Pipeline source: {PIPELINE_PATH}",
        "",
        "## Priority Messages",
    ]
    if not messages:
        lines.append("- No open leads found. Add/qualify leads first.")
    else:
        for idx, item in enumerate(messages, start=1):
            lines.extend(
                [
                    f"### {idx}. {item['lead_name']} ({item['lead_id']})",
                    f"- Stage: {item['stage']}",
                    f"- Channel: {item['channel']}",
                    f"- Estimated value: ${item['est_value']:,.0f}",
                    f"- Due: {item['next_action_due'] or '-'}",
                    f"- Subject: {item['subject']}",
                    "",
                    "```text",
                    item["body"],
                    "```",
                    "",
                ]
            )

    lines.extend(
        [
            "## Governance Notes",
            "- Draft-only: human review required before any send/publish action.",
            "- Keep claims factual and aligned with approved offer + CTA.",
            "",
        ]
    )

    report = "\n".join(lines)
    md_path.write_text(report, encoding="utf-8")
    latest_path.write_text(report, encoding="utf-8")

    payload = {
        "generated_at": _utc_now().isoformat(),
        "pipeline_path": str(PIPELINE_PATH),
        "messages": messages,
        "latest_markdown": str(latest_path),
    }
    json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return md_path, json_path


def main() -> int:
    rows = _load_pipeline_rows()
    ranked = _rank_rows(rows)
    messages = [_build_message(row) for row in ranked[:7]]
    md_path, json_path = _write_outputs(messages)
    print(f"Revenue outreach pack written: {md_path}")
    print(f"Revenue outreach latest: {OUTPUT_DIR / 'revenue_outreach_pack_latest.md'}")
    print(f"Tool payload written: {json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
