#!/usr/bin/env python3
"""
Generate a weekly revenue summary from pipeline, intake, and queue artifacts.
"""

from __future__ import annotations

import json
import os
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parents[1]
WORKING_DIR = Path(os.getenv("PERMANENCE_WORKING_DIR", str(BASE_DIR / "memory" / "working")))
OUTPUT_DIR = Path(os.getenv("PERMANENCE_OUTPUT_DIR", str(BASE_DIR / "outputs")))
TOOL_DIR = Path(os.getenv("PERMANENCE_TOOL_DIR", str(BASE_DIR / "memory" / "tool")))

PIPELINE_PATH = Path(os.getenv("PERMANENCE_SALES_PIPELINE_PATH", str(WORKING_DIR / "sales_pipeline.json")))
INTAKE_PATH = Path(os.getenv("PERMANENCE_REVENUE_INTAKE_PATH", str(WORKING_DIR / "revenue_intake.jsonl")))
PLAYBOOK_PATH = Path(os.getenv("PERMANENCE_REVENUE_PLAYBOOK_PATH", str(WORKING_DIR / "revenue_playbook.json")))

ACTION_RE = re.compile(r"^\d+\.\s+\[(.+)\]\s+(.+)$")
STAGE_PROB = {
    "lead": 0.10,
    "qualified": 0.25,
    "call_scheduled": 0.40,
    "proposal_sent": 0.60,
    "negotiation": 0.75,
    "won": 1.00,
    "lost": 0.00,
}


