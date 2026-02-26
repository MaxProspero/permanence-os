#!/usr/bin/env python3
"""
Generate a daily revenue execution board from queue + pipeline + targets.
"""

from __future__ import annotations

import json
import os
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parents[1]
WORKING_DIR = Path(os.getenv("PERMANENCE_WORKING_DIR", str(BASE_DIR / "memory" / "working")))
OUTPUT_DIR = Path(os.getenv("PERMANENCE_OUTPUT_DIR", str(BASE_DIR / "outputs")))
TOOL_DIR = Path(os.getenv("PERMANENCE_TOOL_DIR", str(BASE_DIR / "memory" / "tool")))

PIPELINE_PATH = Path(os.getenv("PERMANENCE_SALES_PIPELINE_PATH", str(WORKING_DIR / "sales_pipeline.json")))
TARGETS_PATH = Path(os.getenv("PERMANENCE_REVENUE_TARGETS_PATH", str(WORKING_DIR / "revenue_targets.json")))
PLAYBOOK_PATH = Path(os.getenv("PERMANENCE_REVENUE_PLAYBOOK_PATH", str(WORKING_DIR / "revenue_playbook.json")))

QUEUE_ACTION_RE = re.compile(r"^\d+\.\s+\[(.+)\]\s+(.+)$")
EMAIL_BUCKET_RE = re.compile(r"^##\s+(P[0-3])\s+\((\d+)\)")


