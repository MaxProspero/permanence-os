#!/usr/bin/env python3
"""
Cross-pipeline revenue intelligence: connect bookmark intelligence,
idea intake, opportunity ranking, and revenue systems to identify
monetizable opportunities.
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
REVENUE_INTAKE_PATH = Path(
    os.getenv("PERMANENCE_REVENUE_INTAKE_PATH", str(WORKING_DIR / "revenue_intake.jsonl"))
)
PLAYBOOK_PATH = Path(
    os.getenv("PERMANENCE_REVENUE_PLAYBOOK_PATH", str(WORKING_DIR / "revenue_playbook.json"))
)
MAX_ITEMS_DEFAULT = int(os.getenv("PERMANENCE_REVENUE_INTEL_MAX_ITEMS", "15"))


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now().isoformat()


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return default


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


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


def _priority_label(score: float) -> str:
    if score >= 80:
        return "HIGH"
    if score >= 45:
        return "MEDIUM"
    return "LOW"


def _item_id(parts: list[str]) -> str:
    base = "|".join(parts)
    return hashlib.sha1(base.encode("utf-8")).hexdigest()[:12]


def _load_playbook() -> dict[str, Any]:
    return _read_json(PLAYBOOK_PATH, {})


def _extract_bookmark_signals(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract high-value signals from bookmark intelligence brief."""
    items = payload.get("top_items")
    if not isinstance(items, list):
        items = []
    clusters = payload.get("topic_clusters")
    if not isinstance(clusters, dict):
        clusters = {}
    signals: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        text = str(item.get("text") or "").strip()
        if not text:
            continue
        topic_tags = item.get("topic_tags") if isinstance(item.get("topic_tags"), list) else []
        score = _safe_float(item.get("signal_score"), 0.0)
        signals.append({
            "text": text,
            "source": "bookmark",
            "topic_tags": topic_tags,
            "score": score,
            "handle": str(item.get("handle") or ""),
            "url": str(item.get("url") or ""),
        })
    return signals


def _extract_opportunity_signals(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract ranked opportunities from opportunity ranker output."""
    items = payload.get("top_items")
    if not isinstance(items, list):
        items = []
    signals: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        if not title:
            continue
        signals.append({
            "title": title,
            "source": str(item.get("source_type") or "unknown"),
            "priority_score": _safe_float(item.get("priority_score"), 0.0),
            "proposed_action": str(item.get("proposed_action") or ""),
            "risk_tier": str(item.get("risk_tier") or "MEDIUM"),
        })
    return signals


def _extract_idea_signals(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract scored ideas from idea intake output."""
    items = payload.get("ranked")
    if not isinstance(items, list):
        items = payload.get("top_items")
    if not isinstance(items, list):
        items = []
    signals: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or item.get("url") or "").strip()
        if not title:
            continue
        signals.append({
            "title": title,
            "source": "idea_intake",
            "score": _safe_float(item.get("score"), 0.0),
            "category": str(item.get("category") or ""),
            "url": str(item.get("url") or ""),
        })
    return signals


REVENUE_KEYWORDS = [
    "saas", "revenue", "monetize", "mrr", "client", "lead", "agency",
    "product", "service", "startup", "founder", "growth", "automation",
    "api", "platform", "subscription", "pricing", "market", "sell",
]


