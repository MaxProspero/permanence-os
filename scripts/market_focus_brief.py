#!/usr/bin/env python3
"""
Generate a compact market focus brief from the latest world-watch payload.
"""

from __future__ import annotations

import json
import os
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import requests

BASE_DIR = Path(__file__).resolve().parents[1]
WORKING_DIR = Path(os.getenv("PERMANENCE_WORKING_DIR", str(BASE_DIR / "memory" / "working")))
OUTPUT_DIR = Path(os.getenv("PERMANENCE_OUTPUT_DIR", str(BASE_DIR / "outputs")))
TOOL_DIR = Path(os.getenv("PERMANENCE_TOOL_DIR", str(BASE_DIR / "memory" / "tool")))
SOURCES_PATH = Path(
    os.getenv("PERMANENCE_WORLD_WATCH_SOURCES_PATH", str(WORKING_DIR / "world_watch_sources.json"))
)
TIMEOUT_SECONDS = int(os.getenv("PERMANENCE_MARKET_BRIEF_TIMEOUT", "10"))

CORE_SYMBOL_FALLBACK = ["SPY", "QQQ", "AAPL", "MSFT", "NVDA", "AMD", "PLTR", "BTC", "ETH"]
MARKET_CATEGORIES = {
    "market_stress",
    "market_volatility",
    "market_index",
    "equity_watch",
    "crypto_market",
    "crypto_market_stress",
    "fx_market",
}


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


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _extract_symbol(title: str) -> str:
    token = str(title or "").upper()
    for match in re.findall(r"\(([A-Z0-9:._/-]{1,16})\)", token):
        candidate = match.replace(".US", "").strip()
        if candidate:
            return candidate
    return ""


def _extract_daily_weekly(summary: str) -> tuple[float | None, float | None]:
    text = str(summary or "")
    daily_match = re.search(r"daily\s*([+-]?\d+(?:\.\d+)?)%", text, re.IGNORECASE)
    weekly_match = re.search(r"5-day\s*([+-]?\d+(?:\.\d+)?)%", text, re.IGNORECASE)
    daily = _safe_float(daily_match.group(1), 0.0) if daily_match else None
    weekly = _safe_float(weekly_match.group(1), 0.0) if weekly_match else None
    return daily, weekly


def _load_core_symbols() -> list[str]:
    payload = _read_json(SOURCES_PATH, {})
    if not isinstance(payload, dict):
        payload = {}
    data_sources = payload.get("data_sources") if isinstance(payload.get("data_sources"), list) else []
    always_include: list[str] = []
    for row in data_sources:
        if not isinstance(row, dict):
            continue
        if str(row.get("type") or "").strip().lower() != "stooq_equity_watchlist":
            continue
        vals = row.get("always_include_symbols")
        if not isinstance(vals, list):
            continue
        for token in vals:
            symbol = str(token).strip().upper().replace(".US", "")
            if symbol and symbol not in always_include:
                always_include.append(symbol)
    if always_include:
        return always_include
    return list(CORE_SYMBOL_FALLBACK)


def _priority_rank(row: dict[str, Any]) -> float:
    category = str(row.get("category") or "").strip().lower()
    score = _safe_float(row.get("severity_score"), 0.0)
    bonus = {
        "market_stress": 24.0,
        "market_volatility": 20.0,
        "equity_watch": 14.0,
        "crypto_market_stress": 18.0,
        "crypto_market": 12.0,
        "market_index": 10.0,
        "fx_market": 8.0,
    }.get(category, 0.0)
    return score + bonus


def _collect_priority_events(events: list[dict[str, Any]], limit: int = 8) -> list[dict[str, Any]]:
    rows = [row for row in events if str(row.get("category") or "").strip().lower() in MARKET_CATEGORIES]
    rows.sort(key=_priority_rank, reverse=True)
    return rows[: max(1, int(limit))]


def _watchlist_status(daily: float | None, weekly: float | None) -> str:
    d = abs(daily) if daily is not None else 0.0
    w = abs(weekly) if weekly is not None else 0.0
    if d >= 3.0 or w >= 8.0:
        return "ALERT"
    if d >= 1.5 or w >= 4.0:
        return "WATCH"
    return "QUIET"


