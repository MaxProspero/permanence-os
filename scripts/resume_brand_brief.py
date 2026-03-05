#!/usr/bin/env python3
"""
Build a practical resume + brand upgrade brief from local working memory.
"""

from __future__ import annotations

import argparse
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
BRAND_DOC_DIR = Path(os.getenv("PERMANENCE_BRAND_DOC_DIR", str(BASE_DIR / "docs" / "brand")))


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


def _safe_int(value: Any) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def _latest_tool(pattern: str) -> Path | None:
    if not TOOL_DIR.exists():
        return None
    items = sorted(TOOL_DIR.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    return items[0] if items else None


def _load_profile() -> dict[str, Any]:
    payload = _read_json(PROFILE_PATH, {})
    if not isinstance(payload, dict):
        payload = {}
    return payload


def _load_tasks() -> list[dict[str, Any]]:
    payload = _read_json(TASKS_PATH, [])
    if not isinstance(payload, list):
        return []
    return [row for row in payload if isinstance(row, dict)]


def _brand_assets() -> list[dict[str, Any]]:
    if not BRAND_DOC_DIR.exists():
        return []
    rows: list[dict[str, Any]] = []
    for path in sorted(BRAND_DOC_DIR.glob("*")):
        if not path.is_file():
            continue
        ext = path.suffix.lower()
        if ext not in {".md", ".txt", ".docx", ".pdf", ".yaml", ".yml"}:
            continue
        note = ""
        if ext in {".md", ".txt", ".yaml", ".yml"}:
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
                note = " ".join(text.split())[:180]
            except OSError:
                note = ""
        rows.append(
            {
                "name": path.name,
                "path": str(path),
                "extension": ext,
                "modified_at": datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(),
                "preview": note,
            }
        )
    return rows


def _resume_bullets(profile: dict[str, Any], tasks: list[dict[str, Any]], attachment_payload: dict[str, Any]) -> list[str]:
    owner = str(profile.get("owner") or "Operator").strip()
    open_tasks = [row for row in tasks if str(row.get("status") or "open").strip().lower() not in {"done", "closed"}]
    business_open = [row for row in open_tasks if str(row.get("domain") or "").strip().lower() in {"business", "revenue"}]
    task_total = len(open_tasks)
    attachment_count = _safe_int(((attachment_payload.get("counts") or {}).get("total")))
    queue_pending = _safe_int(attachment_payload.get("transcription_queue_pending"))
    bullets = [
        (
            f"Built and operate a governed personal AI operating system for {owner}, "
            "with constitutional safety gates and auditable command execution."
        ),
        (
            f"Maintained an active execution stack across {task_total} open priorities "
            f"({len(business_open)} business-facing) using daily machine-generated operating briefs."
        ),
        (
            f"Designed a multi-modal intake pipeline that organizes {attachment_count} attachments and "
            f"tracks {queue_pending} audio/video transcription candidates for downstream content production."
        ),
    ]
    return bullets


def _brand_actions(profile: dict[str, Any], tasks: list[dict[str, Any]], brand_docs: list[dict[str, Any]]) -> list[str]:
    north_star = str(profile.get("north_star") or "").strip()
    actions = [
        "Lock one clear market-facing positioning statement and use it across site, bio, and pitch documents.",
        "Convert one real system outcome into a proof post per day (before/after, metric, operator note).",
        "Maintain a weekly brand architecture pass: offer language, CTA clarity, and visual consistency.",
    ]
    if north_star:
        actions.insert(0, f'Anchor content to north-star narrative: "{north_star}"')
    if not brand_docs:
        actions.append("Add at least one source-of-truth brand document under docs/brand.")
    if not tasks:
        actions.append("Add profile tasks tied to brand growth milestones for measurable compounding.")
    return actions[:6]


def _write_outputs(
    *,
    focus: str,
    profile: dict[str, Any],
    tasks: list[dict[str, Any]],
    brand_docs: list[dict[str, Any]],
    resume_bullets: list[str],
    brand_actions: list[str],
    attachment_payload: dict[str, Any],
) -> tuple[Path, Path]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    TOOL_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _now().strftime("%Y%m%d-%H%M%S")
    md_path = OUTPUT_DIR / f"resume_brand_brief_{stamp}.md"
    latest_md = OUTPUT_DIR / "resume_brand_brief_latest.md"
    json_path = TOOL_DIR / f"resume_brand_brief_{stamp}.json"

    lines = [
        "# Resume + Brand Brief",
        "",
        f"Generated (UTC): {_now_iso()}",
        f"Focus: {focus}",
        f"Profile source: {PROFILE_PATH}",
        f"Tasks source: {TASKS_PATH}",
        f"Brand docs directory: {BRAND_DOC_DIR}",
        "",
        "## Resume Upgrade Bullets",
    ]
    for idx, bullet in enumerate(resume_bullets, start=1):
        lines.append(f"{idx}. {bullet}")

    lines.extend(["", "## Brand System Actions"])
    for idx, action in enumerate(brand_actions, start=1):
        lines.append(f"{idx}. {action}")

    lines.extend(["", "## Brand Source Docs"])
    if not brand_docs:
        lines.append("- No brand docs found.")
    for doc in brand_docs:
        lines.append(f"- {doc.get('name')} | modified={doc.get('modified_at')} | path={doc.get('path')}")
        preview = str(doc.get("preview") or "").strip()
        if preview:
            lines.append(f"  preview: {preview}")

    attachment_counts = attachment_payload.get("counts") or {}
    lines.extend(
        [
            "",
            "## Multi-Modal Context",
            f"- Attachment docs: {_safe_int(attachment_counts.get('document'))}",
            f"- Attachment images: {_safe_int(attachment_counts.get('image'))}",
            f"- Attachment audio: {_safe_int(attachment_counts.get('audio'))}",
            f"- Attachment video: {_safe_int(attachment_counts.get('video'))}",
            f"- Pending transcription queue: {_safe_int(attachment_payload.get('transcription_queue_pending'))}",
            "",
            "## Governance Notes",
            "- Brand/resume output is draft guidance; publishing remains human-approved.",
            "- Do not include secrets, private keys, or sensitive personal details in public-facing copy.",
            "",
        ]
    )

    report = "\n".join(lines)
    md_path.write_text(report, encoding="utf-8")
    latest_md.write_text(report, encoding="utf-8")

    payload = {
        "generated_at": _now_iso(),
        "focus": focus,
        "profile_path": str(PROFILE_PATH),
        "tasks_path": str(TASKS_PATH),
        "brand_doc_dir": str(BRAND_DOC_DIR),
        "brand_doc_count": len(brand_docs),
        "resume_bullets": resume_bullets,
        "brand_actions": brand_actions,
        "attachment_counts": attachment_counts,
        "transcription_queue_pending": _safe_int(attachment_payload.get("transcription_queue_pending")),
        "latest_markdown": str(latest_md),
    }
    json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return md_path, json_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate resume + brand optimization brief.")
    parser.add_argument("--focus", choices=["resume", "brand", "both"], default="both", help="Primary focus")
    args = parser.parse_args(argv)

    profile = _load_profile()
    tasks = _load_tasks()
    brand_docs = _brand_assets()
    attachment_tool = _latest_tool("attachment_pipeline_*.json")
    attachment_payload = _read_json(attachment_tool, {}) if attachment_tool else {}
    if not isinstance(attachment_payload, dict):
        attachment_payload = {}

    bullets = _resume_bullets(profile, tasks, attachment_payload)
    actions = _brand_actions(profile, tasks, brand_docs)
    if args.focus == "resume":
        actions = actions[:3]
    elif args.focus == "brand":
        bullets = bullets[:2]

    md_path, json_path = _write_outputs(
        focus=args.focus,
        profile=profile,
        tasks=tasks,
        brand_docs=brand_docs,
        resume_bullets=bullets,
        brand_actions=actions,
        attachment_payload=attachment_payload,
    )
    print(f"Resume + brand brief written: {md_path}")
    print(f"Resume + brand latest: {OUTPUT_DIR / 'resume_brand_brief_latest.md'}")
    print(f"Tool payload written: {json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