def _score_revenue_potential(
    bookmark_signals: list[dict[str, Any]],
    opportunity_signals: list[dict[str, Any]],
    idea_signals: list[dict[str, Any]],
    playbook: dict[str, Any],
) -> list[dict[str, Any]]:
    """Cross-reference signals to identify monetizable opportunities."""
    candidates: list[dict[str, Any]] = []

    for sig in bookmark_signals:
        text_lower = sig["text"].lower()
        revenue_hits = [kw for kw in REVENUE_KEYWORDS if kw in text_lower]
        if not revenue_hits:
            continue
        base_score = 25.0 + sig["score"] * 3.0 + len(revenue_hits) * 5.0
        tags = sig.get("topic_tags") or []
        if "startup" in tags or "product" in tags:
            base_score += 10.0
        if "agents" in tags or "ai" in tags:
            base_score += 8.0
        candidates.append({
            "revenue_id": _item_id(["bookmark", sig["text"][:80], sig.get("url", "")]),
            "source_pipeline": "bookmark_intelligence",
            "title": sig["text"][:140],
            "revenue_score": round(base_score, 2),
            "priority": _priority_label(base_score),
            "revenue_keywords": revenue_hits[:10],
            "topic_tags": tags[:10],
            "evidence": [sig.get("url", "")],
            "handle": sig.get("handle", ""),
            "proposed_action": (
                "Evaluate this signal for product or service opportunity. "
                "Define one prototype or offer variant."
            ),
            "manual_approval_required": True,
        })

    for sig in opportunity_signals:
        text_lower = sig["title"].lower()
        revenue_hits = [kw for kw in REVENUE_KEYWORDS if kw in text_lower]
        if not revenue_hits and sig["priority_score"] < 50:
            continue
        base_score = sig["priority_score"] * 0.8 + len(revenue_hits) * 4.0
        candidates.append({
            "revenue_id": _item_id(["opportunity", sig["title"][:80]]),
            "source_pipeline": "opportunity_ranker",
            "title": sig["title"][:140],
            "revenue_score": round(base_score, 2),
            "priority": _priority_label(base_score),
            "revenue_keywords": revenue_hits[:10],
            "topic_tags": [],
            "evidence": [],
            "handle": "",
            "proposed_action": sig.get("proposed_action", "Review and scope."),
            "manual_approval_required": True,
        })

    for sig in idea_signals:
        text_lower = sig["title"].lower()
        revenue_hits = [kw for kw in REVENUE_KEYWORDS if kw in text_lower]
        if not revenue_hits and sig["score"] < 60:
            continue
        base_score = sig["score"] * 0.6 + len(revenue_hits) * 5.0
        candidates.append({
            "revenue_id": _item_id(["idea", sig["title"][:80]]),
            "source_pipeline": "idea_intake",
            "title": sig["title"][:140],
            "revenue_score": round(base_score, 2),
            "priority": _priority_label(base_score),
            "revenue_keywords": revenue_hits[:10],
            "topic_tags": [],
            "evidence": [sig.get("url", "")],
            "handle": "",
            "proposed_action": "Evaluate idea for revenue potential and create one bounded prototype.",
            "manual_approval_required": True,
        })

    candidates.sort(key=lambda c: c.get("revenue_score", 0), reverse=True)
    return candidates


def _write_revenue_intake(candidates: list[dict[str, Any]], max_items: int) -> int:
    """Append top candidates to revenue intake JSONL for revenue_action_queue."""
    REVENUE_INTAKE_PATH.parent.mkdir(parents=True, exist_ok=True)
    existing_ids: set[str] = set()
    if REVENUE_INTAKE_PATH.exists():
        try:
            for line in REVENUE_INTAKE_PATH.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                    rid = str(row.get("revenue_id") or "").strip()
                    if rid:
                        existing_ids.add(rid)
                except json.JSONDecodeError:
                    continue
        except OSError:
            pass

    written = 0
    with open(REVENUE_INTAKE_PATH, "a", encoding="utf-8") as fh:
        for candidate in candidates[:max_items]:
            rid = str(candidate.get("revenue_id") or "").strip()
            if rid in existing_ids:
                continue
            entry = {
                "revenue_id": rid,
                "title": candidate.get("title", ""),
                "source_pipeline": candidate.get("source_pipeline", ""),
                "revenue_score": candidate.get("revenue_score", 0),
                "priority": candidate.get("priority", "LOW"),
                "proposed_action": candidate.get("proposed_action", ""),
                "manual_approval_required": True,
                "queued_at": _now_iso(),
            }
            fh.write(json.dumps(entry) + "\n")
            existing_ids.add(rid)
            written += 1
    return written