def _build_core_watchlist(events: list[dict[str, Any]], core_symbols: list[str]) -> list[dict[str, Any]]:
    by_symbol: dict[str, dict[str, Any]] = {}
    for row in events:
        if str(row.get("category") or "").strip().lower() != "equity_watch":
            continue
        symbol = _extract_symbol(str(row.get("title") or ""))
        if not symbol:
            continue
        existing = by_symbol.get(symbol)
        if existing is None or _safe_float(row.get("severity_score"), 0.0) > _safe_float(existing.get("severity_score"), 0.0):
            by_symbol[symbol] = row

    out: list[dict[str, Any]] = []
    for symbol in core_symbols:
        row = by_symbol.get(symbol)
        if row is None:
            out.append(
                {
                    "symbol": symbol,
                    "status": "QUIET",
                    "daily_pct": None,
                    "weekly_pct": None,
                    "severity_score": 0.0,
                    "title": "No major move over configured threshold.",
                }
            )
            continue
        daily, weekly = _extract_daily_weekly(str(row.get("summary") or ""))
        out.append(
            {
                "symbol": symbol,
                "status": _watchlist_status(daily, weekly),
                "daily_pct": daily,
                "weekly_pct": weekly,
                "severity_score": _safe_float(row.get("severity_score"), 0.0),
                "title": str(row.get("title") or ""),
            }
        )
    return out


def _fetch_polygon_xau_signal() -> dict[str, Any] | None:
    key = str(os.getenv("POLYGON_API_KEY", "")).strip()
    if not key:
        return None
    end = date.today()
    start = end - timedelta(days=14)
    url = f"https://api.polygon.io/v2/aggs/ticker/C:XAUUSD/range/1/day/{start}/{end}"
    try:
        response = requests.get(
            url,
            timeout=TIMEOUT_SECONDS,
            params={"adjusted": "true", "sort": "asc", "limit": "100", "apiKey": key},
            headers={"User-Agent": "permanence-os-market-focus-brief"},
        )
        response.raise_for_status()
        payload = response.json()
    except Exception:
        return None
    rows = payload.get("results") if isinstance(payload, dict) else []
    if not isinstance(rows, list) or len(rows) < 2:
        return None

    latest = rows[-1]
    previous = rows[-2]
    week_ref = rows[-6] if len(rows) >= 6 else rows[0]

    close = _safe_float(latest.get("c"), 0.0)
    prev_close = _safe_float(previous.get("c"), 0.0)
    week_close = _safe_float(week_ref.get("c"), 0.0)
    if close <= 0.0:
        return None

    daily = ((close - prev_close) / prev_close * 100.0) if prev_close else 0.0
    weekly = ((close - week_close) / week_close * 100.0) if week_close else 0.0
    score = 30.0 + min(48.0, abs(daily) * 10.0 + abs(weekly) * 3.0)
    if abs(daily) >= 1.0:
        score += 8.0
    if abs(weekly) >= 2.0:
        score += 8.0
    ts_ms = int(_safe_float(latest.get("t"), 0.0))
    occurred = datetime.fromtimestamp(ts_ms / 1000.0, timezone.utc).isoformat() if ts_ms > 0 else _now_iso()
    status = "ALERT" if abs(daily) >= 1.0 or abs(weekly) >= 2.0 else ("WATCH" if abs(daily) >= 0.5 else "QUIET")
    return {
        "event_id": "polygon:C:XAUUSD",
        "category": "fx_market",
        "title": f"XAUUSD {daily:+.2f}% day ({close:,.2f})",
        "summary": f"XAUUSD daily {daily:+.2f}% and 5-day {weekly:+.2f}% via Polygon.",
        "severity_score": round(score, 2),
        "severity_level": "high" if score >= 70 else ("medium" if score >= 45 else "low"),
        "occurred_at": occurred,
        "region": "Global FX/Metals",
        "source_type": "polygon_forex",
        "status": status,
        "daily_pct": round(daily, 3),
        "weekly_pct": round(weekly, 3),
        "price": round(close, 4),
    }


