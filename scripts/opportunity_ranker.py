#!/usr/bin/env python3
"""
Rank multi-source opportunities for Phase 3 manual-approval workflows.

This script is advisory only and never executes external actions.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parents[1]
WORKING_DIR = Path(os.getenv("PERMANENCE_WORKING_DIR", str(BASE_DIR / "memory" / "working")))
OUTPUT_DIR = Path(os.getenv("PERMANENCE_OUTPUT_DIR", str(BASE_DIR / "outputs")))
TOOL_DIR = Path(os.getenv("PERMANENCE_TOOL_DIR", str(BASE_DIR / "memory" / "tool")))
POLICY_PATH = Path(
    os.getenv("PERMANENCE_OPPORTUNITY_POLICY_PATH", str(WORKING_DIR / "opportunity_rank_policy.json"))
)
MAX_ITEMS_DEFAULT = int(os.getenv("PERMANENCE_OPPORTUNITY_MAX_ITEMS", "20"))
SOCIAL_SPAM_PATTERNS = [
    "winning prize",
    "dm to claim",
    "send me a dm",
    "airdrop",
    "giveaway",
    "claim it now",
    "telegram.me",
    "whatsapp",
    "deeply sorry",
]
SOCIAL_INTENT_TOKENS = [
    "saas",
    "automation",
    "mcp",
    "api",
    "growth",
    "monetize",
    "revenue",
    "mrr",
    "client",
    "lead",
    "service",
    "agency",
    "product",
    "launch",
    "show hn",
    "open source",
    "founder",
    "workflow",
]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now().isoformat()


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
    rows = sorted(TOOL_DIR.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    return rows[0] if rows else None


def _load_tool_payload(pattern: str) -> tuple[dict[str, Any], Path | None]:
    path = _latest_tool(pattern)
    payload = _read_json(path, {}) if path else {}
    if not isinstance(payload, dict):
        payload = {}
    return payload, path


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _priority_label(score: float) -> str:
    if score >= 80:
        return "HIGH"
    if score >= 45:
        return "MEDIUM"
    return "LOW"


def _normalize_risk(value: Any, fallback: str = "MEDIUM") -> str:
    token = str(value or "").strip().upper()
    if token in {"LOW", "MEDIUM", "HIGH"}:
        return token
    return fallback


def _opportunity_id(parts: list[str]) -> str:
    base = "|".join(parts)
    return hashlib.sha1(base.encode("utf-8")).hexdigest()[:12]


def _default_policy() -> dict[str, Any]:
    return {
        "max_items": max(5, MAX_ITEMS_DEFAULT),
        "min_priority_score": 18.0,
        "include_source_types": ["social", "github", "github_trending", "ecosystem", "prediction", "portfolio", "bookmark"],
        "weights": {
            "social": 1.00,
            "github": 1.00,
            "github_trending": 0.90,
            "ecosystem": 0.95,
            "prediction": 1.15,
            "portfolio": 0.90,
            "bookmark": 1.10,
        },
        "updated_at": _now_iso(),
    }


def _ensure_policy(path: Path, force_template: bool) -> tuple[dict[str, Any], str]:
    defaults = _default_policy()
    if force_template or not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(defaults, indent=2) + "\n", encoding="utf-8")
        return defaults, "written"

    payload = _read_json(path, {})
    if not isinstance(payload, dict):
        payload = {}
    merged = dict(defaults)
    merged.update(payload)
    if not isinstance(merged.get("weights"), dict):
        merged["weights"] = dict(defaults["weights"])
    else:
        fixed = dict(defaults["weights"])
        fixed.update(merged.get("weights") or {})
        merged["weights"] = fixed
    if not isinstance(merged.get("include_source_types"), list):
        merged["include_source_types"] = list(defaults["include_source_types"])
    if merged != payload:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(merged, indent=2) + "\n", encoding="utf-8")
        return merged, "updated"
    return merged, "existing"


def _social_ops(payload: dict[str, Any], source_path: Path | None, weight: float) -> list[dict[str, Any]]:
    rows = payload.get("top_items")
    if not isinstance(rows, list):
        rows = []

    out: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        title = str(row.get("title") or "").strip()
        if not title:
            continue
        summary = str(row.get("summary") or title).strip()
        score = _safe_float(row.get("score"), 0.0)
        matched = row.get("matched_keywords") if isinstance(row.get("matched_keywords"), list) else []
        matched_hits = len([x for x in matched if str(x).strip()])
        text_blob = f"{title} {summary}".lower()
        if any(pattern in text_blob for pattern in SOCIAL_SPAM_PATTERNS):
            continue
        intent_hits = [token for token in SOCIAL_INTENT_TOKENS if token in text_blob]
        if title.strip().startswith("@") and not intent_hits:
            continue
        if not intent_hits and score < 5.5:
            continue
        priority_score = round((score * 12.0 + matched_hits * 2.0) * max(0.1, weight), 2)
        link = str(row.get("link") or "").strip()
        risk = "MEDIUM" if any(token in text_blob for token in ["trade", "market", "prediction", "crypto"]) else "LOW"
        proposed_action = (
            "Run one reversible validation test and capture conversion/engagement evidence before scaling."
        )
        draft_task = (
            "Review this signal, define one low-risk test, and log results in the next daily board update."
        )
        out.append(
            {
                "opportunity_id": _opportunity_id(["social", title, link, proposed_action]),
                "source_type": "social",
                "source_name": str(row.get("source") or row.get("platform") or "social"),
                "source_ref": str(source_path) if source_path else "none",
                "title": title,
                "summary": summary[:500],
                "priority_score": priority_score,
                "priority": _priority_label(priority_score),
                "risk_tier": risk,
                "implementation_scope": "opportunity_execution",
                "proposed_action": proposed_action,
                "expected_benefit": "Captures early demand signals with bounded risk.",
                "risk_if_ignored": "A useful trend may be discovered too late to capture leverage.",
                "draft_codex_task": draft_task,
                "manual_approval_required": True,
                "evidence": [link] if link else [],
                "metadata": {
                    "matched_keywords": matched[:10],
                    "intent_hits": intent_hits[:10],
                    "raw_score": score,
                },
            }
        )
    return out


def _github_ops(payload: dict[str, Any], source_path: Path | None, weight: float) -> list[dict[str, Any]]:
    repos = payload.get("repos")
    if not isinstance(repos, list):
        repos = []

    out: list[dict[str, Any]] = []
    for repo_row in repos:
        if not isinstance(repo_row, dict):
            continue
        repo = str(repo_row.get("repo") or "unknown/repo").strip()
        stale_issues = _safe_int(repo_row.get("stale_issues"), 0)
        stale_prs = _safe_int(repo_row.get("stale_prs"), 0)
        focus_hits = _safe_int(repo_row.get("focus_label_hits"), 0)
        open_issues = _safe_int(repo_row.get("open_issues"), 0)
        base_score = 35.0 + stale_issues * 6.0 + stale_prs * 7.0 + focus_hits * 3.0 + min(20.0, float(open_issues))

        actions = repo_row.get("top_actions")
        if not isinstance(actions, list):
            actions = []
        if not actions:
            actions = ["Review open engineering backlog for highest-value fix."]

        for action in actions[:3]:
            action_text = str(action or "").strip()
            if not action_text:
                continue
            priority_score = round(base_score * max(0.1, weight), 2)
            title = f"{repo}: {action_text}"
            out.append(
                {
                    "opportunity_id": _opportunity_id(["github", repo, action_text]),
                    "source_type": "github",
                    "source_name": repo,
                    "source_ref": str(source_path) if source_path else "none",
                    "title": title[:180],
                    "summary": (
                        f"Backlog signal from {repo} with stale_issues={stale_issues}, "
                        f"stale_prs={stale_prs}, focus_label_hits={focus_hits}."
                    ),
                    "priority_score": priority_score,
                    "priority": _priority_label(priority_score),
                    "risk_tier": "LOW",
                    "implementation_scope": "system_improvement",
                    "proposed_action": action_text,
                    "expected_benefit": "Reduces technical drag and unlocks compounding output velocity.",
                    "risk_if_ignored": "Operational debt increases and slows execution quality.",
                    "draft_codex_task": f"Create a scoped implementation plan for: {action_text}",
                    "manual_approval_required": True,
                    "evidence": [],
                    "metadata": {
                        "stale_issues": stale_issues,
                        "stale_prs": stale_prs,
                        "focus_label_hits": focus_hits,
                    },
                }
            )
    return out


def _github_trending_ops(payload: dict[str, Any], source_path: Path | None, weight: float) -> list[dict[str, Any]]:
    rows = payload.get("top_items")
    if not isinstance(rows, list):
        rows = []

    out: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        repo = str(row.get("repo") or "").strip()
        if not repo:
            continue
        score_raw = _safe_float(row.get("priority_score"), 0.0)
        stars_period = _safe_int(row.get("stars_period"), 0)
        keyword_hits = row.get("keyword_hits") if isinstance(row.get("keyword_hits"), list) else []
        watchlist_hit = bool(row.get("watchlist_hit"))
        title = f"{repo} trending spike"
        priority_score = round((max(10.0, score_raw) + min(40.0, stars_period * 0.03)) * max(0.1, weight), 2)
        action = "Review architecture and extract one deployable pattern for Permanence OS."
        if watchlist_hit:
            action = "Prioritize deep review and create an integration memo with one prototype task."

        out.append(
            {
                "opportunity_id": _opportunity_id(["github_trending", repo, str(row.get("url") or "")]),
                "source_type": "github_trending",
                "source_name": repo,
                "source_ref": str(source_path) if source_path else "none",
                "title": title[:180],
                "summary": (
                    f"score={score_raw}, stars_period={stars_period}, "
                    f"language={row.get('language') or '-'}, watchlist_hit={watchlist_hit}"
                ),
                "priority_score": priority_score,
                "priority": _priority_label(priority_score),
                "risk_tier": "LOW",
                "implementation_scope": "system_improvement",
                "proposed_action": action,
                "expected_benefit": "Accelerates adoption of proven open-source patterns.",
                "risk_if_ignored": "Missed compounding opportunities from active ecosystem shifts.",
                "draft_codex_task": (
                    f"Analyze {repo} and produce a governed 'adopt/adapt/reject' implementation note."
                ),
                "manual_approval_required": True,
                "evidence": [str(row.get("url") or "")] if str(row.get("url") or "").strip() else [],
                "metadata": {
                    "stars_period": stars_period,
                    "language": str(row.get("language") or ""),
                    "keyword_hits": keyword_hits[:10],
                    "watchlist_hit": watchlist_hit,
                },
            }
        )
    return out


def _ecosystem_ops(payload: dict[str, Any], source_path: Path | None, weight: float) -> list[dict[str, Any]]:
    repos = payload.get("repos")
    if not isinstance(repos, list):
        repos = []
    developers = payload.get("developers")
    if not isinstance(developers, list):
        developers = []
    docs = payload.get("docs")
    if not isinstance(docs, list):
        docs = []
    communities = payload.get("communities")
    if not isinstance(communities, list):
        communities = []

    out: list[dict[str, Any]] = []
    for row in sorted([r for r in repos if isinstance(r, dict)], key=lambda r: _safe_float(r.get("priority_score"), 0), reverse=True)[:6]:
        repo = str(row.get("repo") or "").strip()
        if not repo:
            continue
        score_raw = _safe_float(row.get("priority_score"), 0.0)
        stars = _safe_int(row.get("stars"), 0)
        action = "Create adopt/adapt/reject memo with one bounded prototype task."
        priority_score = round((max(12.0, score_raw) + min(26.0, stars * 0.001)) * max(0.1, weight), 2)
        out.append(
            {
                "opportunity_id": _opportunity_id(["ecosystem_repo", repo, str(row.get("updated_at") or "")]),
                "source_type": "ecosystem",
                "source_name": repo,
                "source_ref": str(source_path) if source_path else "none",
                "title": f"{repo} ecosystem adoption review"[:180],
                "summary": (
                    f"score={score_raw}, stars={stars}, language={row.get('language') or '-'}, "
                    f"open_issues={_safe_int(row.get('open_issues'), 0)}"
                ),
                "priority_score": priority_score,
                "priority": _priority_label(priority_score),
                "risk_tier": "LOW",
                "implementation_scope": "system_improvement",
                "proposed_action": action,
                "expected_benefit": "Captures proven architecture patterns earlier and compounds platform capability.",
                "risk_if_ignored": "Missed leverage from active ecosystem shifts and interoperability patterns.",
                "draft_codex_task": f"Analyze {repo} and draft a 1-page integration recommendation with rollback plan.",
                "manual_approval_required": True,
                "evidence": [str(row.get("html_url") or "")] if str(row.get("html_url") or "").strip() else [],
                "metadata": {
                    "priority_score_raw": score_raw,
                    "stars": stars,
                    "language": str(row.get("language") or ""),
                },
            }
        )

    for row in sorted([r for r in developers if isinstance(r, dict)], key=lambda r: _safe_float(r.get("priority_score"), 0), reverse=True)[:4]:
        login = str(row.get("login") or "").strip()
        if not login:
            continue
        score_raw = _safe_float(row.get("priority_score"), 0.0)
        followers = _safe_int(row.get("followers"), 0)
        priority_score = round((max(10.0, score_raw) + min(16.0, followers * 0.01)) * max(0.1, weight), 2)
        out.append(
            {
                "opportunity_id": _opportunity_id(["ecosystem_dev", login, str(row.get("html_url") or "")]),
                "source_type": "ecosystem",
                "source_name": f"@{login}",
                "source_ref": str(source_path) if source_path else "none",
                "title": f"Track @{login} patterns and releases"[:180],
                "summary": (
                    f"score={score_raw}, followers={followers}, "
                    f"public_repos={_safe_int(row.get('public_repos'), 0)}"
                ),
                "priority_score": priority_score,
                "priority": _priority_label(priority_score),
                "risk_tier": "LOW",
                "implementation_scope": "research_intelligence",
                "proposed_action": "Capture release/design patterns and map to one practical system upgrade opportunity.",
                "expected_benefit": "Improves signal quality by following high-output builders directly.",
                "risk_if_ignored": "Signals remain fragmented and less actionable.",
                "draft_codex_task": f"Generate a weekly watch brief for @{login} with concrete integration candidates.",
                "manual_approval_required": True,
                "evidence": [str(row.get("html_url") or "")] if str(row.get("html_url") or "").strip() else [],
                "metadata": {
                    "priority_score_raw": score_raw,
                    "followers": followers,
                },
            }
        )

    down_links = [row for row in [*docs, *communities] if isinstance(row, dict) and not bool(row.get("reachable"))]
    for row in down_links[:3]:
        url = str(row.get("url") or "").strip()
        if not url:
            continue
        priority_score = round(24.0 * max(0.1, weight), 2)
        out.append(
            {
                "opportunity_id": _opportunity_id(["ecosystem_link", url]),
                "source_type": "ecosystem",
                "source_name": "ecosystem_links",
                "source_ref": str(source_path) if source_path else "none",
                "title": "Repair or replace stale ecosystem source link",
                "summary": f"Unreachable source in watchlist: {url}",
                "priority_score": priority_score,
                "priority": _priority_label(priority_score),
                "risk_tier": "LOW",
                "implementation_scope": "system_improvement",
                "proposed_action": "Replace with a verified primary source and update watchlist provenance notes.",
                "expected_benefit": "Keeps research inputs fresh and lowers blind spots in automation.",
                "risk_if_ignored": "Signal quality decays due to stale references.",
                "draft_codex_task": f"Patch ecosystem watchlist to replace stale URL: {url}",
                "manual_approval_required": True,
                "evidence": [url],
                "metadata": {"status": _safe_int(row.get("status"), 0)},
            }
        )

    return out


def _prediction_ops(payload: dict[str, Any], source_path: Path | None, weight: float) -> list[dict[str, Any]]:
    results = payload.get("results")
    if not isinstance(results, list):
        results = []

    out: list[dict[str, Any]] = []
    for row in results:
        if not isinstance(row, dict):
            continue
        decision = str(row.get("decision") or "").strip().lower()
        if decision == "reject_negative_ev":
            continue
        title = str(row.get("title") or "").strip()
        if not title:
            continue
        edge = _safe_float(row.get("edge"), 0.0)
        ev = _safe_float(row.get("expected_pnl_per_1usd"), 0.0)
        suggestion = _safe_float(row.get("suggested_stake_usd"), 0.0)
        base_score = 30.0 + max(0.0, edge * 600.0) + max(0.0, ev * 120.0)
        if decision == "review_for_manual_execution":
            base_score += 25.0
        priority_score = round(base_score * max(0.1, weight), 2)
        market = str(row.get("market") or "unknown")
        out.append(
            {
                "opportunity_id": _opportunity_id(["prediction", market, title, str(row.get("hypothesis_id"))]),
                "source_type": "prediction",
                "source_name": market,
                "source_ref": str(source_path) if source_path else "none",
                "title": title[:180],
                "summary": (
                    f"edge={edge:.4f}, ev_per_$1={ev:.4f}, suggested_stake=${suggestion:,.2f}, decision={decision or 'watchlist'}"
                ),
                "priority_score": priority_score,
                "priority": _priority_label(priority_score),
                "risk_tier": "HIGH",
                "implementation_scope": "manual_financial_review",
                "proposed_action": "Run manual desk review + paper-trade validation. Do not execute autonomous trades.",
                "expected_benefit": "Surfaces positive-EV hypotheses for disciplined human review.",
                "risk_if_ignored": "Potentially high-quality edges go unreviewed or decay.",
                "draft_codex_task": (
                    "Prepare a one-page risk memo (thesis, invalidation, max loss) and request explicit human go/no-go."
                ),
                "manual_approval_required": True,
                "evidence": [],
                "metadata": {
                    "hypothesis_id": str(row.get("hypothesis_id") or ""),
                    "decision": decision,
                    "edge": edge,
                    "expected_pnl_per_1usd": ev,
                    "suggested_stake_usd": suggestion,
                },
            }
        )
    return out


def _portfolio_ops(payload: dict[str, Any], source_path: Path | None, weight: float) -> list[dict[str, Any]]:
    rows = payload.get("top_actions")
    if not isinstance(rows, list):
        rows = payload.get("streams")
    if not isinstance(rows, list):
        rows = []

    out: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        name = str(row.get("name") or "").strip()
        if not name:
            continue
        stream_id = str(row.get("stream_id") or "stream")
        next_action = str(row.get("next_action") or "").strip() or "Define the next measurable milestone."
        priority_raw = _safe_float(row.get("priority_score"), 0.0)
        weekly_gap = _safe_float(row.get("weekly_gap_usd"), 0.0)
        priority_score = round(min(120.0, max(15.0, priority_raw / 10.0 + weekly_gap / 120.0)) * max(0.1, weight), 2)
        risk = _normalize_risk(row.get("risk"), fallback="MEDIUM")
        out.append(
            {
                "opportunity_id": _opportunity_id(["portfolio", stream_id, name, next_action]),
                "source_type": "portfolio",
                "source_name": stream_id,
                "source_ref": str(source_path) if source_path else "none",
                "title": f"{name} ({stream_id})"[:180],
                "summary": (
                    f"weekly_gap=${weekly_gap:,.0f}, risk={risk.lower()}, "
                    f"pipeline_count={_safe_int(row.get('pipeline_count'), 0)}."
                ),
                "priority_score": priority_score,
                "priority": _priority_label(priority_score),
                "risk_tier": risk,
                "implementation_scope": "business_execution",
                "proposed_action": next_action,
                "expected_benefit": "Moves one stream forward with measurable weekly output.",
                "risk_if_ignored": "Portfolio stagnates and misses compounding revenue opportunities.",
                "draft_codex_task": f"Convert this stream action into a checklist with owner, deadline, and success metric: {next_action}",
                "manual_approval_required": True,
                "evidence": [],
                "metadata": {
                    "stream_id": stream_id,
                    "priority_score_raw": priority_raw,
                    "weekly_gap_usd": weekly_gap,
                },
            }
        )
    return out


def _bookmark_ops(payload: dict[str, Any], source_path: Path | None, weight: float) -> list[dict[str, Any]]:
    rows = payload.get("top_items")
    if not isinstance(rows, list):
        rows = []

    out: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        text = str(row.get("text") or "").strip()
        if not text:
            continue
        title = text if len(text) <= 140 else (text[:137] + "...")
        url = str(row.get("url") or "").strip()
        handle = str(row.get("handle") or row.get("author") or "").strip()
        topic_tags = row.get("topic_tags") if isinstance(row.get("topic_tags"), list) else []
        signal_score = _safe_float(row.get("signal_score"), 0.0)
        text_blob = f"{text} {' '.join(topic_tags)}".lower()
        if any(pattern in text_blob for pattern in SOCIAL_SPAM_PATTERNS):
            continue
        intent_hits = [token for token in SOCIAL_INTENT_TOKENS if token in text_blob]
        base_score = 30.0 + signal_score * 4.0 + len(topic_tags) * 3.0 + len(intent_hits) * 2.0
        priority_score = round(base_score * max(0.1, weight), 2)
        action = "Review this bookmark signal and identify one buildable prototype or integration opportunity."
        out.append(
            {
                "opportunity_id": _opportunity_id(["bookmark", text[:80], url]),
                "source_type": "bookmark",
                "source_name": f"@{handle}" if handle else "x_bookmark",
                "source_ref": str(source_path) if source_path else "none",
                "title": title,
                "summary": text[:500],
                "priority_score": priority_score,
                "priority": _priority_label(priority_score),
                "risk_tier": "LOW",
                "implementation_scope": "research_intelligence",
                "proposed_action": action,
                "expected_benefit": "Captures curated signals from personal bookmarks for systematic review.",
                "risk_if_ignored": "Valuable bookmarked ideas may decay before evaluation.",
                "draft_codex_task": (
                    f"Review bookmark from @{handle}: {text[:100]}. "
                    "Produce adopt/adapt/reject recommendation with one reversible next step."
                ),
                "manual_approval_required": True,
                "evidence": [url] if url else [],
                "metadata": {
                    "handle": handle,
                    "topic_tags": topic_tags[:10],
                    "signal_score": signal_score,
                    "intent_hits": intent_hits[:10],
                },
            }
        )
    return out


def _dedupe(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for row in rows:
        key = str(row.get("opportunity_id") or "").strip()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(row)
    return out


def _filter_rank(
    rows: list[dict[str, Any]],
    min_priority_score: float,
    max_items: int,
    include_source_types: list[str],
) -> list[dict[str, Any]]:
    source_allow = {str(item).strip().lower() for item in include_source_types if str(item).strip()}
    filtered: list[dict[str, Any]] = []
    for row in rows:
        source_type = str(row.get("source_type") or "").strip().lower()
        if source_allow and source_type not in source_allow:
            continue
        score = _safe_float(row.get("priority_score"), 0.0)
        if score < min_priority_score:
            continue
        filtered.append(row)
    filtered.sort(key=lambda row: _safe_float(row.get("priority_score"), 0.0), reverse=True)
    return filtered[: max(1, max_items)]


def _write_outputs(
    ranked: list[dict[str, Any]],
    policy: dict[str, Any],
    policy_status: str,
    source_paths: dict[str, str],
    source_counts: dict[str, int],
    warnings: list[str],
) -> tuple[Path, Path]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    TOOL_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _now().strftime("%Y%m%d-%H%M%S")
    md_path = OUTPUT_DIR / f"opportunity_ranker_{stamp}.md"
    latest_md = OUTPUT_DIR / "opportunity_ranker_latest.md"
    json_path = TOOL_DIR / f"opportunity_ranker_{stamp}.json"

    lines = [
        "# Opportunity Ranker",
        "",
        f"Generated (UTC): {_now_iso()}",
        f"Policy: {POLICY_PATH} ({policy_status})",
        "",
        "## Summary",
        f"- Ranked opportunities: {len(ranked)}",
        (
            "- Source counts: "
            f"social={source_counts.get('social', 0)}, github={source_counts.get('github', 0)}, "
            f"github_trending={source_counts.get('github_trending', 0)}, ecosystem={source_counts.get('ecosystem', 0)}, "
            f"prediction={source_counts.get('prediction', 0)}, portfolio={source_counts.get('portfolio', 0)}, "
            f"bookmark={source_counts.get('bookmark', 0)}"
        ),
        f"- Min priority score: {policy.get('min_priority_score')}",
        f"- Max items: {policy.get('max_items')}",
        "",
        "## Top Opportunities",
    ]
    if not ranked:
        lines.append("- No opportunities met ranking thresholds.")
    for idx, row in enumerate(ranked, start=1):
        lines.extend(
            [
                f"{idx}. {row.get('title')} [{row.get('source_type')}]",
                (
                    "   - "
                    f"score={row.get('priority_score')} | priority={row.get('priority')} | risk={row.get('risk_tier')} | "
                    f"scope={row.get('implementation_scope')}"
                ),
                f"   - action={row.get('proposed_action')}",
            ]
        )

    if warnings:
        lines.extend(["", "## Warnings"])
        for warning in warnings:
            lines.append(f"- {warning}")

    lines.extend(
        [
            "",
            "## Governance Notes",
            "- Ranking is advisory only and never executes money/publishing actions.",
            "- Every ranked opportunity stays human-approved before execution.",
            "",
        ]
    )

    report = "\n".join(lines)
    md_path.write_text(report, encoding="utf-8")
    latest_md.write_text(report, encoding="utf-8")

    payload = {
        "generated_at": _now_iso(),
        "policy_path": str(POLICY_PATH),
        "policy_status": policy_status,
        "policy": policy,
        "source_paths": source_paths,
        "source_counts": source_counts,
        "item_count": len(ranked),
        "top_items": ranked,
        "warnings": warnings,
        "latest_markdown": str(latest_md),
    }
    json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return md_path, json_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Rank multi-source opportunities for manual review.")
    parser.add_argument("--force-policy", action="store_true", help="Rewrite ranking policy template file")
    parser.add_argument("--max-items", type=int, help="Override max opportunities retained")
    parser.add_argument("--min-score", type=float, help="Override minimum priority score threshold")
    args = parser.parse_args(argv)

    policy, policy_status = _ensure_policy(POLICY_PATH, force_template=args.force_policy)
    weights = policy.get("weights") if isinstance(policy.get("weights"), dict) else {}
    include_source_types = policy.get("include_source_types") if isinstance(policy.get("include_source_types"), list) else []

    social_payload, social_path = _load_tool_payload("social_research_ingest_*.json")
    github_payload, github_path = _load_tool_payload("github_research_ingest_*.json")
    github_trending_payload, github_trending_path = _load_tool_payload("github_trending_ingest_*.json")
    ecosystem_payload, ecosystem_path = _load_tool_payload("ecosystem_research_ingest_*.json")
    prediction_payload, prediction_path = _load_tool_payload("prediction_lab_*.json")
    portfolio_payload, portfolio_path = _load_tool_payload("side_business_portfolio_*.json")
    bookmark_payload, bookmark_path = _load_tool_payload("x_bookmark_ingest_*.json")

    warnings: list[str] = []
    if not social_path:
        warnings.append("No social_research_ingest payload found in memory/tool.")
    if not github_path:
        warnings.append("No github_research_ingest payload found in memory/tool.")
    if not github_trending_path:
        warnings.append("No github_trending_ingest payload found in memory/tool.")
    if not ecosystem_path:
        warnings.append("No ecosystem_research_ingest payload found in memory/tool.")
    if not prediction_path:
        warnings.append("No prediction_lab payload found in memory/tool.")
    if not portfolio_path:
        warnings.append("No side_business_portfolio payload found in memory/tool.")
    if not bookmark_path:
        warnings.append("No x_bookmark_ingest payload found in memory/tool.")

    rows: list[dict[str, Any]] = []
    rows.extend(_social_ops(social_payload, social_path, _safe_float(weights.get("social"), 1.0)))
    rows.extend(_github_ops(github_payload, github_path, _safe_float(weights.get("github"), 1.0)))
    rows.extend(
        _github_trending_ops(
            github_trending_payload,
            github_trending_path,
            _safe_float(weights.get("github_trending"), 0.9),
        )
    )
    rows.extend(_ecosystem_ops(ecosystem_payload, ecosystem_path, _safe_float(weights.get("ecosystem"), 0.95)))
    rows.extend(_prediction_ops(prediction_payload, prediction_path, _safe_float(weights.get("prediction"), 1.0)))
    rows.extend(_portfolio_ops(portfolio_payload, portfolio_path, _safe_float(weights.get("portfolio"), 1.0)))
    rows.extend(_bookmark_ops(bookmark_payload, bookmark_path, _safe_float(weights.get("bookmark"), 1.1)))
    rows = _dedupe(rows)

    max_items = _safe_int(args.max_items, _safe_int(policy.get("max_items"), MAX_ITEMS_DEFAULT))
    min_priority_score = _safe_float(args.min_score, _safe_float(policy.get("min_priority_score"), 18.0))
    ranked = _filter_rank(
        rows,
        min_priority_score=min_priority_score,
        max_items=max_items,
        include_source_types=[str(item) for item in include_source_types],
    )

    source_counts = {
        "social": sum(1 for row in ranked if row.get("source_type") == "social"),
        "github": sum(1 for row in ranked if row.get("source_type") == "github"),
        "github_trending": sum(1 for row in ranked if row.get("source_type") == "github_trending"),
        "ecosystem": sum(1 for row in ranked if row.get("source_type") == "ecosystem"),
        "prediction": sum(1 for row in ranked if row.get("source_type") == "prediction"),
        "portfolio": sum(1 for row in ranked if row.get("source_type") == "portfolio"),
        "bookmark": sum(1 for row in ranked if row.get("source_type") == "bookmark"),
    }
    source_paths = {
        "social": str(social_path) if social_path else "none",
        "github": str(github_path) if github_path else "none",
        "github_trending": str(github_trending_path) if github_trending_path else "none",
        "ecosystem": str(ecosystem_path) if ecosystem_path else "none",
        "prediction": str(prediction_path) if prediction_path else "none",
        "portfolio": str(portfolio_path) if portfolio_path else "none",
        "bookmark": str(bookmark_path) if bookmark_path else "none",
    }

    md_path, json_path = _write_outputs(
        ranked=ranked,
        policy=policy,
        policy_status=policy_status,
        source_paths=source_paths,
        source_counts=source_counts,
        warnings=warnings,
    )
    print(f"Opportunity ranker written: {md_path}")
    print(f"Opportunity ranker latest: {OUTPUT_DIR / 'opportunity_ranker_latest.md'}")
    print(f"Tool payload written: {json_path}")
    print(f"Ranked opportunities: {len(ranked)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
