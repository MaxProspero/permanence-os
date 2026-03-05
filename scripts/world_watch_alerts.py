#!/usr/bin/env python3
"""
Create and optionally dispatch world-watch alerts to Discord/Telegram.

Dispatch is opt-in (`--send`). Default mode is draft-only.
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

BASE_DIR = Path(__file__).resolve().parents[1]


def _load_local_env() -> None:
    env_path = BASE_DIR / ".env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key or key in os.environ:
            continue
        value = value.strip()
        if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
            value = value[1:-1]
        os.environ[key] = value


_load_local_env()
OUTPUT_DIR = Path(os.getenv("PERMANENCE_OUTPUT_DIR", str(BASE_DIR / "outputs")))
TOOL_DIR = Path(os.getenv("PERMANENCE_TOOL_DIR", str(BASE_DIR / "memory" / "tool")))
TIMEOUT_SECONDS = int(os.getenv("PERMANENCE_WORLD_WATCH_ALERT_TIMEOUT", "10"))

DISCORD_WEBHOOK_ENV = "PERMANENCE_DISCORD_ALERT_WEBHOOK_URL"
TELEGRAM_BOT_TOKEN_ENV = "PERMANENCE_TELEGRAM_BOT_TOKEN"
TELEGRAM_CHAT_ID_ENV = "PERMANENCE_TELEGRAM_CHAT_ID"


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


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _latest_tool(pattern: str) -> Path | None:
    if not TOOL_DIR.exists():
        return None
    rows = sorted(TOOL_DIR.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    return rows[0] if rows else None


def _normalize_focus(payload: dict[str, Any]) -> dict[str, Any]:
    focus = payload.get("alert_focus") if isinstance(payload.get("alert_focus"), dict) else {}
    major_categories = [
        str(row).strip().lower()
        for row in (focus.get("major_categories") or [])
        if str(row).strip()
    ]
    if not major_categories:
        major_categories = [
            "market_stress",
            "market_volatility",
            "market_index",
            "equity_watch",
            "crypto_market",
            "crypto_market_stress",
            "fx_market",
            "weather_local_alert",
            "weather_local",
            "war_conflict",
        ]
    always_include = [
        str(row).strip().lower()
        for row in (focus.get("always_include_categories") or [])
        if str(row).strip()
    ]
    if not always_include:
        always_include = ["market_stress", "market_volatility", "market_index", "crypto_market", "fx_market"]
    headline_keywords = [
        str(row).strip().lower()
        for row in (focus.get("headline_keywords") or [])
        if str(row).strip()
    ]
    if not headline_keywords:
        headline_keywords = ["war", "conflict", "missile", "market crash", "selloff", "volatility", "earthquake"]
    min_major_score = _safe_float(focus.get("min_major_score"), 68.0)
    market_only = str(focus.get("market_only", "false")).strip().lower() in {"1", "true", "yes", "on"}
    return {
        "major_categories": set(major_categories),
        "always_include_categories": set(always_include),
        "headline_keywords": headline_keywords,
        "min_major_score": min_major_score,
        "market_only": market_only,
    }


def _event_rank(row: dict[str, Any], focus: dict[str, Any]) -> float:
    score = _safe_float(row.get("severity_score"), 0.0)
    category = str(row.get("category") or "").strip().lower()
    category_bonus = {
        "war_conflict": 26.0,
        "market_stress": 22.0,
        "market_volatility": 18.0,
        "market_index": 14.0,
        "equity_watch": 14.0,
        "crypto_market": 16.0,
        "crypto_market_stress": 20.0,
        "fx_market": 12.0,
        "weather_local_alert": 18.0,
        "weather_local": 12.0,
        "earthquake": 10.0,
        "humanitarian_report": 8.0,
    }.get(category, 0.0)
    if category == "weather_alert":
        category_bonus -= 20.0
    text = f"{row.get('title') or ''} {row.get('summary') or ''}".lower()
    keyword_hits = sum(1 for kw in focus["headline_keywords"] if kw in text)
    keyword_bonus = min(20.0, keyword_hits * 5.0)
    return score + category_bonus + keyword_bonus


def _select_major_alerts(
    events: list[dict[str, Any]],
    focus: dict[str, Any],
    *,
    max_alerts: int,
    min_score: float,
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    major_categories = focus["major_categories"]
    focus_min = max(float(min_score), _safe_float(focus.get("min_major_score"), min_score))
    market_only = bool(focus.get("market_only"))
    market_categories = {
        "market_stress",
        "market_volatility",
        "market_index",
        "equity_watch",
        "crypto_market",
        "crypto_market_stress",
        "fx_market",
    }
    for row in events:
        if not isinstance(row, dict):
            continue
        score = _safe_float(row.get("severity_score"), 0.0)
        category = str(row.get("category") or "").strip().lower()
        if market_only and category not in market_categories:
            continue
        text = f"{row.get('title') or ''} {row.get('summary') or ''}".lower()
        keyword_match = any(kw in text for kw in focus["headline_keywords"])
        category_min = focus_min
        if category in market_categories:
            category_min = max(30.0, focus_min - 22.0)
        keep = (
            (category in major_categories and score >= category_min)
            or (keyword_match and score >= max(60.0, min_score - 8.0))
            or (score >= 88.0 and category != "weather_alert")
            or (category == "weather_alert" and score >= 95.0 and keyword_match)
        )
        if market_only and category in market_categories:
            keep = keep or score >= max(25.0, category_min - 8.0)
        if keep:
            row_copy = dict(row)
            row_copy["_rank"] = _event_rank(row, focus)
            candidates.append(row_copy)

    candidates.sort(key=lambda item: _safe_float(item.get("_rank"), 0.0), reverse=True)
    selected = candidates[: max(1, int(max_alerts))]

    always_categories = focus["always_include_categories"]
    selected_categories = {str(item.get("category") or "").strip().lower() for item in selected}
    for wanted in always_categories:
        if market_only and wanted not in market_categories:
            continue
        if wanted in selected_categories:
            continue
        fallback_rows = candidates + [dict(row) for row in events if isinstance(row, dict)]
        fallback_rows.sort(key=lambda item: _event_rank(item, focus), reverse=True)
        for row in fallback_rows:
            category = str(row.get("category") or "").strip().lower()
            score = _safe_float(row.get("severity_score"), 0.0)
            min_required = 0.0 if category in market_categories else 40.0
            if category == wanted and score >= min_required:
                row_copy = dict(row)
                row_copy["_rank"] = _event_rank(row_copy, focus)
                if len(selected) < max_alerts:
                    selected.append(row_copy)
                else:
                    protected = focus["always_include_categories"]
                    category_counts: dict[str, int] = {}
                    for existing in selected:
                        existing_category = str(existing.get("category") or "").strip().lower()
                        category_counts[existing_category] = category_counts.get(existing_category, 0) + 1

                    replace_idx = -1
                    replace_rank = 10_000.0

                    for idx, existing in enumerate(selected):
                        existing_category = str(existing.get("category") or "").strip().lower()
                        existing_rank = _safe_float(existing.get("_rank"), 0.0)
                        if existing_category in protected:
                            continue
                        if existing_rank < replace_rank:
                            replace_rank = existing_rank
                            replace_idx = idx

                    if replace_idx < 0:
                        for idx, existing in enumerate(selected):
                            existing_category = str(existing.get("category") or "").strip().lower()
                            existing_rank = _safe_float(existing.get("_rank"), 0.0)
                            if category_counts.get(existing_category, 0) <= 1:
                                continue
                            if existing_rank < replace_rank:
                                replace_rank = existing_rank
                                replace_idx = idx

                    if replace_idx < 0:
                        for idx, existing in enumerate(selected):
                            existing_rank = _safe_float(existing.get("_rank"), 0.0)
                            if existing_rank < replace_rank:
                                replace_rank = existing_rank
                                replace_idx = idx

                    if replace_idx < 0:
                        replace_idx = len(selected) - 1
                    selected[replace_idx] = row_copy
                selected_categories = {str(item.get("category") or "").strip().lower() for item in selected}
                break
    selected.sort(key=lambda item: _safe_float(item.get("_rank"), 0.0), reverse=True)
    for row in selected:
        row.pop("_rank", None)
    return selected[: max(1, int(max_alerts))]


def _build_message(
    alerts: list[dict[str, Any]],
    map_views: list[dict[str, Any]],
    market_monitors: list[dict[str, Any]],
    *,
    include_links: bool = False,
) -> str:
    lines = [
        f"Permanence Market Alerts | {_now().strftime('%Y-%m-%d %H:%M UTC')}",
        f"items: {len(alerts)}",
        "",
    ]
    for idx, row in enumerate(alerts, start=1):
        title = str(row.get("title") or "Alert").strip()
        category = str(row.get("category") or "event").strip()
        score = _safe_float(row.get("severity_score"), 0.0)
        region = str(row.get("region") or "").strip() or "-"
        summary = str(row.get("summary") or "").strip()
        url = str(row.get("url") or "").strip()
        lines.append(f"{idx}) {title[:108]} [{category}] S{score:.0f}")
        if summary:
            lines.append(f"   {summary[:180]} | {region}")
        if include_links and url:
            lines.append(f"   {url}")
    if map_views:
        names: list[str] = []
        for row in map_views[:3]:
            if not isinstance(row, dict):
                continue
            name = str(row.get("name") or "Map").strip()
            url = str(row.get("url") or "").strip()
            if name:
                names.append(name)
            if include_links and url:
                lines.append(f"map:{name} {url}")
        if names:
            lines.extend(["", f"maps: {' | '.join(names[:3])}"])
    if market_monitors:
        names: list[str] = []
        preferred: list[dict[str, Any]] = []
        prediction_rows = [
            row
            for row in market_monitors
            if isinstance(row, dict) and str(row.get("type") or "").strip().lower() == "prediction_market"
        ]
        preferred.extend(prediction_rows[:2])
        for row in market_monitors:
            if not isinstance(row, dict):
                continue
            if row in preferred:
                continue
            preferred.append(row)
            if len(preferred) >= 8:
                break
        for row in preferred[:8]:
            if not isinstance(row, dict):
                continue
            name = str(row.get("name") or "Monitor").strip()
            url = str(row.get("url") or "").strip()
            if name:
                names.append(name)
            if include_links and url:
                lines.append(f"monitor:{name} {url}")
        if names:
            lines.extend(["", f"monitors: {' | '.join(names[:8])}"])
    return "\n".join(lines)


def _send_discord(webhook_url: str, message: str) -> tuple[bool, str]:
    if not webhook_url.strip():
        return False, "Missing Discord webhook URL."
    response = requests.post(
        webhook_url,
        timeout=TIMEOUT_SECONDS,
        json={"content": message[:1900]},
        headers={"User-Agent": "permanence-os-world-watch-alerts"},
    )
    if 200 <= response.status_code < 300:
        return True, f"Discord sent ({response.status_code})"
    return False, f"Discord failed ({response.status_code})"


def _send_telegram(bot_token: str, chat_id: str, message: str) -> tuple[bool, str]:
    if not bot_token.strip() or not chat_id.strip():
        return False, "Missing Telegram bot token or chat id."
    api_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    response = requests.post(
        api_url,
        timeout=TIMEOUT_SECONDS,
        data={
            "chat_id": chat_id,
            "text": message[:3900],
            "disable_web_page_preview": "true",
        },
        headers={"User-Agent": "permanence-os-world-watch-alerts"},
    )
    if response.status_code == 200:
        payload = response.json()
        if bool(payload.get("ok")):
            return True, "Telegram sent (ok)"
        return False, "Telegram API returned ok=false"
    return False, f"Telegram failed ({response.status_code})"


def _write_outputs(
    *,
    source_path: Path | None,
    alert_count: int,
    min_score: float,
    focus: dict[str, Any],
    message: str,
    dispatch_results: list[dict[str, Any]],
    include_links: bool,
) -> tuple[Path, Path]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    TOOL_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _now().strftime("%Y%m%d-%H%M%S")
    md_path = OUTPUT_DIR / f"world_watch_alerts_{stamp}.md"
    latest_md = OUTPUT_DIR / "world_watch_alerts_latest.md"
    json_path = TOOL_DIR / f"world_watch_alerts_{stamp}.json"

    lines = [
        "# World Watch Alerts",
        "",
        f"Generated (UTC): {_now_iso()}",
        f"Source: {source_path if source_path else 'none'}",
        f"Alerts selected: {alert_count}",
        f"Min score: {min_score}",
        "",
        "## Dispatch",
    ]
    if not dispatch_results:
        lines.append("- No channels attempted (draft mode).")
    for row in dispatch_results:
        lines.append(
            f"- {row.get('channel')}: {'OK' if row.get('ok') else 'FAIL'} | {row.get('detail')}"
        )
    lines.extend(["", "## Message Draft", "```text", message, "```", ""])

    report = "\n".join(lines)
    md_path.write_text(report, encoding="utf-8")
    latest_md.write_text(report, encoding="utf-8")

    payload = {
        "generated_at": _now_iso(),
        "source_path": str(source_path) if source_path else "none",
        "alert_count": alert_count,
        "min_score": min_score,
        "focus": {
            "major_categories": sorted(list(focus.get("major_categories", set()))),
            "always_include_categories": sorted(list(focus.get("always_include_categories", set()))),
            "min_major_score": focus.get("min_major_score"),
            "market_only": bool(focus.get("market_only")),
        },
        "dispatch_results": dispatch_results,
        "message": message,
        "include_links": include_links,
        "latest_markdown": str(latest_md),
    }
    json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return md_path, json_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create and optionally dispatch world-watch alert brief.")
    parser.add_argument("--send", action="store_true", help="Actually dispatch alerts to configured channels")
    parser.add_argument("--max-alerts", type=int, default=6, help="Max alerts to include in the message")
    parser.add_argument("--min-score", type=float, default=68.0, help="Minimum severity score")
    parser.add_argument("--include-links", action="store_true", help="Include URLs in the alert message body")
    args = parser.parse_args(argv)

    source_path = _latest_tool("world_watch_20*.json")
    payload = _read_json(source_path, {}) if source_path else {}
    if not isinstance(payload, dict):
        payload = {}
    focus_events = payload.get("focus_events") if isinstance(payload.get("focus_events"), list) else []
    top_major_events = payload.get("top_major_events") if isinstance(payload.get("top_major_events"), list) else []
    top_events = payload.get("top_events") if isinstance(payload.get("top_events"), list) else []
    merged_events: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for bucket in (focus_events, top_major_events, top_events):
        for row in bucket:
            if not isinstance(row, dict):
                continue
            event_id = str(row.get("event_id") or "").strip()
            dedupe_key = event_id or f"{row.get('category')}|{row.get('title')}"
            if dedupe_key in seen_ids:
                continue
            seen_ids.add(dedupe_key)
            merged_events.append(row)
    map_views = payload.get("map_views") if isinstance(payload.get("map_views"), list) else []
    market_monitors = payload.get("market_monitors") if isinstance(payload.get("market_monitors"), list) else []
    focus = _normalize_focus(payload)
    min_score = float(args.min_score)
    selected = _select_major_alerts(
        [row for row in merged_events if isinstance(row, dict)],
        focus,
        max_alerts=max(1, int(args.max_alerts)),
        min_score=min_score,
    )

    message = _build_message(
        selected,
        map_views,
        market_monitors,
        include_links=bool(args.include_links),
    )
    dispatch_results: list[dict[str, Any]] = []
    if args.send:
        discord_url = str(os.getenv(DISCORD_WEBHOOK_ENV, "")).strip()
        telegram_token = str(os.getenv(TELEGRAM_BOT_TOKEN_ENV, "")).strip()
        telegram_chat = str(os.getenv(TELEGRAM_CHAT_ID_ENV, "")).strip()

        ok, detail = _send_discord(discord_url, message)
        dispatch_results.append({"channel": "discord", "ok": ok, "detail": detail})

        ok, detail = _send_telegram(telegram_token, telegram_chat, message)
        dispatch_results.append({"channel": "telegram", "ok": ok, "detail": detail})

    md_path, json_path = _write_outputs(
        source_path=source_path,
        alert_count=len(selected),
        min_score=min_score,
        focus=focus,
        message=message,
        dispatch_results=dispatch_results,
        include_links=bool(args.include_links),
    )

    print(f"World watch alerts written: {md_path}")
    print(f"World watch alerts latest: {OUTPUT_DIR / 'world_watch_alerts_latest.md'}")
    print(f"Tool payload written: {json_path}")
    print(f"Alerts selected: {len(selected)}")
    if args.send:
        sent_ok = sum(1 for row in dispatch_results if row.get("ok"))
        print(f"Channels ok: {sent_ok}/{len(dispatch_results)}")
    else:
        print("Dispatch mode: draft-only (use --send to dispatch)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
