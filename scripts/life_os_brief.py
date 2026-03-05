#!/usr/bin/env python3
"""
Generate a daily Life OS brief for personal second-brain operations.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parents[1]
WORKING_DIR = Path(os.getenv("PERMANENCE_WORKING_DIR", str(BASE_DIR / "memory" / "working")))
OUTPUT_DIR = Path(os.getenv("PERMANENCE_OUTPUT_DIR", str(BASE_DIR / "outputs")))
TOOL_DIR = Path(os.getenv("PERMANENCE_TOOL_DIR", str(BASE_DIR / "memory" / "tool")))

PROFILE_PATH = Path(os.getenv("PERMANENCE_LIFE_PROFILE_PATH", str(WORKING_DIR / "life_profile.json")))
TASKS_PATH = Path(os.getenv("PERMANENCE_LIFE_TASKS_PATH", str(WORKING_DIR / "life_tasks.json")))


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def _default_profile() -> dict[str, Any]:
    return {
        "owner": "Operator",
        "north_star": "Build a high-trust life and business operating system.",
        "identity_principles": [
            "Protect focus before urgency.",
            "Compounding actions over heroic sprints.",
            "Health, relationships, and cash flow are equal pillars.",
        ],
        "daily_non_negotiables": [
            "Sleep plan and hydration check",
            "25-minute language output sprint",
            "Top revenue action before noon",
            "Family and relationship touchpoint",
        ],
        "weekly_focus": [
            "Ship one meaningful system upgrade.",
            "Advance one income stream by one stage.",
        ],
    }


def _default_tasks() -> list[dict[str, Any]]:
    return [
        {
            "task_id": "LIFE-001",
            "title": "Run language output sprint",
            "domain": "cognitive",
            "priority": "high",
            "status": "open",
            "due": "today",
            "next_action": "Speak or write for 10 minutes and capture corrections.",
        },
        {
            "task_id": "LIFE-002",
            "title": "Execute top revenue action",
            "domain": "business",
            "priority": "high",
            "status": "open",
            "due": "today",
            "next_action": "Complete one outreach or closing action.",
        },
        {
            "task_id": "LIFE-003",
            "title": "Health baseline reset",
            "domain": "health",
            "priority": "normal",
            "status": "open",
            "due": "today",
            "next_action": "Get steps and hydration minimums done before evening.",
        },
    ]


def _load_profile() -> dict[str, Any]:
    payload = _read_json(PROFILE_PATH, {})
    if not isinstance(payload, dict):
        payload = {}
    profile = dict(_default_profile())
    profile.update(payload)
    return profile


def _load_tasks() -> list[dict[str, Any]]:
    payload = _read_json(TASKS_PATH, [])
    if not isinstance(payload, list):
        payload = []
    rows = [row for row in payload if isinstance(row, dict)]
    if not rows:
        rows = _default_tasks()
    return rows


def _priority_rank(value: Any) -> int:
    text = str(value or "").strip().lower()
    if text == "high":
        return 0
    if text == "normal":
        return 1
    return 2


def _open_tasks(tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for row in tasks:
        status = str(row.get("status") or "open").strip().lower()
        if status in {"done", "closed"}:
            continue
        rows.append(row)
    rows.sort(
        key=lambda row: (
            _priority_rank(row.get("priority")),
            str(row.get("due") or ""),
            str(row.get("task_id") or ""),
        )
    )
    return rows


def _build_domain_counts(tasks: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in tasks:
        domain = str(row.get("domain") or "general").strip().lower()
        counts[domain] = counts.get(domain, 0) + 1
    return counts


def _write_outputs(profile: dict[str, Any], tasks: list[dict[str, Any]]) -> tuple[Path, Path]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    TOOL_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _now().strftime("%Y%m%d-%H%M%S")
    md_path = OUTPUT_DIR / f"life_os_brief_{stamp}.md"
    latest_md = OUTPUT_DIR / "life_os_brief_latest.md"
    json_path = TOOL_DIR / f"life_os_brief_{stamp}.json"

    open_rows = _open_tasks(tasks)
    top_rows = open_rows[:7]
    domain_counts = _build_domain_counts(open_rows)

    lines = [
        "# Life OS Brief",
        "",
        f"Generated (UTC): {_now().isoformat()}",
        f"Profile source: {PROFILE_PATH}",
        f"Task source: {TASKS_PATH}",
        "",
        "## North Star",
        f"- {profile.get('north_star')}",
        "",
        "## Identity Principles",
    ]
    for item in profile.get("identity_principles") or []:
        lines.append(f"- {item}")

    lines.extend(["", "## Daily Non-Negotiables"])
    for item in profile.get("daily_non_negotiables") or []:
        lines.append(f"- {item}")

    lines.extend(["", "## Weekly Focus"])
    for item in profile.get("weekly_focus") or []:
        lines.append(f"- {item}")

    lines.extend(["", "## Top Actions (Today)"])
    if not top_rows:
        lines.append("- No open life tasks. Add tasks to maintain momentum.")
    for idx, row in enumerate(top_rows, start=1):
        lines.extend(
            [
                f"{idx}. [{row.get('priority', 'normal')}] {row.get('title', 'Untitled')} ({row.get('task_id', 'n/a')})",
                f"   - domain={row.get('domain', 'general')} | due={row.get('due', '-')}",
                f"   - next_action={row.get('next_action', '-')}",
            ]
        )

    lines.extend(["", "## Open Task Load by Domain"])
    if not domain_counts:
        lines.append("- No open tasks.")
    else:
        for domain, count in sorted(domain_counts.items()):
            lines.append(f"- {domain}: {count}")

    lines.extend(
        [
            "",
            "## Governance Notes",
            "- This brief is advisory and human-directed.",
            "- Financial or health decisions remain manual by design.",
            "",
        ]
    )

    report = "\n".join(lines)
    md_path.write_text(report, encoding="utf-8")
    latest_md.write_text(report, encoding="utf-8")

    payload = {
        "generated_at": _now().isoformat(),
        "profile_path": str(PROFILE_PATH),
        "tasks_path": str(TASKS_PATH),
        "owner": profile.get("owner"),
        "top_actions": top_rows,
        "open_task_count": len(open_rows),
        "domain_counts": domain_counts,
        "latest_markdown": str(latest_md),
    }
    json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return md_path, json_path


def main() -> int:
    profile = _load_profile()
    tasks = _load_tasks()
    md_path, json_path = _write_outputs(profile, tasks)
    print(f"Life OS brief written: {md_path}")
    print(f"Life OS brief latest: {OUTPUT_DIR / 'life_os_brief_latest.md'}")
    print(f"Tool payload written: {json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
