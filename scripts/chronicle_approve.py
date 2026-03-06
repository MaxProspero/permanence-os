#!/usr/bin/env python3
"""
Manage human decisions for chronicle queue items.

This command updates approval status records only; it does not execute tasks.
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parents[1]
OUTPUT_DIR = Path(os.getenv("PERMANENCE_OUTPUT_DIR", str(BASE_DIR / "outputs")))
TOOL_DIR = Path(os.getenv("PERMANENCE_TOOL_DIR", str(BASE_DIR / "memory" / "tool")))
APPROVALS_PATH = Path(os.getenv("PERMANENCE_APPROVALS_PATH", str(BASE_DIR / "memory" / "approvals.json")))
DEFAULT_SOURCE = "chronicle_refinement_queue"
DECISION_TO_STATUS = {"approve": "APPROVED", "reject": "REJECTED", "defer": "DEFERRED"}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now().isoformat().replace("+00:00", "Z")


def _safe_text(text: str, max_chars: int = 220) -> str:
    payload = " ".join(str(text or "").split())
    if len(payload) <= max_chars:
        return payload
    return payload[: max_chars - 3].rstrip() + "..."


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _load_approvals(path: Path) -> list[dict[str, Any]]:
    payload = _read_json(path, [])
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict) and isinstance(payload.get("approvals"), list):
        return [row for row in payload.get("approvals", []) if isinstance(row, dict)]
    return []


def _normalize_sources(tokens: list[str]) -> list[str]:
    rows = [str(token or "").strip().lower() for token in tokens if str(token or "").strip()]
    if rows:
        return rows
    return [DEFAULT_SOURCE]


def _filtered(rows: list[dict[str, Any]], sources: list[str]) -> list[dict[str, Any]]:
    source_set = set(sources)
    return [row for row in rows if str(row.get("source") or "").strip().lower() in source_set]


def _status_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    out = {"PENDING_HUMAN_REVIEW": 0, "APPROVED": 0, "REJECTED": 0, "DEFERRED": 0, "OTHER": 0}
    for row in rows:
        status = str(row.get("status") or "").strip().upper()
        if status in out:
            out[status] += 1
        else:
            out["OTHER"] += 1
    return out


def _pending_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    pending = [row for row in rows if str(row.get("status") or "").strip().upper() == "PENDING_HUMAN_REVIEW"]
    pending.sort(key=lambda row: str(row.get("queued_at") or row.get("created_at") or ""))
    return pending


def _row_id(row: dict[str, Any]) -> str:
    return str(row.get("id") or row.get("proposal_id") or row.get("approval_id") or "").strip()


def _find_target(rows: list[dict[str, Any]], proposal_id: str) -> dict[str, Any] | None:
    token = str(proposal_id or "").strip()
    if not token:
        return None
    for row in rows:
        if token in {_row_id(row), str(row.get("source_opportunity_id") or "").strip(), str(row.get("source_report_id") or "").strip()}:
            return row
    return None


def _decide(
    *,
    rows: list[dict[str, Any]],
    sources: list[str],
    decision: str,
    proposal_id: str,
    decided_by: str,
    note: str,
) -> tuple[list[dict[str, Any]], dict[str, Any] | None, str | None]:
    scoped = _filtered(rows, sources)
    target = _find_target(scoped, proposal_id)
    if target is None:
        if proposal_id:
            return rows, None, f"proposal not found in source scope: {proposal_id}"
        pending = _pending_rows(scoped)
        if not pending:
            return rows, None, "no pending chronicle approvals found in source scope"
        target = pending[0]

    status = DECISION_TO_STATUS.get(str(decision or "").strip().lower())
    if not status:
        return rows, None, f"unsupported decision: {decision}"
    target["status"] = status
    target["decided_at"] = _now_iso()
    target["decided_by"] = str(decided_by or "operator").strip() or "operator"
    target["decision"] = str(decision).strip().lower()
    if str(note or "").strip():
        target["decision_note"] = str(note).strip()
    target["decision_source"] = "chronicle_approve_cli"
    return rows, target, None


def _write_outputs(
    *,
    action: str,
    approvals_path: Path,
    source_filters: list[str],
    rows: list[dict[str, Any]],
    target: dict[str, Any] | None,
    warnings: list[str],
    limit: int,
) -> tuple[Path, Path]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    TOOL_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _now().strftime("%Y%m%d-%H%M%S")
    md_path = OUTPUT_DIR / f"chronicle_approve_{stamp}.md"
    latest_md = OUTPUT_DIR / "chronicle_approve_latest.md"
    json_path = TOOL_DIR / f"chronicle_approve_{stamp}.json"

    scoped = _filtered(rows, source_filters)
    counts = _status_counts(scoped)
    pending = _pending_rows(scoped)

    lines = [
        "# Chronicle Approvals",
        "",
        f"Generated (UTC): {_now_iso()}",
        f"Action: {action}",
        f"Approvals path: {approvals_path}",
        f"Source filters: {', '.join(source_filters)}",
        "",
        "## Summary",
        f"- Scoped total: {len(scoped)}",
        f"- Pending: {counts.get('PENDING_HUMAN_REVIEW', 0)}",
        f"- Approved: {counts.get('APPROVED', 0)}",
        f"- Rejected: {counts.get('REJECTED', 0)}",
        f"- Deferred: {counts.get('DEFERRED', 0)}",
        "",
    ]

    if target:
        lines.extend(
            [
                "## Decision Applied",
                f"- id: {_row_id(target)}",
                f"- status: {target.get('status')}",
                f"- title: {_safe_text(str(target.get('title') or ''))}",
                "",
            ]
        )

    lines.append("## Pending Queue")
    head = pending[: max(1, int(limit))]
    if not head:
        lines.append("- No pending items in scope.")
    for idx, row in enumerate(head, start=1):
        lines.append(
            f"{idx}. {_row_id(row)} [{row.get('priority') or 'MEDIUM'}] {_safe_text(str(row.get('title') or ''))}"
        )

    if warnings:
        lines.extend(["", "## Warnings"])
        for warning in warnings:
            lines.append(f"- {warning}")

    lines.extend(
        [
            "",
            "## Governance Notes",
            "- Decision updates are logged in approvals; no task execution occurs here.",
            "- Use chronicle-execution-board after approvals are marked APPROVED.",
            "",
        ]
    )

    markdown = "\n".join(lines) + "\n"
    md_path.write_text(markdown, encoding="utf-8")
    latest_md.write_text(markdown, encoding="utf-8")

    payload = {
        "generated_at": _now_iso(),
        "action": action,
        "approvals_path": str(approvals_path),
        "source_filters": source_filters,
        "scoped_total": len(scoped),
        "counts": counts,
        "decision_target_id": _row_id(target) if target else "",
        "warnings": warnings,
        "pending_head": head,
        "latest_markdown": str(latest_md),
    }
    json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return md_path, json_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Review and decide chronicle queue approvals.")
    parser.add_argument("--action", choices=["status", "list", "decide"], default="status")
    parser.add_argument("--approvals-path", help="Override approvals JSON path")
    parser.add_argument("--source", action="append", default=[], help="Source filter (repeatable)")
    parser.add_argument("--limit", type=int, default=12, help="Number of pending rows to display")
    parser.add_argument("--decision", choices=["approve", "reject", "defer"], help="Decision for decide action")
    parser.add_argument("--proposal-id", help="Proposal/approval id (default: oldest pending in scope)")
    parser.add_argument("--decided-by", default="operator", help="Decision actor")
    parser.add_argument("--note", default="", help="Optional decision note")
    args = parser.parse_args(argv)

    approvals_path = Path(args.approvals_path).expanduser() if args.approvals_path else APPROVALS_PATH
    source_filters = _normalize_sources(args.source)
    warnings: list[str] = []
    rows = _load_approvals(approvals_path)
    target: dict[str, Any] | None = None

    if args.action == "decide":
        if not args.decision:
            warnings.append("decision is required for --action decide")
        else:
            rows, target, err = _decide(
                rows=rows,
                sources=source_filters,
                decision=str(args.decision),
                proposal_id=str(args.proposal_id or ""),
                decided_by=str(args.decided_by or "operator"),
                note=str(args.note or ""),
            )
            if err:
                warnings.append(err)
            else:
                _write_json(approvals_path, rows)

    md_path, json_path = _write_outputs(
        action=args.action,
        approvals_path=approvals_path,
        source_filters=source_filters,
        rows=rows,
        target=target,
        warnings=warnings,
        limit=max(1, int(args.limit)),
    )
    scoped = _filtered(rows, source_filters)
    counts = _status_counts(scoped)
    print(f"Chronicle approvals report: {md_path}")
    print(f"Chronicle approvals latest: {OUTPUT_DIR / 'chronicle_approve_latest.md'}")
    print(f"Tool payload: {json_path}")
    print(f"Scoped total: {len(scoped)} | pending: {counts.get('PENDING_HUMAN_REVIEW', 0)}")
    if target:
        print(f"Decision applied to: {_row_id(target)} -> {target.get('status')}")
    if warnings:
        print(f"Warnings: {len(warnings)}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
