#!/usr/bin/env python3
"""
Build a revenue activation queue from the latest agent outputs.

This is read-only synthesis across existing markdown artifacts and does not
publish or send anything.
"""

from __future__ import annotations

import json
import os
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

BASE_DIR = Path(__file__).resolve().parents[1]
OUTPUT_DIR = Path(os.getenv("PERMANENCE_OUTPUT_DIR", str(BASE_DIR / "outputs")))
TOOL_DIR = Path(os.getenv("PERMANENCE_TOOL_DIR", str(BASE_DIR / "memory" / "tool")))
WORKING_DIR = Path(os.getenv("PERMANENCE_WORKING_DIR", str(BASE_DIR / "memory" / "working")))
PIPELINE_PATH = Path(os.getenv("PERMANENCE_SALES_PIPELINE_PATH", str(WORKING_DIR / "sales_pipeline.json")))
INTAKE_PATH = Path(os.getenv("PERMANENCE_REVENUE_INTAKE_PATH", str(WORKING_DIR / "revenue_intake.jsonl")))

SOCIAL_RE = re.compile(r"^-\s+(.+)\s+\[(.+)\]\s+\((.+)\)\s*$")
OPEN_STAGES = {"lead", "qualified", "call_scheduled", "proposal_sent", "negotiation"}


def _latest(pattern: str) -> Path | None:
    if not OUTPUT_DIR.exists():
        return None
    matches = sorted(OUTPUT_DIR.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    return matches[0] if matches else None


def _parse_email(path: Path | None) -> list[dict]:
    if not path or not path.exists():
        return []
    items: list[dict] = []
    bucket = "P3"
    for raw in path.read_text(errors="ignore").splitlines():
        line = raw.strip()
        if line.startswith("## P0"):
            bucket = "P0"
            continue
        if line.startswith("## P1"):
            bucket = "P1"
            continue
        if line.startswith("## P2"):
            bucket = "P2"
            continue
        if line.startswith("## P3"):
            bucket = "P3"
            continue
        if not line.startswith("- [") or "] " not in line:
            continue
        try:
            score_text = line.split("]", 1)[0].replace("- [", "").strip()
            score = int(score_text)
        except ValueError:
            continue
        body = line.split("] ", 1)[1].strip()
        if "<" in body and ">" in body and body.rfind(">") > body.rfind("<"):
            summary = body[: body.rfind(">") + 1]
            received = ""
        elif " (" in body and body.endswith(")"):
            summary, received = body.rsplit(" (", 1)
            received = received[:-1]
        else:
            summary, received = body, ""
        items.append({"bucket": bucket, "score": score, "summary": summary, "received": received})

    priority_order = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
    items.sort(key=lambda x: (priority_order.get(x["bucket"], 9), -x["score"]))
    return items


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def _load_pipeline_rows() -> list[dict]:
    data = _read_json(PIPELINE_PATH, [])
    if not isinstance(data, list):
        return []
    return [row for row in data if isinstance(row, dict)]


def _load_intake_rows() -> list[dict]:
    if not INTAKE_PATH.exists():
        return []
    rows: list[dict] = []
    for raw in INTAKE_PATH.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line:
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict):
            rows.append(item)
    rows.sort(key=lambda r: str(r.get("created_at", "")), reverse=True)
    return rows


