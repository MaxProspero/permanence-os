#!/usr/bin/env python3
"""
Queue ranked opportunities into memory/approvals.json for manual review.

This script only writes approval records; it never executes opportunities.
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
    os.getenv("PERMANENCE_OPPORTUNITY_QUEUE_POLICY_PATH", str(WORKING_DIR / "opportunity_queue_policy.json"))
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


def _default_policy() -> dict[str, Any]:
    return {
        "max_queue_items": 7,
        "min_priority_score": 30.0,
        "include_priorities": ["HIGH", "MEDIUM", "LOW"],
        "include_source_types": ["social", "github", "prediction", "portfolio"],
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
    if not isinstance(merged.get("include_priorities"), list):
        merged["include_priorities"] = list(defaults["include_priorities"])
    if not isinstance(merged.get("include_source_types"), list):
        merged["include_source_types"] = list(defaults["include_source_types"])
    if merged != payload:
        path.write_text(json.dumps(merged, indent=2) + "\n", encoding="utf-8")
        return merged, "updated"
    return merged, "existing"


def _load_ranked_opportunities() -> tuple[list[dict[str, Any]], Path | None]:
    path = _latest_tool("opportunity_ranker_*.json")
    if path is None:
        return [], None
    payload = _read_json(path, {})
    if not isinstance(payload, dict):
        return [], path
    rows = payload.get("top_items")
    if not isinstance(rows, list):
        rows = []
    out = [row for row in rows if isinstance(row, dict)]
    return out, path


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


def _approval_id(opportunity: dict[str, Any]) -> str:
    source = str(opportunity.get("source_type") or "opp").strip().upper()
    opp_id = str(opportunity.get("opportunity_id") or "").strip()
    if opp_id:
        return f"OPP-{source}-{opp_id[:12]}"
    digest = hashlib.sha1(json.dumps(opportunity, sort_keys=True).encode("utf-8")).hexdigest()[:12]
    return f"OPP-{source}-{digest}"


def _queue_item(opportunity: dict[str, Any], source_path: Path | None) -> dict[str, Any]:
    now = _now_iso()
    item_id = _approval_id(opportunity)
    source_type = str(opportunity.get("source_type") or "unknown").strip().lower()
    source_name = str(opportunity.get("source_name") or source_type).strip()
    title = str(opportunity.get("title") or "Ranked opportunity").strip()
    summary = str(opportunity.get("summary") or "").strip()
    proposed_action = str(opportunity.get("proposed_action") or "Review and scope next action.").strip()
    expected_benefit = str(opportunity.get("expected_benefit") or "Potential upside requires human review.").strip()
    risk_if_ignored = str(opportunity.get("risk_if_ignored") or "Opportunity may decay with inaction.").strip()
    draft_task = str(opportunity.get("draft_codex_task") or "").strip() or None
    source_finding = str(opportunity.get("opportunity_id") or item_id)
    source_ref = str(opportunity.get("source_ref") or (str(source_path) if source_path else "none"))
    evidence = opportunity.get("evidence") if isinstance(opportunity.get("evidence"), list) else []
    source_findings: list[str] = []
    if source_ref:
        source_findings.append(source_ref)
    if source_finding:
        source_findings.append(source_finding)
    for row in evidence:
        token = str(row or "").strip()
        if token:
            source_findings.append(token)

    normalized = {
        "proposal_id": item_id,
        "id": item_id,
        "approval_id": item_id,
        "title": title,
        "finding_summary": summary or proposed_action,
        "current_state": f"Opportunity candidate from {source_type}:{source_name}.",
        "proposed_change": proposed_action,
        "expected_benefit": expected_benefit,
        "risk_if_ignored": risk_if_ignored,
        "implementation_scope": str(opportunity.get("implementation_scope") or "opportunity_execution"),
        "draft_canon_amendment": None,
        "draft_codex_task": draft_task,
        "source_findings": source_findings[:8],
        "priority": _normalize_priority(opportunity.get("priority")),
        "status": "PENDING_HUMAN_REVIEW",
        "created_at": now,
        "queued_at": now,
        "source": "phase3_opportunity_queue",
        "source_report_id": str(opportunity.get("opportunity_id") or item_id),
        "source_opportunity_id": str(opportunity.get("opportunity_id") or item_id),
        "opportunity_score": round(_safe_float(opportunity.get("priority_score"), 0.0), 2),
        "manual_approval_required": True,
    }
    normalized["proposal_fingerprint"] = hashlib.sha1(
        json.dumps(normalized, sort_keys=True).encode("utf-8")
    ).hexdigest()[:16]
    return normalized


def _should_include(opportunity: dict[str, Any], policy: dict[str, Any]) -> bool:
    include_priorities = {
        _normalize_priority(token)
        for token in (policy.get("include_priorities") or [])
        if str(token).strip()
    }
    include_source_types = {
        str(token).strip().lower()
        for token in (policy.get("include_source_types") or [])
        if str(token).strip()
    }
    score = _safe_float(opportunity.get("priority_score"), 0.0)
    min_score = _safe_float(policy.get("min_priority_score"), 30.0)
    if score < min_score:
        return False
    priority = _normalize_priority(opportunity.get("priority"))
    if include_priorities and priority not in include_priorities:
        return False
    source_type = str(opportunity.get("source_type") or "").strip().lower()
    if include_source_types and source_type not in include_source_types:
        return False
    return True


def _write_outputs(
    *,
    queued_items: list[dict[str, Any]],
    skipped_existing: int,
    skipped_filtered: int,
    pending_total: int,
    policy: dict[str, Any],
    policy_status: str,
    source_path: Path | None,
) -> tuple[Path, Path]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    TOOL_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _now().strftime("%Y%m%d-%H%M%S")
    md_path = OUTPUT_DIR / f"opportunity_approval_queue_{stamp}.md"
    latest_md = OUTPUT_DIR / "opportunity_approval_queue_latest.md"
    json_path = TOOL_DIR / f"opportunity_approval_queue_{stamp}.json"

    lines = [
        "# Opportunity Approval Queue",
        "",
        f"Generated (UTC): {_now_iso()}",
        f"Approvals path: {APPROVALS_PATH}",
        f"Ranked input: {source_path if source_path else 'none'}",
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
        lines.append("- No new items queued.")
    for idx, row in enumerate(queued_items, start=1):
        lines.extend(
            [
                f"{idx}. {row.get('title')} [{row.get('priority')}]",
                f"   - scope={row.get('implementation_scope')} | score={row.get('opportunity_score')} | id={row.get('id')}",
            ]
        )

    lines.extend(
        [
            "",
            "## Governance Notes",
            "- Queue entries are pending-only and require explicit human decision.",
            "- Approval does not auto-execute irreversible actions.",
            "",
        ]
    )

    report = "\n".join(lines)
    md_path.write_text(report, encoding="utf-8")
    latest_md.write_text(report, encoding="utf-8")

    payload = {
        "generated_at": _now_iso(),
        "approvals_path": str(APPROVALS_PATH),
        "ranked_input_path": str(source_path) if source_path else "none",
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
    parser = argparse.ArgumentParser(description="Queue ranked opportunities for manual approval.")
    parser.add_argument("--force-policy", action="store_true", help="Rewrite queue policy template file")
    parser.add_argument("--max-items", type=int, help="Override max number of new queue items for this run")
    args = parser.parse_args(argv)

    policy, policy_status = _ensure_policy(POLICY_PATH, force_template=args.force_policy)
    ranked, source_path = _load_ranked_opportunities()
    approvals = _load_approvals(APPROVALS_PATH)

    max_items = _safe_int(args.max_items, _safe_int(policy.get("max_queue_items"), 7))
    if max_items <= 0:
        max_items = 1

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
    for opportunity in ranked:
        if len(queued_items) >= max_items:
            break
        if not _should_include(opportunity, policy):
            skipped_filtered += 1
            continue
        queue_item = _queue_item(opportunity, source_path)
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
        policy=policy,
        policy_status=policy_status,
        source_path=source_path,
    )
    print(f"Opportunity approval queue written: {md_path}")
    print(f"Opportunity approval queue latest: {OUTPUT_DIR / 'opportunity_approval_queue_latest.md'}")
    print(f"Tool payload written: {json_path}")
    print(f"Queued now: {len(queued_items)} | pending total: {pending_total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
