#!/usr/bin/env python3
"""
Build a scoped execution board from approved chronicle queue items.

Advisory only: this script never auto-executes tasks.
"""

from __future__ import annotations

import argparse
import json
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parents[1]
OUTPUT_DIR = Path(os.getenv("PERMANENCE_OUTPUT_DIR", str(BASE_DIR / "outputs")))
TOOL_DIR = Path(os.getenv("PERMANENCE_TOOL_DIR", str(BASE_DIR / "memory" / "tool")))
WORKING_DIR = Path(os.getenv("PERMANENCE_WORKING_DIR", str(BASE_DIR / "memory" / "working")))
APPROVALS_PATH = Path(os.getenv("PERMANENCE_APPROVALS_PATH", str(BASE_DIR / "memory" / "approvals.json")))
TASKS_PATH = Path(
    os.getenv("PERMANENCE_CHRONICLE_TASKS_PATH", str(WORKING_DIR / "chronicle_execution_tasks.json"))
)

PRIORITY_ORDER = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
RISK_ORDER = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
DEFAULT_SOURCE = "chronicle_refinement_queue"


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


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _normalize_priority(value: Any) -> str:
    token = str(value or "").strip().upper()
    if token in {"LOW", "MEDIUM", "HIGH"}:
        return token
    return "MEDIUM"


def _normalize_risk(value: Any) -> str:
    token = str(value or "").strip().upper()
    if token in {"LOW", "MEDIUM", "HIGH"}:
        return token
    return "MEDIUM"


def _action_type(scope: str, risk_tier: str) -> str:
    scope_token = str(scope or "").strip().lower()
    if scope_token in {"manual_financial_review"} or risk_tier == "HIGH":
        return "risk_review"
    if scope_token in {"canon_amendment"}:
        return "governance_review"
    if scope_token in {"system_improvement", "agent_update"}:
        return "build"
    if scope_token in {"business_execution", "opportunity_execution"}:
        return "experiment"
    return "execution"


def _due_hint(priority: str) -> str:
    if priority == "HIGH":
        return "24h"
    if priority == "MEDIUM":
        return "72h"
    return "7d"


def _scope_package(row: dict[str, Any], action_type: str) -> str:
    scope = str(row.get("implementation_scope") or "").strip().lower()
    text = (
        f"{row.get('title') or ''} "
        f"{row.get('proposed_change') or ''} "
        f"{row.get('draft_codex_task') or ''} "
        f"{row.get('finding_summary') or ''}"
    ).lower()
    if scope == "canon_amendment":
        return "governance_patch"
    if "queue" in text or "backlog" in text:
        return "queue_hygiene"
    if "test" in text or "regression" in text:
        return "reliability_patch"
    if "roadmap" in text or "priority" in text or "direction" in text:
        return "roadmap_update"
    if "telegram" in text or "discord" in text or "comms" in text:
        return "comms_hardening"
    if action_type == "governance_review":
        return "governance_review"
    if action_type == "build":
        return "system_build"
    return "execution_task"


def _success_criteria(scope_package: str, scope: str) -> str:
    if scope_package == "queue_hygiene":
        return "Queue/backlog metrics improve and daily closeout remains <= 1 pending."
    if scope_package == "reliability_patch":
        return "Root cause resolved and regression coverage added for the failure path."
    if scope_package == "roadmap_update":
        return "Roadmap sequence is updated with explicit owners and measurable milestones."
    if scope_package == "comms_hardening":
        return "Communication loops remain fresh and pass status/doctor checks without warnings."
    if scope in {"canon_amendment"}:
        return "Canon review completed with explicit approve/reject decision and rationale."
    return "Scoped task is implemented with a verifiable local validation step."


def _deliverables(next_action: str, scope_package: str) -> list[str]:
    action = str(next_action or "Define and implement scoped change.").strip()
    return [
        f"Scoped plan: {action}",
        f"Implementation package: {scope_package}",
        "Validation note: run targeted checks/tests and capture outcome in report.",
    ]