def _write_outputs(
    candidates: list[dict[str, Any]],
    bookmark_count: int,
    opportunity_count: int,
    idea_count: int,
    playbook: dict[str, Any],
    intake_written: int,
    warnings: list[str],
    source_paths: dict[str, str],
) -> tuple[Path, Path]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    TOOL_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _now().strftime("%Y%m%d-%H%M%S")
    md_path = OUTPUT_DIR / f"revenue_intelligence_{stamp}.md"
    latest_md = OUTPUT_DIR / "revenue_intelligence_latest.md"
    json_path = TOOL_DIR / f"revenue_intelligence_{stamp}.json"

    offer = str(playbook.get("offer_name") or "No active offer")
    price = _safe_float(playbook.get("price_usd"), 0)

    lines = [
        "# Revenue Intelligence Brief",
        "",
        f"Generated (UTC): {_now_iso()}",
        "",
        "## Summary",
        f"- Bookmark signals analyzed: {bookmark_count}",
        f"- Opportunity signals analyzed: {opportunity_count}",
        f"- Idea signals analyzed: {idea_count}",
        f"- Revenue candidates identified: {len(candidates)}",
        f"- Queued to revenue intake: {intake_written}",
        f"- Active offer: {offer} (${price:,.0f})" if price else f"- Active offer: {offer}",
        "",
        "## Top Revenue Candidates",
    ]
    if not candidates:
        lines.append("- No revenue candidates met scoring thresholds.")
    for idx, row in enumerate(candidates[:15], start=1):
        lines.extend([
            f"{idx}. {row.get('title')} [{row.get('source_pipeline')}]",
            f"   - revenue_score={row.get('revenue_score')} | priority={row.get('priority')}",
            f"   - keywords={','.join(row.get('revenue_keywords') or []) or '-'}",
            f"   - action={row.get('proposed_action', '')}",
        ])

    if warnings:
        lines.extend(["", "## Warnings"])
        for w in warnings:
            lines.append(f"- {w}")

    lines.extend([
        "",
        "## Source Paths",
    ])
    for key, val in source_paths.items():
        lines.append(f"- {key}: {val}")

    lines.extend([
        "",
        "## Governance Notes",
        "- All candidates flagged manual_approval_required=true.",
        "- Revenue intelligence is advisory only. No financial actions are executed.",
        "- Human review required before any outbound action, pricing change, or commitment.",
        "",
    ])

    report = "\n".join(lines)
    md_path.write_text(report, encoding="utf-8")
    latest_md.write_text(report, encoding="utf-8")

    payload = {
        "generated_at": _now_iso(),
        "bookmark_signals": bookmark_count,
        "opportunity_signals": opportunity_count,
        "idea_signals": idea_count,
        "candidate_count": len(candidates),
        "intake_written": intake_written,
        "top_items": candidates[:15],
        "playbook_offer": offer,
        "source_paths": source_paths,
        "warnings": warnings,
        "latest_markdown": str(latest_md),
    }
    json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return md_path, json_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Cross-pipeline revenue intelligence synthesis.")
    parser.add_argument("--max-items", type=int, default=MAX_ITEMS_DEFAULT, help="Max items to queue")
    parser.add_argument("--action", default="run", choices=["run", "status"], help="Action to perform")
    args = parser.parse_args(argv)

    if args.action == "status":
        latest = _latest_tool("revenue_intelligence_*.json")
        if not latest:
            print("No revenue intelligence reports found.")
            return 0
        payload = _read_json(latest, {})
        print(f"Latest report: {latest}")
        print(f"Generated: {payload.get('generated_at', 'unknown')}")
        print(f"Candidates: {payload.get('candidate_count', 0)}")
        print(f"Queued to intake: {payload.get('intake_written', 0)}")
        return 0

    bookmark_payload, bookmark_path = _load_tool_payload("x_bookmark_ingest_*.json")
    bookmark_intel_payload, bookmark_intel_path = _load_tool_payload("bookmark_intelligence_*.json")
    opportunity_payload, opportunity_path = _load_tool_payload("opportunity_ranker_*.json")
    idea_payload, idea_path = _load_tool_payload("idea_intake_*.json")
    playbook = _load_playbook()

    warnings: list[str] = []
    if not bookmark_path and not bookmark_intel_path:
        warnings.append("No bookmark ingest or intelligence payload found in memory/tool.")
    if not opportunity_path:
        warnings.append("No opportunity_ranker payload found in memory/tool.")
    if not idea_path:
        warnings.append("No idea_intake payload found in memory/tool.")

    bookmark_source = bookmark_intel_payload if bookmark_intel_path else bookmark_payload
    bookmark_signals = _extract_bookmark_signals(bookmark_source)
    opportunity_signals = _extract_opportunity_signals(opportunity_payload)
    idea_signals = _extract_idea_signals(idea_payload)

    candidates = _score_revenue_potential(
        bookmark_signals, opportunity_signals, idea_signals, playbook
    )

    intake_written = _write_revenue_intake(candidates, max_items=args.max_items)

    source_paths = {
        "bookmark_ingest": str(bookmark_path) if bookmark_path else "none",
        "bookmark_intelligence": str(bookmark_intel_path) if bookmark_intel_path else "none",
        "opportunity_ranker": str(opportunity_path) if opportunity_path else "none",
        "idea_intake": str(idea_path) if idea_path else "none",
        "playbook": str(PLAYBOOK_PATH),
    }

    md_path, json_path = _write_outputs(
        candidates=candidates,
        bookmark_count=len(bookmark_signals),
        opportunity_count=len(opportunity_signals),
        idea_count=len(idea_signals),
        playbook=playbook,
        intake_written=intake_written,
        warnings=warnings,
        source_paths=source_paths,
    )

    print(f"Revenue intelligence written: {md_path}")
    print(f"Revenue intelligence latest: {OUTPUT_DIR / 'revenue_intelligence_latest.md'}")
    print(f"Tool payload written: {json_path}")
    print(f"Revenue candidates: {len(candidates)} | queued to intake: {intake_written}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
