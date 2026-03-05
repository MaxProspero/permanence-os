#!/usr/bin/env python3
"""
Generate a governed side-business portfolio board with prioritized actions.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parents[1]
WORKING_DIR = Path(os.getenv("PERMANENCE_WORKING_DIR", str(BASE_DIR / "memory" / "working")))
OUTPUT_DIR = Path(os.getenv("PERMANENCE_OUTPUT_DIR", str(BASE_DIR / "outputs")))
TOOL_DIR = Path(os.getenv("PERMANENCE_TOOL_DIR", str(BASE_DIR / "memory" / "tool")))
PORTFOLIO_PATH = Path(os.getenv("PERMANENCE_SIDE_BUSINESS_PATH", str(WORKING_DIR / "side_business_portfolio.json")))

STAGE_ORDER = {"idea": 0, "build": 1, "validate": 2, "launch": 3, "scale": 4}
RISK_ORDER = {"low": 0, "medium": 1, "high": 2}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def _default_streams() -> list[dict[str, Any]]:
    return [
        {
            "stream_id": "clip-studio",
            "name": "Shorts Clipping Studio",
            "model": "service",
            "stage": "validate",
            "risk": "medium",
            "weekly_goal_usd": 1500,
            "weekly_actual_usd": 0,
            "pipeline_count": 0,
            "manual_approval_required": True,
            "next_action": "Offer 5 sample clips to one creator niche and collect conversion data.",
        },
        {
            "stream_id": "prediction-research",
            "name": "Prediction Research Desk",
            "model": "research",
            "stage": "build",
            "risk": "high",
            "weekly_goal_usd": 500,
            "weekly_actual_usd": 0,
            "pipeline_count": 0,
            "manual_approval_required": True,
            "next_action": "Run paper EV + risk models before any real-money action.",
        },
        {
            "stream_id": "automation-builds",
            "name": "AI Automation Builds",
            "model": "service",
            "stage": "validate",
            "risk": "low",
            "weekly_goal_usd": 2000,
            "weekly_actual_usd": 0,
            "pipeline_count": 1,
            "manual_approval_required": True,
            "next_action": "Ship one paid client workflow with clear before/after value metrics.",
        },
        {
            "stream_id": "digital-products",
            "name": "Templates and Playbooks",
            "model": "product",
            "stage": "idea",
            "risk": "low",
            "weekly_goal_usd": 300,
            "weekly_actual_usd": 0,
            "pipeline_count": 0,
            "manual_approval_required": True,
            "next_action": "Define one narrow digital product and list 10 distribution channels.",
        },
    ]


def _load_streams() -> list[dict[str, Any]]:
    payload = _read_json(PORTFOLIO_PATH, [])
    if not isinstance(payload, list):
        payload = []
    rows = [row for row in payload if isinstance(row, dict)]
    if not rows:
        rows = _default_streams()
    return rows


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _priority_score(row: dict[str, Any]) -> float:
    goal = _as_float(row.get("weekly_goal_usd"), 0)
    actual = _as_float(row.get("weekly_actual_usd"), 0)
    gap = max(0.0, goal - actual)
    stage = str(row.get("stage") or "idea").strip().lower()
    stage_rank = STAGE_ORDER.get(stage, 0)
    pipeline = int(_as_float(row.get("pipeline_count"), 0))
    base = gap
    if stage in {"validate", "launch", "scale"}:
        base += 200
    base += min(300.0, pipeline * 50.0)
    base += stage_rank * 25.0
    return base


def _normalize_stream(row: dict[str, Any]) -> dict[str, Any]:
    out = dict(row)
    out["stage"] = str(out.get("stage") or "idea").strip().lower()
    out["risk"] = str(out.get("risk") or "medium").strip().lower()
    out["manual_approval_required"] = bool(out.get("manual_approval_required", True))
    out["weekly_goal_usd"] = _as_float(out.get("weekly_goal_usd"), 0.0)
    out["weekly_actual_usd"] = _as_float(out.get("weekly_actual_usd"), 0.0)
    out["pipeline_count"] = int(_as_float(out.get("pipeline_count"), 0))
    out["weekly_gap_usd"] = max(0.0, out["weekly_goal_usd"] - out["weekly_actual_usd"])
    out["priority_score"] = round(_priority_score(out), 2)
    return out


def _write_outputs(streams: list[dict[str, Any]]) -> tuple[Path, Path]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    TOOL_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _now().strftime("%Y%m%d-%H%M%S")
    md_path = OUTPUT_DIR / f"side_business_portfolio_{stamp}.md"
    latest_md = OUTPUT_DIR / "side_business_portfolio_latest.md"
    json_path = TOOL_DIR / f"side_business_portfolio_{stamp}.json"

    normalized = [_normalize_stream(row) for row in streams]
    normalized.sort(key=lambda row: row.get("priority_score", 0), reverse=True)
    top_actions = normalized[:7]

    total_goal = sum(row["weekly_goal_usd"] for row in normalized)
    total_actual = sum(row["weekly_actual_usd"] for row in normalized)
    total_gap = sum(row["weekly_gap_usd"] for row in normalized)

    lines = [
        "# Side Business Portfolio",
        "",
        f"Generated (UTC): {_now().isoformat()}",
        f"Portfolio source: {PORTFOLIO_PATH}",
        "",
        "## Portfolio Totals",
        f"- Weekly target: ${total_goal:,.0f}",
        f"- Weekly actual: ${total_actual:,.0f}",
        f"- Weekly gap: ${total_gap:,.0f}",
        "",
        "## Stream Priorities",
    ]

    if not normalized:
        lines.append("- No streams configured.")
    else:
        for idx, row in enumerate(top_actions, start=1):
            lines.extend(
                [
                    f"{idx}. {row.get('name', 'Untitled')} ({row.get('stream_id', 'n/a')})",
                    (
                        "   - "
                        f"stage={row.get('stage')} | risk={row.get('risk')} | "
                        f"target=${row.get('weekly_goal_usd', 0):,.0f} | actual=${row.get('weekly_actual_usd', 0):,.0f} | "
                        f"gap=${row.get('weekly_gap_usd', 0):,.0f} | pipeline={row.get('pipeline_count', 0)}"
                    ),
                    f"   - next_action={row.get('next_action', '-')}",
                ]
            )

    lines.extend(["", "## Governance Notes"])
    high_risk = [row for row in normalized if row.get("risk") == "high"]
    lines.append(f"- High-risk streams: {len(high_risk)}")
    lines.append("- All execution remains human-in-the-loop for financial and legal actions.")
    lines.append("- Keep separate accounting per stream to prevent hidden losses.")
    lines.append("")

    report = "\n".join(lines)
    md_path.write_text(report, encoding="utf-8")
    latest_md.write_text(report, encoding="utf-8")

    payload = {
        "generated_at": _now().isoformat(),
        "portfolio_path": str(PORTFOLIO_PATH),
        "stream_count": len(normalized),
        "totals": {
            "weekly_goal_usd": total_goal,
            "weekly_actual_usd": total_actual,
            "weekly_gap_usd": total_gap,
        },
        "streams": normalized,
        "top_actions": top_actions,
        "latest_markdown": str(latest_md),
    }
    json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return md_path, json_path


def main() -> int:
    streams = _load_streams()
    md_path, json_path = _write_outputs(streams)
    print(f"Side business portfolio written: {md_path}")
    print(f"Side business portfolio latest: {OUTPUT_DIR / 'side_business_portfolio_latest.md'}")
    print(f"Tool payload written: {json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
