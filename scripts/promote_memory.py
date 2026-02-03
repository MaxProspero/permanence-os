#!/usr/bin/env python3
"""
Generate a Canon change proposal draft from episodic memory.
This does not modify the Canon.
"""

import argparse
import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
LOG_DIR = os.getenv("PERMANENCE_LOG_DIR", os.path.join(BASE_DIR, "logs"))


def log(message: str, level: str = "INFO") -> str:
    timestamp = datetime.now(timezone.utc).isoformat()
    entry = f"[{timestamp}] [{level}] {message}"

    os.makedirs(LOG_DIR, exist_ok=True)
    log_file = os.path.join(LOG_DIR, f"{datetime.now(timezone.utc).strftime('%Y-%m-%d')}.log")
    with open(log_file, "a") as f:
        f.write(entry + "\n")

    print(entry)
    return entry


MEMORY_DIR = os.getenv("PERMANENCE_MEMORY_DIR", os.path.join(BASE_DIR, "memory"))
EPISODIC_DIR = os.path.join(MEMORY_DIR, "episodic")
OUTPUT_DIR = os.getenv("PERMANENCE_OUTPUT_DIR", os.path.join(BASE_DIR, "outputs"))
DEFAULT_OUTPUT = os.getenv(
    "PERMANENCE_PROMOTION_OUTPUT",
    os.path.join(OUTPUT_DIR, "canon_change_proposal.md"),
)
DEFAULT_TEMPLATE = os.path.join(BASE_DIR, "docs", "canon_change_template.md")
DEFAULT_RUBRIC = os.getenv(
    "PERMANENCE_PROMOTION_RUBRIC",
    os.path.join(BASE_DIR, "docs", "promotion_rubric.md"),
)


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _load_episodes(episodic_dir: str) -> Tuple[List[Dict[str, Any]], List[str]]:
    episodes: List[Dict[str, Any]] = []
    errors: List[str] = []
    if not os.path.isdir(episodic_dir):
        return episodes, errors

    for name in os.listdir(episodic_dir):
        if not name.endswith(".json"):
            continue
        path = os.path.join(episodic_dir, name)
        try:
            with open(path, "r") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                raise ValueError("Episode is not a JSON object")
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            errors.append(f"{name}: {exc}")
            continue

        sort_dt = _parse_dt(data.get("updated_at")) or _parse_dt(data.get("created_at"))
        if not sort_dt:
            sort_dt = datetime.fromtimestamp(os.path.getmtime(path), tz=timezone.utc)

        episodes.append({"data": data, "path": path, "sort_dt": sort_dt})

    episodes.sort(key=lambda item: item["sort_dt"], reverse=True)
    return episodes, errors


def _filter_episodes(
    episodes: List[Dict[str, Any]],
    since_dt: Optional[datetime],
    count: Optional[int],
) -> List[Dict[str, Any]]:
    if since_dt:
        episodes = [ep for ep in episodes if ep["sort_dt"] >= since_dt]
    if count:
        episodes = episodes[:count]
    return episodes


def _render_episode(data: Dict[str, Any]) -> List[str]:
    task_id = data.get("task_id", "unknown")
    goal = data.get("task_goal", "")
    status = data.get("status", "unknown")
    stage = data.get("stage", "unknown")
    risk = data.get("risk_tier", "unknown")
    created = data.get("created_at", "")
    updated = data.get("updated_at", "")
    escalation = data.get("escalation")

    lines = [f"- {task_id} | {status}/{stage} | risk: {risk} | goal: {goal}"]

    if created or updated:
        lines.append(f"  - Created: {created} | Updated: {updated}")
    if escalation:
        lines.append(f"  - Escalation: {escalation}")
    if isinstance(data.get("sources"), list):
        lines.append(f"  - Sources: {len(data.get('sources', []))}")
    if isinstance(data.get("artifacts"), dict) and data.get("artifacts"):
        keys = ", ".join(sorted(data.get("artifacts", {}).keys()))
        lines.append(f"  - Artifacts: {keys}")
    return lines


def _render_report(
    episodes: List[Dict[str, Any]],
    errors: List[str],
    template: str,
    rubric: str,
) -> str:
    lines: List[str] = []
    lines.append("# Canon Change Draft")
    lines.append("")
    lines.append(f"Generated (UTC): {datetime.now(timezone.utc).isoformat()}")
    lines.append("")

    lines.append("## Candidate Episodes")
    if not episodes:
        lines.append("- None found")
    else:
        for ep in episodes:
            lines.extend(_render_episode(ep["data"]))
    lines.append("")

    lines.append("## Escalations and Failures")
    flagged: List[Dict[str, Any]] = []
    for ep in episodes:
        data = ep["data"]
        status = str(data.get("status", "")).upper()
        stage = str(data.get("stage", "")).upper()
        escalation = data.get("escalation")
        if escalation or status in {"FAILED", "BLOCKED"} or stage in {"FAILED", "ESCALATED"}:
            flagged.append(ep)

    if not flagged:
        lines.append("- None recorded in selected episodes")
    else:
        for ep in flagged:
            data = ep["data"]
            task_id = data.get("task_id", "unknown")
            reason = data.get("escalation") or "Status/Stage flagged"
            lines.append(f"- {task_id}: {reason}")
    lines.append("")

    if errors:
        lines.append("## Parse Errors")
        for err in errors:
            lines.append(f"- {err}")
        lines.append("")

    lines.append("## Notes")
    lines.append("This draft does not modify the Canon.")
    lines.append("Human review and approval are required for any Canon change.")
    lines.append("")

    if template:
        lines.append("---")
        lines.append("")
        lines.append("## Canon Change Template")
        lines.append(template.strip())
        lines.append("")

    if rubric:
        lines.append("---")
        lines.append("")
        lines.append("## Canon Promotion Rubric")
        lines.append(rubric.strip())
        lines.append("")

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate a Canon change proposal draft from episodic memory"
    )
    parser.add_argument("--since", help="ISO date/time filter (UTC)")
    parser.add_argument("--count", type=int, help="Limit to N most recent episodes")
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help="Output markdown path")
    parser.add_argument(
        "--template", default=DEFAULT_TEMPLATE, help="Canon change template path"
    )
    parser.add_argument(
        "--rubric", default=DEFAULT_RUBRIC, help="Promotion rubric path"
    )

    args = parser.parse_args()

    since_dt = _parse_dt(args.since) if args.since else None
    if args.since and since_dt is None:
        print("Invalid --since value. Use ISO format like 2026-02-02 or 2026-02-02T00:00:00+00:00")
        return 2

    episodes, errors = _load_episodes(EPISODIC_DIR)
    episodes = _filter_episodes(episodes, since_dt, args.count)

    template = ""
    if args.template and os.path.exists(args.template):
        with open(args.template, "r") as f:
            template = f.read()

    rubric = ""
    if args.rubric and os.path.exists(args.rubric):
        with open(args.rubric, "r") as f:
            rubric = f.read()

    report = _render_report(episodes, errors, template, rubric)
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, "w") as f:
        f.write(report)

    log(f"Canon change draft written: {args.output}")
    print(f"Draft written to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
