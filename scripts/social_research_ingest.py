#!/usr/bin/env python3
"""
Ingest read-only social/trend feeds and rank opportunities.
"""

from __future__ import annotations

import argparse
import json
import os
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
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

FEEDS_PATH = Path(
    os.getenv("PERMANENCE_SOCIAL_RESEARCH_FEEDS_PATH", str(WORKING_DIR / "social_research_feeds.json"))
)
POLICY_PATH = Path(
    os.getenv(
        "PERMANENCE_SOCIAL_DISCERNMENT_POLICY_PATH",
        str(WORKING_DIR / "social_discernment_policy.json"),
    )
)
MAX_ITEMS_PER_FEED = int(os.getenv("PERMANENCE_SOCIAL_MAX_ITEMS", "25"))
TIMEOUT_SECONDS = int(os.getenv("PERMANENCE_SOCIAL_TIMEOUT", "8"))
X_RECENT_SEARCH_URL = os.getenv(
    "PERMANENCE_X_RECENT_SEARCH_URL",
    "https://api.twitter.com/2/tweets/search/recent",
)
X_DEFAULT_MAX_RESULTS = int(os.getenv("PERMANENCE_X_MAX_RESULTS", "25"))
X_TOKEN_ENV = "PERMANENCE_SOCIAL_READ_TOKEN"
DISCORD_BOT_TOKEN_ENV = "PERMANENCE_DISCORD_BOT_TOKEN"
DISCORD_MESSAGES_LIMIT = int(os.getenv("PERMANENCE_DISCORD_MAX_MESSAGES", "50"))


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


def _default_feeds() -> list[dict[str, Any]]:
    return [
        {"name": "Reddit Entrepreneur", "platform": "reddit", "url": "https://www.reddit.com/r/Entrepreneur/.rss"},
        {"name": "Reddit SideProject", "platform": "reddit", "url": "https://www.reddit.com/r/SideProject/.rss"},
        {
            "name": "X Agents/Automation",
            "platform": "x",
            "query": "(ai OR agent OR automation OR saas) -is:retweet lang:en",
            "max_results": 25,
        },
        {
            "name": "X Market/Macro",
            "platform": "x",
            "query": "(stocks OR macro OR yields OR inflation OR fed OR recession OR risk-on OR risk-off) -is:retweet lang:en",
            "max_results": 25,
        },
        {
            "name": "X Gold/FX/Crypto",
            "platform": "x",
            "query": "(xauusd OR gold OR forex OR dxy OR bitcoin OR btc OR ethereum) -is:retweet lang:en",
            "max_results": 25,
        },
        {
            "name": "WorkOS Changelog",
            "platform": "changelog",
            "url": "https://workos.com/changelog/rss.xml",
        },
        {
            "name": "Discord Server A (set channel_id)",
            "platform": "discord",
            "enabled": False,
            "channel_id": "",
            "max_messages": 50,
        },
        {
            "name": "Discord Server B (set channel_id)",
            "platform": "discord",
            "enabled": False,
            "channel_id": "",
            "max_messages": 50,
        },
        {
            "name": "YouTube Reviewer A (set channel_id)",
            "platform": "youtube",
            "enabled": False,
            "channel_id": "",
        },
        {
            "name": "YouTube Reviewer B (set channel_id)",
            "platform": "youtube",
            "enabled": False,
            "channel_id": "",
        },
        {"name": "HN Frontpage", "platform": "hackernews", "url": "https://hnrss.org/frontpage"},
    ]


def _default_policy() -> dict[str, Any]:
    return {
        "min_score_keep": 0.5,
        "require_keyword_match": False,
        "drop_on_exclude_match": False,
        "include_keywords": ["ai", "agent", "automation", "saas", "growth", "monetize", "trading", "prediction"],
        "exclude_keywords": ["meme", "giveaway", "nsfw", "airdrop"],
        "include_bonus": 0.25,
        "exclude_penalty": 1.5,
        "freshness_half_life_hours": 48.0,
        "freshness_max_bonus": 1.5,
        "platform_weights": {
            "blog": 0.8,
            "youtube": 0.6,
            "changelog": 0.7,
            "hackernews": 0.5,
            "x": 0.4,
            "reddit": 0.2,
            "discord": 0.1,
        },
        "source_weights": {
            "x personal @xdevelopers": 0.5,
            "x personal @roundtablespace": 0.3,
            "x personal @juliangoldieseo": 0.2,
        },
        "top_items_limit": 30,
        "updated_at": _now_iso(),
    }


