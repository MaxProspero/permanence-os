#!/usr/bin/env python3
"""
Generate a practical cost-recovery plan so revenue actions cover tool/API spend first.
"""

from __future__ import annotations

import argparse
import json
import math
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
TARGETS_PATH = Path(os.getenv("PERMANENCE_REVENUE_TARGETS_PATH", str(WORKING_DIR / "revenue_targets.json")))
PLAYBOOK_PATH = Path(os.getenv("PERMANENCE_REVENUE_PLAYBOOK_PATH", str(WORKING_DIR / "revenue_playbook.json")))
COST_PLAN_PATH = Path(
    os.getenv("PERMANENCE_COST_RECOVERY_PLAN_PATH", str(WORKING_DIR / "api_cost_plan.json"))
)

QUEUE_ACTION_RE = re.compile(r"^\d+\.\s+\[(.+)\]\s+(.+)$")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


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


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def _default_plan() -> dict[str, Any]:
    return {
        "x_api_monthly_budget_usd": _safe_int(os.getenv("PERMANENCE_X_API_MONTHLY_BUDGET_USD", "25"), 25),
        "llm_monthly_budget_usd": _safe_int(os.getenv("PERMANENCE_LLM_MONTHLY_BUDGET_USD", "50"), 50),
        "other_tools_monthly_budget_usd": _safe_int(
            os.getenv("PERMANENCE_OTHER_TOOLS_MONTHLY_BUDGET_USD", "25"), 25
        ),
        "recovery_buffer_multiplier": _safe_float(
            os.getenv("PERMANENCE_RECOVERY_BUFFER_MULTIPLIER", "1.5"), 1.5
        ),
        "payback_window_days": max(7, _safe_int(os.getenv("PERMANENCE_PAYBACK_WINDOW_DAYS", "14"), 14)),
        "close_rate_assumption": _clamp(
            _safe_float(os.getenv("PERMANENCE_CLOSE_RATE_ASSUMPTION", "0.2"), 0.2), 0.05, 0.8
        ),
        "outreach_per_new_lead": max(1, _safe_int(os.getenv("PERMANENCE_OUTREACH_PER_NEW_LEAD", "10"), 10)),
        "updated_at": _utc_now().isoformat(),
    }


def _ensure_cost_plan(force_template: bool = False) -> tuple[dict[str, Any], str]:
    defaults = _default_plan()
    if force_template or not COST_PLAN_PATH.exists():
        _write_json(COST_PLAN_PATH, defaults)
        return defaults, "written"
    payload = _read_json(COST_PLAN_PATH, {})
    if not isinstance(payload, dict):
        payload = {}
    merged = dict(defaults)
    merged.update(payload)
    if merged != payload:
        _write_json(COST_PLAN_PATH, merged)
        return merged, "updated"
    return merged, "existing"


def _latest_output(pattern: str) -> Path | None:
    if not OUTPUT_DIR.exists():
        return None
    files = sorted(OUTPUT_DIR.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0] if files else None


def _queue_actions(path: Path | None) -> list[str]:
    if not path or not path.exists():
        return []
    actions: list[str] = []
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        match = QUEUE_ACTION_RE.match(line)
        if match:
            actions.append(f"[{match.group(1)}] {match.group(2)}")
    return actions


def _action_money_score(action: str) -> int:
    text = action.lower()
    positive_terms = [
        "lead",
        "book fit call",
        "book call",
        "fit call",
        "call",
        "proposal",
        "close",
        "follow up",
        "outreach",
        "dm",
        "cta",
        "offer",
        "qualified",
        "intake",
        "pipeline",
    ]
    negative_terms = [
        "receipt",
        "invoice",
        "newsletter",
        "digest",
        "google",
        "alphasignal",
    ]
    score = 0
    for term in positive_terms:
        if term in text:
            score += 2
    for term in negative_terms:
        if term in text:
            score -= 3
    return score


