#!/usr/bin/env python3
"""
Build a revenue activation queue from the latest agent outputs.

This is read-only synthesis across existing markdown artifacts and does not
publish or send anything.
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
OUTPUT_DIR = Path(os.getenv("PERMANENCE_OUTPUT_DIR", str(BASE_DIR / "outputs")))
TOOL_DIR = Path(os.getenv("PERMANENCE_TOOL_DIR", str(BASE_DIR / "memory" / "tool")))

SOCIAL_RE = re.compile(r"^-\s+(.+)\s+\[(.+)\]\s+\((.+)\)\s*$")


def _latest(pattern: str) -> Path | None:
    if not OUTPUT_DIR.exists():
        return None
    matches = sorted(OUTPUT_DIR.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    return matches[0] if matches else None


def _parse_email(path: Path | None) -> list[dict]:
    if not path or not path.exists():
        return []
    items: list[dict] = []
    bucket = "P3"
    for raw in path.read_text(errors="ignore").splitlines():
        line = raw.strip()
        if line.startswith("## P0"):
            bucket = "P0"
            continue
        if line.startswith("## P1"):
            bucket = "P1"
            continue
        if line.startswith("## P2"):
            bucket = "P2"
            continue
        if line.startswith("## P3"):
            bucket = "P3"
            continue
        if not line.startswith("- [") or "] " not in line:
            continue
        try:
            score_text = line.split("]", 1)[0].replace("- [", "").strip()
            score = int(score_text)
        except ValueError:
            continue
        body = line.split("] ", 1)[1].strip()
        if "<" in body and ">" in body and body.rfind(">") > body.rfind("<"):
            summary = body[: body.rfind(">") + 1]
            received = ""
        elif " (" in body and body.endswith(")"):
            summary, received = body.rsplit(" (", 1)
            received = received[:-1]
        else:
            summary, received = body, ""
        items.append({"bucket": bucket, "score": score, "summary": summary, "received": received})

    priority_order = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
    items.sort(key=lambda x: (priority_order.get(x["bucket"], 9), -x["score"]))
    return items


def _parse_social(path: Path | None) -> list[dict]:
    if not path or not path.exists():
        return []
    drafts: list[dict] = []
    for raw in path.read_text(errors="ignore").splitlines():
        line = raw.strip()
        m = SOCIAL_RE.match(line)
        if not m:
            continue
        drafts.append(
            {
                "title": m.group(1),
                "platform": m.group(2),
                "created_at": m.group(3),
            }
        )
    return drafts


def _build_actions(email_items: list[dict], social_items: list[dict]) -> list[dict]:
    actions: list[dict] = []

    for item in email_items[:3]:
        actions.append(
            {
                "type": "email_followup",
                "window": "today",
                "action": f"Resolve high-priority email: {item['summary']}",
                "source_bucket": item["bucket"],
            }
        )

    for draft in social_items[:2]:
        actions.append(
            {
                "type": "content_publish",
                "window": "today",
                "action": f"Polish + publish draft on {draft['platform']}: {draft['title']}",
                "source_bucket": "social_draft",
            }
        )

    defaults = [
        {
            "type": "offer_clarity",
            "window": "today",
            "action": "Define one core offer and one CTA for this week (single sentence each).",
            "source_bucket": "template",
        },
        {
            "type": "lead_capture",
            "window": "tomorrow",
            "action": "Create one lead capture asset (form/doc) and link it from every social bio.",
            "source_bucket": "template",
        },
        {
            "type": "outreach",
            "window": "48h",
            "action": "Send 5 direct outreach messages to qualified prospects with the weekly CTA.",
            "source_bucket": "template",
        },
        {
            "type": "offer_iteration",
            "window": "72h",
            "action": "Review response patterns and tighten messaging based on objections.",
            "source_bucket": "template",
        },
        {
            "type": "weekly_review",
            "window": "7d",
            "action": "Run weekly review: pipeline count, response rate, and next experiments.",
            "source_bucket": "template",
        },
    ]

    for default in defaults:
        if len(actions) >= 7:
            break
        actions.append(default)

    return actions[:7]


def _write_output(actions: list[dict], email_src: Path | None, social_src: Path | None) -> tuple[Path, Path]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    TOOL_DIR.mkdir(parents=True, exist_ok=True)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    md_path = OUTPUT_DIR / f"revenue_action_queue_{stamp}.md"
    json_path = TOOL_DIR / f"revenue_action_queue_{stamp}.json"

    lines = [
        "# Revenue Action Queue",
        "",
        f"Generated (UTC): {datetime.now(timezone.utc).isoformat()}",
        "",
        "## Inputs",
        f"- Email triage source: {email_src if email_src else 'none'}",
        f"- Social summary source: {social_src if social_src else 'none'}",
        "",
        "## Next 7 Actions",
    ]
    for idx, item in enumerate(actions, start=1):
        lines.append(f"{idx}. [{item['window']}] {item['action']}")

    lines.extend(
        [
            "",
            "## Governance Notes",
            "- Public posts and outbound messages still require human approval before sending/publishing.",
            "- Financial, legal, payment, and contract actions remain escalation-gated.",
            "",
        ]
    )
    md_path.write_text("\n".join(lines), encoding="utf-8")

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "inputs": {
            "email_triage": str(email_src) if email_src else None,
            "social_summary": str(social_src) if social_src else None,
        },
        "actions": actions,
    }
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return md_path, json_path


def main() -> int:
    email_path = _latest("email_triage_*.md")
    social_path = _latest("social_summary_*.md")
    email_items = _parse_email(email_path)
    social_items = _parse_social(social_path)
    actions = _build_actions(email_items, social_items)
    md_path, json_path = _write_output(actions, email_path, social_path)

    print(f"Revenue action queue written: {md_path}")
    print(f"Tool payload written: {json_path}")
    print(f"Actions generated: {len(actions)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