def _ensure_feeds(path: Path, force_template: bool) -> tuple[list[dict[str, Any]], str]:
    if path.exists() and not force_template:
        payload = _read_json(path, [])
        if isinstance(payload, list):
            rows = [
                row
                for row in payload
                if isinstance(row, dict)
                and (
                    row.get("url")
                    or (str(row.get("platform") or "").lower() in {"x", "twitter"} and row.get("query"))
                    or (str(row.get("platform") or "").lower() == "discord" and row.get("channel_id"))
                    or (str(row.get("platform") or "").lower() == "youtube" and row.get("channel_id"))
                )
            ]
            if rows:
                return rows, "existing"
    rows = _default_feeds()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    return rows, "written"


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
    merged["updated_at"] = str(payload.get("updated_at") or defaults["updated_at"])
    if merged != payload:
        path.write_text(json.dumps(merged, indent=2) + "\n", encoding="utf-8")
        return merged, "updated"
    return merged, "existing"


def _keywords() -> list[str]:
    raw = str(os.getenv("PERMANENCE_SOCIAL_KEYWORDS", "")).strip()
    if raw:
        rows = [item.strip().lower() for item in raw.split(",") if item.strip()]
        if rows:
            return rows
    return [
        "ai",
        "agent",
        "automation",
        "saas",
        "growth",
        "monetize",
        "trading",
        "prediction",
        "backtest",
        "xauusd",
        "gold",
        "btc",
        "crypto",
        "forex",
        "liquidity",
        "order block",
        "fair value gap",
        "clip",
        "shorts",
    ]


def _fetch_text(url: str) -> str:
    if url.startswith("file://"):
        path = Path(url[7:])
        if not path.exists():
            return ""
        return path.read_text(encoding="utf-8", errors="ignore")
    response = requests.get(
        url,
        timeout=TIMEOUT_SECONDS,
        headers={"User-Agent": "permanence-os-social-research-ingest"},
    )
    response.raise_for_status()
    return response.text


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


def _x_max_results(value: Any) -> int:
    return max(10, min(100, _safe_int(value, X_DEFAULT_MAX_RESULTS)))


def _youtube_feed_url(feed: dict[str, Any]) -> str:
    explicit_url = str(feed.get("url") or "").strip()
    if explicit_url:
        return explicit_url
    channel_id = str(feed.get("channel_id") or "").strip()
    if channel_id:
        return f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
    return ""


def _fetch_x_items(source_name: str, query: str, max_results: int, token: str) -> list[dict[str, Any]]:
    response = requests.get(
        X_RECENT_SEARCH_URL,
        timeout=TIMEOUT_SECONDS,
        headers={
            "Authorization": f"Bearer {token}",
            "User-Agent": "permanence-os-social-research-ingest",
        },
        params={
            "query": query,
            "max_results": _x_max_results(max_results),
            "tweet.fields": "created_at,lang,public_metrics",
        },
    )
    if response.status_code == 402:
        raise RuntimeError("X API returned 402 Payment Required. Add X API credits/plan to enable this feed.")
    if response.status_code == 401:
        raise RuntimeError("X API returned 401 Unauthorized. Regenerate PERMANENCE_SOCIAL_READ_TOKEN.")
    if response.status_code == 403:
        raise RuntimeError("X API returned 403 Forbidden. Verify app permissions and plan access.")
    response.raise_for_status()
    payload = response.json()
    data = payload.get("data")
    if data is None:
        return []

    rows: list[dict[str, Any]] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        tweet_id = str(item.get("id") or "").strip()
        text = str(item.get("text") or "").replace("\r", " ").replace("\n", " ").strip()
        if not text:
            continue
        title = text if len(text) <= 140 else (text[:137] + "...")
        rows.append(
            {
                "source": source_name,
                "platform": "x",
                "title": title,
                "link": f"https://x.com/i/web/status/{tweet_id}" if tweet_id else "",
                "summary": text,
                "published": str(item.get("created_at") or ""),
                "tweet_id": tweet_id,
            }
        )
    return rows