def _prioritize_money_actions(actions: list[str], limit: int = 5) -> list[str]:
    if not actions:
        return []
    ranked = sorted(actions, key=lambda action: _action_money_score(action), reverse=True)
    preferred = [action for action in ranked if _action_money_score(action) > 0]
    chosen = preferred if preferred else ranked
    return chosen[: max(1, limit)]


def _default_playbook() -> dict[str, Any]:
    return {
        "offer_name": "Permanence OS Foundation Setup",
        "pricing_tier": "Core",
        "price_usd": 1500,
        "cta_public": 'DM me "FOUNDATION".',
    }


def _load_playbook() -> dict[str, Any]:
    payload = _read_json(PLAYBOOK_PATH, {})
    if not isinstance(payload, dict):
        payload = {}
    merged = dict(_default_playbook())
    merged.update(payload)
    return merged


def _load_targets() -> dict[str, Any]:
    payload = _read_json(TARGETS_PATH, {})
    if not isinstance(payload, dict):
        payload = {}
    return payload


def _parse_iso_datetime(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def _pipeline_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    open_rows = [row for row in rows if str(row.get("stage") or "lead") not in {"won", "lost"}]
    weighted_open = 0.0
    stage_prob = {
        "lead": 0.10,
        "qualified": 0.25,
        "call_scheduled": 0.40,
        "proposal_sent": 0.60,
        "negotiation": 0.75,
        "won": 1.00,
        "lost": 0.00,
    }
    for row in open_rows:
        stage = str(row.get("stage") or "lead")
        est_value = _safe_float(row.get("est_value"), 0.0)
        weighted_open += est_value * stage_prob.get(stage, 0.0)

    wins = 0
    losses = 0
    week_start = date.today() - timedelta(days=date.today().weekday())
    week_end = week_start + timedelta(days=6)
    won_this_week = 0
    won_value_week = 0.0
    for row in rows:
        stage = str(row.get("stage") or "")
        if stage == "won":
            wins += 1
            closed = _parse_iso_datetime(row.get("closed_at"))
            if closed and week_start <= closed.date() <= week_end:
                won_this_week += 1
                won_value_week += _safe_float(row.get("actual_value"), _safe_float(row.get("est_value"), 0.0))
        elif stage == "lost":
            losses += 1

    return {
        "open_count": len(open_rows),
        "weighted_open_value": weighted_open,
        "wins": wins,
        "losses": losses,
        "won_this_week": won_this_week,
        "won_value_week": won_value_week,
    }


def _compute_plan(
    *,
    cost_plan: dict[str, Any],
    playbook: dict[str, Any],
    targets: dict[str, Any],
    pipeline: dict[str, Any],
) -> dict[str, Any]:
    x_cost = max(0.0, _safe_float(cost_plan.get("x_api_monthly_budget_usd"), 25.0))
    llm_cost = max(0.0, _safe_float(cost_plan.get("llm_monthly_budget_usd"), 50.0))
    other_cost = max(0.0, _safe_float(cost_plan.get("other_tools_monthly_budget_usd"), 25.0))
    total_cost = x_cost + llm_cost + other_cost
    buffer_multiplier = _clamp(_safe_float(cost_plan.get("recovery_buffer_multiplier"), 1.5), 1.0, 3.0)
    target_recovery = total_cost * buffer_multiplier

    offer_price = max(1.0, _safe_float(playbook.get("price_usd"), 1500.0))
    break_even_closes = max(1, int(math.ceil(total_cost / offer_price)))
    target_closes = max(1, int(math.ceil(target_recovery / offer_price)))

    historical_wins = _safe_int(pipeline.get("wins"), 0)
    historical_losses = _safe_int(pipeline.get("losses"), 0)
    historical_closed = historical_wins + historical_losses
    historical_rate = (historical_wins / historical_closed) if historical_closed > 0 else 0.0
    fallback_rate = _clamp(_safe_float(cost_plan.get("close_rate_assumption"), 0.2), 0.05, 0.8)
    close_rate_used = historical_rate if historical_closed >= 5 else fallback_rate
    close_rate_used = _clamp(close_rate_used, 0.05, 0.8)

    leads_needed = max(1, int(math.ceil(target_closes / close_rate_used)))
    outreach_per_lead = max(1, _safe_int(cost_plan.get("outreach_per_new_lead"), 10))
    outreach_needed = leads_needed * outreach_per_lead
    payback_days = max(7, _safe_int(cost_plan.get("payback_window_days"), 14))
    daily_outreach_needed = max(1, int(math.ceil(outreach_needed / payback_days)))
    current_daily_target = max(1, _safe_int(targets.get("daily_outreach_target"), 10))
    outreach_gap = max(0, daily_outreach_needed - current_daily_target)

    return {
        "monthly_tool_cost_usd": round(total_cost, 2),
        "monthly_x_cost_usd": round(x_cost, 2),
        "monthly_llm_cost_usd": round(llm_cost, 2),
        "monthly_other_cost_usd": round(other_cost, 2),
        "buffer_multiplier": buffer_multiplier,
        "target_recovery_usd": round(target_recovery, 2),
        "offer_price_usd": round(offer_price, 2),
        "break_even_closes": break_even_closes,
        "target_closes": target_closes,
        "close_rate_used": round(close_rate_used, 4),
        "close_rate_source": "historical" if historical_closed >= 5 else "assumption",
        "historical_closed_deals": historical_closed,
        "leads_needed": leads_needed,
        "outreach_per_lead": outreach_per_lead,
        "outreach_needed": outreach_needed,
        "payback_days": payback_days,
        "daily_outreach_needed": daily_outreach_needed,
        "current_daily_outreach_target": current_daily_target,
        "daily_outreach_gap": outreach_gap,
    }


def _write_outputs(
    *,
    cost_plan: dict[str, Any],
    cost_plan_status: str,
    playbook: dict[str, Any],
    targets: dict[str, Any],
    queue_actions: list[str],
    priority_actions: list[str],
    queue_path: Path | None,
    pipeline_summary: dict[str, Any],
    recovery_plan: dict[str, Any],
) -> tuple[Path, Path]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    TOOL_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _utc_now().strftime("%Y%m%d-%H%M%S")
    md_path = OUTPUT_DIR / f"revenue_cost_recovery_{stamp}.md"
    latest_md = OUTPUT_DIR / "revenue_cost_recovery_latest.md"
    json_path = TOOL_DIR / f"revenue_cost_recovery_{stamp}.json"

    lines = [
        "# Revenue Cost Recovery Plan",
        "",
        f"Generated (UTC): {_utc_now().isoformat()}",
        "",
        "## Cost Inputs",
        f"- Cost plan path: {COST_PLAN_PATH} ({cost_plan_status})",
        f"- Monthly API/tool budget: ${recovery_plan['monthly_tool_cost_usd']:,.0f}",
        f"- X API budget: ${recovery_plan['monthly_x_cost_usd']:,.0f}",
        f"- LLM budget: ${recovery_plan['monthly_llm_cost_usd']:,.0f}",
        f"- Other tools budget: ${recovery_plan['monthly_other_cost_usd']:,.0f}",
        f"- Recovery buffer: x{recovery_plan['buffer_multiplier']:.2f}",
        "",
        "## Coverage Math",
        f"- Offer price used: ${recovery_plan['offer_price_usd']:,.0f} ({playbook.get('offer_name', 'offer')})",
        f"- Break-even closes needed: {recovery_plan['break_even_closes']}",
        f"- Target closes needed (buffered): {recovery_plan['target_closes']}",
        f"- Revenue recovery target: ${recovery_plan['target_recovery_usd']:,.0f}",
        f"- Close rate used: {recovery_plan['close_rate_used'] * 100:.1f}% ({recovery_plan['close_rate_source']})",
        f"- Leads needed: {recovery_plan['leads_needed']}",
        f"- Outreach touches needed: {recovery_plan['outreach_needed']}",
        f"- Payback window: {recovery_plan['payback_days']} days",
        f"- Daily outreach needed: {recovery_plan['daily_outreach_needed']}",
        f"- Current daily outreach target: {recovery_plan['current_daily_outreach_target']}",
    ]
    if recovery_plan["daily_outreach_gap"] > 0:
        lines.append(f"- Daily outreach gap: +{recovery_plan['daily_outreach_gap']} (raise target or extend window)")
    else:
        lines.append("- Daily outreach gap: 0 (current target is sufficient)")

    lines.extend(
        [
            "",
            "## Pipeline Reality Check",
            f"- Open leads now: {pipeline_summary['open_count']}",
            f"- Weighted open pipeline: ${pipeline_summary['weighted_open_value']:,.0f}",
            f"- Wins this week: {pipeline_summary['won_this_week']} (${pipeline_summary['won_value_week']:,.0f})",
            "",
            "## Priority Actions (Today)",
            f"- Queue source: {queue_path if queue_path else 'none'}",
        ]
    )
    if priority_actions:
        for idx, action in enumerate(priority_actions[:5], start=1):
            lines.append(f"{idx}. {action}")
    else:
        lines.append("1. No queue actions found. Run `python cli.py money-loop` first.")

    lines.extend(
        [
            "",
            "## Governance Notes",
            "- This is an execution plan, not autonomous financial execution.",
            "- Human approval remains required for outbound messages, contracts, payment actions, and trades.",
            "- Keep claims factual and follow the locked offer + CTA policy.",
            "",
        ]
    )

    report = "\n".join(lines)
    md_path.write_text(report, encoding="utf-8")
    latest_md.write_text(report, encoding="utf-8")

    payload = {
        "generated_at": _utc_now().isoformat(),
        "cost_plan": cost_plan,
        "cost_plan_status": cost_plan_status,
        "playbook": playbook,
        "targets": targets,
        "pipeline_summary": pipeline_summary,
        "recovery_plan": recovery_plan,
        "queue_source": str(queue_path) if queue_path else None,
        "priority_actions": priority_actions[:5],
        "queue_actions": queue_actions[:5],
        "latest_markdown": str(latest_md),
    }
    json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return md_path, json_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate revenue cost-recovery plan from current operating data.")
    parser.add_argument(
        "--force-template",
        action="store_true",
        help=f"Rewrite {COST_PLAN_PATH.name} with default values before computing.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    playbook = _load_playbook()
    targets = _load_targets()
    cost_plan, cost_plan_status = _ensure_cost_plan(force_template=args.force_template)

    pipeline_rows = _read_json(PIPELINE_PATH, [])
    if not isinstance(pipeline_rows, list):
        pipeline_rows = []
    pipeline_rows = [row for row in pipeline_rows if isinstance(row, dict)]
    pipeline_summary = _pipeline_summary(pipeline_rows)

    queue_path = _latest_output("revenue_action_queue_*.md")
    queue_actions = _queue_actions(queue_path)
    priority_actions = _prioritize_money_actions(queue_actions)

    recovery_plan = _compute_plan(
        cost_plan=cost_plan,
        playbook=playbook,
        targets=targets,
        pipeline=pipeline_summary,
    )

    md_path, json_path = _write_outputs(
        cost_plan=cost_plan,
        cost_plan_status=cost_plan_status,
        playbook=playbook,
        targets=targets,
        queue_actions=queue_actions,
        priority_actions=priority_actions,
        queue_path=queue_path,
        pipeline_summary=pipeline_summary,
        recovery_plan=recovery_plan,
    )
    print(f"Revenue cost recovery written: {md_path}")
    print(f"Revenue cost recovery latest: {OUTPUT_DIR / 'revenue_cost_recovery_latest.md'}")
    print(f"Tool payload written: {json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
