#!/usr/bin/env python3
"""
Ingest GitHub trending repositories and score opportunities.

Read-only collection only. No GitHub write actions are performed.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

BASE_DIR = Path(__file__).resolve().parents[1]
WORKING_DIR = Path(os.getenv("PERMANENCE_WORKING_DIR", str(BASE_DIR / "memory" / "working")))
OUTPUT_DIR = Path(os.getenv("PERMANENCE_OUTPUT_DIR", str(BASE_DIR / "outputs")))
TOOL_DIR = Path(os.getenv("PERMANENCE_TOOL_DIR", str(BASE_DIR / "memory" / "tool")))
FOCUS_PATH = Path(
    os.getenv("PERMANENCE_GITHUB_TRENDING_FOCUS_PATH", str(WORKING_DIR / "github_trending_focus.json"))
)
TIMEOUT_SECONDS = int(os.getenv("PERMANENCE_GITHUB_TRENDING_TIMEOUT", "10"))
TRENDING_BASE_URL = os.getenv("PERMANENCE_GITHUB_TRENDING_URL", "https://github.com/trending")

TRENDING_ARTICLE_RE = re.compile(r"<article[^>]*class=\"[^\"]*Box-row[^\"]*\"[^>]*>(.*?)</article>", re.DOTALL)
REPO_PATH_RE = re.compile(r"href=\"/(?P<owner>[A-Za-z0-9_.-]+)/(?P<repo>[A-Za-z0-9_.-]+)\"")
STARS_PERIOD_RE = re.compile(r"([\d,]+)\s+stars?\s+(today|this week|this month)", re.IGNORECASE)
TOTAL_STARS_RE = re.compile(r"href=\"/[^\"]+/stargazers\"[^>]*>\s*([\d,]+)\s*</a>", re.IGNORECASE)
LANG_RE = re.compile(r"programmingLanguage\">\s*([^<]+)\s*</span>", re.IGNORECASE)
DESC_RE = re.compile(r"<p[^>]*>\s*(.*?)\s*</p>", re.DOTALL)
TAG_RE = re.compile(r"<[^>]+>")


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


def _clean_text(raw_html: str) -> str:
    text = TAG_RE.sub(" ", raw_html)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _token() -> str:
    for name in ("PERMANENCE_GITHUB_READ_TOKEN", "GH_TOKEN", "GITHUB_TOKEN"):
        value = str(os.getenv(name, "")).strip()
        if value:
            return value
    return ""


def _headers() -> dict[str, str]:
    headers = {"User-Agent": "permanence-os-github-trending-ingest"}
    token = _token()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _default_focus() -> dict[str, Any]:
    return {
        "since": "daily",
        "languages": ["python", "typescript", "rust"],
        "top_limit": 30,
        "watchlist_repos": [
            "MaxProspero/permanence-os",
            "ytdl-org/youtube-dl",
            "Asabeneh/30-Days-Of-Python",
            "tw93/Pake",
            "KRTirtho/spotube",
            "glanceapp/glance",
            "iawia002/lux",
            "InternLM/xtuner",
            "shaxiu/XianyuAutoAgent",
            "getsentry/XcodeBuildMCP",
            "mvanhorn/last30days-skill",
            "Josh-XT/AGiXT",
            "EvoAgentX/EvoAgentX",
            "ValueCell-ai/ClawX",
            "0xNyk/xint-rs",
            "qdev89/AppXDev.Opengravity",
            "xingbo778/xbworld",
            "azizkode/ArXiv-Agent",
            "maddada/agent-manager-x",
            "ruvnet/RuView",
            "moeru-ai/airi",
            "anthropics/prompt-eng-interactive-tutorial",
            "ruvnet/ruflo",
            "alibaba/OpenSandbox",
            "microsoft/markitdown",
            "K-Dense-AI/claude-scientific-skills",
            "superset-sh/superset",
            "servo/servo",
        ],
        "keywords": [
            "agent",
            "mcp",
            "automation",
            "finance",
            "trading",
            "quant",
            "research",
            "knowledge",
            "dashboard",
            "workflow",
        ],
        "updated_at": _now_iso(),
    }


def _ensure_focus(path: Path, force_template: bool) -> tuple[dict[str, Any], str]:
    defaults = _default_focus()
    if force_template or not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(defaults, indent=2) + "\n", encoding="utf-8")
        return defaults, "written"

    payload = _read_json(path, {})
    if not isinstance(payload, dict):
        payload = {}
    merged = dict(defaults)
    merged.update(payload)
    if not isinstance(merged.get("languages"), list):
        merged["languages"] = defaults["languages"]
    if not isinstance(merged.get("watchlist_repos"), list):
        merged["watchlist_repos"] = defaults["watchlist_repos"]
    if not isinstance(merged.get("keywords"), list):
        merged["keywords"] = defaults["keywords"]
    merged["top_limit"] = max(5, min(100, _safe_int(merged.get("top_limit"), 30)))
    if merged != payload:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(merged, indent=2) + "\n", encoding="utf-8")
        return merged, "updated"
    return merged, "existing"


def _fetch_trending_html(language: str, since: str) -> str:
    language_path = f"/{language.strip().lower()}" if language.strip() else ""
    url = f"{TRENDING_BASE_URL}{language_path}"
    response = requests.get(
        url,
        params={"since": since},
        headers=_headers(),
        timeout=TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    return response.text


def _parse_trending_items(html: str, language_hint: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for article in TRENDING_ARTICLE_RE.findall(html):
        repo_match = REPO_PATH_RE.search(article)
        if not repo_match:
            continue
        owner = repo_match.group("owner").strip()
        repo = repo_match.group("repo").strip()
        full_repo = f"{owner}/{repo}"

        desc_match = DESC_RE.search(article)
        desc = _clean_text(desc_match.group(1)) if desc_match else ""
        lang_match = LANG_RE.search(article)
        language = (lang_match.group(1).strip() if lang_match else language_hint)

        stars_period_match = STARS_PERIOD_RE.search(article)
        stars_period_value = 0
        stars_period_label = ""
        if stars_period_match:
            stars_period_value = _safe_int(stars_period_match.group(1).replace(",", ""), 0)
            stars_period_label = stars_period_match.group(2).strip().lower()

        total_stars_match = TOTAL_STARS_RE.search(article)
        total_stars = _safe_int(total_stars_match.group(1).replace(",", ""), 0) if total_stars_match else 0

        rows.append(
            {
                "repo": full_repo,
                "owner": owner,
                "name": repo,
                "language": language,
                "description": desc,
                "stars_period": stars_period_value,
                "stars_period_label": stars_period_label,
                "stars_total": total_stars,
                "url": f"https://github.com/{full_repo}",
            }
        )
    return rows


def _score_items(items: list[dict[str, Any]], focus: dict[str, Any]) -> list[dict[str, Any]]:
    watchlist = {
        str(v).strip().lower() for v in (focus.get("watchlist_repos") or []) if str(v).strip()
    }
    keywords = [str(v).strip().lower() for v in (focus.get("keywords") or []) if str(v).strip()]

    scored: list[dict[str, Any]] = []
    for row in items:
        item = dict(row)
        repo_l = str(item.get("repo") or "").strip().lower()
        desc_l = str(item.get("description") or "").strip().lower()

        keyword_hits = [kw for kw in keywords if kw and (kw in repo_l or kw in desc_l)]
        watchlist_hit = repo_l in watchlist
        stars_period = _safe_int(item.get("stars_period"), 0)

        score = min(100.0, stars_period * 0.02)
        if watchlist_hit:
            score += 30.0
        score += len(keyword_hits) * 4.5
        if str(item.get("language") or "").strip().lower() in {"python", "typescript", "rust", "go"}:
            score += 4.0

        item["priority_score"] = round(min(100.0, score), 2)
        item["watchlist_hit"] = watchlist_hit
        item["keyword_hits"] = keyword_hits
        scored.append(item)

    scored.sort(key=lambda r: r.get("priority_score", 0), reverse=True)
    return scored


def _dedupe(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for row in rows:
        key = str(row.get("repo") or "").strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(row)
    return out


def _write_outputs(
    focus_path: Path,
    focus_status: str,
    scored: list[dict[str, Any]],
    warnings: list[str],
    source_languages: list[str],
    since: str,
) -> tuple[Path, Path]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    TOOL_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _now().strftime("%Y%m%d-%H%M%S")
    md_path = OUTPUT_DIR / f"github_trending_ingest_{stamp}.md"
    latest_md = OUTPUT_DIR / "github_trending_ingest_latest.md"
    json_path = TOOL_DIR / f"github_trending_ingest_{stamp}.json"

    watchlist_hits = sum(1 for row in scored if bool(row.get("watchlist_hit")))
    top = scored[:30]

    lines = [
        "# GitHub Trending Ingest",
        "",
        f"Generated (UTC): {_now_iso()}",
        f"Focus path: {focus_path} ({focus_status})",
        f"Since window: {since}",
        f"Languages: {', '.join(source_languages)}",
        "",
        "## Summary",
        f"- Trending repositories collected: {len(scored)}",
        f"- Watchlist overlaps: {watchlist_hits}",
        f"- Top entries shown: {len(top)}",
    ]
    if warnings:
        lines.append(f"- Warnings: {len(warnings)}")

    lines.extend(["", "## Ranked Repositories"])
    if not top:
        lines.append("- No trending repositories parsed.")
    for idx, row in enumerate(top, start=1):
        lines.append(
            f"{idx}. {row.get('repo')} | score={row.get('priority_score')} | "
            f"stars={row.get('stars_period')} {row.get('stars_period_label') or ''} | "
            f"lang={row.get('language') or '-'}"
        )
        if row.get("watchlist_hit"):
            lines.append("   - watchlist_hit=true")
        if row.get("keyword_hits"):
            lines.append(f"   - keyword_hits={','.join(row.get('keyword_hits') or [])}")
        if row.get("description"):
            lines.append(f"   - {row.get('description')}")

    if warnings:
        lines.extend(["", "## Warnings"])
        for warning in warnings:
            lines.append(f"- {warning}")

    lines.extend(
        [
            "",
            "## Governance Notes",
            "- Trending ingest is read-only and does not clone or execute untrusted code.",
            "- Treat trending repos as research inputs; manual approval remains required.",
            "",
        ]
    )

    report = "\n".join(lines)
    md_path.write_text(report, encoding="utf-8")
    latest_md.write_text(report, encoding="utf-8")

    payload = {
        "generated_at": _now_iso(),
        "focus_path": str(focus_path),
        "focus_status": focus_status,
        "since": since,
        "languages": source_languages,
        "repo_count": len(scored),
        "watchlist_hit_count": watchlist_hits,
        "top_items": top,
        "warnings": warnings,
        "latest_markdown": str(latest_md),
    }
    json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return md_path, json_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Collect and score GitHub trending repositories.")
    parser.add_argument("--force-template", action="store_true", help="Rewrite focus template file")
    parser.add_argument("--since", choices=["daily", "weekly", "monthly"], help="Override trending window")
    args = parser.parse_args(argv)

    focus, focus_status = _ensure_focus(FOCUS_PATH, force_template=args.force_template)
    since = str(args.since or focus.get("since") or "daily").strip().lower()
    if since not in {"daily", "weekly", "monthly"}:
        since = "daily"

    languages = [str(v).strip().lower() for v in (focus.get("languages") or []) if str(v).strip()]
    if not languages:
        languages = ["python", "typescript", "rust"]

    items: list[dict[str, Any]] = []
    warnings: list[str] = []
    for language in languages:
        try:
            html = _fetch_trending_html(language=language, since=since)
            rows = _parse_trending_items(html, language_hint=language)
            items.extend(rows)
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"{language}: {exc}")

    deduped = _dedupe(items)
    scored = _score_items(deduped, focus)
    top_limit = max(5, min(100, _safe_int(focus.get("top_limit"), 30)))
    scored = scored[:top_limit]

    md_path, json_path = _write_outputs(
        focus_path=FOCUS_PATH,
        focus_status=focus_status,
        scored=scored,
        warnings=warnings,
        source_languages=languages,
        since=since,
    )
    print(f"GitHub trending ingest written: {md_path}")
    print(f"GitHub trending latest: {OUTPUT_DIR / 'github_trending_ingest_latest.md'}")
    print(f"Tool payload written: {json_path}")
    print(f"Repositories collected: {len(scored)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