def _discord_limit(value: Any) -> int:
    return max(5, min(100, _safe_int(value, DISCORD_MESSAGES_LIMIT)))


def _fetch_discord_items(
    source_name: str,
    channel_id: str,
    max_messages: int,
    token: str,
) -> list[dict[str, Any]]:
    response = requests.get(
        f"https://discord.com/api/v10/channels/{channel_id}/messages",
        timeout=TIMEOUT_SECONDS,
        headers={
            "Authorization": f"Bot {token}",
            "User-Agent": "permanence-os-social-research-ingest",
        },
        params={"limit": _discord_limit(max_messages)},
    )
    if response.status_code == 401:
        raise RuntimeError("Discord API returned 401 Unauthorized. Regenerate PERMANENCE_DISCORD_BOT_TOKEN.")
    if response.status_code == 403:
        raise RuntimeError("Discord API returned 403 Forbidden. Ensure bot has view/read access in that channel.")
    if response.status_code == 404:
        raise RuntimeError("Discord API returned 404 Channel Not Found. Verify channel_id.")
    response.raise_for_status()

    payload = response.json()
    rows = payload if isinstance(payload, list) else []
    out: list[dict[str, Any]] = []
    for item in rows:
        if not isinstance(item, dict):
            continue
        content = str(item.get("content") or "").replace("\r", " ").replace("\n", " ").strip()
        attachments = item.get("attachments") if isinstance(item.get("attachments"), list) else []
        if not content and attachments:
            files = [str(att.get("filename") or "").strip() for att in attachments if isinstance(att, dict)]
            content = "attachments: " + ", ".join([f for f in files if f][:4])
        if not content:
            continue

        msg_id = str(item.get("id") or "").strip()
        guild_id = str(item.get("guild_id") or "").strip()
        link = f"https://discord.com/channels/{guild_id}/{channel_id}/{msg_id}" if (guild_id and msg_id) else ""
        title = content if len(content) <= 140 else (content[:137] + "...")
        out.append(
            {
                "source": source_name,
                "platform": "discord",
                "title": title,
                "link": link,
                "summary": content,
                "published": str(item.get("timestamp") or ""),
                "message_id": msg_id,
                "channel_id": channel_id,
            }
        )
    return out


def _first_text(node: ET.Element, names: list[str]) -> str:
    for name in names:
        found = node.find(name)
        if found is not None and found.text:
            return found.text.strip()
    return ""


def _parse_date(value: str) -> datetime | None:
    text = (value or "").strip()
    if not text:
        return None
    try:
        if "T" in text:
            return datetime.fromisoformat(text.replace("Z", "+00:00"))
        return parsedate_to_datetime(text).astimezone(timezone.utc)
    except Exception:  # noqa: BLE001
        return None


