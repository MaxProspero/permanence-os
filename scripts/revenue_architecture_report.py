#!/usr/bin/env python3
"""
Generate Revenue Architecture v1 report (streams, KPI scorecard, pipeline).
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
STREAMS_PATH = Path(os.getenv("PERMANENCE_REVENUE_STREAMS_PATH", str(WORKING_DIR / "revenue_streams.json")))
TARGETS_PATH = Path(os.getenv("PERMANENCE_REVENUE_TARGETS_PATH", str(WORKING_DIR / "revenue_targets.json")))

STAGE_PROB = {
    "lead": 0.10,
    "qualified": 0.25,
    "call_scheduled": 0.40,
    "proposal_sent": 0.60,
    "negotiation": 0.75,
    "won": 1.00,
    "lost": 0.00,
}

ACTION_RE = re.compile(r"^\d+\.\s+\[(.+)\]\s+(.+)$")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _week_start(today: date | None = None) -> str:
    today = today or date.today()
    monday = today - timedelta(days=today.weekday())
    return monday.isoformat()


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _ensure_targets() -> dict[str, Any]:
    weekly_revenue_target = int(os.getenv("PERMANENCE_REVENUE_WEEKLY_TARGET", "3000"))
    defaults = {
        "week_of": _week_start(),
        "weekly_revenue_target": weekly_revenue_target,
        "monthly_revenue_target": int(os.getenv("PERMANENCE_REVENUE_MONTHLY_TARGET", str(max(12000, weekly_revenue_target * 4)))),
        "weekly_leads_target": int(os.getenv("PERMANENCE_REVENUE_WEEKLY_LEADS_TARGET", "10")),
        "weekly_calls_target": int(os.getenv("PERMANENCE_REVENUE_WEEKLY_CALLS_TARGET", "5")),
        "weekly_closes_target": int(os.getenv("PERMANENCE_REVENUE_WEEKLY_CLOSES_TARGET", "2")),
        "daily_outreach_target": int(os.getenv("PERMANENCE_REVENUE_DAILY_OUTREACH_TARGET", "10")),
    }
    current = _read_json(TARGETS_PATH, defaults)
    if not isinstance(current, dict):
        current = defaults
    for key, value in defaults.items():
        current.setdefault(key, value)
    _write_json(TARGETS_PATH, current)
    return current


def _ensure_streams() -> list[dict[str, Any]]:
    defaults = [
        {
            "stream": "Done-for-you Foundation setup",
            "status": "active",
            "offer": "Permanence OS Foundation Setup",
            "price_hint": "750-3000",
            "owner": "Payton",
        },
        {
            "stream": "Monthly optimization retainer",
            "status": "active",
            "offer": "Permanence OS Operator Retainer",
            "price_hint": "500-1500/mo",
            "owner": "Payton",
        },
        {
            "stream": "Custom automation add-ons",
            "status": "active",
            "offer": "Workflow Add-On Build",
            "price_hint": "300-1200",
            "owner": "Payton",
        },
        {
            "stream": "Templates and playbooks",
            "status": "building",
            "offer": "Operating Playbook Pack",
            "price_hint": "49-199",
            "owner": "Payton",
        },
        {
            "stream": "Hosted app subscription",
            "status": "roadmap",
            "offer": "Permanence Cloud",
            "price_hint": "49-299/mo",
            "owner": "Payton",
        },
    ]
    current = _read_json(STREAMS_PATH, defaults)
    if not isinstance(current, list):
        current = defaults
    if not current:
        current = defaults
    _write_json(STREAMS_PATH, current)
    return current


def _ensure_pipeline() -> list[dict[str, Any]]:
    current = _read_json(PIPELINE_PATH, [])
    if not isinstance(current, list):
        current = []
    _write_json(PIPELINE_PATH, current)
    return [row for row in current if isinstance(row, dict)]


def _latest(path: Path, pattern: str) -> Path | None:
    if not path.exists():
        return None
    matches = sorted(path.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    return matches[0] if matches else None


def _parse_actions(path: Path | None) -> list[str]:
    if not path or not path.exists():
        return []
    actions: list[str] = []
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        m = ACTION_RE.match(line)
        if m:
            actions.append(f"[{m.group(1)}] {m.group(2)}")
    return actions


def _pipeline_stats(rows: list[dict[str, Any]]) -> dict[str, Any]:
    stage_counts: dict[str, int] = {}
    open_rows: list[dict[str, Any]] = []
    won_rows: list[dict[str, Any]] = []
    for row in rows:
        stage = str(row.get("stage", "lead"))
        stage_counts[stage] = stage_counts.get(stage, 0) + 1
        if stage in {"won", "lost"}:
            if stage == "won":
                won_rows.append(row)
            continue
        open_rows.append(row)

    open_value = 0.0
    weighted_value = 0.0
    for row in open_rows:
        est = _as_float(row.get("est_value"), 0.0)
        stage = str(row.get("stage", "lead"))
        open_value += est
        weighted_value += est * STAGE_PROB.get(stage, 0.0)

    now = _utc_now()
    won_month_value = 0.0
    for row in won_rows:
        closed_raw = str(row.get("closed_at") or "")
        if not closed_raw:
            continue
        try:
            closed = datetime.fromisoformat(closed_raw.replace("Z", "+00:00"))
        except ValueError:
            continue
        if closed.year == now.year and closed.month == now.month:
            won_month_value += _as_float(row.get("actual_value"), _as_float(row.get("est_value"), 0.0))

    due_cutoff = (date.today() + timedelta(days=1)).isoformat()
    urgent = []
    for row in open_rows:
        due = str(row.get("next_action_due") or "")
        if due and due <= due_cutoff:
            urgent.append(row)
    urgent.sort(key=lambda r: str(r.get("next_action_due", "")))

    open_rows.sort(key=lambda r: str(r.get("updated_at", "")), reverse=True)
    return {
        "total": len(rows),
        "open_count": len(open_rows),
        "won_count": len(won_rows),
        "stage_counts": stage_counts,
        "open_value": open_value,
        "weighted_value": weighted_value,
        "won_month_value": won_month_value,
        "open_rows": open_rows,
        "urgent_rows": urgent[:5],
    }


def _write_report(
    *,
    targets: dict[str, Any],
    streams: list[dict[str, Any]],
    stats: dict[str, Any],
    queue_actions: list[str],
    queue_path: Path | None,
) -> tuple[Path, Path]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    TOOL_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _utc_now().strftime("%Y%m%d-%H%M%S")
    md_path = OUTPUT_DIR / f"revenue_architecture_{stamp}.md"
    json_path = TOOL_DIR / f"revenue_architecture_{stamp}.json"
    latest_md = OUTPUT_DIR / "revenue_architecture_latest.md"

    leads_target = int(targets.get("weekly_leads_target", 10))
    calls_target = int(targets.get("weekly_calls_target", 5))
    closes_target = int(targets.get("weekly_closes_target", 2))
    revenue_target = _as_float(targets.get("weekly_revenue_target"), 3000.0)

    stage_counts = stats["stage_counts"]
    leads_now = stage_counts.get("lead", 0) + stage_counts.get("qualified", 0)
    calls_now = stage_counts.get("call_scheduled", 0)
    closes_now = stage_counts.get("won", 0)

    lines = [
        "# Revenue Architecture v1",
        "",
        f"Generated (UTC): {_utc_now().isoformat()}",
        "",
        "## Business Model Streams",
    ]
    for s in streams:
        stream = s.get("stream", "unknown")
        status = s.get("status", "unknown")
        offer = s.get("offer", "unknown")
        price = s.get("price_hint", "n/a")
        lines.append(f"- {stream} | status={status} | offer={offer} | price={price}")

    lines.extend(
        [
            "",
            "## Weekly Scorecard",
            f"- Week of: {targets.get('week_of')}",
            f"- Revenue target: ${revenue_target:,.0f} | won MTD: ${stats['won_month_value']:,.0f} | open weighted: ${stats['weighted_value']:,.0f}",
            f"- Leads target: {leads_target} | now: {leads_now}",
            f"- Calls target: {calls_target} | now: {calls_now}",
            f"- Closes target: {closes_target} | now: {closes_now}",
            "",
            "## Pipeline Snapshot",
            f"- Total leads: {stats['total']}",
            f"- Open leads: {stats['open_count']}",
            f"- Open pipeline value: ${stats['open_value']:,.0f}",
            f"- Weighted pipeline value: ${stats['weighted_value']:,.0f}",
            "",
            "### Stage Counts",
        ]
    )
    for stage in sorted(STAGE_PROB.keys()):
        lines.append(f"- {stage}: {stage_counts.get(stage, 0)}")

    lines.append("")
    lines.append("### Open Leads (Most Recent)")
    if stats["open_rows"]:
        for row in stats["open_rows"][:10]:
            lines.append(
                f"- {row.get('lead_id', 'unknown')} | {row.get('name', 'unknown')} | "
                f"stage={row.get('stage', 'lead')} | est=${_as_float(row.get('est_value')):,.0f} | "
                f"next={row.get('next_action') or '-'} | due={row.get('next_action_due') or '-'}"
            )
    else:
        lines.append("- No open leads yet. Use `python scripts/sales_pipeline.py add ...`.")

    lines.append("")
    lines.append("### Urgent Next Actions (Due <= 24h)")
    if stats["urgent_rows"]:
        for row in stats["urgent_rows"]:
            lines.append(
                f"- {row.get('lead_id', 'unknown')} | {row.get('name', 'unknown')} | "
                f"due={row.get('next_action_due') or '-'} | {row.get('next_action') or '-'}"
            )
    else:
        lines.append("- No urgent due actions in pipeline.")

    lines.append("")
    lines.append("## Revenue Queue (Latest)")
    lines.append(f"- Source: {queue_path if queue_path else 'none'}")
    if queue_actions:
        for action in queue_actions[:7]:
            lines.append(f"- {action}")
    else:
        lines.append("- No queue actions parsed.")

    lines.extend(
        [
            "",
            "## Data Paths",
            f"- Targets: {TARGETS_PATH}",
            f"- Streams: {STREAMS_PATH}",
            f"- Pipeline: {PIPELINE_PATH}",
            "",
            "## Notes",
            "- Keep one locked offer + one CTA per week to avoid split conversion.",
            "- Treat this report as operating truth for daily sales actions.",
            "",
        ]
    )

    report = "\n".join(lines)
    md_path.write_text(report, encoding="utf-8")
    latest_md.write_text(report, encoding="utf-8")

    payload = {
        "generated_at": _utc_now().isoformat(),
        "targets": targets,
        "streams": streams,
        "stats": {
            "total": stats["total"],
            "open_count": stats["open_count"],
            "won_count": stats["won_count"],
            "stage_counts": stats["stage_counts"],
            "open_value": stats["open_value"],
            "weighted_value": stats["weighted_value"],
            "won_month_value": stats["won_month_value"],
        },
        "queue_source": str(queue_path) if queue_path else None,
        "queue_actions": queue_actions[:7],
        "paths": {
            "targets": str(TARGETS_PATH),
            "streams": str(STREAMS_PATH),
            "pipeline": str(PIPELINE_PATH),
            "latest_md": str(latest_md),
        },
    }
    json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return md_path, json_path


def main() -> int:
    targets = _ensure_targets()
    streams = _ensure_streams()
    pipeline = _ensure_pipeline()
    stats = _pipeline_stats(pipeline)

    queue_path = _latest(OUTPUT_DIR, "revenue_action_queue_*.md")
    queue_actions = _parse_actions(queue_path)
    md_path, json_path = _write_report(
        targets=targets,
        streams=streams,
        stats=stats,
        queue_actions=queue_actions,
        queue_path=queue_path,
    )

    print(f"Revenue architecture report written: {md_path}")
    print(f"Revenue architecture latest: {OUTPUT_DIR / 'revenue_architecture_latest.md'}")
    print(f"Tool payload written: {json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
