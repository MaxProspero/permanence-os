#!/usr/bin/env python3
"""
Monitor upstream platform/API changes and generate actionable update tasks.

This command is read-only:
- Reads changelog/doc feeds (RSS/Atom/HTML)
- Reads local email inbox ingest output
- Scans local code references to estimate impact
- Writes markdown + JSON payloads and optional local action queue
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from html import unescape
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
WORKING_DIR = Path(os.getenv("PERMANENCE_WORKING_DIR", str(BASE_DIR / "memory" / "working")))
OUTPUT_DIR = Path(os.getenv("PERMANENCE_OUTPUT_DIR", str(BASE_DIR / "outputs")))
TOOL_DIR = Path(os.getenv("PERMANENCE_TOOL_DIR", str(BASE_DIR / "memory" / "tool")))
WATCHLIST_PATH = Path(
    os.getenv(
        "PERMANENCE_PLATFORM_WATCHLIST_PATH",
        str(WORKING_DIR / "platform_change_watchlist.json"),
    )
)
EMAIL_INBOX_PATH = Path(
    os.getenv(
        "PERMANENCE_PLATFORM_WATCH_EMAIL_INBOX",
        str(WORKING_DIR / "email" / "inbox.json"),
    )
)
QUEUE_PATH = Path(
    os.getenv(
        "PERMANENCE_PLATFORM_WATCH_QUEUE_PATH",
        str(WORKING_DIR / "platform_change_action_queue.jsonl"),
    )
)
TIMEOUT_SECONDS = int(os.getenv("PERMANENCE_PLATFORM_WATCH_TIMEOUT", "10"))
MAX_ALERT_ITEMS = int(os.getenv("PERMANENCE_PLATFORM_WATCH_MAX_ITEMS", "40"))
LOOKBACK_DAYS = int(os.getenv("PERMANENCE_PLATFORM_WATCH_LOOKBACK_DAYS", "14"))
MIN_SCORE = float(os.getenv("PERMANENCE_PLATFORM_WATCH_MIN_SCORE", "34"))

UPDATE_TERMS = [
    "update",
    "release",
    "changelog",
    "version",
    "migration",
    "rate limit",
    "policy",
    "oauth",
    "authentication",
    "auth",
    "api",
    "sdk",
]
ACTION_TERMS = [
    "action required",
    "required",
    "must",
    "before",
    "deadline",
    "sunset",
    "retire",
    "revoke",
    "rotate",
]
CRITICAL_TERMS = [
    "breaking",
    "deprecated",
    "deprecation",
    "remove",
    "removed",
    "discontinue",
    "incompatible",
    "unsupported",
    "403",
    "401",
    "410",
]
PLATFORM_HINTS = {
    "x": ["x api", "x.com", "twitter", "api.twitter.com", "@xdevelopers", "tweet"],
    "telegram": ["telegram", "botfather", "core.telegram.org", "tg bot", "teleophtxn"],
    "discord": ["discord", "discord.com", "webhook", "guild", "channel"],
    "gmail": ["gmail", "google workspace", "google api", "googleapiclient"],
    "anthropic": ["anthropic", "claude", "console.anthropic.com"],
    "openai": ["openai", "chatgpt", "api.openai.com", "gpt-"],
    "xai": ["xai", "grok", "api.x.ai"],
}
PROMO_BLOCK_TERMS = [
    "unsubscribe",
    "sale",
    "discount",
    "promo",
    "sponsored",
    "shop now",
    "buy now",
    "call now",
    "limited time",
]
CODE_PATTERNS = {
    "x": [
        "api.twitter.com",
        "x-account-watch",
        "permanence_social_read_token",
        "social_research_ingest",
        "x.com/i/web/status/",
    ],
    "telegram": [
        "telegram",
        "teleophtxnbot",
        "permanence_telegram_bot_token",
        "telegram_control.py",
    ],
    "discord": [
        "discord",
        "permanence_discord_bot_token",
        "discord_telegram_relay",
        "webhook",
    ],
    "gmail": [
        "gmail",
        "googleapiclient",
        "permanence_gmail_credentials",
        "gmail_ingest",
    ],
    "anthropic": ["anthropic_api_key", "claude", "anthropic"],
    "openai": ["openai_api_key", "api.openai.com", "openai"],
    "xai": ["xai_api_key", "api.x.ai", "grok"],
}
SCANNABLE_EXTS = {
    ".py",
    ".sh",
    ".md",
    ".txt",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".ini",
    ".cfg",
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now().isoformat()


def _safe_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=True) + "\n")


def _parse_time(text: str) -> datetime | None:
    token = str(text or "").strip()
    if not token:
        return None
    try:
        parsed = datetime.fromisoformat(token.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except ValueError:
        pass
    try:
        return parsedate_to_datetime(token).astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


def _is_recent(published_at: str, lookback_days: int) -> bool:
    parsed = _parse_time(published_at)
    if parsed is None:
        return True
    return parsed >= (_now() - timedelta(days=max(1, int(lookback_days))))


def _fingerprint(*parts: str) -> str:
    token = "|".join(str(part or "").strip().lower() for part in parts)
    return hashlib.sha1(token.encode("utf-8")).hexdigest()


def _extract_years(text: str) -> list[int]:
    years: list[int] = []
    for token in re.findall(r"\b(20\d{2})\b", str(text or "")):
        value = _safe_int(token, 0)
        if value >= 2000:
            years.append(value)
    return years


def _default_watchlist() -> list[dict[str, Any]]:
    return [
        {
            "name": "X Developer Changelog",
            "platform": "x",
            "url": "https://docs.x.com/changelog",
            "enabled": True,
            "max_items": 20,
        },
        {
            "name": "Telegram Bot API Docs",
            "platform": "telegram",
            "url": "https://core.telegram.org/bots/api",
            "enabled": True,
            "max_items": 20,
        },
        {
            "name": "Discord Developer Changelog",
            "platform": "discord",
            "url": "https://discord.com/developers/docs/change-log",
            "enabled": True,
            "max_items": 20,
        },
        {
            "name": "Gmail API Release Notes",
            "platform": "gmail",
            "url": "https://developers.google.com/workspace/gmail/release-notes",
            "enabled": True,
            "max_items": 20,
        },
        {
            "name": "Anthropic Release Notes",
            "platform": "anthropic",
            "url": "https://docs.anthropic.com/en/release-notes/overview",
            "enabled": True,
            "max_items": 20,
        },
    ]


def _ensure_watchlist(path: Path, force_template: bool) -> tuple[list[dict[str, Any]], str]:
    if path.exists() and (not force_template):
        payload = _read_json(path, [])
        if isinstance(payload, list):
            rows = [row for row in payload if isinstance(row, dict) and str(row.get("url") or "").strip()]
            if rows:
                return rows, "existing"
    rows = _default_watchlist()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    return rows, "written"


def _fetch_text(url: str) -> str:
    target = str(url or "").strip()
    if target.startswith("file://"):
        path = Path(target[7:])
        if not path.exists():
            return ""
        return path.read_text(encoding="utf-8", errors="ignore")
    response = requests.get(
        target,
        timeout=TIMEOUT_SECONDS,
        headers={"User-Agent": "permanence-os-platform-change-watch/0.1"},
    )
    response.raise_for_status()
    return response.text


def _first_text(node: ET.Element, tags: list[str]) -> str:
    for tag in tags:
        found = node.find(tag)
        if found is not None and found.text:
            value = " ".join(found.text.split()).strip()
            if value:
                return value
    return ""


def _first_link(node: ET.Element) -> str:
    for tag in ["link", "{http://www.w3.org/2005/Atom}link"]:
        for found in node.findall(tag):
            href = str(found.attrib.get("href") or "").strip()
            if href:
                return href
            value = " ".join(str(found.text or "").split()).strip()
            if value.startswith("http://") or value.startswith("https://"):
                return value
    return ""


def _looks_like_feed(text: str) -> bool:
    token = str(text or "").lstrip().lower()
    return token.startswith("<?xml") or token.startswith("<rss") or token.startswith("<feed")


def _strip_html(value: str) -> str:
    text = str(value or "")
    text = re.sub(r"(?is)<script.*?>.*?</script>", " ", text)
    text = re.sub(r"(?is)<style.*?>.*?</style>", " ", text)
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</(p|div|li|h1|h2|h3|h4|h5|h6|tr|section|article)>", "\n", text)
    text = re.sub(r"(?is)<[^>]+>", " ", text)
    text = unescape(text)
    text = re.sub(r"\r\n?", "\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    lines = [" ".join(row.split()).strip() for row in text.split("\n")]
    lines = [row for row in lines if row]
    return "\n".join(lines)


def _guess_platform(text: str, fallback: str = "") -> str:
    blob = str(text or "").lower()
    for platform, hints in PLATFORM_HINTS.items():
        if any(hint in blob for hint in hints):
            return platform
    return str(fallback or "unknown").strip().lower() or "unknown"


def _term_matches(text: str, terms: list[str]) -> list[str]:
    blob = str(text or "").lower()
    seen: list[str] = []
    for term in terms:
        token = str(term or "").strip().lower()
        if token and token in blob and token not in seen:
            seen.append(token)
    return seen


def _base_signal_score(text: str) -> tuple[float, list[str]]:
    update_hits = _term_matches(text, UPDATE_TERMS)
    action_hits = _term_matches(text, ACTION_TERMS)
    critical_hits = _term_matches(text, CRITICAL_TERMS)
    score = (len(update_hits) * 7.0) + (len(action_hits) * 10.0) + (len(critical_hits) * 22.0)
    tags = update_hits + [f"action:{row}" for row in action_hits] + [f"critical:{row}" for row in critical_hits]
    if "security" in str(text or "").lower():
        score += 6.0
    return min(100.0, score), tags


def _parse_source_items(source: dict[str, Any], text: str) -> list[dict[str, Any]]:
    source_name = str(source.get("name") or "Unknown Source").strip() or "Unknown Source"
    source_url = str(source.get("url") or "").strip()
    platform = _guess_platform(str(source.get("platform") or ""), fallback=str(source.get("platform") or ""))
    out: list[dict[str, Any]] = []

    if _looks_like_feed(text):
        try:
            root = ET.fromstring(text)
        except ET.ParseError:
            root = ET.Element("empty")
        entries = list(root.findall(".//item"))
        if not entries:
            entries = list(root.findall(".//{http://www.w3.org/2005/Atom}entry"))
        for item in entries:
            title = _first_text(item, ["title", "{http://www.w3.org/2005/Atom}title"])
            summary = _first_text(
                item,
                [
                    "description",
                    "summary",
                    "{http://www.w3.org/2005/Atom}summary",
                    "{http://www.w3.org/2005/Atom}content",
                ],
            )
            link = _first_link(item) or source_url
            published_at = _first_text(
                item,
                [
                    "pubDate",
                    "published",
                    "updated",
                    "{http://www.w3.org/2005/Atom}published",
                    "{http://www.w3.org/2005/Atom}updated",
                ],
            )
            if title or summary:
                out.append(
                    {
                        "source_type": "feed",
                        "source": source_name,
                        "platform": platform,
                        "title": title or source_name,
                        "summary": summary,
                        "link": link,
                        "published_at": published_at,
                    }
                )
        return out

    lines = re.split(r"[\r\n]+", _strip_html(text))
    seen: set[str] = set()
    for line in lines:
        sample = " ".join(line.split()).strip()
        if len(sample) < 28:
            continue
        if len(sample) > 360:
            continue
        score, _tags = _base_signal_score(sample)
        if score <= 0:
            continue
        key = sample.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(
            {
                "source_type": "web",
                "source": source_name,
                "platform": platform,
                "title": sample,
                "summary": "",
                "link": source_url,
                "published_at": "",
            }
        )
        if len(out) >= 20:
            break
    return out


def _collect_external_signals(
    sources: list[dict[str, Any]],
    lookback_days: int,
) -> tuple[list[dict[str, Any]], list[str]]:
    rows: list[dict[str, Any]] = []
    warnings: list[str] = []
    for source in sources:
        enabled = str(source.get("enabled", True)).strip().lower()
        if enabled in {"0", "false", "no", "off"}:
            continue
        source_name = str(source.get("name") or "Unknown Source").strip() or "Unknown Source"
        url = str(source.get("url") or "").strip()
        if not url:
            warnings.append(f"{source_name}: missing url")
            continue
        source_max = max(1, _safe_int(source.get("max_items"), 20))
        try:
            text = _fetch_text(url)
            candidates = _parse_source_items(source, text)
            if not candidates:
                warnings.append(f"{source_name}: no parsable change items found; verify source format/url")
            kept = 0
            for row in candidates:
                if kept >= source_max:
                    break
                published_at = str(row.get("published_at") or "")
                if not _is_recent(published_at, lookback_days):
                    continue
                if (not published_at) and str(row.get("source_type") or "") == "web":
                    years = _extract_years(f"{row.get('title') or ''} {row.get('summary') or ''}")
                    if years and max(years) < (_now().year - 1):
                        continue
                blob = " ".join(
                    [
                        str(row.get("title") or ""),
                        str(row.get("summary") or ""),
                        str(row.get("link") or ""),
                        str(row.get("source") or ""),
                    ]
                )
                base_score, tags = _base_signal_score(blob)
                if base_score <= 0:
                    continue
                item = dict(row)
                item["score_base"] = round(base_score, 3)
                item["tags"] = tags
                rows.append(item)
                kept += 1
            if kept == 0 and candidates:
                warnings.append(f"{source_name}: parsed items but none passed change-signal scoring")
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"{source_name}: {exc}")
    return rows, warnings


def _load_email_signals(path: Path, lookback_days: int) -> list[dict[str, Any]]:
    payload = _read_json(path, [])
    messages: list[dict[str, Any]]
    if isinstance(payload, list):
        messages = [row for row in payload if isinstance(row, dict)]
    elif isinstance(payload, dict):
        messages = [payload]
    else:
        messages = []
    rows: list[dict[str, Any]] = []
    for msg in messages:
        sender = str(msg.get("from") or "")
        subject = str(msg.get("subject") or "")
        snippet = str(msg.get("snippet") or msg.get("body") or "")
        sent_at = str(msg.get("date") or "")
        if not _is_recent(sent_at, lookback_days):
            continue
        blob = " ".join([sender, subject, snippet])
        score, tags = _base_signal_score(blob)
        platform = _guess_platform(blob, fallback="email")
        sender_lower = sender.lower()
        update_hits = _term_matches(blob, UPDATE_TERMS)
        critical_hits = _term_matches(blob, CRITICAL_TERMS)
        has_update_signal = bool(update_hits or critical_hits)
        trusted_sender = any(
            domain in sender_lower
            for domain in [
                "@x.com",
                "@twitter.com",
                "discord",
                "telegram",
                "google",
                "anthropic",
                "openai",
                "x.ai",
            ]
        )
        blob_lower = blob.lower()
        if (not has_update_signal) and ("developer" not in blob_lower) and ("release note" not in blob_lower):
            continue
        if (not trusted_sender) and any(term in blob_lower for term in PROMO_BLOCK_TERMS):
            continue
        if trusted_sender and score < 16.0:
            score = 16.0
            tags = tags + ["sender:platform-domain"]
        if (platform in {"email", "unknown"}) and (not trusted_sender):
            if not (update_hits and critical_hits and score >= 36.0):
                continue
        if score <= 0:
            continue
        rows.append(
            {
                "source_type": "email",
                "source": "email-inbox",
                "platform": platform,
                "title": subject or f"Platform update email from {sender or 'unknown'}",
                "summary": snippet,
                "link": "",
                "published_at": sent_at,
                "score_base": round(score, 3),
                "tags": tags,
            }
        )
    return rows


def _scan_files(scan_roots: list[Path]) -> dict[str, dict[str, Any]]:
    footprint: dict[str, dict[str, Any]] = {
        platform: {"hit_count": 0, "files": []}
        for platform in CODE_PATTERNS
    }
    for root in scan_roots:
        if not root.exists():
            continue
        candidates: list[Path] = []
        if root.is_file():
            candidates = [root]
        else:
            for path in root.rglob("*"):
                if path.is_dir():
                    continue
                if path.suffix.lower() not in SCANNABLE_EXTS:
                    continue
                if path.name.startswith("."):
                    continue
                candidates.append(path)
        for path in candidates:
            try:
                text = path.read_text(encoding="utf-8", errors="ignore").lower()
            except OSError:
                continue
            for platform, patterns in CODE_PATTERNS.items():
                if any(pattern in text for pattern in patterns):
                    data = footprint[platform]
                    data["hit_count"] = int(data.get("hit_count") or 0) + 1
                    files = data.get("files")
                    if isinstance(files, list) and len(files) < 10:
                        files.append(str(path))
    return footprint


def _score_alert(item: dict[str, Any], footprint: dict[str, dict[str, Any]]) -> dict[str, Any]:
    platform = str(item.get("platform") or "unknown").strip().lower() or "unknown"
    base = _safe_float(item.get("score_base"), 0.0)
    impact = 0.0
    platform_hits = 0
    platform_files: list[str] = []
    if platform in footprint:
        platform_hits = _safe_int(footprint[platform].get("hit_count"), 0)
        impact = min(26.0, platform_hits * 1.8)
        files = footprint[platform].get("files")
        if isinstance(files, list):
            platform_files = [str(row) for row in files[:8]]

    recency_bonus = 0.0
    parsed = _parse_time(str(item.get("published_at") or ""))
    if parsed is not None:
        age_hours = max(0.0, (_now() - parsed).total_seconds() / 3600.0)
        if age_hours <= 24:
            recency_bonus = 8.0
        elif age_hours <= 72:
            recency_bonus = 4.0
        elif age_hours <= 168:
            recency_bonus = 2.0

    source_bonus = 6.0 if str(item.get("source_type") or "") == "email" else 0.0
    score = min(100.0, base + impact + recency_bonus + source_bonus)
    if score >= 75:
        level = "critical"
    elif score >= 55:
        level = "high"
    elif score >= 34:
        level = "medium"
    else:
        level = "low"

    alert = dict(item)
    alert["platform"] = platform
    alert["score"] = round(score, 3)
    alert["level"] = level
    alert["code_hits"] = platform_hits
    alert["impact_files"] = platform_files
    alert["alert_id"] = "PLT-" + _fingerprint(platform, str(item.get("title")), str(item.get("link")))[:10].upper()
    return alert


def _dedupe_and_rank(
    external_rows: list[dict[str, Any]],
    email_rows: list[dict[str, Any]],
    footprint: dict[str, dict[str, Any]],
    min_score: float,
    max_items: int,
) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for item in [*external_rows, *email_rows]:
        fingerprint = _fingerprint(str(item.get("platform")), str(item.get("title")), str(item.get("link")))
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        alert = _score_alert(item, footprint)
        if _safe_float(alert.get("score"), 0.0) < min_score:
            continue
        out.append(alert)
    out.sort(
        key=lambda row: (
            _safe_float(row.get("score"), 0.0),
            _parse_time(str(row.get("published_at") or "")) or datetime(1970, 1, 1, tzinfo=timezone.utc),
        ),
        reverse=True,
    )
    return out[: max(1, int(max_items))]


def _suggested_commands(platform: str) -> list[str]:
    mapping = {
        "x": [
            "python cli.py social-research-ingest",
            "python -m pytest tests/test_social_research_ingest.py tests/test_x_account_watch.py",
        ],
        "telegram": [
            "python cli.py telegram-control --action status",
            "python -m pytest tests/test_telegram_control.py",
        ],
        "discord": [
            "python cli.py discord-telegram-relay --action status",
            "python -m pytest tests/test_discord_telegram_relay.py tests/test_discord_feed_manager.py",
        ],
        "gmail": [
            "python cli.py gmail-ingest --max 20",
            "python -m pytest tests/test_gmail_ingest.py tests/test_email_agent.py",
        ],
        "anthropic": [
            "python cli.py integration-readiness",
            "python -m pytest tests/test_model_router_providers.py tests/test_integration_readiness.py",
        ],
        "openai": [
            "python cli.py integration-readiness",
            "python -m pytest tests/test_model_router_providers.py tests/test_integration_readiness.py",
        ],
        "xai": [
            "python cli.py integration-readiness",
            "python -m pytest tests/test_model_router_providers.py tests/test_integration_readiness.py",
        ],
    }
    return mapping.get(
        platform,
        [
            "python cli.py integration-readiness",
            "python cli.py comms-doctor --allow-warnings",
        ],
    )


def _queue_actions(path: Path, alerts: list[dict[str, Any]]) -> tuple[int, int]:
    existing = _load_jsonl(path)
    known = {
        str(row.get("fingerprint") or "")
        for row in existing
        if isinstance(row, dict)
    }
    pending_before = sum(1 for row in existing if str(row.get("status") or "").upper() == "PENDING")
    added = 0
    for alert in alerts:
        if str(alert.get("level") or "") not in {"critical", "high"}:
            continue
        fingerprint = _fingerprint(
            str(alert.get("platform")),
            str(alert.get("title")),
            str(alert.get("link")),
        )
        if fingerprint in known:
            continue
        known.add(fingerprint)
        platform = str(alert.get("platform") or "unknown")
        item_id = "PLTQ-" + fingerprint[:10].upper()
        existing.append(
            {
                "id": item_id,
                "created_at": _now_iso(),
                "status": "PENDING",
                "source": "platform_change_watch",
                "platform": platform,
                "level": str(alert.get("level") or "medium"),
                "score": _safe_float(alert.get("score"), 0.0),
                "title": str(alert.get("title") or ""),
                "summary": str(alert.get("summary") or ""),
                "link": str(alert.get("link") or ""),
                "fingerprint": fingerprint,
                "suggested_commands": _suggested_commands(platform),
            }
        )
        added += 1

    _write_jsonl(path, existing)
    pending_after = sum(1 for row in existing if str(row.get("status") or "").upper() == "PENDING")
    return added, pending_after if added else pending_before


def _write_outputs(
    *,
    watchlist_path: Path,
    watchlist_status: str,
    email_path: Path,
    queue_path: Path,
    scan_roots: list[Path],
    external_rows: list[dict[str, Any]],
    email_rows: list[dict[str, Any]],
    alerts: list[dict[str, Any]],
    warnings: list[str],
    footprint: dict[str, dict[str, Any]],
    queue_added: int,
    queue_pending: int,
) -> tuple[Path, Path]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    TOOL_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _now().strftime("%Y%m%d-%H%M%S")
    md_path = OUTPUT_DIR / f"platform_change_watch_{stamp}.md"
    latest_md = OUTPUT_DIR / "platform_change_watch_latest.md"
    json_path = TOOL_DIR / f"platform_change_watch_{stamp}.json"

    critical_count = sum(1 for row in alerts if str(row.get("level") or "") == "critical")
    high_count = sum(1 for row in alerts if str(row.get("level") or "") == "high")
    medium_count = sum(1 for row in alerts if str(row.get("level") or "") == "medium")

    lines = [
        "# Platform Change Watch",
        "",
        f"Generated (UTC): {_now_iso()}",
        f"Watchlist path: {watchlist_path} ({watchlist_status})",
        f"Email inbox path: {email_path}",
        f"Action queue path: {queue_path}",
        f"Scan roots: {', '.join(str(path) for path in scan_roots)}",
        "",
        "## Summary",
        f"- External signals: {len(external_rows)}",
        f"- Email signals: {len(email_rows)}",
        f"- Alerts: {len(alerts)}",
        f"- Critical: {critical_count}",
        f"- High: {high_count}",
        f"- Medium: {medium_count}",
        f"- Queue items added: {queue_added}",
        f"- Queue pending total: {queue_pending}",
    ]
    if warnings:
        lines.append(f"- Warnings: {len(warnings)}")

    lines.extend(["", "## Top Alerts"])
    if not alerts:
        lines.append("- No platform update alerts above threshold.")
    for idx, alert in enumerate(alerts[:25], start=1):
        tags = ",".join(str(tag) for tag in (alert.get("tags") or [])[:8]) or "-"
        lines.append(
            f"{idx}. [{alert.get('level')}] [{alert.get('platform')}] "
            f"{alert.get('title')} | score={alert.get('score')} | code_hits={alert.get('code_hits')} | tags={tags}"
        )
        link = str(alert.get("link") or "").strip()
        if link:
            lines.append(f"   - link={link}")
        impact_files = alert.get("impact_files") if isinstance(alert.get("impact_files"), list) else []
        if impact_files:
            lines.append(f"   - impact_files={', '.join(str(path) for path in impact_files[:4])}")

    lines.extend(["", "## Integration Footprint"])
    for platform, data in sorted(footprint.items()):
        count = _safe_int(data.get("hit_count"), 0)
        files = data.get("files") if isinstance(data.get("files"), list) else []
        preview = ", ".join(str(path) for path in files[:3]) if files else "-"
        lines.append(f"- {platform}: hits={count} files={preview}")

    lines.extend(["", "## Suggested Next Commands"])
    seen_cmds: set[str] = set()
    commands: list[str] = []
    for alert in alerts[:8]:
        for cmd in _suggested_commands(str(alert.get("platform") or "unknown")):
            if cmd not in seen_cmds:
                seen_cmds.add(cmd)
                commands.append(cmd)
    if not commands:
        commands = [
            "python cli.py integration-readiness",
            "python cli.py comms-doctor --allow-warnings",
        ]
    for cmd in commands[:10]:
        lines.append(f"- {cmd}")

    if warnings:
        lines.extend(["", "## Warnings"])
        for warning in warnings[:40]:
            lines.append(f"- {warning}")

    lines.extend(
        [
            "",
            "## Governance Notes",
            "- Read-only watch mode: no social posting, no account mutations, no outbound writes.",
            "- High/critical alerts are queued for human review before code changes.",
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
        "email_inbox_path": str(email_path),
        "queue_path": str(queue_path),
        "scan_roots": [str(path) for path in scan_roots],
        "external_signal_count": len(external_rows),
        "email_signal_count": len(email_rows),
        "alert_count": len(alerts),
        "critical_count": critical_count,
        "high_count": high_count,
        "medium_count": medium_count,
        "queue_added": queue_added,
        "queue_pending": queue_pending,
        "alerts": alerts,
        "integration_footprint": footprint,
        "warnings": warnings,
        "latest_markdown": str(latest_md),
    }
    json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return md_path, json_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Watch platform/API changes and queue update actions.")
    parser.add_argument("--force-template", action="store_true", help="Rewrite watchlist template")
    parser.add_argument("--watchlist-path", help="Override watchlist JSON path")
    parser.add_argument("--email-path", help="Override email inbox JSON path")
    parser.add_argument("--queue-path", help="Override action queue JSONL path")
    parser.add_argument("--scan-root", action="append", default=[], help="Root path to scan for integration references")
    parser.add_argument("--lookback-days", type=int, default=LOOKBACK_DAYS, help="Lookback window in days")
    parser.add_argument("--min-score", type=float, default=MIN_SCORE, help="Minimum alert score threshold")
    parser.add_argument("--max-items", type=int, default=MAX_ALERT_ITEMS, help="Max alerts to include")
    parser.add_argument("--no-queue", action="store_true", help="Skip queue file updates")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero when critical alerts are present")
    args = parser.parse_args(argv)

    watchlist_path = Path(args.watchlist_path).expanduser() if args.watchlist_path else WATCHLIST_PATH
    email_path = Path(args.email_path).expanduser() if args.email_path else EMAIL_INBOX_PATH
    queue_path = Path(args.queue_path).expanduser() if args.queue_path else QUEUE_PATH

    watchlist_rows, watchlist_status = _ensure_watchlist(watchlist_path, force_template=bool(args.force_template))
    scan_roots = [Path(path).expanduser() for path in (args.scan_root or []) if str(path or "").strip()]
    if not scan_roots:
        scan_roots = [
            BASE_DIR / "cli.py",
            BASE_DIR / "scripts",
            BASE_DIR / "agents",
            BASE_DIR / "core",
            BASE_DIR / "models",
        ]

    external_rows, warnings = _collect_external_signals(
        watchlist_rows,
        lookback_days=max(1, int(args.lookback_days)),
    )
    email_rows = _load_email_signals(
        path=email_path,
        lookback_days=max(1, int(args.lookback_days)),
    )
    footprint = _scan_files(scan_roots)
    alerts = _dedupe_and_rank(
        external_rows=external_rows,
        email_rows=email_rows,
        footprint=footprint,
        min_score=max(0.0, float(args.min_score)),
        max_items=max(1, int(args.max_items)),
    )

    queue_added = 0
    queue_pending = sum(1 for row in _load_jsonl(queue_path) if str(row.get("status") or "").upper() == "PENDING")
    if not args.no_queue:
        queue_added, queue_pending = _queue_actions(queue_path, alerts)

    md_path, json_path = _write_outputs(
        watchlist_path=watchlist_path,
        watchlist_status=watchlist_status,
        email_path=email_path,
        queue_path=queue_path,
        scan_roots=scan_roots,
        external_rows=external_rows,
        email_rows=email_rows,
        alerts=alerts,
        warnings=warnings,
        footprint=footprint,
        queue_added=queue_added,
        queue_pending=queue_pending,
    )

    critical_count = sum(1 for row in alerts if str(row.get("level") or "") == "critical")
    print(f"Platform change watch report: {md_path}")
    print(f"Platform change watch latest: {OUTPUT_DIR / 'platform_change_watch_latest.md'}")
    print(f"Tool payload: {json_path}")
    print(f"Alerts: {len(alerts)} (critical={critical_count})")
    print(f"Queue added: {queue_added} | pending: {queue_pending}")

    if args.strict and critical_count > 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