def _parse_items(xml_text: str, source_name: str, platform: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not xml_text.strip():
        return rows
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return rows

    for item in root.findall(".//item"):
        title = _first_text(item, ["title"])
        link = _first_text(item, ["link"])
        summary = _first_text(item, ["description"])
        published = _first_text(item, ["pubDate"])
        if not title:
            continue
        rows.append(
            {
                "source": source_name,
                "platform": platform,
                "title": title,
                "link": link,
                "summary": summary,
                "published": published,
            }
        )

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
        rows.append(
            {
                "source": source_name,
                "platform": platform,
                "title": title,
                "link": link,
                "summary": summary,
                "published": published,
            }
        )
    return rows[:MAX_ITEMS_PER_FEED]


def _score_item(item: dict[str, Any], keywords: list[str]) -> tuple[float, list[str]]:
    title = str(item.get("title") or "")
    summary = str(item.get("summary") or "")
    text = f"{title} {summary}".lower()
    matched = [kw for kw in keywords if kw in text]
    score = float(len(matched))
    published_at = _parse_date(str(item.get("published") or ""))
    if published_at is not None:
        age_hours = max(0.0, (_now() - published_at).total_seconds() / 3600.0)
        if age_hours <= 24:
            score += 1.5
        elif age_hours <= 72:
            score += 0.5
    if "?" in title:
        score += 0.2
    return round(score, 3), matched


def _text_blob(item: dict[str, Any]) -> str:
    title = str(item.get("title") or "")
    summary = str(item.get("summary") or "")
    return f"{title} {summary}".lower()


def _discernment_policy_values(policy: dict[str, Any]) -> dict[str, Any]:
    min_score_keep = max(0.0, float(policy.get("min_score_keep", 0.5)))
    require_match = bool(policy.get("require_keyword_match", False))
    drop_on_exclude = bool(policy.get("drop_on_exclude_match", False))
    include_bonus = max(0.0, float(policy.get("include_bonus", 0.25)))
    exclude_penalty = max(0.0, float(policy.get("exclude_penalty", 1.5)))
    freshness_half_life = max(1.0, float(policy.get("freshness_half_life_hours", 48.0)))
    freshness_max_bonus = max(0.0, float(policy.get("freshness_max_bonus", 1.5)))
    top_limit = max(1, min(200, _safe_int(policy.get("top_items_limit", 30), 30)))
    include_keywords = [str(v).strip().lower() for v in (policy.get("include_keywords") or []) if str(v).strip()]
    exclude_keywords = [str(v).strip().lower() for v in (policy.get("exclude_keywords") or []) if str(v).strip()]
    platform_weights_raw = policy.get("platform_weights") if isinstance(policy.get("platform_weights"), dict) else {}
    source_weights_raw = policy.get("source_weights") if isinstance(policy.get("source_weights"), dict) else {}
    platform_weights = {
        str(key).strip().lower(): _safe_float(value, 0.0)
        for key, value in platform_weights_raw.items()
        if str(key).strip()
    }
    source_weights = {
        str(key).strip().lower(): _safe_float(value, 0.0)
        for key, value in source_weights_raw.items()
        if str(key).strip()
    }
    return {
        "min_score_keep": min_score_keep,
        "require_keyword_match": require_match,
        "drop_on_exclude_match": drop_on_exclude,
        "include_bonus": include_bonus,
        "exclude_penalty": exclude_penalty,
        "freshness_half_life_hours": freshness_half_life,
        "freshness_max_bonus": freshness_max_bonus,
        "platform_weights": platform_weights,
        "source_weights": source_weights,
        "top_items_limit": top_limit,
        "include_keywords": include_keywords,
        "exclude_keywords": exclude_keywords,
    }


def _apply_discernment(
    ranked: list[dict[str, Any]],
    policy: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    cfg = _discernment_policy_values(policy)
    kept: list[dict[str, Any]] = []
    dropped: list[dict[str, Any]] = []

    for row in ranked:
        scored = dict(row)
        text = _text_blob(scored)
        include_hits = [kw for kw in cfg["include_keywords"] if kw in text]
        exclude_hits = [kw for kw in cfg["exclude_keywords"] if kw in text]
        base_score = float(scored.get("score") or 0.0)
        platform = str(scored.get("platform") or "").strip().lower()
        source_name = str(scored.get("source") or "").strip().lower()
        platform_bonus = float(cfg["platform_weights"].get(platform, 0.0))
        source_bonus = float(cfg["source_weights"].get(source_name, 0.0))

        freshness_bonus = 0.0
        published_at = _parse_date(str(scored.get("published") or ""))
        if published_at is not None:
            age_hours = max(0.0, (_now() - published_at).total_seconds() / 3600.0)
            decay = 0.5 ** (age_hours / float(cfg["freshness_half_life_hours"]))
            freshness_bonus = float(cfg["freshness_max_bonus"]) * decay

        score = (
            base_score
            + (len(include_hits) * cfg["include_bonus"])
            - (len(exclude_hits) * cfg["exclude_penalty"])
            + platform_bonus
            + source_bonus
            + freshness_bonus
        )
        keep = score >= cfg["min_score_keep"]
        reasons: list[str] = []
        if score < cfg["min_score_keep"]:
            reasons.append("score_below_min")
        if cfg["require_keyword_match"] and not (scored.get("matched_keywords") or include_hits):
            keep = False
            reasons.append("no_keyword_match")
        if cfg["drop_on_exclude_match"] and exclude_hits:
            keep = False
            reasons.append("exclude_keyword_match")

        scored["score"] = round(score, 3)
        scored["discernment"] = {
            "keep": keep,
            "include_hits": include_hits,
            "exclude_hits": exclude_hits,
            "platform_bonus": round(platform_bonus, 3),
            "source_bonus": round(source_bonus, 3),
            "freshness_bonus": round(freshness_bonus, 3),
            "reasons": reasons,
        }
        if keep:
            kept.append(scored)
        else:
            dropped.append(scored)

    kept.sort(key=lambda row: row.get("score", 0), reverse=True)
    dropped.sort(key=lambda row: row.get("score", 0), reverse=True)
    return kept, dropped, cfg


def _collect(feeds: list[dict[str, Any]], keywords: list[str]) -> tuple[list[dict[str, Any]], list[str]]:
    warnings: list[str] = []
    ranked: list[dict[str, Any]] = []
    for feed in feeds:
        if isinstance(feed.get("enabled"), bool) and not bool(feed.get("enabled")):
            continue
        name = str(feed.get("name") or "feed")
        url = str(feed.get("url") or "")
        platform = str(feed.get("platform") or "unknown")
        if platform.lower() in {"x", "twitter"}:
            query = str(feed.get("query") or "").strip()
            token = str(os.getenv(X_TOKEN_ENV, "")).strip()
            if not query:
                warnings.append(f"{name}: missing 'query' for X feed.")
                continue
            if not token:
                warnings.append(
                    f"{name}: missing {X_TOKEN_ENV}; skipping X feed. "
                    "Install token with `python cli.py connector-keychain --target social-read --from-file ...`."
                )
                continue
            max_results = _x_max_results(feed.get("max_results", X_DEFAULT_MAX_RESULTS))
            try:
                items = _fetch_x_items(
                    source_name=name,
                    query=query,
                    max_results=max_results,
                    token=token,
                )
                for item in items:
                    score, matched = _score_item(item, keywords)
                    row = dict(item)
                    row["score"] = score
                    row["matched_keywords"] = matched
                    ranked.append(row)
            except Exception as exc:  # noqa: BLE001
                warnings.append(f"{name}: {exc}")
            continue
        if platform.lower() == "discord":
            channel_id = str(feed.get("channel_id") or "").strip()
            token = str(os.getenv(DISCORD_BOT_TOKEN_ENV, "")).strip()
            if not channel_id:
                warnings.append(f"{name}: missing 'channel_id' for Discord feed.")
                continue
            if not token:
                warnings.append(
                    f"{name}: missing {DISCORD_BOT_TOKEN_ENV}; skipping Discord feed. "
                    "Install token with `python cli.py connector-keychain --target discord-bot-token --from-file ...`."
                )
                continue
            max_messages = _discord_limit(feed.get("max_messages", DISCORD_MESSAGES_LIMIT))
            try:
                items = _fetch_discord_items(
                    source_name=name,
                    channel_id=channel_id,
                    max_messages=max_messages,
                    token=token,
                )
                for item in items:
                    score, matched = _score_item(item, keywords)
                    row = dict(item)
                    row["score"] = score
                    row["matched_keywords"] = matched
                    ranked.append(row)
            except Exception as exc:  # noqa: BLE001
                warnings.append(f"{name}: {exc}")
            continue
        if platform.lower() == "youtube":
            feed_url = _youtube_feed_url(feed)
            if not feed_url:
                warnings.append(
                    f"{name}: missing youtube feed URL. Set `url` to a YouTube RSS feed or set `channel_id`."
                )
                continue
            try:
                xml_text = _fetch_text(feed_url)
                items = _parse_items(xml_text, source_name=name, platform=platform)
                for item in items:
                    score, matched = _score_item(item, keywords)
                    row = dict(item)
                    row["score"] = score
                    row["matched_keywords"] = matched
                    ranked.append(row)
            except Exception as exc:  # noqa: BLE001
                warnings.append(f"{name}: {exc}")
            continue
        if not url:
            continue
        try:
            xml_text = _fetch_text(url)
            items = _parse_items(xml_text, source_name=name, platform=platform)
            for item in items:
                score, matched = _score_item(item, keywords)
                row = dict(item)
                row["score"] = score
                row["matched_keywords"] = matched
                ranked.append(row)
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"{name}: {exc}")
    ranked.sort(key=lambda row: row.get("score", 0), reverse=True)
    return ranked, warnings


def _write_outputs(
    feeds_path: Path,
    feeds_status: str,
    policy_path: Path,
    policy_status: str,
    policy_cfg: dict[str, Any],
    keywords: list[str],
    ranked: list[dict[str, Any]],
    dropped: list[dict[str, Any]],
    warnings: list[str],
) -> tuple[Path, Path]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    TOOL_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _now().strftime("%Y%m%d-%H%M%S")
    md_path = OUTPUT_DIR / f"social_research_ingest_{stamp}.md"
    latest_md = OUTPUT_DIR / "social_research_ingest_latest.md"
    json_path = TOOL_DIR / f"social_research_ingest_{stamp}.json"

    top = ranked[: int(policy_cfg.get("top_items_limit", 30))]
    keyword_hits: dict[str, int] = {}
    for row in top:
        for keyword in row.get("matched_keywords") or []:
            keyword_hits[keyword] = keyword_hits.get(keyword, 0) + 1

    lines = [
        "# Social Research Ingest",
        "",
        f"Generated (UTC): {_now_iso()}",
        f"Feeds path: {feeds_path} ({feeds_status})",
        f"Discernment policy: {policy_path} ({policy_status})",
        f"Keywords: {', '.join(keywords)}",
        "",
        "## Summary",
        f"- Items ranked: {len(ranked)}",
        f"- Items filtered out: {len(dropped)}",
        f"- Top items shown: {len(top)}",
        f"- Min score keep: {policy_cfg.get('min_score_keep')}",
        f"- Unique keyword hits: {len(keyword_hits)}",
    ]
    if warnings:
        lines.append(f"- Warnings: {len(warnings)}")

    lines.extend(["", "## Top Trends"])
    if not top:
        lines.append("- No trend items collected.")
    for idx, row in enumerate(top, start=1):
        lines.append(
            f"{idx}. [{row.get('platform')}] {row.get('title')} | score={row.get('score')} | "
            f"keywords={','.join(row.get('matched_keywords') or []) or '-'}"
        )
        if row.get("link"):
            lines.append(f"   - link={row.get('link')}")

    lines.extend(["", "## Keyword Heat"])
    if not keyword_hits:
        lines.append("- No keyword matches.")
    else:
        for key, count in sorted(keyword_hits.items(), key=lambda item: item[1], reverse=True):
            lines.append(f"- {key}: {count}")

    if warnings:
        lines.extend(["", "## Warnings"])
        for warning in warnings:
            lines.append(f"- {warning}")

    lines.extend(
        [
            "",
            "## Governance Notes",
            "- Read-only trend collection. No social publishing endpoints are used.",
            "- Human review required before any outbound post or campaign action.",
            "",
        ]
    )

    report = "\n".join(lines)
    md_path.write_text(report, encoding="utf-8")
    latest_md.write_text(report, encoding="utf-8")

    payload = {
        "generated_at": _now_iso(),
        "feeds_path": str(feeds_path),
        "feeds_status": feeds_status,
        "policy_path": str(policy_path),
        "policy_status": policy_status,
        "policy": policy_cfg,
        "keyword_count": len(keywords),
        "item_count": len(ranked),
        "filtered_out_count": len(dropped),
        "top_items": top,
        "dropped_items": dropped[:20],
        "keyword_hits": keyword_hits,
        "warnings": warnings,
        "latest_markdown": str(latest_md),
    }
    json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return md_path, json_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only social trend ingest.")
    parser.add_argument("--force-template", action="store_true", help="Rewrite feeds template file")
    parser.add_argument("--force-policy", action="store_true", help="Rewrite discernment policy template file")
    args = parser.parse_args(argv)

    feeds, feeds_status = _ensure_feeds(FEEDS_PATH, force_template=args.force_template)
    policy, policy_status = _ensure_policy(POLICY_PATH, force_template=args.force_policy)
    keywords = _keywords()
    ranked_raw, warnings = _collect(feeds, keywords)
    ranked, dropped, policy_cfg = _apply_discernment(ranked_raw, policy)
    md_path, json_path = _write_outputs(
        FEEDS_PATH,
        feeds_status,
        POLICY_PATH,
        policy_status,
        policy_cfg,
        keywords,
        ranked,
        dropped,
        warnings,
    )

    print(f"Social research ingest written: {md_path}")
    print(f"Social research latest: {OUTPUT_DIR / 'social_research_ingest_latest.md'}")
    print(f"Tool payload written: {json_path}")
    print(f"Items ranked: {len(ranked)} | filtered_out: {len(dropped)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
