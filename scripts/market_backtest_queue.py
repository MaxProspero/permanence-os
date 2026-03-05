#!/usr/bin/env python3
"""
Build a market backtest queue from article/video/news evidence.

Advisory only: this script does not place trades.
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
WATCHLIST_PATH = Path(
    os.getenv("PERMANENCE_MARKET_BACKTEST_WATCHLIST_PATH", str(WORKING_DIR / "market_backtest_watchlist.json"))
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


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _priority_label(score: float) -> str:
    if score >= 80:
        return "HIGH"
    if score >= 45:
        return "MEDIUM"
    return "LOW"


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


def _default_watchlist() -> dict[str, Any]:
    return {
        "assets": [
            {
                "symbol": "XAUUSD",
                "keywords": ["xauusd", "gold", "bullion"],
                "timeframes": ["M15", "H1", "H4"],
            },
            {
                "symbol": "BTCUSD",
                "keywords": ["btc", "bitcoin", "btcusd"],
                "timeframes": ["M15", "H1", "H4", "D1"],
            },
            {
                "symbol": "SPY",
                "keywords": ["spy", "s&p", "sp500", "equities"],
                "timeframes": ["H1", "H4", "D1"],
            },
            {
                "symbol": "NVDA",
                "keywords": ["nvda", "nvidia", "semiconductor"],
                "timeframes": ["H1", "H4", "D1"],
            },
        ],
        "strategy_lenses": [
            {
                "strategy_id": "liquidity_sweep_fvg",
                "name": "Liquidity Sweep + FVG (ICC/SMC)",
                "keywords": [
                    "liquidity",
                    "liquidity sweep",
                    "fvg",
                    "fair value gap",
                    "bos",
                    "choch",
                    "order block",
                    "displacement",
                    "market structure",
                ],
                "lookback_days": 365,
                "min_samples": 80,
            },
            {
                "strategy_id": "event_volatility_breakout",
                "name": "Event Volatility Breakout",
                "keywords": [
                    "cpi",
                    "fomc",
                    "fed",
                    "nfp",
                    "rate decision",
                    "volatility",
                    "breakout",
                    "macro shock",
                ],
                "lookback_days": 730,
                "min_samples": 60,
            },
            {
                "strategy_id": "trend_pullback",
                "name": "Trend Pullback Continuation",
                "keywords": [
                    "trend",
                    "pullback",
                    "continuation",
                    "higher high",
                    "higher low",
                    "moving average",
                ],
                "lookback_days": 540,
                "min_samples": 100,
            },
        ],
        "money_keywords": [
            "yield",
            "rates",
            "dollar",
            "liquidity",
            "funding",
            "treasury",
            "oil",
            "gold",
            "bitcoin",
        ],
        "min_signal_score": 2.0,
        "top_setups_limit": 12,
        "updated_at": _now_iso(),
    }


def _ensure_watchlist(path: Path, force_template: bool) -> tuple[dict[str, Any], str]:
    defaults = _default_watchlist()
    if force_template or not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(defaults, indent=2) + "\n", encoding="utf-8")
        return defaults, "written"

    payload = _read_json(path, {})
    if not isinstance(payload, dict):
        payload = {}
    merged = dict(defaults)
    merged.update(payload)
    if not isinstance(merged.get("assets"), list):
        merged["assets"] = defaults["assets"]
    if not isinstance(merged.get("strategy_lenses"), list):
        merged["strategy_lenses"] = defaults["strategy_lenses"]
    if not isinstance(merged.get("money_keywords"), list):
        merged["money_keywords"] = defaults["money_keywords"]
    merged["min_signal_score"] = _safe_float(merged.get("min_signal_score"), 2.0)
    merged["top_setups_limit"] = max(1, min(50, _safe_int(merged.get("top_setups_limit"), 12)))
    if merged != payload:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(merged, indent=2) + "\n", encoding="utf-8")
        return merged, "updated"
    return merged, "existing"


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
    }


def _collect_evidence(
    social_payload: dict[str, Any],
    prediction_ingest_payload: dict[str, Any],
    world_watch_payload: dict[str, Any],
    prediction_lab_payload: dict[str, Any],
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []

    social_rows = social_payload.get("top_items")
    if isinstance(social_rows, list):
        for row in social_rows[:80]:
            if isinstance(row, dict):
                items.append(_normalize_item(row, "social"))

    headline_rows = prediction_ingest_payload.get("headlines")
    if isinstance(headline_rows, list):
        for row in headline_rows[:120]:
            if isinstance(row, dict):
                items.append(_normalize_item(row, "news"))

    watch_rows = world_watch_payload.get("top_alerts")
    if isinstance(watch_rows, list):
        for row in watch_rows[:80]:
            if isinstance(row, dict):
                items.append(_normalize_item(row, "world_watch"))

    lab_rows = prediction_lab_payload.get("results")
    if isinstance(lab_rows, list):
        for row in lab_rows[:80]:
            if not isinstance(row, dict):
                continue
            items.append(
                {
                    "source_type": "prediction_lab",
                    "source": str(row.get("market") or "prediction_lab"),
                    "title": str(row.get("title") or "").strip(),
                    "summary": (
                        f"decision={row.get('decision')} edge={row.get('edge')} "
                        f"ev_per_1usd={row.get('expected_pnl_per_1usd')}"
                    ),
                    "link": "",
                    "published": "",
                }
            )

    out: list[dict[str, Any]] = []
    for row in items:
        text = f"{row.get('title', '')} {row.get('summary', '')}".strip()
        if not text:
            continue
        enriched = dict(row)
        enriched["text"] = text
        enriched["text_lower"] = text.lower()
        out.append(enriched)
    return out


def _keyword_hits(text_lower: str, keywords: list[str]) -> list[str]:
    return [kw for kw in keywords if kw and kw in text_lower]


def _setup_id(symbol: str, strategy_id: str) -> str:
    return hashlib.sha1(f"{symbol}|{strategy_id}".encode("utf-8")).hexdigest()[:12]


def _build_setups(watchlist: dict[str, Any], evidence_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    assets = watchlist.get("assets") if isinstance(watchlist.get("assets"), list) else []
    lenses = watchlist.get("strategy_lenses") if isinstance(watchlist.get("strategy_lenses"), list) else []
    money_keywords = [
        str(v).strip().lower() for v in (watchlist.get("money_keywords") or []) if str(v).strip()
    ]
    min_signal_score = _safe_float(watchlist.get("min_signal_score"), 2.0)

    setups: list[dict[str, Any]] = []
    for asset in assets:
        if not isinstance(asset, dict):
            continue
        symbol = str(asset.get("symbol") or "").strip().upper()
        if not symbol:
            continue
        asset_keywords = [str(v).strip().lower() for v in (asset.get("keywords") or []) if str(v).strip()]
        timeframes = [str(v).strip() for v in (asset.get("timeframes") or []) if str(v).strip()]

        for lens in lenses:
            if not isinstance(lens, dict):
                continue
            strategy_id = str(lens.get("strategy_id") or "").strip().lower()
            strategy_name = str(lens.get("name") or strategy_id or "strategy").strip()
            if not strategy_id:
                continue
            strategy_keywords = [str(v).strip().lower() for v in (lens.get("keywords") or []) if str(v).strip()]
            lookback_days = max(30, _safe_int(lens.get("lookback_days"), 365))
            min_samples = max(20, _safe_int(lens.get("min_samples"), 60))

            combo_hits = 0
            asset_hits_count = 0
            strategy_hits_count = 0
            money_hits_count = 0
            evidence: list[dict[str, Any]] = []
            sources: set[str] = set()

            for item in evidence_items:
                text_lower = str(item.get("text_lower") or "")
                if not text_lower:
                    continue
                asset_hits = _keyword_hits(text_lower, asset_keywords)
                strategy_hits = _keyword_hits(text_lower, strategy_keywords)
                money_hits = _keyword_hits(text_lower, money_keywords)
                if not (asset_hits or strategy_hits):
                    continue

                asset_hits_count += 1 if asset_hits else 0
                strategy_hits_count += 1 if strategy_hits else 0
                money_hits_count += len(money_hits)
                if asset_hits and strategy_hits:
                    combo_hits += 1
                sources.add(str(item.get("source_type") or "unknown"))

                if len(evidence) < 8 and (asset_hits or strategy_hits):
                    evidence.append(
                        {
                            "source_type": item.get("source_type"),
                            "source": item.get("source"),
                            "title": item.get("title"),
                            "link": item.get("link"),
                            "published": item.get("published"),
                            "matched_asset": asset_hits,
                            "matched_strategy": strategy_hits,
                            "money_hits": money_hits,
                        }
                    )

            signal_score = (
                combo_hits * 1.25
                + asset_hits_count * 0.25
                + strategy_hits_count * 0.15
                + len(sources) * 0.20
                + min(2.0, money_hits_count * 0.10)
            )
            if signal_score < min_signal_score:
                continue

            priority_score = min(100.0, round(signal_score * 18.0, 2))
            setups.append(
                {
                    "setup_id": _setup_id(symbol, strategy_id),
                    "symbol": symbol,
                    "strategy_id": strategy_id,
                    "strategy_name": strategy_name,
                    "priority": _priority_label(priority_score),
                    "priority_score": priority_score,
                    "signal_score": round(signal_score, 3),
                    "timeframes": timeframes,
                    "lookback_days": lookback_days,
                    "min_samples": min_samples,
                    "evidence_count": len(evidence),
                    "sources_touched": sorted(sources),
                    "manual_approval_required": True,
                    "status": "queued_for_manual_backtest",
                    "protocol": [
                        "Define one falsifiable entry/exit rule set before touching results.",
                        "Backtest with full transaction-cost assumptions and fixed risk cap.",
                        "Run out-of-sample validation before any paper trade.",
                    ],
                    "evidence": evidence,
                }
            )

    setups.sort(key=lambda row: row.get("priority_score", 0), reverse=True)
    top_limit = max(1, min(50, _safe_int(watchlist.get("top_setups_limit"), 12)))
    return setups[:top_limit]


def _write_outputs(
    watchlist_path: Path,
    watchlist_status: str,
    setups: list[dict[str, Any]],
    evidence_count: int,
    source_paths: dict[str, str],
    warnings: list[str],
) -> tuple[Path, Path]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    TOOL_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _now().strftime("%Y%m%d-%H%M%S")
    md_path = OUTPUT_DIR / f"market_backtest_queue_{stamp}.md"
    latest_md = OUTPUT_DIR / "market_backtest_queue_latest.md"
    json_path = TOOL_DIR / f"market_backtest_queue_{stamp}.json"

    high_count = sum(1 for row in setups if str(row.get("priority")) == "HIGH")
    lines = [
        "# Market Backtest Queue",
        "",
        f"Generated (UTC): {_now_iso()}",
        f"Watchlist path: {watchlist_path} ({watchlist_status})",
        "",
        "## Summary",
        f"- Evidence items scanned: {evidence_count}",
        f"- Backtest setups queued: {len(setups)}",
        f"- High-priority setups: {high_count}",
        "",
        "## Ranked Setups",
    ]
    if not setups:
        lines.append("- No setups met current signal threshold.")
    for idx, row in enumerate(setups, start=1):
        lines.extend(
            [
                f"{idx}. {row.get('symbol')} | {row.get('strategy_name')}",
                (
                    "   - "
                    f"priority={row.get('priority')} score={row.get('priority_score')} "
                    f"signal={row.get('signal_score')} evidence={row.get('evidence_count')}"
                ),
                (
                    "   - "
                    f"timeframes={','.join(row.get('timeframes') or []) or '-'} | "
                    f"lookback_days={row.get('lookback_days')} | min_samples={row.get('min_samples')}"
                ),
            ]
        )
        evidence = row.get("evidence") if isinstance(row.get("evidence"), list) else []
        for evidence_row in evidence[:3]:
            if not isinstance(evidence_row, dict):
                continue
            lines.append(
                "   - evidence: "
                f"[{evidence_row.get('source_type')}] {evidence_row.get('title')}"
            )

    lines.extend(["", "## Source Payloads"])
    for key in ["social", "prediction_ingest", "world_watch", "prediction_lab"]:
        lines.append(f"- {key}: {source_paths.get(key, 'none')}")

    if warnings:
        lines.extend(["", "## Warnings"])
        for warning in warnings:
            lines.append(f"- {warning}")

    lines.extend(
        [
            "",
            "## Governance Notes",
            "- Research + backtest planning only; no autonomous order execution.",
            "- Human review is mandatory before paper-trading or live deployment.",
            "",
        ]
    )

    report = "\n".join(lines)
    md_path.write_text(report, encoding="utf-8")
    latest_md.write_text(report, encoding="utf-8")

    payload = {
        "generated_at": _now_iso(),
        "watchlist_path": str(watchlist_path),
        "watchlist_status": watchlist_status,
        "evidence_count": evidence_count,
        "setup_count": len(setups),
        "high_priority_count": high_count,
        "setups": setups,
        "source_paths": source_paths,
        "warnings": warnings,
        "latest_markdown": str(latest_md),
    }
    json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return md_path, json_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build market backtest queue from multi-source evidence.")
    parser.add_argument("--force-template", action="store_true", help="Rewrite watchlist template")
    args = parser.parse_args(argv)

    watchlist, watchlist_status = _ensure_watchlist(WATCHLIST_PATH, force_template=args.force_template)

    social_payload, social_path = _load_tool_payload("social_research_ingest_*.json")
    prediction_ingest_payload, prediction_ingest_path = _load_tool_payload("prediction_ingest_*.json")
    world_watch_payload, world_watch_path = _load_tool_payload("world_watch_20*.json")
    prediction_lab_payload, prediction_lab_path = _load_tool_payload("prediction_lab_*.json")

    warnings: list[str] = []
    if not social_path:
        warnings.append("No social_research_ingest payload found in memory/tool.")
    if not prediction_ingest_path:
        warnings.append("No prediction_ingest payload found in memory/tool.")
    if not world_watch_path:
        warnings.append("No world_watch payload found in memory/tool.")
    if not prediction_lab_path:
        warnings.append("No prediction_lab payload found in memory/tool.")

    evidence_items = _collect_evidence(
        social_payload,
        prediction_ingest_payload,
        world_watch_payload,
        prediction_lab_payload,
    )
    setups = _build_setups(watchlist, evidence_items)

    source_paths = {
        "social": str(social_path) if social_path else "none",
        "prediction_ingest": str(prediction_ingest_path) if prediction_ingest_path else "none",
        "world_watch": str(world_watch_path) if world_watch_path else "none",
        "prediction_lab": str(prediction_lab_path) if prediction_lab_path else "none",
    }
    md_path, json_path = _write_outputs(
        watchlist_path=WATCHLIST_PATH,
        watchlist_status=watchlist_status,
        setups=setups,
        evidence_count=len(evidence_items),
        source_paths=source_paths,
        warnings=warnings,
    )

    print(f"Market backtest queue written: {md_path}")
    print(f"Market backtest latest: {OUTPUT_DIR / 'market_backtest_queue_latest.md'}")
    print(f"Tool payload written: {json_path}")
    print(f"Backtest setups queued: {len(setups)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