def _default_playbook() -> dict[str, Any]:
    return {
        "offer_name": "Permanence OS Foundation Setup",
        "cta_keyword": "FOUNDATION",
        "cta_public": 'DM me "FOUNDATION".',
        "pricing_tier": "Core",
        "price_usd": 1500,
    }


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_datetime(raw: Any) -> datetime | None:
    text = str(raw or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def _week_window(today: date | None = None) -> tuple[date, date]:
    today = today or date.today()
    start = today - timedelta(days=today.weekday())
    end = start + timedelta(days=6)
    return start, end


def _in_week(dt: datetime | None, week_start: date, week_end: date) -> bool:
    if dt is None:
        return False
    d = dt.date()
    return week_start <= d <= week_end


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def _load_playbook() -> dict[str, Any]:
    payload = _read_json(PLAYBOOK_PATH, {})
    if not isinstance(payload, dict):
        payload = {}
    merged = dict(_default_playbook())
    merged.update(payload)
    return merged


def _load_pipeline_rows() -> list[dict[str, Any]]:
    payload = _read_json(PIPELINE_PATH, [])
    if not isinstance(payload, list):
        return []
    return [row for row in payload if isinstance(row, dict)]


def _load_intake_rows() -> list[dict[str, Any]]:
    if not INTAKE_PATH.exists():
        return []
    rows: list[dict[str, Any]] = []
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
    return rows


def _latest_queue_path() -> Path | None:
    if not OUTPUT_DIR.exists():
        return None
    matches = sorted(OUTPUT_DIR.glob("revenue_action_queue_*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
    return matches[0] if matches else None


def _queue_actions(path: Path | None) -> list[str]:
    if not path or not path.exists():
        return []
    actions: list[str] = []
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        match = ACTION_RE.match(line)
        if not match:
            continue
        actions.append(f"[{match.group(1)}] {match.group(2)}")
    return actions


def _stage_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts = {stage: 0 for stage in STAGE_PROB}
    for row in rows:
        stage = str(row.get("stage") or "lead")
        counts[stage] = counts.get(stage, 0) + 1
    return counts


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _summarize_pipeline(rows: list[dict[str, Any]], week_start: date, week_end: date) -> dict[str, Any]:
    open_rows = [row for row in rows if str(row.get("stage")) not in {"won", "lost"}]
    stage_counts = _stage_counts(rows)

    leads_created_week = 0
    won_week = 0
    won_week_value = 0.0
    lost_week = 0

    for row in rows:
        created = _parse_datetime(row.get("created_at"))
        closed = _parse_datetime(row.get("closed_at"))
        stage = str(row.get("stage") or "lead")
        if _in_week(created, week_start, week_end):
            leads_created_week += 1
        if stage == "won" and _in_week(closed, week_start, week_end):
            won_week += 1
            won_week_value += _as_float(row.get("actual_value"), _as_float(row.get("est_value"), 0.0))
        if stage == "lost" and _in_week(closed, week_start, week_end):
            lost_week += 1

    open_value = 0.0
    weighted_value = 0.0
    urgent_rows: list[dict[str, Any]] = []
    cutoff = (date.today() + timedelta(days=1)).isoformat()
    for row in open_rows:
        est = _as_float(row.get("est_value"), 0.0)
        stage = str(row.get("stage") or "lead")
        open_value += est
        weighted_value += est * STAGE_PROB.get(stage, 0.0)
        due = str(row.get("next_action_due") or "")
        if due and due <= cutoff:
            urgent_rows.append(row)

    urgent_rows.sort(key=lambda r: str(r.get("next_action_due", "")))
    open_rows.sort(key=lambda r: str(r.get("updated_at", "")), reverse=True)
    return {
        "stage_counts": stage_counts,
        "open_count": len(open_rows),
        "open_value": open_value,
        "weighted_value": weighted_value,
        "leads_created_week": leads_created_week,
        "won_week": won_week,
        "won_week_value": won_week_value,
        "lost_week": lost_week,
        "urgent_rows": urgent_rows[:7],
        "open_rows": open_rows[:10],
    }


def _summarize_intake(rows: list[dict[str, Any]], week_start: date, week_end: date) -> dict[str, Any]:
    week_rows: list[dict[str, Any]] = []
    for row in rows:
        created = _parse_datetime(row.get("created_at"))
        if _in_week(created, week_start, week_end):
            week_rows.append(row)
    week_rows.sort(key=lambda r: str(r.get("created_at", "")), reverse=True)
    return {
        "count_week": len(week_rows),
        "rows_week": week_rows[:10],
    }


def _write_report(
    *,
    week_start: date,
    week_end: date,
    pipeline_summary: dict[str, Any],
    intake_summary: dict[str, Any],
    queue_actions: list[str],
    queue_source: Path | None,
    playbook: dict[str, Any],
) -> tuple[Path, Path]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    TOOL_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _utc_now().strftime("%Y%m%d-%H%M%S")
    md_path = OUTPUT_DIR / f"revenue_weekly_summary_{stamp}.md"
    latest_path = OUTPUT_DIR / "revenue_weekly_summary_latest.md"
    json_path = TOOL_DIR / f"revenue_weekly_summary_{stamp}.json"

    lines = [
        "# Revenue Weekly Summary",
        "",
        f"Generated (UTC): {_utc_now().isoformat()}",
        f"Week window (local): {week_start.isoformat()} to {week_end.isoformat()}",
        "",
        "## Weekly KPIs",
        f"- New leads created (week): {pipeline_summary['leads_created_week']}",
        f"- Intake submissions (week): {intake_summary['count_week']}",
        f"- Wins closed (week): {pipeline_summary['won_week']} | value=${pipeline_summary['won_week_value']:,.0f}",
        f"- Losses closed (week): {pipeline_summary['lost_week']}",
        "",
        "## Open Pipeline Snapshot",
        f"- Open leads now: {pipeline_summary['open_count']}",
        f"- Open pipeline value: ${pipeline_summary['open_value']:,.0f}",
        f"- Weighted pipeline value: ${pipeline_summary['weighted_value']:,.0f}",
        "",
        "### Stage Counts",
    ]

    for stage in sorted(pipeline_summary["stage_counts"].keys()):
        lines.append(f"- {stage}: {pipeline_summary['stage_counts'][stage]}")

    lines.extend(["", "### Urgent Actions (<=24h)"])
    if pipeline_summary["urgent_rows"]:
        for row in pipeline_summary["urgent_rows"]:
            lines.append(
                f"- {row.get('lead_id', 'unknown')} | {row.get('name', 'unknown')} | "
                f"stage={row.get('stage', 'lead')} | due={row.get('next_action_due') or '-'} | "
                f"next={row.get('next_action') or '-'}"
            )
    else:
        lines.append("- No urgent due actions.")

    lines.extend(["", "## Intake This Week"])
    if intake_summary["rows_week"]:
        for row in intake_summary["rows_week"]:
            lines.append(
                f"- {row.get('name', 'unknown')} | {row.get('email', 'unknown')} | "
                f"workflow={row.get('workflow') or '-'} | package={row.get('package') or '-'} | "
                f"at={row.get('created_at') or '-'}"
            )
    else:
        lines.append("- No intake submissions this week.")

    lines.extend(["", "## Focus Actions (Latest Queue)"])
    lines.append(f"- Queue source: {queue_source if queue_source else 'none'}")
    if queue_actions:
        for action in queue_actions[:7]:
            lines.append(f"- {action}")
    else:
        lines.append("- No queue actions found.")

    lines.extend(
        [
            "",
        "## Operator Notes",
            f"- Keep offer + CTA locked for the entire week: {playbook.get('offer_name')} | {playbook.get('cta_public')}",
            "- Move every touched lead to a concrete next stage before end of day.",
            "",
        ]
    )

    report = "\n".join(lines)
    md_path.write_text(report, encoding="utf-8")
    latest_path.write_text(report, encoding="utf-8")

    payload = {
        "generated_at": _utc_now().isoformat(),
        "week_start": week_start.isoformat(),
        "week_end": week_end.isoformat(),
        "pipeline_summary": pipeline_summary,
        "intake_summary": intake_summary,
        "queue_source": str(queue_source) if queue_source else None,
        "queue_actions": queue_actions[:7],
        "playbook": playbook,
        "paths": {
            "pipeline": str(PIPELINE_PATH),
            "intake": str(INTAKE_PATH),
            "playbook": str(PLAYBOOK_PATH),
            "latest_summary": str(latest_path),
        },
    }
    json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return md_path, json_path


def main() -> int:
    week_start, week_end = _week_window()
    pipeline_rows = _load_pipeline_rows()
    intake_rows = _load_intake_rows()
    queue_source = _latest_queue_path()
    queue_actions = _queue_actions(queue_source)
    playbook = _load_playbook()

    pipeline_summary = _summarize_pipeline(pipeline_rows, week_start, week_end)
    intake_summary = _summarize_intake(intake_rows, week_start, week_end)
    md_path, json_path = _write_report(
        week_start=week_start,
        week_end=week_end,
        pipeline_summary=pipeline_summary,
        intake_summary=intake_summary,
        queue_actions=queue_actions,
        queue_source=queue_source,
        playbook=playbook,
    )

    print(f"Revenue weekly summary written: {md_path}")
    print(f"Revenue weekly latest: {OUTPUT_DIR / 'revenue_weekly_summary_latest.md'}")
    print(f"Tool payload written: {json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