def _task_from_approval(row: dict[str, Any]) -> dict[str, Any]:
    item_id = str(row.get("id") or row.get("proposal_id") or row.get("approval_id") or "unknown")
    priority = _normalize_priority(row.get("priority"))
    risk = _normalize_risk(row.get("risk_tier") or row.get("priority"))
    scope = str(row.get("implementation_scope") or "execution").strip()
    next_action = str(row.get("draft_codex_task") or row.get("proposed_change") or "Define scoped next action.")
    action_type = _action_type(scope, risk)
    scope_package = _scope_package(row, action_type=action_type)
    task = {
        "task_id": f"CEX-{item_id[-10:]}",
        "approval_id": item_id,
        "title": str(row.get("title") or "Approved chronicle action"),
        "priority": priority,
        "risk_tier": risk,
        "implementation_scope": scope,
        "action_type": action_type,
        "scope_package": scope_package,
        "next_action": next_action,
        "deliverables": _deliverables(next_action, scope_package),
        "success_criteria": _success_criteria(scope_package, scope),
        "expected_benefit": str(row.get("expected_benefit") or ""),
        "risk_if_ignored": str(row.get("risk_if_ignored") or ""),
        "source": str(row.get("source") or "chronicle_refinement_queue"),
        "status": "READY",
        "due_hint": _due_hint(priority),
        "created_at": _now_iso(),
    }
    return task


def _load_approvals(path: Path) -> list[dict[str, Any]]:
    payload = _read_json(path, [])
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict) and isinstance(payload.get("approvals"), list):
        return [row for row in payload["approvals"] if isinstance(row, dict)]
    return []


def _sort_tasks(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        rows,
        key=lambda row: (
            PRIORITY_ORDER.get(str(row.get("priority")), 9),
            RISK_ORDER.get(str(row.get("risk_tier")), 9),
            str(row.get("title", "")).lower(),
        ),
    )


