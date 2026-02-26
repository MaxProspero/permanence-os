#!/usr/bin/env python3
"""
Generate follow-up queue from outreach status and latest outreach pack.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parents[1]
WORKING_DIR = Path(os.getenv("PERMANENCE_WORKING_DIR", str(BASE_DIR / "memory" / "working")))
OUTPUT_DIR = Path(os.getenv("PERMANENCE_OUTPUT_DIR", str(BASE_DIR / "outputs")))
TOOL_DIR = Path(os.getenv("PERMANENCE_TOOL_DIR", str(BASE_DIR / "memory" / "tool")))
OUTREACH_STATUS_PATH = Path(
    os.getenv("PERMANENCE_REVENUE_OUTREACH_STATUS_PATH", str(WORKING_DIR / "revenue_outreach_status.jsonl"))
)
FOLLOWUP_HOURS = int(os.getenv("PERMANENCE_REVENUE_FOLLOWUP_HOURS", "48"))


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def _latest_tool_file(pattern: str) -> Path | None:
    if not TOOL_DIR.exists():
        return None
    matches = sorted(TOOL_DIR.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    return matches[0] if matches else None


def _load_outreach_messages() -> tuple[list[dict[str, Any]], Path | None]:
    tool_path = _latest_tool_file("revenue_outreach_pack_*.json")
    if not tool_path:
        return [], None
    payload = _read_json(tool_path, {})
    if not isinstance(payload, dict):
        return [], tool_path
    rows = payload.get("messages") or []
    if not isinstance(rows, list):
        return [], tool_path
    messages = [row for row in rows if isinstance(row, dict)]
    return messages, tool_path


def _message_key(message: dict[str, Any]) -> str:
    lead_id = str(message.get("lead_id") or "").strip()
    if lead_id:
        return lead_id
    explicit = str(message.get("message_key") or "").strip()
    if explicit:
        return explicit
    base = f"{message.get('lead_name', '')}|{message.get('subject', '')}"
    return hashlib.sha256(base.encode()).hexdigest()[:16]


def _parse_iso(raw: Any) -> datetime | None:
    text = str(raw or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def _load_outreach_status() -> dict[str, dict[str, Any]]:
    if not OUTREACH_STATUS_PATH.exists():
        return {}
    latest_by_key: dict[str, dict[str, Any]] = {}
    for raw in OUTREACH_STATUS_PATH.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict):
            continue
        key = str(payload.get("message_key") or "").strip()
        if key:
            latest_by_key[key] = payload
    return latest_by_key


def _build_followups(messages: list[dict[str, Any]], status_map: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    now = _utc_now()
    followups: list[dict[str, Any]] = []
    for message in messages:
        key = _message_key(message)
        state = status_map.get(key, {})
        status = str(state.get("status") or "pending").strip().lower()
        stage = str(message.get("stage") or "lead").strip().lower()
        sent_at = _parse_iso(state.get("timestamp"))
        lead_id = str(message.get("lead_id") or key)
        lead_name = str(message.get("lead_name") or message.get("name") or lead_id)
        channel = str(message.get("channel") or "dm")

        if status == "pending" and stage in {"proposal_sent", "negotiation"}:
            followups.append(
                {
                    "type": "first_touch",
                    "priority": "high",
                    "lead_id": lead_id,
                    "lead_name": lead_name,
                    "message_key": key,
                    "channel": channel,
                    "status": status,
                    "reason": f"High-stage lead ({stage}) still pending first send",
                    "action": "Send first outreach touch now and log as sent.",
                    "due_at": now.isoformat(),
                }
            )
            continue

        if status != "sent" or sent_at is None:
            continue
        due_at = sent_at + timedelta(hours=FOLLOWUP_HOURS)
        if now < due_at:
            continue
        followups.append(
            {
                "type": "follow_up",
                "priority": "high" if stage in {"proposal_sent", "negotiation"} else "normal",
                "lead_id": lead_id,
                "lead_name": lead_name,
                "message_key": key,
                "channel": channel,
                "status": status,
                "reason": f"No reply after {FOLLOWUP_HOURS}h",
                "action": "Send follow-up message and update outreach status when sent/replied.",
                "due_at": due_at.isoformat(),
                "last_sent_at": sent_at.isoformat(),
            }
        )

    followups.sort(key=lambda row: (row.get("priority") != "high", str(row.get("due_at") or "")))
    return followups[:14]


def _write_outputs(
    followups: list[dict[str, Any]],
    *,
    outreach_tool_path: Path | None,
) -> tuple[Path, Path]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    TOOL_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _utc_now().strftime("%Y%m%d-%H%M%S")
    md_path = OUTPUT_DIR / f"revenue_followup_queue_{stamp}.md"
    latest_md = OUTPUT_DIR / "revenue_followup_queue_latest.md"
    json_path = TOOL_DIR / f"revenue_followup_queue_{stamp}.json"

    lines = [
        "# Revenue Follow-up Queue",
        "",
        f"Generated (UTC): {_utc_now().isoformat()}",
        f"Outreach status source: {OUTREACH_STATUS_PATH}",
        f"Outreach tool source: {outreach_tool_path if outreach_tool_path else 'none'}",
        "",
        "## Follow-ups Due",
    ]
    if followups:
        for idx, item in enumerate(followups, start=1):
            lines.extend(
                [
                    f"{idx}. [{item.get('priority')}] {item.get('lead_name')} ({item.get('lead_id')})",
                    f"   - channel={item.get('channel')} | due={item.get('due_at')}",
                    f"   - reason={item.get('reason')}",
                    f"   - action={item.get('action')}",
                ]
            )
    else:
        lines.append("- No follow-ups due right now.")

    lines.extend(
        [
            "",
            "## Governance Notes",
            "- Draft-and-review workflow: human operator approves all outbound sends.",
            "- Update outreach status after each send/reply to keep queue accurate.",
            "",
        ]
    )
    report = "\n".join(lines)
    md_path.write_text(report, encoding="utf-8")
    latest_md.write_text(report, encoding="utf-8")

    payload = {
        "generated_at": _utc_now().isoformat(),
        "followup_hours": FOLLOWUP_HOURS,
        "status_path": str(OUTREACH_STATUS_PATH),
        "outreach_tool_path": str(outreach_tool_path) if outreach_tool_path else None,
        "count": len(followups),
        "followups": followups,
        "latest_markdown": str(latest_md),
    }
    json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return md_path, json_path


def main() -> int:
    messages, tool_path = _load_outreach_messages()
    status_map = _load_outreach_status()
    followups = _build_followups(messages, status_map)
    md_path, json_path = _write_outputs(followups, outreach_tool_path=tool_path)
    print(f"Revenue follow-up queue written: {md_path}")
    print(f"Revenue follow-up latest: {OUTPUT_DIR / 'revenue_followup_queue_latest.md'}")
    print(f"Tool payload written: {json_path}")
    print(f"Follow-ups due: {len(followups)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
