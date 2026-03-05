#!/usr/bin/env python3
"""
Ingest news headlines and refresh hypothesis signal scores for prediction research.

Advisory only: this script does not execute trades.
"""

from __future__ import annotations

import json
import os
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from typing import Any

import requests

BASE_DIR = Path(__file__).resolve().parents[1]
WORKING_DIR = Path(os.getenv("PERMANENCE_WORKING_DIR", str(BASE_DIR / "memory" / "working")))
OUTPUT_DIR = Path(os.getenv("PERMANENCE_OUTPUT_DIR", str(BASE_DIR / "outputs")))
TOOL_DIR = Path(os.getenv("PERMANENCE_TOOL_DIR", str(BASE_DIR / "memory" / "tool")))

HYPOTHESIS_PATH = Path(os.getenv("PERMANENCE_PREDICTION_HYPOTHESES_PATH", str(WORKING_DIR / "prediction_hypotheses.json")))
FEEDS_PATH = Path(os.getenv("PERMANENCE_PREDICTION_FEEDS_PATH", str(WORKING_DIR / "prediction_news_feeds.json")))
TELEGRAM_SOURCES_PATH = Path(
    os.getenv("PERMANENCE_PREDICTION_TELEGRAM_SOURCES_PATH", str(WORKING_DIR / "prediction_telegram_sources.json"))
)
MAX_ITEMS_PER_FEED = int(os.getenv("PERMANENCE_PREDICTION_MAX_NEWS_ITEMS", "20"))
MAX_TELEGRAM_POSTS_PER_SOURCE = int(os.getenv("PERMANENCE_PREDICTION_MAX_TELEGRAM_POSTS", "20"))
TIMEOUT_SECONDS = int(os.getenv("PERMANENCE_PREDICTION_NEWS_TIMEOUT", "8"))


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def _default_feeds() -> list[dict[str, str]]:
    return [
        {"name": "Reuters World", "url": "https://feeds.reuters.com/Reuters/worldNews"},
        {"name": "Reuters Business", "url": "https://feeds.reuters.com/reuters/businessNews"},
        {"name": "Yahoo Finance", "url": "https://finance.yahoo.com/news/rssindex"},
    ]


def _load_feeds() -> list[dict[str, str]]:
    payload = _read_json(FEEDS_PATH, [])
    if not isinstance(payload, list):
        payload = []
    rows = [row for row in payload if isinstance(row, dict) and row.get("url")]
    if not rows:
        rows = _default_feeds()
    normalized: list[dict[str, str]] = []
    for row in rows:
        normalized.append(
            {
                "name": str(row.get("name") or "feed").strip(),
                "url": str(row.get("url") or "").strip(),
            }
        )
    return normalized


def _load_hypotheses() -> list[dict[str, Any]]:
    payload = _read_json(HYPOTHESIS_PATH, [])
    if not isinstance(payload, list):
        payload = []
    rows = [row for row in payload if isinstance(row, dict)]
    return rows


def _load_telegram_sources() -> list[dict[str, str]]:
    payload = _read_json(TELEGRAM_SOURCES_PATH, [])
    if not isinstance(payload, list):
        payload = []
    rows: list[dict[str, str]] = []
    for row in payload:
        if not isinstance(row, dict):
            continue
        enabled = row.get("enabled", True)
        if isinstance(enabled, bool) and not enabled:
            continue
        url = str(row.get("url") or "").strip()
        if not url:
            continue
        name = str(row.get("name") or "Telegram Channel").strip() or "Telegram Channel"
        channel = str(row.get("channel") or "").strip()
        rows.append({"name": name, "url": url, "channel": channel})
    return rows


def _fetch_text(url: str) -> str:
    if url.startswith("file://"):
        path = Path(url[7:])
        if path.exists():
            return path.read_text(encoding="utf-8", errors="ignore")
        return ""
    response = requests.get(url, timeout=TIMEOUT_SECONDS)
    response.raise_for_status()
    return response.text


def _first_text(node: ET.Element, names: list[str]) -> str:
    for name in names:
        target = node.find(name)
        if target is not None and target.text:
            return target.text.strip()
    return ""