def _write_outputs(
    *,
    approved_rows: list[dict[str, Any]],
    tasks: list[dict[str, Any]],
    marked_count: int,
    sources: list[str],
    include_canon: bool,
    limit: int,
) -> tuple[Path, Path]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    TOOL_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _now().strftime("%Y%m%d-%H%M%S")
    md_path = OUTPUT_DIR / f"chronicle_execution_board_{stamp}.md"
    latest_md = OUTPUT_DIR / "chronicle_execution_board_latest.md"
    json_path = TOOL_DIR / f"chronicle_execution_board_{stamp}.json"

    priority_counts = Counter(str(row.get("priority") or "MEDIUM") for row in tasks)
    package_counts = Counter(str(row.get("scope_package") or "execution_task") for row in tasks)

    lines = [
        "# Chronicle Execution Board",
        "",
        f"Generated (UTC): {_now_iso()}",
        f"Approvals source: {APPROVALS_PATH}",
        f"Task board: {TASKS_PATH}",
        "",
        "## Summary",
        f"- Source filters: {', '.join(sources)}",
        f"- Include canon amendments: {include_canon}",
        f"- Approved chronicle items found: {len(approved_rows)}",
        f"- Tasks surfaced (limit {limit}): {len(tasks)}",
        f"- Priority mix: HIGH={priority_counts.get('HIGH', 0)}, MEDIUM={priority_counts.get('MEDIUM', 0)}, LOW={priority_counts.get('LOW', 0)}",
        f"- Newly marked queued: {marked_count}",
        "",
        "## Scope Packages",
    ]
    if package_counts:
        for name, count in sorted(package_counts.items(), key=lambda item: (-item[1], item[0])):
            lines.append(f"- {name}: {count}")
    else:
        lines.append("- none")

    lines.extend(["", "## Execution Queue"])
    if not tasks:
        lines.append("- No approved chronicle tasks available.")
    for idx, row in enumerate(tasks, start=1):
        lines.extend(
            [
                f"{idx}. {row.get('title')} [{row.get('priority')}]",
                (
                    "   - "
                    f"scope_package={row.get('scope_package')} | action_type={row.get('action_type')} | "
                    f"risk={row.get('risk_tier')} | due={row.get('due_hint')}"
                ),
                f"   - next_action={row.get('next_action')}",
                f"   - success_criteria={row.get('success_criteria')}",
            ]
        )

    lines.extend(
        [
            "",
            "## Governance Notes",
            "- This board is planning-only and does not auto-execute any task.",
            "- Human control remains final for canon changes, financial actions, and external publishing.",
            "",
        ]
    )

    report = "\n".join(lines)
    md_path.write_text(report, encoding="utf-8")
    latest_md.write_text(report, encoding="utf-8")

    payload = {
        "generated_at": _now_iso(),
        "approvals_path": str(APPROVALS_PATH),
        "tasks_path": str(TASKS_PATH),
        "source_filters": sources,
        "include_canon": bool(include_canon),
        "approved_count": len(approved_rows),
        "task_count": len(tasks),
        "limit": limit,
        "marked_queued_count": marked_count,
        "tasks": tasks,
        "latest_markdown": str(latest_md),
    }
    json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return md_path, json_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build chronicle execution board from approved queue items.")
    parser.add_argument("--limit", type=int, default=8, help="Max surfaced tasks")
    parser.add_argument(
        "--source",
        action="append",
        default=[],
        help="Approval source filter (repeatable; default: chronicle_refinement_queue)",
    )
    parser.add_argument("--no-canon", action="store_true", help="Exclude canon_amendment items")
    parser.add_argument(
        "--no-mark-queued",
        action="store_true",
        help="Do not update approvals with execution queue metadata",
    )
    args = parser.parse_args(argv)

    sources = [str(token).strip() for token in args.source if str(token).strip()]
    if not sources:
        sources = [DEFAULT_SOURCE]
    source_set = {token.lower() for token in sources}
    include_canon = not bool(args.no_canon)
    limit = max(1, int(args.limit))

    approvals = _load_approvals(APPROVALS_PATH)
    approved_rows = [
        row
        for row in approvals
        if str(row.get("status") or "").upper() == "APPROVED"
        and str(row.get("source") or "").strip().lower() in source_set
        and (include_canon or str(row.get("implementation_scope") or "").strip().lower() != "canon_amendment")
    ]
    tasks = _sort_tasks([_task_from_approval(row) for row in approved_rows])[:limit]

    _write_json(
        TASKS_PATH,
        {
            "generated_at": _now_iso(),
            "approvals_path": str(APPROVALS_PATH),
            "source_filters": sources,
            "include_canon": include_canon,
            "task_count": len(tasks),
            "tasks": tasks,
        },
    )

    marked_count = 0
    if not args.no_mark_queued:
        for row in approvals:
            if str(row.get("status") or "").upper() != "APPROVED":
                continue
            if str(row.get("source") or "").strip().lower() not in source_set:
                continue
            if (not include_canon) and str(row.get("implementation_scope") or "").strip().lower() == "canon_amendment":
                continue
            execution_status = str(row.get("execution_status") or "").strip().upper()
            if execution_status:
                continue
            row["execution_status"] = "QUEUED_FOR_EXECUTION"
            row["execution_queue"] = "chronicle_execution_board"
            row["execution_queued_at"] = _now_iso()
            marked_count += 1
        if marked_count:
            _write_json(APPROVALS_PATH, approvals)

    md_path, json_path = _write_outputs(
        approved_rows=approved_rows,
        tasks=tasks,
        marked_count=marked_count,
        sources=sources,
        include_canon=include_canon,
        limit=limit,
    )
    print(f"Chronicle execution board written: {md_path}")
    print(f"Chronicle execution board latest: {OUTPUT_DIR / 'chronicle_execution_board_latest.md'}")
    print(f"Task board written: {TASKS_PATH}")
    print(f"Tool payload written: {json_path}")
    print(f"Approved chronicle items found: {len(approved_rows)} | surfaced tasks: {len(tasks)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