def _parse_datetime(raw: Any) -> Optional[datetime]:
    text = str(raw or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def _week_window(today: Optional[date] = None) -> tuple[date, date]:
    today = today or datetime.now().date()
    start = today - timedelta(days=today.weekday())
    end = start + timedelta(days=6)
    return start, end


def _in_window(dt: Optional[datetime], start: date, end: date) -> bool:
    if dt is None:
        return False
    day = dt.date()
    return start <= day <= end


def _safe_rate(numerator: int, denominator: int) -> Optional[float]:
    if denominator <= 0:
        return None
    return numerator / denominator


def _build_revenue_funnel(pipeline_rows: list[dict], intake_rows: list[dict]) -> dict:
    week_start, week_end = _week_window()

    intake_week = 0
    for row in intake_rows:
        created = _parse_datetime(row.get("created_at"))
        if _in_window(created, week_start, week_end):
            intake_week += 1

    leads_week = 0
    wins_week = 0
    for row in pipeline_rows:
        created = _parse_datetime(row.get("created_at"))
        closed = _parse_datetime(row.get("closed_at"))
        stage = str(row.get("stage") or "lead")
        if _in_window(created, week_start, week_end):
            leads_week += 1
        if stage == "won" and _in_window(closed, week_start, week_end):
            wins_week += 1

    total = len(pipeline_rows)
    qualified_plus = sum(
        1 for row in pipeline_rows if str(row.get("stage") or "lead") in {"qualified", "call_scheduled", "proposal_sent", "negotiation", "won"}
    )
    call_plus = sum(
        1 for row in pipeline_rows if str(row.get("stage") or "lead") in {"call_scheduled", "proposal_sent", "negotiation", "won"}
    )
    proposal_plus = sum(
        1 for row in pipeline_rows if str(row.get("stage") or "lead") in {"proposal_sent", "negotiation", "won"}
    )
    won_total = sum(1 for row in pipeline_rows if str(row.get("stage") or "lead") == "won")

    segments = [
        {
            "key": "intake_to_lead",
            "label": "Intake -> Lead",
            "numerator": leads_week,
            "denominator": intake_week,
            "rate": _safe_rate(leads_week, intake_week),
        },
        {
            "key": "lead_to_qualified",
            "label": "Lead -> Qualified",
            "numerator": qualified_plus,
            "denominator": total,
            "rate": _safe_rate(qualified_plus, total),
        },
        {
            "key": "qualified_to_call",
            "label": "Qualified -> Call",
            "numerator": call_plus,
            "denominator": qualified_plus,
            "rate": _safe_rate(call_plus, qualified_plus),
        },
        {
            "key": "call_to_proposal",
            "label": "Call -> Proposal",
            "numerator": proposal_plus,
            "denominator": call_plus,
            "rate": _safe_rate(proposal_plus, call_plus),
        },
        {
            "key": "proposal_to_won",
            "label": "Proposal -> Won",
            "numerator": won_total,
            "denominator": proposal_plus,
            "rate": _safe_rate(won_total, proposal_plus),
        },
    ]

    bottleneck: Optional[dict] = None
    for segment in segments:
        rate = segment.get("rate")
        denominator = int(segment.get("denominator") or 0)
        if rate is None or denominator <= 0:
            continue
        candidate = {
            "key": segment["key"],
            "label": segment["label"],
            "rate": rate,
            "numerator": segment["numerator"],
            "denominator": denominator,
        }
        if bottleneck is None or float(rate) < float(bottleneck["rate"]):
            bottleneck = candidate

    suggestions = {
        "intake_to_lead": "Close intake loop same-day: respond and book fit call inside 2 hours.",
        "lead_to_qualified": "Tighten qualification: use 3 must-pass questions before scheduling.",
        "qualified_to_call": "Boost call conversion: direct calendar link plus 2 follow-up nudges.",
        "call_to_proposal": "Ship proposal within 24h after each call.",
        "proposal_to_won": "Increase closes with urgency, objection handling, and 48h follow-up.",
    }
    if bottleneck is not None:
        bottleneck["recommendation"] = suggestions.get(
            bottleneck["key"],
            "Focus this stage with stronger follow-up discipline.",
        )

    return {
        "week_start": week_start.isoformat(),
        "week_end": week_end.isoformat(),
        "intake_week": intake_week,
        "leads_created_week": leads_week,
        "wins_week": wins_week,
        "pipeline_total": total,
        "segments": segments,
        "bottleneck": bottleneck,
    }


def _parse_social(path: Path | None) -> list[dict]:
    if not path or not path.exists():
        return []
    drafts: list[dict] = []
    for raw in path.read_text(errors="ignore").splitlines():
        line = raw.strip()
        m = SOCIAL_RE.match(line)
        if not m:
            continue
        drafts.append(
            {
                "title": m.group(1),
                "platform": m.group(2),
                "created_at": m.group(3),
            }
        )
    return drafts


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _next_stage(stage: str) -> str:
    stages = ["lead", "qualified", "call_scheduled", "proposal_sent", "negotiation", "won"]
    try:
        idx = stages.index(stage)
    except ValueError:
        return "qualified"
    if idx >= len(stages) - 1:
        return stage
    return stages[idx + 1]


def _pipeline_actions(pipeline_rows: list[dict]) -> list[dict]:
    actions: list[dict] = []
    today = date.today().isoformat()
    tomorrow = (date.today() + timedelta(days=1)).isoformat()

    open_rows = [row for row in pipeline_rows if str(row.get("stage") or "lead") in OPEN_STAGES]
    open_rows.sort(key=lambda r: (str(r.get("next_action_due") or "9999-12-31"), str(r.get("updated_at") or "")))

    urgent = [row for row in open_rows if str(row.get("next_action_due") or "") and str(row.get("next_action_due")) <= tomorrow]
    for row in urgent[:3]:
        stage = str(row.get("stage") or "lead")
        lead_id = str(row.get("lead_id") or "unknown")
        name = str(row.get("name") or "Lead")
        due = str(row.get("next_action_due") or "-")
        next_action = str(row.get("next_action") or "Move stage forward")
        actions.append(
            {
                "type": "pipeline_urgent",
                "window": "today",
                "action": f"{next_action} — {name} ({lead_id}) due {due}; target stage: {_next_stage(stage)}",
                "source_bucket": "pipeline",
            }
        )

    stale_cutoff = datetime.now(timezone.utc) - timedelta(days=3)
    stale_rows = []
    for row in open_rows:
        updated = _parse_datetime(row.get("updated_at"))
        if updated and updated < stale_cutoff:
            stale_rows.append(row)
    stale_rows.sort(key=lambda r: str(r.get("updated_at") or ""))
    for row in stale_rows[:2]:
        lead_id = str(row.get("lead_id") or "unknown")
        name = str(row.get("name") or "Lead")
        stage = str(row.get("stage") or "lead")
        est_value = _as_float(row.get("est_value"), 0.0)
        actions.append(
            {
                "type": "pipeline_stale",
                "window": "48h",
                "action": f"Re-engage stale lead {name} ({lead_id}) at stage={stage} (~${est_value:,.0f})",
                "source_bucket": "pipeline",
            }
        )

    return actions


def _add_unique_action(actions: list[dict], seen: set[str], item: dict, max_actions: int = 7) -> None:
    if len(actions) >= max_actions:
        return
    text = str(item.get("action") or "").strip()
    if not text:
        return
    key = text.lower()
    if key in seen:
        return
    seen.add(key)
    actions.append(item)


def _build_actions(
    email_items: list[dict],
    social_items: list[dict],
    pipeline_rows: list[dict],
    intake_rows: list[dict],
) -> tuple[list[dict], dict]:
    actions: list[dict] = []
    seen: set[str] = set()
    funnel = _build_revenue_funnel(pipeline_rows, intake_rows)

    for item in email_items[:2]:
        _add_unique_action(
            actions,
            seen,
            {
                "type": "email_followup",
                "window": "today",
                "action": f"Resolve high-priority email: {item['summary']}",
                "source_bucket": item["bucket"],
            },
        )

    for item in _pipeline_actions(pipeline_rows):
        _add_unique_action(actions, seen, item)

    bottleneck = funnel.get("bottleneck")
    if isinstance(bottleneck, dict) and bottleneck.get("label"):
        _add_unique_action(
            actions,
            seen,
            {
                "type": "funnel_bottleneck",
                "window": "today",
                "action": f"Fix funnel bottleneck ({bottleneck['label']}): {bottleneck.get('recommendation', 'Improve this stage')}",
                "source_bucket": "funnel",
            },
        )

    intake_week = int(funnel.get("intake_week") or 0)
    leads_week = int(funnel.get("leads_created_week") or 0)
    intake_gap = intake_week - leads_week
    if intake_gap > 0:
        _add_unique_action(
            actions,
            seen,
            {
                "type": "intake_gap",
                "window": "today",
                "action": f"Close intake gap: convert {intake_gap} unworked intake submissions into qualified leads.",
                "source_bucket": "funnel",
            },
        )

    for draft in social_items[:2]:
        _add_unique_action(
            actions,
            seen,
            {
                "type": "content_publish",
                "window": "today",
                "action": f"Polish + publish draft on {draft['platform']}: {draft['title']}",
                "source_bucket": "social_draft",
            },
        )

    defaults = [
        {
            "type": "offer_clarity",
            "window": "today",
            "action": "Define one core offer and one CTA for this week (single sentence each).",
            "source_bucket": "template",
        },
        {
            "type": "lead_capture",
            "window": "tomorrow",
            "action": "Create one lead capture asset (form/doc) and link it from every social bio.",
            "source_bucket": "template",
        },
        {
            "type": "outreach",
            "window": "48h",
            "action": "Send 5 direct outreach messages to qualified prospects with the weekly CTA.",
            "source_bucket": "template",
        },
        {
            "type": "offer_iteration",
            "window": "72h",
            "action": "Review response patterns and tighten messaging based on objections.",
            "source_bucket": "template",
        },
        {
            "type": "proposal_velocity",
            "window": "today",
            "action": "Send every pending proposal before end of day with one explicit close question.",
            "source_bucket": "template",
        },
        {
            "type": "followup_cadence",
            "window": "48h",
            "action": "Run 2-touch follow-up on every open lead with no reply in the last 72h.",
            "source_bucket": "template",
        },
        {
            "type": "weekly_review",
            "window": "7d",
            "action": "Run weekly review: pipeline count, response rate, and next experiments.",
            "source_bucket": "template",
        },
    ]

    for default in defaults:
        _add_unique_action(actions, seen, default)

    return actions[:7], funnel


def _write_output(
    actions: list[dict],
    *,
    email_src: Path | None,
    social_src: Path | None,
    funnel: dict,
) -> tuple[Path, Path]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    TOOL_DIR.mkdir(parents=True, exist_ok=True)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    md_path = OUTPUT_DIR / f"revenue_action_queue_{stamp}.md"
    latest_path = OUTPUT_DIR / "revenue_action_queue_latest.md"
    json_path = TOOL_DIR / f"revenue_action_queue_{stamp}.json"

    lines = [
        "# Revenue Action Queue",
        "",
        f"Generated (UTC): {datetime.now(timezone.utc).isoformat()}",
        "",
        "## Inputs",
        f"- Email triage source: {email_src if email_src else 'none'}",
        f"- Social summary source: {social_src if social_src else 'none'}",
        f"- Pipeline source: {PIPELINE_PATH}",
        f"- Intake source: {INTAKE_PATH}",
        "",
        "## Funnel Signals",
        (
            f"- Week: {funnel.get('week_start', 'unknown')} to {funnel.get('week_end', 'unknown')} | "
            f"intake={funnel.get('intake_week', 0)} | leads={funnel.get('leads_created_week', 0)} | "
            f"wins={funnel.get('wins_week', 0)}"
        ),
        (
            f"- Bottleneck: {funnel.get('bottleneck', {}).get('label', 'n/a')} | "
            f"{funnel.get('bottleneck', {}).get('recommendation', 'insufficient data')}"
            if isinstance(funnel.get("bottleneck"), dict)
            else "- Bottleneck: insufficient data"
        ),
        "",
        "## Next 7 Actions",
    ]
    for idx, item in enumerate(actions, start=1):
        lines.append(f"{idx}. [{item['window']}] {item['action']}")

    lines.extend(
        [
            "",
            "## Governance Notes",
            "- Public posts and outbound messages still require human approval before sending/publishing.",
            "- Financial, legal, payment, and contract actions remain escalation-gated.",
            "",
        ]
    )
    report = "\n".join(lines)
    md_path.write_text(report, encoding="utf-8")
    latest_path.write_text(report, encoding="utf-8")

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "inputs": {
            "email_triage": str(email_src) if email_src else None,
            "social_summary": str(social_src) if social_src else None,
            "pipeline": str(PIPELINE_PATH),
            "intake": str(INTAKE_PATH),
        },
        "latest_markdown": str(latest_path),
        "funnel": funnel,
        "actions": actions,
    }
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return md_path, json_path


def main() -> int:
    email_path = _latest("email_triage_*.md")
    social_path = _latest("social_summary_*.md")
    email_items = _parse_email(email_path)
    social_items = _parse_social(social_path)
    pipeline_rows = _load_pipeline_rows()
    intake_rows = _load_intake_rows()
    actions, funnel = _build_actions(email_items, social_items, pipeline_rows, intake_rows)
    md_path, json_path = _write_output(
        actions,
        email_src=email_path,
        social_src=social_path,
        funnel=funnel,
    )

    print(f"Revenue action queue written: {md_path}")
    print(f"Tool payload written: {json_path}")
    print(f"Actions generated: {len(actions)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
