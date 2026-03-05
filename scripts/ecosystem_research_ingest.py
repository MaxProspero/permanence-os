#!/usr/bin/env python3
"""
Ecosystem research ingest:
- Tracks selected repositories, developers, docs, and communities
- Produces a scored digest for adoption/prioritization

Read-only collection only.
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
WORKING_DIR = Path(os.getenv("PERMANENCE_WORKING_DIR", str(BASE_DIR / "memory" / "working")))
OUTPUT_DIR = Path(os.getenv("PERMANENCE_OUTPUT_DIR", str(BASE_DIR / "outputs")))
TOOL_DIR = Path(os.getenv("PERMANENCE_TOOL_DIR", str(BASE_DIR / "memory" / "tool")))
WATCHLIST_PATH = Path(
    os.getenv("PERMANENCE_ECOSYSTEM_WATCHLIST_PATH", str(WORKING_DIR / "ecosystem_watchlist.json"))
)
TIMEOUT_SECONDS = int(os.getenv("PERMANENCE_ECOSYSTEM_TIMEOUT", "10"))

GITHUB_API = "https://api.github.com"


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


def _token() -> str:
    for name in ("PERMANENCE_GITHUB_READ_TOKEN", "GH_TOKEN", "GITHUB_TOKEN"):
        value = str(os.getenv(name, "")).strip()
        if value:
            return value
    return ""


def _headers() -> dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "permanence-os-ecosystem-research-ingest",
    }
    token = _token()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _default_watchlist() -> dict[str, Any]:
    return {
        "docs_urls": [
            "https://docs.github.com/en/copilot/concepts/agents/coding-agent/about-coding-agent",
            "https://docs.github.com/en/copilot/concepts/about-copilot-coding-agent",
            "https://docs.github.com/en/codespaces/overview",
            "https://docs.github.com/en/organizations/organizing-members-into-teams/about-teams",
            "https://docs.x.com/x-api/posts/bookmarks/introduction",
        ],
        "repos": [
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
            "mitchellh/vouch",
            "ranaroussi/yfinance",
            "ekzhu/datasketch",
        ],
        "developers": [
            "ruvnet",
            "mxsm",
            "tjx666",
            "stephenberry",
            "njbrake",
            "andimarafioti",
            "mitchellh",
            "aurelleb",
            "masagrator",
            "krille-chan",
            "Th0rgal",
            "ranaroussi",
            "1c7",
            "gunnarmorling",
            "eitsupi",
            "jasnell",
            "marcus",
            "zhayujie",
            "nisalgunawardhana",
            "dkhamsing",
            "bradygaster",
            "zkochan",
            "FagnerMartinsBrack",
            "Kitenite",
            "ekzhu",
        ],
        "communities": [
            "https://t.me/iccmafia",
            "https://discord.gg/tradesbysci",
            "https://discord.gg/bpKbBHGqg",
            "https://workos.com/changelog",
        ],
        "keywords": [
            "agent",
            "mcp",
            "orchestration",
            "workflow",
            "research",
            "finance",
            "trading",
            "memory",
            "copilot",
            "codespaces",
        ],
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
    for key in ["docs_urls", "repos", "developers", "communities", "keywords"]:
        if not isinstance(merged.get(key), list):
            merged[key] = defaults[key]
    if merged != payload:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(merged, indent=2) + "\n", encoding="utf-8")
        return merged, "updated"
    return merged, "existing"


def _fetch_repo(repo: str) -> dict[str, Any] | None:
    response = requests.get(f"{GITHUB_API}/repos/{repo}", headers=_headers(), timeout=TIMEOUT_SECONDS)
    if response.status_code >= 400:
        return None
    payload = response.json()
    return {
        "repo": repo,
        "stars": _safe_int(payload.get("stargazers_count"), 0),
        "forks": _safe_int(payload.get("forks_count"), 0),
        "open_issues": _safe_int(payload.get("open_issues_count"), 0),
        "language": str(payload.get("language") or ""),
        "updated_at": str(payload.get("updated_at") or ""),
        "description": str(payload.get("description") or "").strip(),
        "html_url": str(payload.get("html_url") or f"https://github.com/{repo}"),
    }


def _fetch_developer(login: str) -> dict[str, Any] | None:
    response = requests.get(f"{GITHUB_API}/users/{login}", headers=_headers(), timeout=TIMEOUT_SECONDS)
    if response.status_code >= 400:
        return None
    payload = response.json()
    return {
        "login": login,
        "name": str(payload.get("name") or "").strip(),
        "followers": _safe_int(payload.get("followers"), 0),
        "public_repos": _safe_int(payload.get("public_repos"), 0),
        "html_url": str(payload.get("html_url") or f"https://github.com/{login}"),
        "bio": str(payload.get("bio") or "").strip(),
    }


def _fetch_link_status(url: str) -> dict[str, Any]:
    status = 0
    try:
        response = requests.get(url, timeout=TIMEOUT_SECONDS, allow_redirects=True)
        status = int(response.status_code)
    except Exception:  # noqa: BLE001
        status = 0
    return {"url": url, "status": status, "reachable": status >= 200 and status < 400}


def _score_repo(row: dict[str, Any], keywords: list[str]) -> float:
    stars = _safe_int(row.get("stars"), 0)
    forks = _safe_int(row.get("forks"), 0)
    desc = str(row.get("description") or "").lower()
    hits = sum(1 for kw in keywords if kw and kw in desc)
    score = min(100.0, stars * 0.001 + forks * 0.002 + hits * 6.0)
    return round(score, 2)


def _score_dev(row: dict[str, Any]) -> float:
    followers = _safe_int(row.get("followers"), 0)
    repos = _safe_int(row.get("public_repos"), 0)
    score = min(100.0, followers * 0.01 + repos * 0.2)
    return round(score, 2)


def _write_outputs(
    watchlist_path: Path,
    watchlist_status: str,
    repos: list[dict[str, Any]],
    developers: list[dict[str, Any]],
    docs: list[dict[str, Any]],
    communities: list[dict[str, Any]],
    warnings: list[str],
) -> tuple[Path, Path]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    TOOL_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _now().strftime("%Y%m%d-%H%M%S")
    md_path = OUTPUT_DIR / f"ecosystem_research_ingest_{stamp}.md"
    latest_md = OUTPUT_DIR / "ecosystem_research_ingest_latest.md"
    json_path = TOOL_DIR / f"ecosystem_research_ingest_{stamp}.json"

    lines = [
        "# Ecosystem Research Ingest",
        "",
        f"Generated (UTC): {_now_iso()}",
        f"Watchlist path: {watchlist_path} ({watchlist_status})",
        "",
        "## Summary",
        f"- Repositories analyzed: {len(repos)}",
        f"- Developers analyzed: {len(developers)}",
        f"- Docs links checked: {len(docs)}",
        f"- Community links checked: {len(communities)}",
    ]
    if warnings:
        lines.append(f"- Warnings: {len(warnings)}")

    lines.extend(["", "## Top Repositories"])
    if not repos:
        lines.append("- No repositories resolved.")
    for idx, row in enumerate(sorted(repos, key=lambda r: r.get("priority_score", 0), reverse=True)[:12], start=1):
        lines.append(
            f"{idx}. {row.get('repo')} | score={row.get('priority_score')} | stars={row.get('stars')} | lang={row.get('language') or '-'}"
        )

    lines.extend(["", "## Top Developers"])
    if not developers:
        lines.append("- No developers resolved.")
    for idx, row in enumerate(sorted(developers, key=lambda r: r.get("priority_score", 0), reverse=True)[:12], start=1):
        lines.append(
            f"{idx}. @{row.get('login')} | score={row.get('priority_score')} | followers={row.get('followers')} | repos={row.get('public_repos')}"
        )

    lines.extend(["", "## Docs Health"])
    for row in docs:
        lines.append(f"- {row.get('status') or 0} | {row.get('url')}")

    lines.extend(["", "## Communities Health"])
    for row in communities:
        lines.append(f"- {row.get('status') or 0} | {row.get('url')}")

    if warnings:
        lines.extend(["", "## Warnings"])
        for warning in warnings:
            lines.append(f"- {warning}")

    lines.extend(
        [
            "",
            "## Governance Notes",
            "- Read-only ecosystem intelligence: no write actions to GitHub/X/Discord/Telegram.",
            "- Manual approval required before adopting code, posting, or execution changes.",
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
        "repo_count": len(repos),
        "developer_count": len(developers),
        "docs_count": len(docs),
        "communities_count": len(communities),
        "repos": repos,
        "developers": developers,
        "docs": docs,
        "communities": communities,
        "warnings": warnings,
        "latest_markdown": str(latest_md),
    }
    json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return md_path, json_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ingest ecosystem watchlist: repos, devs, docs, communities.")
    parser.add_argument("--force-template", action="store_true", help="Rewrite ecosystem watchlist template")
    args = parser.parse_args(argv)

    watchlist, watchlist_status = _ensure_watchlist(WATCHLIST_PATH, force_template=args.force_template)
    keywords = [str(v).strip().lower() for v in (watchlist.get("keywords") or []) if str(v).strip()]

    warnings: list[str] = []
    repos: list[dict[str, Any]] = []
    for repo in [str(v).strip() for v in (watchlist.get("repos") or []) if str(v).strip()]:
        row = _fetch_repo(repo)
        if row is None:
            warnings.append(f"repo_not_found_or_blocked: {repo}")
            continue
        row["priority_score"] = _score_repo(row, keywords)
        repos.append(row)

    developers: list[dict[str, Any]] = []
    for login in [str(v).strip() for v in (watchlist.get("developers") or []) if str(v).strip()]:
        row = _fetch_developer(login)
        if row is None:
            warnings.append(f"developer_not_found_or_blocked: {login}")
            continue
        row["priority_score"] = _score_dev(row)
        developers.append(row)

    docs = [_fetch_link_status(str(url).strip()) for url in (watchlist.get("docs_urls") or []) if str(url).strip()]
    communities = [
        _fetch_link_status(str(url).strip()) for url in (watchlist.get("communities") or []) if str(url).strip()
    ]

    md_path, json_path = _write_outputs(
        watchlist_path=WATCHLIST_PATH,
        watchlist_status=watchlist_status,
        repos=repos,
        developers=developers,
        docs=docs,
        communities=communities,
        warnings=warnings,
    )
    print(f"Ecosystem research ingest written: {md_path}")
    print(f"Ecosystem research latest: {OUTPUT_DIR / 'ecosystem_research_ingest_latest.md'}")
    print(f"Tool payload written: {json_path}")
    print(f"Repos={len(repos)} Developers={len(developers)} Docs={len(docs)} Communities={len(communities)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
