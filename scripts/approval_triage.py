#!/usr/bin/env python3
"""
Review and decide pending approvals from memory/approvals.json.

This script updates approval statuses only and never executes external actions.
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
DECISION_TO_STATUS = {"approve": "APPROVED", "reject": "REJECTED", "defer": "DEFERRED"}
LEVEL_RANK = {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}


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
    out: list[str] = []
    for token in tokens:
        value = str(token or "").strip().lower()
        if not value:
            continue
        if value not in out:
            out.append(value)
    return out


def _row_id(row: dict[str, Any]) -> str:
    return str(row.get("id") or row.get("proposal_id") or row.get("approval_id") or "").strip()


def _row_source(row: dict[str, Any]) -> str:
    return str(row.get("source") or "unknown").strip().lower() or "unknown"


def _row_priority(row: dict[str, Any]) -> str:
    value = str(row.get("priority") or "MEDIUM").strip().upper() or "MEDIUM"
    return value if value in LEVEL_RANK else "MEDIUM"


def _row_risk_level(row: dict[str, Any]) -> str:
    value = str(row.get("risk_level") or row.get("risk") or "").strip().upper()
    if value in LEVEL_RANK:
        return value
    return _row_priority(row)


def _normalize_level(level: str, default: str = "") -> str:
    token = str(level or "").strip().upper()
    if not token:
        return default
    return token if token in LEVEL_RANK else default


def _in_scope(row: dict[str, Any], sources: list[str]) -> bool:
    if not sources:
        return True
    return _row_source(row) in set(sources)


def _status_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    out = {"PENDING_HUMAN_REVIEW": 0, "APPROVED": 0, "REJECTED": 0, "DEFERRED": 0, "OTHER": 0}
    for row in rows:
        status = str(row.get("status") or "").strip().upper()
        if status in out:
            out[status] += 1
        else:
            out["OTHER"] += 1
    return out


def _is_level_at_or_below(value: str, ceiling: str) -> bool:
    value_norm = _normalize_level(value)
    ceiling_norm = _normalize_level(ceiling)
    if not value_norm or not ceiling_norm:
        return True
    return LEVEL_RANK[value_norm] <= LEVEL_RANK[ceiling_norm]


def _pending_rows(
    rows: list[dict[str, Any]],
    sources: list[str],
    *,
    order: str = "oldest",
    max_priority: str = "",
    max_risk: str = "",
) -> list[dict[str, Any]]:
    pending = [
        row
        for row in rows
        if _in_scope(row, sources) and str(row.get("status") or "").strip().upper() == "PENDING_HUMAN_REVIEW"
    ]
    ceiling_priority = _normalize_level(max_priority)
    ceiling_risk = _normalize_level(max_risk)
    if ceiling_priority:
        pending = [row for row in pending if _is_level_at_or_below(_row_priority(row), ceiling_priority)]
    if ceiling_risk:
        pending = [row for row in pending if _is_level_at_or_below(_row_risk_level(row), ceiling_risk)]

    if str(order or "").strip().lower() == "top":
        pending.sort(
            key=lambda row: (
                -LEVEL_RANK.get(_row_priority(row), 2),
                -float(row.get("opportunity_score") or 0.0),
                str(row.get("queued_at") or row.get("created_at") or row.get("timestamp") or ""),
            )
        )
    else:
        pending.sort(key=lambda row: str(row.get("queued_at") or row.get("created_at") or row.get("timestamp") or ""))
    return pending


def _find_target(rows: list[dict[str, Any]], proposal_id: str, sources: list[str]) -> dict[str, Any] | None:
    token = str(proposal_id or "").strip()
    if not token:
        return None
    token_lower = token.lower()
    for row in rows:
        if not _in_scope(row, sources):
            continue
        candidates = {
            _row_id(row).lower(),
            str(row.get("source_opportunity_id") or "").strip().lower(),
            str(row.get("source_report_id") or "").strip().lower(),
        }
        if token_lower in candidates:
            return row
    return None


def _count_by_source(rows: list[dict[str, Any]], status_filter: str = "") -> list[tuple[str, int]]:
    counts: dict[str, int] = {}
    needle = str(status_filter or "").strip().upper()
    for row in rows:
        status = str(row.get("status") or "").strip().upper()
        if needle and status != needle:
            continue
        source = _row_source(row)
        counts[source] = counts.get(source, 0) + 1
    return sorted(counts.items(), key=lambda item: item[1], reverse=True)


def _apply_decision(
    *,
    target: dict[str, Any],
    decision: str,
    status: str,
    decided_by: str,
    note: str,
) -> None:
    target["status"] = status
    target["decision"] = str(decision).strip().lower()
    target["decided_at"] = _now_iso()
    target["decided_by"] = str(decided_by or "operator").strip() or "operator"
    target["decision_source"] = "approval_triage_cli"
    if str(note or "").strip():
        target["decision_note"] = str(note).strip()


def _decide(
    *,
    rows: list[dict[str, Any]],
    sources: list[str],
    decision: str,
    proposal_id: str,
    decided_by: str,
    note: str,
) -> tuple[list[dict[str, Any]], dict[str, Any] | None, str | None]:
    status = DECISION_TO_STATUS.get(str(decision or "").strip().lower())
    if not status:
        return rows, None, f"unsupported decision: {decision}"

    target = _find_target(rows, proposal_id, sources) if proposal_id else None
    if target is None:
        pending = _pending_rows(rows, sources)
        if proposal_id and not pending:
            return rows, None, f"proposal not found in scope: {proposal_id}"
        if not pending:
            return rows, None, "no pending approvals found in scope"
        target = pending[0]

    current_status = str(target.get("status") or "").strip().upper()
    if current_status != "PENDING_HUMAN_REVIEW":
        return rows, None, f"target is not pending: {_row_id(target)} ({current_status})"

    _apply_decision(target=target, decision=decision, status=status, decided_by=decided_by, note=note)
    return rows, target, None


def _decide_batch(
    *,
    rows: list[dict[str, Any]],
    sources: list[str],
    decision: str,
    proposal_id: str,
    decided_by: str,
    note: str,
    batch_size: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    warnings: list[str] = []
    decided: list[dict[str, Any]] = []
    cap = max(1, int(batch_size))

    if str(proposal_id or "").strip():
        rows, target, error = _decide(
            rows=rows,
            sources=sources,
            decision=decision,
            proposal_id=proposal_id,
            decided_by=decided_by,
            note=note,
        )
        if error:
            warnings.append(error)
        elif target is not None:
            decided.append(target)

    while len(decided) < cap:
        rows, target, error = _decide(
            rows=rows,
            sources=sources,
            decision=decision,
            proposal_id="",
            decided_by=decided_by,
            note=note,
        )
        if error:
            if (not decided) or ("no pending approvals found in scope" not in error.lower()):
                warnings.append(error)
            break
        if target is None:
            break
        decided.append(target)
    return rows, decided, warnings


def _decide_batch_safe(
    *,
    rows: list[dict[str, Any]],
    sources: list[str],
    decision: str,
    proposal_id: str,
    decided_by: str,
    note: str,
    batch_size: int,
    safe_max_priority: str,
    safe_max_risk: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str], int]:
    warnings: list[str] = []
    decided: list[dict[str, Any]] = []
    cap = max(1, int(batch_size))
    status = DECISION_TO_STATUS.get(str(decision or "").strip().lower())
    if not status:
        return rows, decided, [f"unsupported decision: {decision}"], 0
    if not sources:
        return rows, decided, ["safe batch requires at least one --source allowlist filter"], 0

    safe_priority = _normalize_level(safe_max_priority, default="MEDIUM")
    safe_risk = _normalize_level(safe_max_risk, default="HIGH")
    eligible = _pending_rows(
        rows,
        sources,
        order="oldest",
        max_priority=safe_priority,
        max_risk=safe_risk,
    )
    eligible_ids = {_row_id(row) for row in eligible}

    if str(proposal_id or "").strip():
        target = _find_target(eligible, proposal_id, sources)
        if target is None:
            warnings.append(f"proposal not eligible for safe batch: {proposal_id}")
        else:
            _apply_decision(target=target, decision=decision, status=status, decided_by=decided_by, note=note)
            decided.append(target)
            eligible_ids.discard(_row_id(target))

    if len(decided) < cap:
        for row in eligible:
            row_id = _row_id(row)
            if row_id not in eligible_ids:
                continue
            _apply_decision(target=row, decision=decision, status=status, decided_by=decided_by, note=note)
            decided.append(row)
            if len(decided) >= cap:
                break

    if not decided:
        warnings.append("no safe-eligible pending approvals found for decide-batch-safe")
    return rows, decided, warnings, len(eligible)


def _write_outputs(
    *,
    action: str,
    approvals_path: Path,
    source_filters: list[str],
    rows: list[dict[str, Any]],
    targets: list[dict[str, Any]],
    warnings: list[str],
    limit: int,
    safe_max_priority: str = "",
    safe_max_risk: str = "",
) -> tuple[Path, Path]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    TOOL_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _now().strftime("%Y%m%d-%H%M%S")
    md_path = OUTPUT_DIR / f"approval_triage_{stamp}.md"
    latest_md = OUTPUT_DIR / "approval_triage_latest.md"
    json_path = TOOL_DIR / f"approval_triage_{stamp}.json"

    scoped = [row for row in rows if _in_scope(row, source_filters)]
    counts = _status_counts(scoped)
    sort_mode = "top" if action == "top" else "oldest"
    pending = _pending_rows(
        rows,
        source_filters,
        order=sort_mode,
        max_priority=_normalize_level(safe_max_priority),
        max_risk=_normalize_level(safe_max_risk),
    )
    source_counts = _count_by_source(scoped)
    pending_by_source = _count_by_source(scoped, status_filter="PENDING_HUMAN_REVIEW")

    lines = [
        "# Approval Triage",
        "",
        f"Generated (UTC): {_now_iso()}",
        f"Action: {action}",
        f"Approvals path: {approvals_path}",
        f"Source filters: {', '.join(source_filters) if source_filters else 'ALL'}",
        f"Safe max priority: {_normalize_level(safe_max_priority) or '-'}",
        f"Safe max risk: {_normalize_level(safe_max_risk) or '-'}",
        "",
        "## Summary",
        f"- Scoped total: {len(scoped)}",
        f"- Pending: {counts.get('PENDING_HUMAN_REVIEW', 0)}",
        f"- Approved: {counts.get('APPROVED', 0)}",
        f"- Rejected: {counts.get('REJECTED', 0)}",
        f"- Deferred: {counts.get('DEFERRED', 0)}",
        "",
        "## Source Mix (Scoped)",
    ]
    if source_counts:
        for source, count in source_counts[: max(3, int(limit))]:
            lines.append(f"- {source}: {count}")
    else:
        lines.append("- No approvals in scope.")

    lines.extend(["", "## Pending By Source"])
    if pending_by_source:
        for source, count in pending_by_source[: max(3, int(limit))]:
            lines.append(f"- {source}: {count}")
    else:
        lines.append("- No pending approvals in scope.")

    if targets:
        lines.extend(
            [
                "",
                "## Decisions Applied",
            ]
        )
        for row in targets:
            lines.append(
                f"- {_row_id(row)} [{row.get('status')}] source={_row_source(row)} "
                f"title={_safe_text(str(row.get('title') or ''))}"
            )

    lines.extend(["", "## Pending Queue"])
    head = pending[: max(1, int(limit))]
    if not head:
        lines.append("- No pending items in scope.")
    for idx, row in enumerate(head, start=1):
        lines.append(
            f"{idx}. {_row_id(row)} [{row.get('priority') or 'MEDIUM'}] "
            f"{_safe_text(str(row.get('title') or ''))} (source={_row_source(row)})"
        )

    if warnings:
        lines.extend(["", "## Warnings"])
        for warning in warnings:
            lines.append(f"- {warning}")

    lines.extend(
        [
            "",
            "## Governance Notes",
            "- This command only updates approval decisions and metadata.",
            "- It never executes money, publishing, or connector write actions.",
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
        "safe_max_priority": _normalize_level(safe_max_priority),
        "safe_max_risk": _normalize_level(safe_max_risk),
        "scoped_total": len(scoped),
        "counts": counts,
        "pending_by_source": pending_by_source,
        "decision_target_id": _row_id(targets[0]) if targets else "",
        "decision_target_ids": [_row_id(row) for row in targets],
        "warnings": warnings,
        "pending_head": head,
        "latest_markdown": str(latest_md),
    }
    json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return md_path, json_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Review and triage pending approvals.")
    parser.add_argument(
        "--action",
        choices=["status", "list", "top", "decide", "decide-batch", "decide-batch-safe"],
        default="status",
    )
    parser.add_argument("--approvals-path", help="Override approvals JSON path")
    parser.add_argument("--source", action="append", default=[], help="Source scope filter (repeatable)")
    parser.add_argument("--limit", type=int, default=12, help="Pending rows in report")
    parser.add_argument("--decision", choices=["approve", "reject", "defer"], help="Decision for decide action")
    parser.add_argument("--proposal-id", help="Target approval id (default: oldest pending in scope)")
    parser.add_argument("--batch-size", type=int, default=3, help="Batch size for --action decide-batch")
    parser.add_argument(
        "--safe-max-priority",
        choices=["low", "medium", "high", "critical"],
        default="medium",
        help="For decide-batch-safe: only include rows at or below this priority",
    )
    parser.add_argument(
        "--safe-max-risk",
        choices=["low", "medium", "high", "critical"],
        default="high",
        help="For decide-batch-safe: only include rows at or below this effective risk level",
    )
    parser.add_argument("--decided-by", default="operator", help="Decision actor")
    parser.add_argument("--note", default="", help="Optional decision note")
    args = parser.parse_args(argv)

    approvals_path = Path(args.approvals_path).expanduser() if args.approvals_path else APPROVALS_PATH
    source_filters = _normalize_sources(args.source)
    rows = _load_approvals(approvals_path)
    warnings: list[str] = []
    targets: list[dict[str, Any]] = []
    safe_eligible_count = 0

    if args.action == "decide":
        if not args.decision:
            warnings.append("decision is required for --action decide")
        else:
            rows, target, error = _decide(
                rows=rows,
                sources=source_filters,
                decision=str(args.decision),
                proposal_id=str(args.proposal_id or ""),
                decided_by=str(args.decided_by or "operator"),
                note=str(args.note or ""),
            )
            if error:
                warnings.append(error)
            else:
                if target is not None:
                    targets.append(target)
                _write_json(approvals_path, rows)
    elif args.action == "decide-batch":
        if not args.decision:
            warnings.append("decision is required for --action decide-batch")
        else:
            rows, targets, batch_warnings = _decide_batch(
                rows=rows,
                sources=source_filters,
                decision=str(args.decision),
                proposal_id=str(args.proposal_id or ""),
                decided_by=str(args.decided_by or "operator"),
                note=str(args.note or ""),
                batch_size=max(1, int(args.batch_size)),
            )
            warnings.extend(batch_warnings)
            if targets:
                _write_json(approvals_path, rows)
    elif args.action == "decide-batch-safe":
        if not args.decision:
            warnings.append("decision is required for --action decide-batch-safe")
        else:
            rows, targets, batch_warnings, safe_eligible_count = _decide_batch_safe(
                rows=rows,
                sources=source_filters,
                decision=str(args.decision),
                proposal_id=str(args.proposal_id or ""),
                decided_by=str(args.decided_by or "operator"),
                note=str(args.note or ""),
                batch_size=max(1, int(args.batch_size)),
                safe_max_priority=str(args.safe_max_priority or "medium"),
                safe_max_risk=str(args.safe_max_risk or "high"),
            )
            warnings.extend(batch_warnings)
            if targets:
                _write_json(approvals_path, rows)

    md_path, json_path = _write_outputs(
        action=args.action,
        approvals_path=approvals_path,
        source_filters=source_filters,
        rows=rows,
        targets=targets,
        warnings=warnings,
        limit=max(1, int(args.limit)),
        safe_max_priority=str(args.safe_max_priority or "") if args.action == "decide-batch-safe" else "",
        safe_max_risk=str(args.safe_max_risk or "") if args.action == "decide-batch-safe" else "",
    )

    scoped = [row for row in rows if _in_scope(row, source_filters)]
    counts = _status_counts(scoped)
    print(f"Approval triage report: {md_path}")
    print(f"Approval triage latest: {OUTPUT_DIR / 'approval_triage_latest.md'}")
    print(f"Tool payload: {json_path}")
    print(f"Scoped total: {len(scoped)} | pending: {counts.get('PENDING_HUMAN_REVIEW', 0)}")
    if targets:
        print(f"Decisions applied: {len(targets)}")
        print(f"Latest decision: {_row_id(targets[-1])} -> {targets[-1].get('status')}")
    if args.action == "decide-batch-safe":
        print(
            "Safe filters: "
            f"priority<={_normalize_level(str(args.safe_max_priority or ''), default='MEDIUM')} "
            f"risk<={_normalize_level(str(args.safe_max_risk or ''), default='HIGH')} "
            f"eligible={safe_eligible_count}"
        )
    if warnings:
        print(f"Warnings: {len(warnings)}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