def _parse_feed_items(xml_text: str, source_name: str) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    if not xml_text.strip():
        return items
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return items

    # RSS
    for item in root.findall(".//item"):
        title = _first_text(item, ["title"])
        link = _first_text(item, ["link"])
        summary = _first_text(item, ["description"])
        published = _first_text(item, ["pubDate"])
        if not title:
            continue
        items.append(
            {
                "source": source_name,
                "title": title,
                "link": link,
                "summary": summary,
                "published": published,
            }
        )

    # Atom fallback
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    for entry in root.findall(".//atom:entry", ns):
        title = _first_text(entry, ["{http://www.w3.org/2005/Atom}title"])
        summary = _first_text(entry, ["{http://www.w3.org/2005/Atom}summary"])
        published = _first_text(entry, ["{http://www.w3.org/2005/Atom}updated"])
        link = ""
        link_node = entry.find("{http://www.w3.org/2005/Atom}link")
        if link_node is not None:
            link = str(link_node.attrib.get("href") or "")
        if not title:
            continue
        items.append(
            {
                "source": source_name,
                "title": title,
                "link": link,
                "summary": summary,
                "published": published,
            }
        )
    return items[:MAX_ITEMS_PER_FEED]


def _strip_html_tags(raw_html: str) -> str:
    text = re.sub(r"(?is)<script.*?>.*?</script>", " ", raw_html)
    text = re.sub(r"(?is)<style.*?>.*?</style>", " ", text)
    text = re.sub(r"(?is)<br\s*/?>", "\n", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = unescape(text)
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\n\s+", "\n", text)
    return text.strip()


def _normalize_telegram_url(url: str) -> str:
    raw = str(url or "").strip()
    if raw.startswith("file://"):
        return raw
    if raw.startswith("https://t.me/s/"):
        return raw
    if raw.startswith("https://t.me/"):
        suffix = raw.split("https://t.me/", 1)[1].strip("/")
        if suffix:
            return f"https://t.me/s/{suffix}"
    if raw.startswith("@"):
        return f"https://t.me/s/{raw.lstrip('@')}"
    if raw:
        return f"https://t.me/s/{raw.strip('/')}"
    return ""


def _parse_telegram_posts(html_text: str, source_name: str) -> list[dict[str, str]]:
    if not html_text.strip():
        return []
    posts: list[dict[str, str]] = []
    text_matches = list(re.finditer(r'(?is)<div[^>]*class="[^"]*tgme_widget_message_text[^"]*"[^>]*>(.*?)</div>', html_text))
    for text_match in text_matches:
        text_body = _strip_html_tags(text_match.group(1))
        if not text_body:
            continue
        context = html_text[max(0, text_match.start() - 1800) : text_match.end()]
        link_matches = re.findall(r'(?is)<a[^>]*class="[^"]*tgme_widget_message_date[^"]*"[^>]*href="([^"]+)"', context)
        if not link_matches:
            link_matches = re.findall(r'(?is)<a[^>]*href="([^"]+)"[^>]*>[^<]*<time', context)
        datetime_matches = re.findall(r'(?is)<time[^>]*datetime="([^"]+)"', context)
        posts.append(
            {
                "source": source_name,
                "title": text_body[:140],
                "link": (str(link_matches[-1]).strip() if link_matches else ""),
                "summary": text_body[:420],
                "published": (str(datetime_matches[-1]).strip() if datetime_matches else ""),
            }
        )
        if len(posts) >= MAX_TELEGRAM_POSTS_PER_SOURCE:
            break
    return posts


def _collect_headlines(
    feeds: list[dict[str, str]],
    telegram_sources: list[dict[str, str]],
) -> tuple[list[dict[str, str]], list[str]]:
    headlines: list[dict[str, str]] = []
    warnings: list[str] = []
    for feed in feeds:
        url = str(feed.get("url") or "")
        name = str(feed.get("name") or "feed")
        if not url:
            continue
        try:
            xml_text = _fetch_text(url)
            rows = _parse_feed_items(xml_text, source_name=name)
            headlines.extend(rows)
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"{name}: {exc}")
    for source in telegram_sources:
        raw_url = str(source.get("url") or "")
        url = _normalize_telegram_url(raw_url)
        name = str(source.get("name") or "Telegram Channel")
        if not url:
            continue
        try:
            html_text = _fetch_text(url)
            rows = _parse_telegram_posts(html_text, source_name=name)
            if rows:
                headlines.extend(rows)
            else:
                warnings.append(
                    f"{name} (telegram): no posts parsed from page content; channel may require login or membership."
                )
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"{name} (telegram): {exc}")
    return headlines, warnings