def _default_playbook() -> dict[str, Any]:
    return {
        "offer_name": "Permanence OS Foundation Setup",
        "cta_keyword": "FOUNDATION",
        "cta_public": 'DM me "FOUNDATION".',
        "pricing_tier": "Core",
        "price_usd": 1500,
    }


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def _latest(pattern: str) -> Path | None:
    if not OUTPUT_DIR.exists():
        return None
    matches = sorted(OUTPUT_DIR.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    return matches[0] if matches else None


def _load_playbook() -> dict[str, Any]:
    payload = _read_json(PLAYBOOK_PATH, {})
    if not isinstance(payload, dict):
        payload = {}
    merged = dict(_default_playbook())
    merged.update(payload)
    return merged


def _queue_actions(path: Path | None) -> list[str]:
    if not path or not path.exists():
        return []
    actions: list[str] = []
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        m = QUEUE_ACTION_RE.match(line)
        if m:
            actions.append(f"[{m.group(1)}] {m.group(2)}")
    return actions


def _email_bucket_counts(path: Path | None) -> dict[str, int]:
    counts = {"P0": 0, "P1": 0, "P2": 0, "P3": 0}
    if not path or not path.exists():
        return counts
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        m = EMAIL_BUCKET_RE.match(line)
        if not m:
            continue
        bucket = m.group(1)
        counts[bucket] = int(m.group(2))
    return counts


def _social_drafts(path: Path | None) -> list[str]:
    if not path or not path.exists():
        return []
    items: list[str] = []
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if line.startswith("- ") and " [" in line and "] (" in line:
            items.append(line[2:])
    return items


def _urgent_pipeline_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    open_rows = [r for r in rows if str(r.get("stage")) not in {"won", "lost"}]
    cutoff = (date.today() + timedelta(days=1)).isoformat()
    urgent = []
    for row in open_rows:
        due = str(row.get("next_action_due") or "")
        if due and due <= cutoff:
            urgent.append(row)
    urgent.sort(key=lambda r: str(r.get("next_action_due", "")))
    return urgent


def _write_board(
    *,
    queue_actions: list[str],
    queue_path: Path | None,
    email_counts: dict[str, int],
    email_path: Path | None,
    social_items: list[str],
    social_path: Path | None,
    urgent_rows: list[dict[str, Any]],
    pipeline_path: Path,
    targets: dict[str, Any],
    playbook: dict[str, Any],
) -> tuple[Path, Path]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    TOOL_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _now().strftime("%Y%m%d-%H%M%S")
    md_path = OUTPUT_DIR / f"revenue_execution_board_{stamp}.md"
    latest_path = OUTPUT_DIR / "revenue_execution_board_latest.md"
    json_path = TOOL_DIR / f"revenue_execution_board_{stamp}.json"

    outreach_target = int(targets.get("daily_outreach_target", 10))
    offer_name = str(playbook.get("offer_name") or _default_playbook()["offer_name"])
    cta_public = str(playbook.get("cta_public") or _default_playbook()["cta_public"])
    pricing_tier = str(playbook.get("pricing_tier") or _default_playbook()["pricing_tier"])
    price_usd = int(playbook.get("price_usd") or _default_playbook()["price_usd"])

    lines = [
        "# Revenue Execution Board",
        "",
        f"Generated (UTC): {_now().isoformat()}",
        f"Locked offer: {offer_name} ({pricing_tier}, ${price_usd:,})",
        "",
        "## Today's Non-Negotiables",
    ]

    if queue_actions:
        for idx, action in enumerate(queue_actions[:7], start=1):
            lines.append(f"{idx}. {action}")
    else:
        lines.append("1. No queue actions found. Run money loop first.")

    lines.extend(
        [
            "",
            "## Pipeline Urgent Actions (<=24h)",
        ]
    )
    if urgent_rows:
        for row in urgent_rows[:10]:
            lines.append(
                f"- {row.get('lead_id', 'unknown')} | {row.get('name', 'unknown')} | "
                f"stage={row.get('stage', 'lead')} | due={row.get('next_action_due') or '-'} | "
                f"next={row.get('next_action') or '-'}"
            )
    else:
        lines.append("- No urgent pipeline actions due.")

    lines.extend(
        [
            "",
            "## Publish + Outreach Block",
            f"- Outreach target today: {outreach_target}",
            f"- Locked CTA: {cta_public}",
            "",
            "### Drafts Ready",
        ]
    )
    if social_items:
        for item in social_items[:6]:
            lines.append(f"- {item}")
    else:
        lines.append("- No social drafts found.")

    lines.extend(
        [
            "",
            "### Inbox Pressure",
            f"- P0: {email_counts.get('P0', 0)} | P1: {email_counts.get('P1', 0)} | P2: {email_counts.get('P2', 0)} | P3: {email_counts.get('P3', 0)}",
            "",
            "## End-of-Day Close Checklist",
            "- Update sales pipeline stages for every lead touched.",
            "- Mark won/lost outcomes for closed decisions.",
            "- Regenerate revenue architecture report.",
            "- Keep tomorrow's first action queued with a due date.",
            "",
            "## Data Sources",
            f"- Revenue queue: {queue_path if queue_path else 'none'}",
            f"- Email triage: {email_path if email_path else 'none'}",
            f"- Social summary: {social_path if social_path else 'none'}",
            f"- Pipeline: {pipeline_path}",
            f"- Playbook: {PLAYBOOK_PATH}",
            "",
        ]
    )

    board = "\n".join(lines)
    md_path.write_text(board, encoding="utf-8")
    latest_path.write_text(board, encoding="utf-8")

    payload = {
        "generated_at": _now().isoformat(),
        "targets": targets,
        "playbook": playbook,
        "queue_source": str(queue_path) if queue_path else None,
        "queue_actions": queue_actions[:7],
        "email_source": str(email_path) if email_path else None,
        "email_counts": email_counts,
        "social_source": str(social_path) if social_path else None,
        "social_items": social_items[:6],
        "urgent_pipeline": urgent_rows[:10],
        "pipeline_path": str(pipeline_path),
        "latest_board": str(latest_path),
    }
    json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return md_path, json_path


def main() -> int:
    targets = _read_json(TARGETS_PATH, {"daily_outreach_target": 10})
    if not isinstance(targets, dict):
        targets = {"daily_outreach_target": 10}

    pipeline = _read_json(PIPELINE_PATH, [])
    if not isinstance(pipeline, list):
        pipeline = []
    pipeline_rows = [r for r in pipeline if isinstance(r, dict)]
    urgent_rows = _urgent_pipeline_rows(pipeline_rows)

    queue_path = _latest("revenue_action_queue_*.md")
    email_path = _latest("email_triage_*.md")
    social_path = _latest("social_summary_*.md")

    queue_actions = _queue_actions(queue_path)
    email_counts = _email_bucket_counts(email_path)
    social_items = _social_drafts(social_path)
    playbook = _load_playbook()

    md_path, json_path = _write_board(
        queue_actions=queue_actions,
        queue_path=queue_path,
        email_counts=email_counts,
        email_path=email_path,
        social_items=social_items,
        social_path=social_path,
        urgent_rows=urgent_rows,
        pipeline_path=PIPELINE_PATH,
        targets=targets,
        playbook=playbook,
    )
    print(f"Revenue execution board written: {md_path}")
    print(f"Revenue execution latest: {OUTPUT_DIR / 'revenue_execution_board_latest.md'}")
    print(f"Tool payload written: {json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
