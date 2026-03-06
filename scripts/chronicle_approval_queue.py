#!/usr/bin/env python3
"""
Queue chronicle refinement recommendations into manual approval workflow.

This script only writes pending approval items and does not execute actions.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parents[1]
WORKING_DIR = Path(os.getenv("PERMANENCE_WORKING_DIR", str(BASE_DIR / "memory" / "working")))
TOOL_DIR = Path(os.getenv("PERMANENCE_TOOL_DIR", str(BASE_DIR / "memory" / "tool")))
OUTPUT_DIR = Path(os.getenv("PERMANENCE_OUTPUT_DIR", str(BASE_DIR / "outputs")))
APPROVALS_PATH = Path(os.getenv("PERMANENCE_APPROVALS_PATH", str(BASE_DIR / "memory" / "approvals.json")))
POLICY_PATH = Path(
    os.getenv("PERMANENCE_CHRONICLE_QUEUE_POLICY_PATH", str(WORKING_DIR / "chronicle_queue_policy.json"))
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now().isoformat().replace("+00:00", "Z")


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def _latest_tool(pattern: str) -> Path | None:
    if not TOOL_DIR.exists():
        return None
    rows = sorted(TOOL_DIR.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    return rows[0] if rows else None


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _normalize_priority(value: Any) -> str:
    token = str(value or "").strip().upper()
    if token in {"LOW", "MEDIUM", "HIGH"}:
        return token
    return "MEDIUM"


def _is_true(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _default_policy() -> dict[str, Any]:
    return {
        "max_queue_items": 5,
        "min_score": 60.0,
        "include_categories": ["issue", "direction", "meta"],
        "include_canon_checks": True,
        "updated_at": _now_iso(),
    }


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
    if not isinstance(merged.get("include_categories"), list):
        merged["include_categories"] = list(defaults["include_categories"])
    if merged != payload:
        path.write_text(json.dumps(merged, indent=2) + "\n", encoding="utf-8")
        return merged, "updated"
    return merged, "existing"


def _load_refinement() -> tuple[dict[str, Any], Path | None]:
    path = _latest_tool("chronicle_refinement_*.json")
    payload = _read_json(path, {}) if path else {}
    if not isinstance(payload, dict):
        payload = {}
    return payload, path


def _load_approvals(path: Path) -> list[dict[str, Any]]:
    payload = _read_json(path, [])
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict) and isinstance(payload.get("approvals"), list):
        return [row for row in payload.get("approvals", []) if isinstance(row, dict)]
    return []


def _save_approvals(path: Path, approvals: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(approvals, indent=2) + "\n", encoding="utf-8")


def _fingerprint(payload: dict[str, Any]) -> str:
    return hashlib.sha1(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()[:16]


def _source_findings(row: dict[str, Any], source_path: Path | None) -> list[str]:
    findings: list[str] = []
    if source_path:
        findings.append(str(source_path))
    evidence = row.get("evidence")
    if isinstance(evidence, list):
        findings.extend([str(item).strip() for item in evidence if str(item).strip()])
    return findings[:8]


def _queue_item_from_backlog(row: dict[str, Any], source_path: Path | None) -> dict[str, Any]:
    item_id = str(row.get("id") or "").strip()
    title = str(row.get("title") or "Chronicle backlog update").strip()
    next_action = str(row.get("next_action") or "Define next action.").strip()
    why_now = str(row.get("why_now") or "Chronicle recommends this update.").strip()
    category = str(row.get("category") or "meta").strip().lower()
    score = _safe_float(row.get("score"), 0.0)
    priority = _normalize_priority(row.get("priority"))
    proposal_id = f"CHR-{item_id}" if item_id else f"CHR-{_fingerprint(row)}"
    queue_item = {
        "proposal_id": proposal_id,
        "id": proposal_id,
        "approval_id": proposal_id,
        "title": title,
        "finding_summary": why_now,
        "current_state": f"Chronicle refinement flagged category={category} with score={score:.0f}.",
        "proposed_change": next_action,
        "expected_benefit": "Improves system focus, reliability, and execution quality.",
        "risk_if_ignored": "Operational drag and unresolved chronicle friction may compound.",
        "implementation_scope": "system_improvement",
        "draft_canon_amendment": None,
        "draft_codex_task": next_action,
        "source_findings": _source_findings(row, source_path),
        "priority": priority,
        "status": "PENDING_HUMAN_REVIEW",
        "created_at": _now_iso(),
        "queued_at": _now_iso(),
        "source": "chronicle_refinement_queue",
        "source_report_id": item_id or proposal_id,
        "source_opportunity_id": item_id or proposal_id,
        "opportunity_score": round(score, 2),
        "manual_approval_required": True,
    }
    queue_item["proposal_fingerprint"] = _fingerprint(queue_item)
    return queue_item


def _queue_item_from_canon(row: dict[str, Any], source_path: Path | None) -> dict[str, Any]:
    check_id = str(row.get("check_id") or "").strip()
    trigger = str(row.get("trigger") or "routine_review").strip().lower()
    question = str(row.get("question") or "Review canon alignment for this update.").strip()
    trigger_note = str(row.get("trigger_note") or "").strip()
    priority = "HIGH" if trigger == "direction_shift_detected" else "MEDIUM"
    proposal_id = f"CHR-{check_id}" if check_id else f"CHR-CANON-{_fingerprint(row)}"
    findings = [trigger_note] if trigger_note else []
    if source_path:
        findings.insert(0, str(source_path))
    queue_item = {
        "proposal_id": proposal_id,
        "id": proposal_id,
        "approval_id": proposal_id,
        "title": str(row.get("title") or "Canon alignment review").strip(),
        "finding_summary": trigger_note or "Chronicle requested a canon alignment review.",
        "current_state": f"Canon check trigger={trigger}.",
        "proposed_change": question,
        "expected_benefit": "Keeps new backlog work aligned with non-negotiable governance.",
        "risk_if_ignored": "System drift can weaken safety, authority boundaries, or mission alignment.",
        "implementation_scope": "canon_amendment",
        "draft_canon_amendment": question,
        "draft_codex_task": "Review canon check and decide approve/reject with reasoning.",
        "source_findings": [row for row in findings if str(row).strip()][:8],
        "priority": priority,
        "status": "PENDING_HUMAN_REVIEW",
        "created_at": _now_iso(),
        "queued_at": _now_iso(),
        "source": "chronicle_refinement_queue",
        "source_report_id": check_id or proposal_id,
        "source_opportunity_id": check_id or proposal_id,
        "opportunity_score": 90.0 if priority == "HIGH" else 75.0,
        "manual_approval_required": True,
    }
    queue_item["proposal_fingerprint"] = _fingerprint(queue_item)
    return queue_item


def _should_include_backlog(row: dict[str, Any], policy: dict[str, Any]) -> bool:
    score = _safe_float(row.get("score"), 0.0)
    min_score = _safe_float(policy.get("min_score"), 60.0)
    if score < min_score:
        return False
    allowed = {str(token).strip().lower() for token in (policy.get("include_categories") or []) if str(token).strip()}
    if not allowed:
        return True
    category = str(row.get("category") or "").strip().lower()
    return category in allowed


def _write_outputs(
    *,
    queued_items: list[dict[str, Any]],
    skipped_existing: int,
    skipped_filtered: int,
    pending_total: int,
    source_path: Path | None,
    policy: dict[str, Any],
    policy_status: str,
) -> tuple[Path, Path]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    TOOL_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _now().strftime("%Y%m%d-%H%M%S")
    md_path = OUTPUT_DIR / f"chronicle_approval_queue_{stamp}.md"
    latest_md = OUTPUT_DIR / "chronicle_approval_queue_latest.md"
    json_path = TOOL_DIR / f"chronicle_approval_queue_{stamp}.json"

    lines = [
        "# Chronicle Approval Queue",
        "",
        f"Generated (UTC): {_now_iso()}",
        f"Approvals path: {APPROVALS_PATH}",
        f"Refinement input: {source_path if source_path else 'none'}",
        f"Policy: {POLICY_PATH} ({policy_status})",
        "",
        "## Summary",
        f"- Queued now: {len(queued_items)}",
        f"- Skipped (existing): {skipped_existing}",
        f"- Skipped (policy filtered): {skipped_filtered}",
        f"- Total pending approvals: {pending_total}",
        "",
        "## Queued Items",
    ]

    if not queued_items:
        lines.append("- No new chronicle items queued.")
    for idx, row in enumerate(queued_items, start=1):
        lines.extend(
            [
                f"{idx}. {row.get('title')} [{row.get('priority')}]",
                f"   - scope={row.get('implementation_scope')} | score={row.get('opportunity_score')} | id={row.get('id')}",
                f"   - proposed_change={row.get('proposed_change')}",
            ]
        )

    lines.extend(
        [
            "",
            "## Governance Notes",
            "- Queue entries are pending-only and require explicit human decision.",
            "- Canon checks remain human-reviewed before any amendments.",
            "",
        ]
    )

    report = "\n".join(lines)
    md_path.write_text(report, encoding="utf-8")
    latest_md.write_text(report, encoding="utf-8")

    payload = {
        "generated_at": _now_iso(),
        "approvals_path": str(APPROVALS_PATH),
        "refinement_input_path": str(source_path) if source_path else "none",
        "policy_path": str(POLICY_PATH),
        "policy_status": policy_status,
        "policy": policy,
        "queued_count": len(queued_items),
        "queued_ids": [row.get("id") for row in queued_items],
        "skipped_existing": skipped_existing,
        "skipped_filtered": skipped_filtered,
        "pending_total": pending_total,
        "latest_markdown": str(latest_md),
    }
    json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return md_path, json_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Queue chronicle refinements for manual approval.")
    parser.add_argument("--force-policy", action="store_true", help="Rewrite queue policy template file")
    parser.add_argument("--max-items", type=int, help="Override max number of new queue items for this run")
    parser.add_argument("--no-canon-checks", action="store_true", help="Skip canon-check queue entries this run")
    args = parser.parse_args(argv)

    policy, policy_status = _ensure_policy(POLICY_PATH, force_template=args.force_policy)
    refinement, source_path = _load_refinement()
    approvals = _load_approvals(APPROVALS_PATH)
    backlog_updates = refinement.get("backlog_updates") if isinstance(refinement.get("backlog_updates"), list) else []
    canon_checks = refinement.get("canon_checks") if isinstance(refinement.get("canon_checks"), list) else []

    max_items = _safe_int(args.max_items, _safe_int(policy.get("max_queue_items"), 5))
    if max_items <= 0:
        max_items = 1
    include_canon = _is_true(policy.get("include_canon_checks", True)) and not args.no_canon_checks

    existing_keys: set[str] = set()
    for row in approvals:
        for key in [
            str(row.get("id") or ""),
            str(row.get("proposal_id") or ""),
            str(row.get("approval_id") or ""),
            str(row.get("source_opportunity_id") or ""),
            str(row.get("source_report_id") or ""),
        ]:
            token = key.strip()
            if token:
                existing_keys.add(token)

    queued_items: list[dict[str, Any]] = []
    skipped_existing = 0
    skipped_filtered = 0

    for row in backlog_updates:
        if len(queued_items) >= max_items:
            break
        if not isinstance(row, dict):
            continue
        if not _should_include_backlog(row, policy):
            skipped_filtered += 1
            continue
        queue_item = _queue_item_from_backlog(row, source_path)
        candidate_keys = {
            str(queue_item.get("id") or ""),
            str(queue_item.get("source_opportunity_id") or ""),
            str(queue_item.get("source_report_id") or ""),
        }
        if any((key and key in existing_keys) for key in candidate_keys):
            skipped_existing += 1
            continue
        approvals.append(queue_item)
        queued_items.append(queue_item)
        for key in candidate_keys:
            if key:
                existing_keys.add(key)

    if include_canon and len(queued_items) < max_items:
        for row in canon_checks:
            if len(queued_items) >= max_items:
                break
            if not isinstance(row, dict):
                continue
            queue_item = _queue_item_from_canon(row, source_path)
            candidate_keys = {
                str(queue_item.get("id") or ""),
                str(queue_item.get("source_opportunity_id") or ""),
                str(queue_item.get("source_report_id") or ""),
            }
            if any((key and key in existing_keys) for key in candidate_keys):
                skipped_existing += 1
                continue
            approvals.append(queue_item)
            queued_items.append(queue_item)
            for key in candidate_keys:
                if key:
                    existing_keys.add(key)

    _save_approvals(APPROVALS_PATH, approvals)
    pending_total = sum(1 for row in approvals if str(row.get("status") or "").upper() == "PENDING_HUMAN_REVIEW")
    md_path, json_path = _write_outputs(
        queued_items=queued_items,
        skipped_existing=skipped_existing,
        skipped_filtered=skipped_filtered,
        pending_total=pending_total,
        source_path=source_path,
        policy=policy,
        policy_status=policy_status,
    )
    print(f"Chronicle approval queue written: {md_path}")
    print(f"Chronicle approval queue latest: {OUTPUT_DIR / 'chronicle_approval_queue_latest.md'}")
    print(f"Tool payload written: {json_path}")
    print(f"Queued now: {len(queued_items)} | pending total: {pending_total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
