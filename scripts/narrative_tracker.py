#!/usr/bin/env python3
"""
Track high-uncertainty market narratives with evidence status.

This includes conspiracy-style claims but keeps them in a strict evidence-first
framework (supported / unverified / contradicted).
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parents[1]
WORKING_DIR = Path(os.getenv("PERMANENCE_WORKING_DIR", str(BASE_DIR / "memory" / "working")))
OUTPUT_DIR = Path(os.getenv("PERMANENCE_OUTPUT_DIR", str(BASE_DIR / "outputs")))
TOOL_DIR = Path(os.getenv("PERMANENCE_TOOL_DIR", str(BASE_DIR / "memory" / "tool")))
HYPOTHESES_PATH = Path(
    os.getenv("PERMANENCE_NARRATIVE_HYPOTHESES_PATH", str(WORKING_DIR / "narrative_tracker_hypotheses.json"))
)


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


def _default_hypotheses() -> list[dict[str, Any]]:
    return [
        {
            "hypothesis_id": "NAR-001",
            "title": "Liquidity stress beneath official calm narrative",
            "category": "macro_liquidity",
            "support_keywords": [
                "liquidity stress",
                "funding stress",
                "repo",
                "emergency lending",
                "credit stress",
                "bank stress",
            ],
            "contradict_keywords": [
                "ample liquidity",
                "credit improving",
                "funding stable",
            ],
            "money_keywords": ["yield", "rates", "dollar", "treasury", "gold", "volatility"],
        },
        {
            "hypothesis_id": "NAR-002",
            "title": "Geopolitical escalation reprices commodities before headline consensus",
            "category": "geopolitics_commodities",
            "support_keywords": [
                "strait",
                "shipping disruption",
                "sanction",
                "pipeline",
                "oil shock",
                "energy squeeze",
                "war",
            ],
            "contradict_keywords": [
                "ceasefire",
                "supply normalizing",
                "export flows restored",
            ],
            "money_keywords": ["oil", "gas", "xauusd", "gold", "inflation", "freight"],
        },
        {
            "hypothesis_id": "NAR-003",
            "title": "Narrative-engineered risk rallies diverge from fundamentals",
            "category": "equity_sentiment",
            "support_keywords": [
                "soft landing",
                "ai euphoria",
                "retail frenzy",
                "valuation stretch",
                "risk-on",
                "melt-up",
            ],
            "contradict_keywords": [
                "earnings beat broadly",
                "productivity boom confirmed",
                "broad profit growth",
            ],
            "money_keywords": ["sp500", "nasdaq", "vix", "credit spread", "earnings"],
        },
        {
            "hypothesis_id": "NAR-004",
            "title": "Crypto leverage cycle vulnerable to forced unwind",
            "category": "crypto_leverage",
            "support_keywords": [
                "open interest spike",
                "liquidation",
                "funding rate",
                "overleveraged",
                "perp basis",
                "long squeeze",
            ],
            "contradict_keywords": [
                "deleveraging complete",
                "funding normalized",
                "spot led rally",
            ],
            "money_keywords": ["btc", "bitcoin", "eth", "ethereum", "stablecoin", "exchange outflow"],
        },
    ]


def _ensure_hypotheses(path: Path, force_template: bool) -> tuple[list[dict[str, Any]], str]:
    defaults = _default_hypotheses()
    if force_template or not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(defaults, indent=2) + "\n", encoding="utf-8")
        return defaults, "written"

    payload = _read_json(path, [])
    if not isinstance(payload, list):
        payload = []
    rows = [row for row in payload if isinstance(row, dict)]
    if rows:
        return rows, "existing"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(defaults, indent=2) + "\n", encoding="utf-8")
    return defaults, "updated"


def _normalize_item(row: dict[str, Any], source_type: str) -> dict[str, Any]:
    title = str(row.get("title") or row.get("event") or row.get("name") or "").strip()
    summary = str(row.get("summary") or row.get("description") or row.get("note") or "").strip()
    link = str(row.get("link") or row.get("url") or row.get("source_url") or "").strip()
    published = str(row.get("published") or row.get("occurred_at") or row.get("timestamp") or "").strip()
    return {
        "source_type": source_type,
        "source": str(row.get("source") or row.get("source_name") or source_type),
        "title": title,
        "summary": summary,
        "link": link,
        "published": published,
        "text": f"{title} {summary}".strip(),
        "text_lower": f"{title} {summary}".lower(),
    }


def _collect_items(
    social_payload: dict[str, Any],
    prediction_ingest_payload: dict[str, Any],
    world_watch_payload: dict[str, Any],
    backtest_payload: dict[str, Any],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []

    social_rows = social_payload.get("top_items")
    if isinstance(social_rows, list):
        for row in social_rows[:100]:
            if isinstance(row, dict):
                out.append(_normalize_item(row, "social"))

    headline_rows = prediction_ingest_payload.get("headlines")
    if isinstance(headline_rows, list):
        for row in headline_rows[:120]:
            if isinstance(row, dict):
                out.append(_normalize_item(row, "news"))

    world_rows = world_watch_payload.get("top_alerts")
    if isinstance(world_rows, list):
        for row in world_rows[:80]:
            if isinstance(row, dict):
                out.append(_normalize_item(row, "world_watch"))

    setup_rows = backtest_payload.get("setups")
    if isinstance(setup_rows, list):
        for row in setup_rows[:50]:
            if not isinstance(row, dict):
                continue
            out.append(
                {
                    "source_type": "backtest",
                    "source": str(row.get("strategy_name") or "backtest"),
                    "title": f"{row.get('symbol')} {row.get('strategy_name')}",
                    "summary": f"priority={row.get('priority')} signal={row.get('signal_score')}",
                    "link": "",
                    "published": "",
                    "text": f"{row.get('symbol')} {row.get('strategy_name')} {row.get('protocol')}",
                    "text_lower": (
                        f"{row.get('symbol')} {row.get('strategy_name')} {row.get('protocol')}"
                    ).lower(),
                }
            )

    return [row for row in out if str(row.get("text") or "").strip()]


def _keyword_hits(text_lower: str, keywords: list[str]) -> list[str]:
    return [kw for kw in keywords if kw and kw in text_lower]


def _status_from_score(score: float, support_events: int, contradict_events: int) -> str:
    if score >= 2.8 and support_events >= 2:
        return "supported"
    if score <= -1.2 and contradict_events >= 1 and support_events <= contradict_events:
        return "contradicted"
    return "unverified"


def _evaluate_hypotheses(hypotheses: list[dict[str, Any]], items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for hypothesis in hypotheses:
        hyp_id = str(hypothesis.get("hypothesis_id") or "").strip() or "NAR-UNKNOWN"
        title = str(hypothesis.get("title") or "Untitled narrative").strip()
        category = str(hypothesis.get("category") or "general").strip()
        support_keywords = [
            str(v).strip().lower() for v in (hypothesis.get("support_keywords") or []) if str(v).strip()
        ]
        contradict_keywords = [
            str(v).strip().lower() for v in (hypothesis.get("contradict_keywords") or []) if str(v).strip()
        ]
        money_keywords = [
            str(v).strip().lower() for v in (hypothesis.get("money_keywords") or []) if str(v).strip()
        ]

        support_events = 0
        contradict_events = 0
        support_hits_total = 0
        contradict_hits_total = 0
        money_hits_total = 0
        source_types: set[str] = set()
        evidence_rows: list[dict[str, Any]] = []
        score = 0.0

        for item in items:
            text_lower = str(item.get("text_lower") or "")
            support_hits = _keyword_hits(text_lower, support_keywords)
            contradict_hits = _keyword_hits(text_lower, contradict_keywords)
            money_hits = _keyword_hits(text_lower, money_keywords)
            if not (support_hits or contradict_hits or money_hits):
                continue

            support_events += 1 if support_hits else 0
            contradict_events += 1 if contradict_hits else 0
            support_hits_total += len(support_hits)
            contradict_hits_total += len(contradict_hits)
            money_hits_total += len(money_hits)
            source_types.add(str(item.get("source_type") or "unknown"))

            item_score = len(support_hits) * 1.0 + len(money_hits) * 0.35 - len(contradict_hits) * 1.15
            score += item_score

            if len(evidence_rows) < 8:
                evidence_rows.append(
                    {
                        "source_type": item.get("source_type"),
                        "source": item.get("source"),
                        "title": item.get("title"),
                        "link": item.get("link"),
                        "published": item.get("published"),
                        "support_hits": support_hits,
                        "contradict_hits": contradict_hits,
                        "money_hits": money_hits,
                        "item_score": round(item_score, 3),
                    }
                )

        status = _status_from_score(score, support_events=support_events, contradict_events=contradict_events)
        confidence = min(0.99, max(0.05, 0.2 + abs(score) * 0.08 + len(source_types) * 0.07))
        rows.append(
            {
                "hypothesis_id": hyp_id,
                "title": title,
                "category": category,
                "status": status,
                "score": round(score, 3),
                "confidence": round(confidence, 3),
                "support_events": support_events,
                "contradict_events": contradict_events,
                "support_hits_total": support_hits_total,
                "contradict_hits_total": contradict_hits_total,
                "money_hits_total": money_hits_total,
                "sources_touched": sorted(source_types),
                "evidence_count": len(evidence_rows),
                "evidence": evidence_rows,
                "manual_approval_required": True,
            }
        )

    rows.sort(key=lambda row: (row.get("status") == "supported", row.get("score", 0)), reverse=True)
    return rows


def _write_outputs(
    hypotheses_status: str,
    rows: list[dict[str, Any]],
    evidence_count: int,
    source_paths: dict[str, str],
    warnings: list[str],
) -> tuple[Path, Path]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    TOOL_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _now().strftime("%Y%m%d-%H%M%S")
    md_path = OUTPUT_DIR / f"narrative_tracker_{stamp}.md"
    latest_md = OUTPUT_DIR / "narrative_tracker_latest.md"
    json_path = TOOL_DIR / f"narrative_tracker_{stamp}.json"

    supported_count = sum(1 for row in rows if str(row.get("status")) == "supported")
    contradicted_count = sum(1 for row in rows if str(row.get("status")) == "contradicted")
    unverified_count = sum(1 for row in rows if str(row.get("status")) == "unverified")

    lines = [
        "# Narrative Tracker",
        "",
        f"Generated (UTC): {_now_iso()}",
        f"Hypotheses path: {HYPOTHESES_PATH} ({hypotheses_status})",
        "",
        "## Summary",
        f"- Evidence items scanned: {evidence_count}",
        f"- Hypotheses tracked: {len(rows)}",
        f"- Supported: {supported_count}",
        f"- Unverified: {unverified_count}",
        f"- Contradicted: {contradicted_count}",
        "",
        "## Hypothesis Board",
    ]
    if not rows:
        lines.append("- No hypotheses loaded.")
    for idx, row in enumerate(rows, start=1):
        lines.extend(
            [
                f"{idx}. {row.get('title')} ({row.get('hypothesis_id')})",
                (
                    "   - "
                    f"status={row.get('status')} score={row.get('score')} confidence={row.get('confidence')} "
                    f"money_hits={row.get('money_hits_total')} evidence={row.get('evidence_count')}"
                ),
            ]
        )
        evidence = row.get("evidence") if isinstance(row.get("evidence"), list) else []
        for evidence_row in evidence[:2]:
            if not isinstance(evidence_row, dict):
                continue
            lines.append(
                f"   - evidence: [{evidence_row.get('source_type')}] {evidence_row.get('title')}"
            )

    lines.extend(["", "## Source Payloads"])
    for key in ["social", "prediction_ingest", "world_watch", "market_backtest"]:
        lines.append(f"- {key}: {source_paths.get(key, 'none')}")

    if warnings:
        lines.extend(["", "## Warnings"])
        for warning in warnings:
            lines.append(f"- {warning}")

    lines.extend(
        [
            "",
            "## Governance Notes",
            "- Narrative tracking is evidence-first and can keep claims as UNVERIFIED.",
            "- Do not treat any hypothesis as fact without independent confirmation.",
            "- No autonomous execution or public claims are made from this module.",
            "",
        ]
    )

    report = "\n".join(lines)
    md_path.write_text(report, encoding="utf-8")
    latest_md.write_text(report, encoding="utf-8")

    payload = {
        "generated_at": _now_iso(),
        "hypotheses_path": str(HYPOTHESES_PATH),
        "hypotheses_status": hypotheses_status,
        "evidence_count": evidence_count,
        "hypothesis_count": len(rows),
        "supported_count": supported_count,
        "unverified_count": unverified_count,
        "contradicted_count": contradicted_count,
        "rows": rows,
        "source_paths": source_paths,
        "warnings": warnings,
        "latest_markdown": str(latest_md),
    }
    json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return md_path, json_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Track high-uncertainty narratives with evidence states.")
    parser.add_argument("--force-template", action="store_true", help="Rewrite narrative hypotheses template")
    args = parser.parse_args(argv)

    hypotheses, hypotheses_status = _ensure_hypotheses(HYPOTHESES_PATH, force_template=args.force_template)

    social_payload, social_path = _load_tool_payload("social_research_ingest_*.json")
    prediction_ingest_payload, prediction_ingest_path = _load_tool_payload("prediction_ingest_*.json")
    world_watch_payload, world_watch_path = _load_tool_payload("world_watch_20*.json")
    backtest_payload, backtest_path = _load_tool_payload("market_backtest_queue_*.json")

    warnings: list[str] = []
    if not social_path:
        warnings.append("No social_research_ingest payload found in memory/tool.")
    if not prediction_ingest_path:
        warnings.append("No prediction_ingest payload found in memory/tool.")
    if not world_watch_path:
        warnings.append("No world_watch payload found in memory/tool.")
    if not backtest_path:
        warnings.append("No market_backtest_queue payload found in memory/tool.")

    items = _collect_items(
        social_payload=social_payload,
        prediction_ingest_payload=prediction_ingest_payload,
        world_watch_payload=world_watch_payload,
        backtest_payload=backtest_payload,
    )
    rows = _evaluate_hypotheses(hypotheses, items)

    source_paths = {
        "social": str(social_path) if social_path else "none",
        "prediction_ingest": str(prediction_ingest_path) if prediction_ingest_path else "none",
        "world_watch": str(world_watch_path) if world_watch_path else "none",
        "market_backtest": str(backtest_path) if backtest_path else "none",
    }
    md_path, json_path = _write_outputs(
        hypotheses_status=hypotheses_status,
        rows=rows,
        evidence_count=len(items),
        source_paths=source_paths,
        warnings=warnings,
    )

    print(f"Narrative tracker written: {md_path}")
    print(f"Narrative tracker latest: {OUTPUT_DIR / 'narrative_tracker_latest.md'}")
    print(f"Tool payload written: {json_path}")
    print(f"Hypotheses tracked: {len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