def _prediction_monitors(market_monitors: list[dict[str, Any]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for row in market_monitors:
        if not isinstance(row, dict):
            continue
        if str(row.get("type") or "").strip().lower() != "prediction_market":
            continue
        name = str(row.get("name") or "").strip()
        url = str(row.get("url") or "").strip()
        if name and url:
            rows.append({"name": name, "url": url})
    return rows


def _fmt_pct(value: float | None) -> str:
    if value is None:
        return "-"
    return f"{value:+.2f}%"


def _write_outputs(
    *,
    source_path: Path | None,
    priority_events: list[dict[str, Any]],
    core_watchlist: list[dict[str, Any]],
    prediction_rows: list[dict[str, str]],
    xau_signal: dict[str, Any] | None,
) -> tuple[Path, Path]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    TOOL_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _now().strftime("%Y%m%d-%H%M%S")
    md_path = OUTPUT_DIR / f"market_focus_brief_{stamp}.md"
    latest_md = OUTPUT_DIR / "market_focus_brief_latest.md"
    json_path = TOOL_DIR / f"market_focus_brief_{stamp}.json"

    lines = [
        "# Market Focus Brief",
        "",
        f"Generated (UTC): {_now_iso()}",
        f"Source payload: {source_path if source_path else 'none'}",
        "",
        "## Priority Now",
    ]
    if not priority_events:
        lines.append("- No market events available yet. Run `python cli.py world-watch` first.")
    for idx, row in enumerate(priority_events, start=1):
        lines.append(
            f"{idx}. {row.get('title')} [{row.get('category')}] S{_safe_float(row.get('severity_score'), 0.0):.0f}"
        )
        summary = str(row.get("summary") or "").strip()
        if summary:
            lines.append(f"   - {summary[:200]}")

    lines.extend(["", "## Core Watchlist"])
    for row in core_watchlist:
        lines.append(
            f"- {row.get('symbol')}: {row.get('status')} | daily={_fmt_pct(row.get('daily_pct'))} | "
            f"5d={_fmt_pct(row.get('weekly_pct'))} | S{_safe_float(row.get('severity_score'), 0.0):.0f}"
        )

    lines.extend(
        [
            "",
            "## Trigger Ladder",
            "- Equities: ALERT when daily move >= 3% or 5-day move >= 8%.",
            "- Volatility: ALERT when VIX >= 25, WATCH at 20-25.",
            "- Crypto: ALERT when top-asset 24h swings exceed +/-8%.",
            "- FX/Gold: ALERT when XAUUSD daily >= 1.0% or 5-day >= 2.0%.",
        ]
    )

    lines.extend(["", "## XAUUSD Pulse"])
    if not xau_signal:
        lines.append("- No live XAUUSD signal (add Polygon key or retry).")
    else:
        lines.append(
            f"- XAUUSD: {xau_signal.get('status')} | daily={_fmt_pct(xau_signal.get('daily_pct'))} | "
            f"5d={_fmt_pct(xau_signal.get('weekly_pct'))} | price=${_safe_float(xau_signal.get('price'), 0.0):,.2f}"
        )

    lines.extend(["", "## Prediction Markets"])
    if not prediction_rows:
        lines.append("- No prediction-market monitors configured.")
    for row in prediction_rows:
        lines.append(f"- {row.get('name')}")

    lines.extend(
        [
            "",
            "## Governance",
            "- Research/advisory only. No auto-trade execution.",
            "- Manual approval remains required for live capital deployment.",
            "",
        ]
    )

    report = "\n".join(lines)
    md_path.write_text(report, encoding="utf-8")
    latest_md.write_text(report, encoding="utf-8")

    notification_cards = [
        {
            "headline": str(row.get("title") or "Signal")[:120],
            "category": str(row.get("category") or "market"),
            "score": round(_safe_float(row.get("severity_score"), 0.0), 2),
            "detail": str(row.get("summary") or "")[:180],
        }
        for row in priority_events[:8]
    ]

    payload = {
        "generated_at": _now_iso(),
        "source_path": str(source_path) if source_path else "none",
        "priority_count": len(priority_events),
        "priority_events": priority_events,
        "core_watchlist": core_watchlist,
        "prediction_monitors": prediction_rows,
        "xau_signal": xau_signal or {},
        "trigger_rules": {
            "equity_daily_alert_pct": 3.0,
            "equity_weekly_alert_pct": 8.0,
            "equity_daily_watch_pct": 1.5,
            "equity_weekly_watch_pct": 4.0,
            "vix_watch": 20.0,
            "vix_alert": 25.0,
            "xau_daily_alert_pct": 1.0,
            "xau_weekly_alert_pct": 2.0,
        },
        "notification_cards": notification_cards,
        "latest_markdown": str(latest_md),
    }
    json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return md_path, json_path


def main() -> int:
    source_path = _latest_tool("world_watch_20*.json")
    source = _read_json(source_path, {}) if source_path else {}
    if not isinstance(source, dict):
        source = {}
    events = source.get("top_events") if isinstance(source.get("top_events"), list) else []
    market_monitors = source.get("market_monitors") if isinstance(source.get("market_monitors"), list) else []
    core_symbols = _load_core_symbols()
    filtered_events = [row for row in events if isinstance(row, dict)]
    xau_signal = _fetch_polygon_xau_signal()
    if xau_signal:
        filtered_events.append(xau_signal)
    priority_events = _collect_priority_events(filtered_events, limit=8)
    core_watchlist = _build_core_watchlist(filtered_events, core_symbols)
    prediction_rows = _prediction_monitors([row for row in market_monitors if isinstance(row, dict)])

    md_path, json_path = _write_outputs(
        source_path=source_path,
        priority_events=priority_events,
        core_watchlist=core_watchlist,
        prediction_rows=prediction_rows,
        xau_signal=xau_signal,
    )
    print(f"Market focus brief written: {md_path}")
    print(f"Market focus brief latest: {OUTPUT_DIR / 'market_focus_brief_latest.md'}")
    print(f"Tool payload written: {json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
