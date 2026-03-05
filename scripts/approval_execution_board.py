#!/usr/bin/env python3
"""
Build an execution board from human-approved queue items.

This does not auto-execute external actions. It converts approvals into
prioritized, human-visible work items.
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
WORKING_DIR = Path(os.getenv("PERMANENCE_WORKING_DIR", str(BASE_DIR / "memory" / "working")))
APPROVALS_PATH = Path(os.getenv("PERMANENCE_APPROVALS_PATH", str(BASE_DIR / "memory" / "approvals.json")))
TASKS_PATH = Path(
    os.getenv("PERMANENCE_APPROVED_TASKS_PATH", str(WORKING_DIR / "approved_execution_tasks.json"))
)

PRIORITY_ORDER = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
RISK_ORDER = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}


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


def _task_from_approval(row: dict[str, Any]) -> dict[str, Any]:
    item_id = str(row.get("id") or row.get("proposal_id") or row.get("approval_id") or "unknown")
    priority = _normalize_priority(row.get("priority"))
    risk = _normalize_risk(row.get("risk_tier") or row.get("priority"))
    scope = str(row.get("implementation_scope") or "execution").strip()
    task = {
        "task_id": f"AEX-{item_id[-10:]}",
        "approval_id": item_id,
        "title": str(row.get("title") or "Approved action"),
        "priority": priority,
        "risk_tier": risk,
        "implementation_scope": scope,
        "action_type": _action_type(scope, risk),
        "next_action": str(row.get("draft_codex_task") or row.get("proposed_change") or "Define scoped next action."),
        "expected_benefit": str(row.get("expected_benefit") or ""),
        "risk_if_ignored": str(row.get("risk_if_ignored") or ""),
        "source": str(row.get("source") or "approval_queue"),
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
    approved_rows: list[dict[str, Any]],
    tasks: list[dict[str, Any]],
    marked_count: int,
    limit: int,
) -> tuple[Path, Path]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    TOOL_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _now().strftime("%Y%m%d-%H%M%S")
    md_path = OUTPUT_DIR / f"approval_execution_board_{stamp}.md"
    latest_md = OUTPUT_DIR / "approval_execution_board_latest.md"
    json_path = TOOL_DIR / f"approval_execution_board_{stamp}.json"

    high = sum(1 for row in tasks if str(row.get("priority")) == "HIGH")
    medium = sum(1 for row in tasks if str(row.get("priority")) == "MEDIUM")
    low = sum(1 for row in tasks if str(row.get("priority")) == "LOW")

    lines = [
        "# Approval Execution Board",
        "",
        f"Generated (UTC): {_now_iso()}",
        f"Approvals source: {APPROVALS_PATH}",
        f"Task board: {TASKS_PATH}",
        "",
        "## Summary",
        f"- Approved items found: {len(approved_rows)}",
        f"- Tasks surfaced (limit {limit}): {len(tasks)}",
        f"- Priority mix: HIGH={high}, MEDIUM={medium}, LOW={low}",
        f"- Newly marked queued: {marked_count}",
        "",
        "## Execution Queue",
    ]
    if not tasks:
        lines.append("- No approved tasks available.")
    for idx, row in enumerate(tasks, start=1):
        lines.extend(
            [
                f"{idx}. {row.get('title')} [{row.get('priority')}]",
                (
                    "   - "
                    f"action_type={row.get('action_type')} | risk={row.get('risk_tier')} | "
                    f"scope={row.get('implementation_scope')} | due={row.get('due_hint')}"
                ),
                f"   - next_action={row.get('next_action')}",
            ]
        )

    lines.extend(
        [
            "",
            "## Governance Notes",
            "- This board schedules approved work; it does not bypass any non-negotiables.",
            "- Financial, legal, and public messaging actions remain manually controlled.",
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
    parser = argparse.ArgumentParser(description="Build execution board from approved queue items.")
    parser.add_argument("--limit", type=int, default=12, help="Max surfaced tasks in the execution board")
    parser.add_argument(
        "--no-mark-queued",
        action="store_true",
        help="Do not update approvals with execution_status metadata",
    )
    args = parser.parse_args(argv)

    limit = max(1, int(args.limit))
    approvals = _load_approvals(APPROVALS_PATH)
    approved_rows = [row for row in approvals if str(row.get("status") or "").upper() == "APPROVED"]

    tasks = _sort_tasks([_task_from_approval(row) for row in approved_rows])[:limit]
    _write_json(
        TASKS_PATH,
        {
            "generated_at": _now_iso(),
            "approvals_path": str(APPROVALS_PATH),
            "task_count": len(tasks),
            "tasks": tasks,
        },
    )

    marked_count = 0
    if not args.no_mark_queued:
        for row in approvals:
            if str(row.get("status") or "").upper() != "APPROVED":
                continue
            execution_status = str(row.get("execution_status") or "").strip().upper()
            if execution_status:
                continue
            row["execution_status"] = "QUEUED_FOR_EXECUTION"
            row["execution_queued_at"] = _now_iso()
            marked_count += 1
        if marked_count:
            _write_json(APPROVALS_PATH, approvals)

    md_path, json_path = _write_outputs(
        approved_rows=approved_rows,
        tasks=tasks,
        marked_count=marked_count,
        limit=limit,
    )
    print(f"Approval execution board written: {md_path}")
    print(f"Approval execution board latest: {OUTPUT_DIR / 'approval_execution_board_latest.md'}")
    print(f"Task board written: {TASKS_PATH}")
    print(f"Tool payload written: {json_path}")
    print(f"Approved items found: {len(approved_rows)} | surfaced tasks: {len(tasks)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
