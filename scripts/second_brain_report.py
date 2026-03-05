#!/usr/bin/env python3
"""
Generate a unified second-brain report across life, revenue, and side-business systems.
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


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def _latest_tool(pattern: str) -> Path | None:
    if not TOOL_DIR.exists():
        return None
    items = sorted(TOOL_DIR.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    return items[0] if items else None


def _load_payload(pattern: str) -> tuple[dict[str, Any], Path | None]:
    path = _latest_tool(pattern)
    payload = _read_json(path, {}) if path else {}
    if not isinstance(payload, dict):
        payload = {}
    return payload, path


def _safe_int(value: Any) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def _safe_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _write_outputs(snapshot: dict[str, Any]) -> tuple[Path, Path]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    TOOL_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _now().strftime("%Y%m%d-%H%M%S")
    md_path = OUTPUT_DIR / f"second_brain_report_{stamp}.md"
    latest_md = OUTPUT_DIR / "second_brain_report_latest.md"
    json_path = TOOL_DIR / f"second_brain_report_{stamp}.json"

    life = snapshot.get("life", {})
    revenue = snapshot.get("revenue", {})
    portfolio = snapshot.get("portfolio", {})
    research = snapshot.get("research", {})
    prediction = snapshot.get("prediction", {})
    backtesting = snapshot.get("backtesting", {})
    narratives = snapshot.get("narratives", {})
    clipping = snapshot.get("clipping", {})
    world_watch = snapshot.get("world_watch", {})
    attachments = snapshot.get("attachments", {})
    resume_brand = snapshot.get("resume_brand", {})
    opportunities = snapshot.get("opportunities", {})
    founder = snapshot.get("founder", {})
    cost_recovery = snapshot.get("cost_recovery", {})
    sources = snapshot.get("sources", {})

    lines = [
        "# Second Brain Report",
        "",
        f"Generated (UTC): {_now().isoformat()}",
        "",
        "## Operator Snapshot",
        f"- Open life actions: {_safe_int(life.get('open_task_count'))}",
        f"- Revenue open leads: {_safe_int(revenue.get('open_count'))}",
        f"- Side-business streams: {_safe_int(portfolio.get('stream_count'))}",
        f"- GitHub repos scanned: {_safe_int(research.get('github_repo_count'))}",
        f"- GitHub trending repos tracked: {_safe_int(research.get('github_trending_count'))}",
        f"- Ecosystem repos tracked: {_safe_int(research.get('ecosystem_repo_count'))}",
        f"- Ecosystem developers tracked: {_safe_int(research.get('ecosystem_developer_count'))}",
        f"- Social items ranked: {_safe_int(research.get('social_item_count'))}",
        f"- Prediction hypotheses: {_safe_int(prediction.get('results_count'))}",
        f"- Backtest setups queued: {_safe_int(backtesting.get('setup_count'))}",
        f"- Clipping jobs: {_safe_int(clipping.get('job_count'))}",
        f"- Global alerts tracked: {_safe_int(world_watch.get('item_count'))}",
        f"- High global alerts: {_safe_int(world_watch.get('high_alert_count'))}",
        f"- Narrative hypotheses supported: {_safe_int(narratives.get('supported_count'))}",
        f"- Opportunities ranked: {_safe_int(opportunities.get('ranked_count'))}",
        f"- Opportunities queued: {_safe_int(opportunities.get('queued_count'))}",
        f"- Founder note cards captured: {_safe_int(founder.get('note_card_count'))}",
        f"- Attachments indexed: {_safe_int((attachments.get('counts') or {}).get('total'))}",
        f"- Brand docs tracked: {_safe_int(resume_brand.get('brand_doc_count'))}",
        "",
        "## Money Engine",
        f"- Weighted pipeline value: ${_safe_float(revenue.get('weighted_value')):,.0f}",
        f"- API/tool recovery target: ${_safe_float(cost_recovery.get('target_recovery_usd')):,.0f}",
        f"- Closes needed to cover tools: {_safe_int(cost_recovery.get('target_closes'))}",
        f"- Daily outreach needed (coverage): {_safe_int(cost_recovery.get('daily_outreach_needed'))}",
        f"- Portfolio weekly gap: ${_safe_float(portfolio.get('weekly_gap_usd')):,.0f}",
        f"- GitHub improvement actions: {_safe_int(research.get('github_top_actions'))}",
        f"- Ecosystem intelligence links: {_safe_int(research.get('ecosystem_link_count'))}",
        f"- Prediction manual-review candidates: {_safe_int(prediction.get('manual_review_candidates'))}",
        f"- High-priority backtests: {_safe_int(backtesting.get('high_priority_count'))}",
        f"- Approval queue pending from Phase3: {_safe_int(opportunities.get('pending_total'))}",
        f"- Attachment transcription queue pending: {_safe_int(attachments.get('transcription_queue_pending'))}",
        f"- Founder directives tracked: {_safe_int(founder.get('directive_count'))}",
        "",
        "## Focus Sequence (Today)",
        "1. Complete highest-priority life action before context switching.",
        "2. Execute one revenue action that directly advances a deal stage.",
        "3. Advance one side-business stream by one measurable milestone.",
        "4. Review prediction candidates manually; no autonomous execution.",
        "5. Review top clipping candidates and approve only rights-safe content.",
        "",
        "## Data Sources",
        f"- life: {sources.get('life', 'none')}",
        f"- revenue: {sources.get('revenue', 'none')}",
        f"- portfolio: {sources.get('portfolio', 'none')}",
        f"- github_research: {sources.get('github_research', 'none')}",
        f"- github_trending: {sources.get('github_trending', 'none')}",
        f"- ecosystem_research: {sources.get('ecosystem_research', 'none')}",
        f"- social_research: {sources.get('social_research', 'none')}",
        f"- prediction: {sources.get('prediction', 'none')}",
        f"- market_backtest: {sources.get('market_backtest', 'none')}",
        f"- narrative_tracker: {sources.get('narrative_tracker', 'none')}",
        f"- clipping: {sources.get('clipping', 'none')}",
        f"- world_watch: {sources.get('world_watch', 'none')}",
        f"- world_watch_alerts: {sources.get('world_watch_alerts', 'none')}",
        f"- opportunities_ranked: {sources.get('opportunities_ranked', 'none')}",
        f"- opportunities_queue: {sources.get('opportunities_queue', 'none')}",
        f"- founder_notes: {sources.get('founder_notes', 'none')}",
        f"- attachments: {sources.get('attachments', 'none')}",
        f"- resume_brand: {sources.get('resume_brand', 'none')}",
        f"- cost_recovery: {sources.get('cost_recovery', 'none')}",
        "",
        "## Governance Notes",
        "- Human authority remains final for money, legal, and publishing actions.",
        "- This report is a coordination layer, not an autonomous execution engine.",
        "",
    ]

    report = "\n".join(lines)
    md_path.write_text(report, encoding="utf-8")
    latest_md.write_text(report, encoding="utf-8")

    payload = {
        "generated_at": _now().isoformat(),
        "snapshot": snapshot,
        "latest_markdown": str(latest_md),
    }
    json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return md_path, json_path


def main() -> int:
    life_payload, life_path = _load_payload("life_os_brief_*.json")
    portfolio_payload, portfolio_path = _load_payload("side_business_portfolio_*.json")
    prediction_payload, prediction_path = _load_payload("prediction_lab_*.json")
    backtest_payload, backtest_path = _load_payload("market_backtest_queue_*.json")
    narrative_payload, narrative_path = _load_payload("narrative_tracker_*.json")
    clipping_payload, clipping_path = _load_payload("clipping_pipeline_*.json")
    world_watch_payload, world_watch_path = _load_payload("world_watch_20*.json")
    world_watch_alerts_payload, world_watch_alerts_path = _load_payload("world_watch_alerts_*.json")
    attachments_payload, attachments_path = _load_payload("attachment_pipeline_*.json")
    resume_brand_payload, resume_brand_path = _load_payload("resume_brand_brief_*.json")
    revenue_payload, revenue_path = _load_payload("revenue_execution_board_*.json")
    cost_recovery_payload, cost_recovery_path = _load_payload("revenue_cost_recovery_*.json")
    github_payload, github_path = _load_payload("github_research_ingest_*.json")
    github_trending_payload, github_trending_path = _load_payload("github_trending_ingest_*.json")
    ecosystem_payload, ecosystem_path = _load_payload("ecosystem_research_ingest_*.json")
    social_payload, social_path = _load_payload("social_research_ingest_*.json")
    opportunity_rank_payload, opportunity_rank_path = _load_payload("opportunity_ranker_*.json")
    opportunity_queue_payload, opportunity_queue_path = _load_payload("opportunity_approval_queue_*.json")
    founder_notes_path = WORKING_DIR / "founder_note_cards.json"
    founder_notes_payload = _read_json(founder_notes_path, {})
    if not isinstance(founder_notes_payload, dict):
        founder_notes_payload = {}

    snapshot = {
        "life": {
            "open_task_count": life_payload.get("open_task_count", 0),
            "top_actions": life_payload.get("top_actions", []),
        },
        "revenue": {
            "open_count": (revenue_payload.get("pipeline", {}) or {}).get("open_count", 0),
            "weighted_value": (revenue_payload.get("pipeline", {}) or {}).get("weighted_value", 0),
        },
        "portfolio": {
            "stream_count": portfolio_payload.get("stream_count", 0),
            "weekly_gap_usd": ((portfolio_payload.get("totals") or {}).get("weekly_gap_usd", 0)),
        },
        "research": {
            "github_repo_count": github_payload.get("repo_count", 0),
            "github_top_actions": sum(len((row or {}).get("top_actions") or []) for row in (github_payload.get("repos") or [])),
            "github_trending_count": github_trending_payload.get("repo_count", 0),
            "ecosystem_repo_count": ecosystem_payload.get("repo_count", 0),
            "ecosystem_developer_count": ecosystem_payload.get("developer_count", 0),
            "ecosystem_link_count": (
                int(ecosystem_payload.get("docs_count", 0) or 0)
                + int(ecosystem_payload.get("communities_count", 0) or 0)
            ),
            "social_item_count": social_payload.get("item_count", 0),
            "social_top_item_count": len(social_payload.get("top_items") or []),
        },
        "prediction": {
            "results_count": len(prediction_payload.get("results") or []),
            "manual_review_candidates": prediction_payload.get("manual_review_candidates", 0),
        },
        "backtesting": {
            "setup_count": backtest_payload.get("setup_count", 0),
            "high_priority_count": backtest_payload.get("high_priority_count", 0),
        },
        "narratives": {
            "hypothesis_count": narrative_payload.get("hypothesis_count", 0),
            "supported_count": narrative_payload.get("supported_count", 0),
            "unverified_count": narrative_payload.get("unverified_count", 0),
            "contradicted_count": narrative_payload.get("contradicted_count", 0),
        },
        "clipping": {
            "job_count": clipping_payload.get("job_count", 0),
            "candidate_count": clipping_payload.get("candidate_count", 0),
        },
        "world_watch": {
            "item_count": world_watch_payload.get("item_count", 0),
            "high_alert_count": world_watch_payload.get("high_alert_count", 0),
            "top_alerts": (world_watch_payload.get("top_alerts") or [])[:10],
            "dispatch_results": (world_watch_alerts_payload.get("dispatch_results") or [])[:4],
        },
        "opportunities": {
            "ranked_count": opportunity_rank_payload.get("item_count", 0),
            "queued_count": opportunity_queue_payload.get("queued_count", 0),
            "pending_total": opportunity_queue_payload.get("pending_total", 0),
            "top_items": (opportunity_rank_payload.get("top_items") or [])[:8],
        },
        "attachments": {
            "counts": attachments_payload.get("counts", {}),
            "transcription_queue_pending": attachments_payload.get("transcription_queue_pending", 0),
        },
        "resume_brand": {
            "brand_doc_count": resume_brand_payload.get("brand_doc_count", 0),
            "resume_bullets": resume_brand_payload.get("resume_bullets", []),
            "brand_actions": resume_brand_payload.get("brand_actions", []),
        },
        "cost_recovery": {
            "target_recovery_usd": ((cost_recovery_payload.get("recovery_plan") or {}).get("target_recovery_usd", 0)),
            "target_closes": ((cost_recovery_payload.get("recovery_plan") or {}).get("target_closes", 0)),
            "daily_outreach_needed": (
                (cost_recovery_payload.get("recovery_plan") or {}).get("daily_outreach_needed", 0)
            ),
        },
        "founder": {
            "note_card_count": len(founder_notes_payload.get("note_cards") or []),
            "directive_count": len(founder_notes_payload.get("implementation_directives") or []),
        },
        "sources": {
            "life": str(life_path) if life_path else "none",
            "revenue": str(revenue_path) if revenue_path else "none",
            "portfolio": str(portfolio_path) if portfolio_path else "none",
            "github_research": str(github_path) if github_path else "none",
            "github_trending": str(github_trending_path) if github_trending_path else "none",
            "ecosystem_research": str(ecosystem_path) if ecosystem_path else "none",
            "social_research": str(social_path) if social_path else "none",
            "prediction": str(prediction_path) if prediction_path else "none",
            "market_backtest": str(backtest_path) if backtest_path else "none",
            "narrative_tracker": str(narrative_path) if narrative_path else "none",
            "clipping": str(clipping_path) if clipping_path else "none",
            "world_watch": str(world_watch_path) if world_watch_path else "none",
            "world_watch_alerts": str(world_watch_alerts_path) if world_watch_alerts_path else "none",
            "opportunities_ranked": str(opportunity_rank_path) if opportunity_rank_path else "none",
            "opportunities_queue": str(opportunity_queue_path) if opportunity_queue_path else "none",
            "founder_notes": str(founder_notes_path) if founder_notes_path.exists() else "none",
            "attachments": str(attachments_path) if attachments_path else "none",
            "resume_brand": str(resume_brand_path) if resume_brand_path else "none",
            "cost_recovery": str(cost_recovery_path) if cost_recovery_path else "none",
        },
    }

    md_path, json_path = _write_outputs(snapshot)
    print(f"Second brain report written: {md_path}")
    print(f"Second brain latest: {OUTPUT_DIR / 'second_brain_report_latest.md'}")
    print(f"Tool payload written: {json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