def _as_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _score_hypothesis(row: dict[str, Any], headlines: list[dict[str, str]]) -> tuple[float, list[dict[str, str]]]:
    keywords = [str(x).strip().lower() for x in (row.get("keywords") or []) if str(x).strip()]
    negative_keywords = [str(x).strip().lower() for x in (row.get("negative_keywords") or []) if str(x).strip()]
    if not keywords and not negative_keywords:
        return _as_float(row.get("signal_score"), 0.0), []

    matched: list[dict[str, str]] = []
    raw = 0.0
    for item in headlines:
        text = f"{item.get('title', '')} {item.get('summary', '')}".lower()
        pos_hits = sum(1 for key in keywords if key and key in text)
        neg_hits = sum(1 for key in negative_keywords if key and key in text)
        if pos_hits or neg_hits:
            matched.append(item)
            raw += (pos_hits * 0.35) - (neg_hits * 0.35)

    direction = str(row.get("impact_direction") or "up").strip().lower()
    if direction == "down":
        raw *= -1.0
    raw = max(-2.0, min(2.0, raw))
    existing = _as_float(row.get("signal_score"), 0.0)
    blended = (existing * 0.6) + (raw * 0.4)
    return round(max(-2.0, min(2.0, blended)), 4), matched[:5]


def _write_outputs(
    updated_rows: list[dict[str, Any]],
    headlines: list[dict[str, str]],
    warnings: list[str],
    feed_count: int,
    telegram_source_count: int,
) -> tuple[Path, Path]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    TOOL_DIR.mkdir(parents=True, exist_ok=True)
    HYPOTHESIS_PATH.parent.mkdir(parents=True, exist_ok=True)
    stamp = _now().strftime("%Y%m%d-%H%M%S")
    md_path = OUTPUT_DIR / f"prediction_ingest_{stamp}.md"
    latest_md = OUTPUT_DIR / "prediction_ingest_latest.md"
    json_path = TOOL_DIR / f"prediction_ingest_{stamp}.json"

    HYPOTHESIS_PATH.write_text(json.dumps(updated_rows, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Prediction Ingest",
        "",
        f"Generated (UTC): {_now().isoformat()}",
        f"Hypothesis path: {HYPOTHESIS_PATH}",
        f"Feeds path: {FEEDS_PATH}",
        f"Telegram sources path: {TELEGRAM_SOURCES_PATH}",
        "",
        "## Summary",
        f"- Feeds configured: {feed_count}",
        f"- Telegram sources configured: {telegram_source_count}",
        f"- Headlines ingested: {len(headlines)}",
        f"- Hypotheses updated: {len(updated_rows)}",
    ]
    if warnings:
        lines.append(f"- Warnings: {len(warnings)}")

    lines.extend(["", "## Top Headlines"])
    if not headlines:
        lines.append("- No headlines ingested.")
    for item in headlines[:20]:
        lines.append(f"- [{item.get('source')}] {item.get('title')}")

    lines.extend(["", "## Hypothesis Signal Updates"])
    for row in updated_rows[:20]:
        lines.append(
            f"- {row.get('hypothesis_id', 'unknown')} | signal_score={row.get('signal_score')} | "
            f"evidence={len(row.get('signal_evidence') or [])}"
        )

    if warnings:
        lines.extend(["", "## Warnings"])
        for warning in warnings:
            lines.append(f"- {warning}")

    lines.extend(
        [
            "",
            "## Governance Notes",
            "- News ingest updates signals only; no autonomous trade execution.",
            "- Manual approval remains required for any financial action.",
            "",
        ]
    )

    report = "\n".join(lines)
    md_path.write_text(report, encoding="utf-8")
    latest_md.write_text(report, encoding="utf-8")

    payload = {
        "generated_at": _now().isoformat(),
        "hypothesis_path": str(HYPOTHESIS_PATH),
        "feeds_path": str(FEEDS_PATH),
        "telegram_sources_path": str(TELEGRAM_SOURCES_PATH),
        "feed_count": feed_count,
        "telegram_source_count": telegram_source_count,
        "headline_count": len(headlines),
        "warnings": warnings,
        "updated_rows": updated_rows,
        "headlines": headlines[:50],
        "latest_markdown": str(latest_md),
    }
    json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return md_path, json_path


def main() -> int:
    feeds = _load_feeds()
    telegram_sources = _load_telegram_sources()
    hypotheses = _load_hypotheses()
    headlines, warnings = _collect_headlines(feeds, telegram_sources)

    updated_rows: list[dict[str, Any]] = []
    now_iso = _now().isoformat()
    for row in hypotheses:
        signal_score, evidence = _score_hypothesis(row, headlines)
        item = dict(row)
        item["signal_score"] = signal_score
        item["last_signal_at"] = now_iso
        item["signal_evidence"] = evidence
        updated_rows.append(item)

    md_path, json_path = _write_outputs(
        updated_rows,
        headlines,
        warnings,
        feed_count=len(feeds),
        telegram_source_count=len(telegram_sources),
    )
    print(f"Prediction ingest written: {md_path}")
    print(f"Prediction ingest latest: {OUTPUT_DIR / 'prediction_ingest_latest.md'}")
    print(f"Tool payload written: {json_path}")
    print(f"Hypotheses updated: {len(updated_rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
