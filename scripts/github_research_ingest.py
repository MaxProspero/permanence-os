#!/usr/bin/env python3
"""
Ingest read-only GitHub signals and produce improvement suggestions.

This script never performs write actions against GitHub.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from datetime import datetime, timedelta, timezone
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

TARGETS_PATH = Path(
    os.getenv("PERMANENCE_GITHUB_RESEARCH_TARGETS_PATH", str(WORKING_DIR / "github_research_targets.json"))
)
TIMEOUT_SECONDS = int(os.getenv("PERMANENCE_GITHUB_TIMEOUT", "10"))
MAX_ITEMS = int(os.getenv("PERMANENCE_GITHUB_MAX_ITEMS", "20"))
STALE_DAYS = int(os.getenv("PERMANENCE_GITHUB_STALE_DAYS", "14"))
API_BASE = "https://api.github.com"


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


def _infer_repo_from_git_remote() -> str | None:
    try:
        proc = subprocess.run(
            ["git", "-C", str(BASE_DIR), "config", "--get", "remote.origin.url"],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return None
    remote = (proc.stdout or "").strip()
    if not remote:
        return None
    match = re.search(r"github\.com[:/](?P<owner>[^/]+)/(?P<repo>[^/.]+)(?:\.git)?$", remote)
    if not match:
        return None
    return f"{match.group('owner')}/{match.group('repo')}"


def _default_targets() -> list[dict[str, Any]]:
    inferred = _infer_repo_from_git_remote()
    default_repo = inferred or "octocat/Hello-World"
    return [
        {
            "repo": default_repo,
            "enabled": True,
            "focus_labels": ["bug", "enhancement", "help wanted"],
            "max_items": MAX_ITEMS,
        }
    ]


def _ensure_targets(path: Path, force_template: bool) -> tuple[list[dict[str, Any]], str]:
    if path.exists() and not force_template:
        payload = _read_json(path, [])
        if isinstance(payload, list):
            rows = [row for row in payload if isinstance(row, dict) and str(row.get("repo") or "").strip()]
            return (rows or _default_targets()), "existing"
    rows = _default_targets()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    return rows, "written"


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
        "User-Agent": "permanence-os-github-research-ingest",
    }
    token = _token()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _fetch_json(path: str, params: dict[str, Any] | None = None) -> Any:
    response = requests.get(
        f"{API_BASE}{path}",
        headers=_headers(),
        params=params or {},
        timeout=TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    return response.json()


def _parse_ts(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def _is_stale(updated_at: Any, days: int) -> bool:
    dt = _parse_ts(updated_at)
    if dt is None:
        return False
    return (_now() - dt) > timedelta(days=days)


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    return []


def _focus_labels_from_target(row: dict[str, Any]) -> set[str]:
    labels = row.get("focus_labels")
    if isinstance(labels, list):
        cleaned = {str(item).strip().lower() for item in labels if str(item).strip()}
        if cleaned:
            return cleaned
    return {"bug", "enhancement", "help wanted", "security"}


def _collect_repo(repo: str, max_items: int, stale_days: int, focus_labels: set[str]) -> tuple[dict[str, Any], list[str]]:
    warnings: list[str] = []
    result: dict[str, Any] = {
        "repo": repo,
        "fetched": False,
        "open_issues": 0,
        "open_prs": 0,
        "stale_issues": 0,
        "stale_prs": 0,
        "focus_label_hits": 0,
        "top_actions": [],
        "issues": [],
        "prs": [],
    }
    try:
        metadata = _fetch_json(f"/repos/{repo}")
        result["default_branch"] = metadata.get("default_branch")
        result["stars"] = metadata.get("stargazers_count", 0)
        result["fetched"] = True
    except Exception as exc:  # noqa: BLE001
        warnings.append(f"{repo}: metadata fetch failed ({exc})")
        return result, warnings

    try:
        issues = _as_list(
            _fetch_json(
                f"/repos/{repo}/issues",
                params={"state": "open", "per_page": max(1, min(100, max_items))},
            )
        )
    except Exception as exc:  # noqa: BLE001
        issues = []
        warnings.append(f"{repo}: issues fetch failed ({exc})")

    try:
        prs = _as_list(
            _fetch_json(
                f"/repos/{repo}/pulls",
                params={
                    "state": "open",
                    "per_page": max(1, min(100, max_items)),
                    "sort": "updated",
                    "direction": "desc",
                },
            )
        )
    except Exception as exc:  # noqa: BLE001
        prs = []
        warnings.append(f"{repo}: pulls fetch failed ({exc})")

    issue_rows = [row for row in issues if isinstance(row, dict) and "pull_request" not in row]
    pr_rows = [row for row in prs if isinstance(row, dict)]

    stale_issues = [row for row in issue_rows if _is_stale(row.get("updated_at"), stale_days)]
    stale_prs = [row for row in pr_rows if _is_stale(row.get("updated_at"), stale_days)]

    focus_hits = 0
    for row in issue_rows:
        labels = [str((label or {}).get("name") or "").strip().lower() for label in _as_list(row.get("labels"))]
        if any(label in focus_labels for label in labels):
            focus_hits += 1

    actions: list[str] = []
    if stale_prs:
        actions.append(f"Review {len(stale_prs)} stale PR(s) older than {stale_days} days.")
    if stale_issues:
        actions.append(f"Triage {len(stale_issues)} stale issue(s) and close/update owners.")
    if focus_hits:
        actions.append(f"Address {focus_hits} focus-labeled issue(s): {', '.join(sorted(focus_labels))}.")
    if not actions:
        actions.append("No critical backlog signals detected; continue normal iteration cadence.")

    result.update(
        {
            "open_issues": len(issue_rows),
            "open_prs": len(pr_rows),
            "stale_issues": len(stale_issues),
            "stale_prs": len(stale_prs),
            "focus_label_hits": focus_hits,
            "top_actions": actions[:5],
            "issues": [
                {
                    "number": row.get("number"),
                    "title": row.get("title"),
                    "html_url": row.get("html_url"),
                    "updated_at": row.get("updated_at"),
                }
                for row in issue_rows[:10]
            ],
            "prs": [
                {
                    "number": row.get("number"),
                    "title": row.get("title"),
                    "html_url": row.get("html_url"),
                    "updated_at": row.get("updated_at"),
                }
                for row in pr_rows[:10]
            ],
        }
    )
    return result, warnings


def _write_outputs(
    targets_path: Path,
    targets_status: str,
    repos: list[dict[str, Any]],
    warnings: list[str],
) -> tuple[Path, Path]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    TOOL_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _now().strftime("%Y%m%d-%H%M%S")
    md_path = OUTPUT_DIR / f"github_research_ingest_{stamp}.md"
    latest_md = OUTPUT_DIR / "github_research_ingest_latest.md"
    json_path = TOOL_DIR / f"github_research_ingest_{stamp}.json"

    lines = [
        "# GitHub Research Ingest",
        "",
        f"Generated (UTC): {_now_iso()}",
        f"Targets path: {targets_path} ({targets_status})",
        f"Token configured: {'yes' if bool(_token()) else 'no'}",
        "",
        "## Summary",
        f"- Repositories scanned: {len(repos)}",
        f"- Total open issues: {sum(int(r.get('open_issues') or 0) for r in repos)}",
        f"- Total open PRs: {sum(int(r.get('open_prs') or 0) for r in repos)}",
        f"- Total stale items: {sum(int(r.get('stale_issues') or 0) + int(r.get('stale_prs') or 0) for r in repos)}",
    ]
    if warnings:
        lines.append(f"- Warnings: {len(warnings)}")

    lines.extend(["", "## Repo Breakdown"])
    if not repos:
        lines.append("- No repositories configured.")
    for row in repos:
        lines.extend(
            [
                f"- {row.get('repo')}",
                (
                    "  "
                    f"open_issues={row.get('open_issues')} | open_prs={row.get('open_prs')} | "
                    f"stale_issues={row.get('stale_issues')} | stale_prs={row.get('stale_prs')} | "
                    f"focus_label_hits={row.get('focus_label_hits')}"
                ),
            ]
        )
        for action in row.get("top_actions") or []:
            lines.append(f"  action: {action}")

    if warnings:
        lines.extend(["", "## Warnings"])
        for warning in warnings:
            lines.append(f"- {warning}")

    lines.extend(
        [
            "",
            "## Governance Notes",
            "- Read-only collection only. No GitHub write endpoints are called.",
            "- Keep write/publish tokens disabled unless explicit human approval workflow is enabled.",
            "",
        ]
    )

    report = "\n".join(lines)
    md_path.write_text(report, encoding="utf-8")
    latest_md.write_text(report, encoding="utf-8")

    payload = {
        "generated_at": _now_iso(),
        "targets_path": str(targets_path),
        "targets_status": targets_status,
        "token_configured": bool(_token()),
        "repo_count": len(repos),
        "repos": repos,
        "warnings": warnings,
        "latest_markdown": str(latest_md),
    }
    json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return md_path, json_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only GitHub research ingest.")
    parser.add_argument("--force-template", action="store_true", help="Rewrite targets template file")
    parser.add_argument("--max-items", type=int, default=MAX_ITEMS, help="Max open issues/PRs per repo")
    parser.add_argument("--stale-days", type=int, default=STALE_DAYS, help="Stale threshold in days")
    args = parser.parse_args(argv)

    targets, targets_status = _ensure_targets(TARGETS_PATH, force_template=args.force_template)
    enabled_targets = [row for row in targets if bool(row.get("enabled", True))]

    repos: list[dict[str, Any]] = []
    warnings: list[str] = []
    for row in enabled_targets:
        repo = str(row.get("repo") or "").strip()
        if not repo:
            continue
        item_max = int(row.get("max_items") or args.max_items)
        item_stale = int(row.get("stale_days") or args.stale_days)
        labels = _focus_labels_from_target(row)
        repo_result, repo_warnings = _collect_repo(
            repo,
            max_items=max(1, item_max),
            stale_days=max(1, item_stale),
            focus_labels=labels,
        )
        repos.append(repo_result)
        warnings.extend(repo_warnings)

    md_path, json_path = _write_outputs(TARGETS_PATH, targets_status, repos, warnings)
    print(f"GitHub research ingest written: {md_path}")
    print(f"GitHub research latest: {OUTPUT_DIR / 'github_research_ingest_latest.md'}")
    print(f"Tool payload written: {json_path}")
    print(f"Repositories scanned: {len(repos)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
