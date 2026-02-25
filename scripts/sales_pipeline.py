#!/usr/bin/env python3
"""
Simple sales pipeline manager for FOUNDATION revenue operations.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parents[1]
WORKING_DIR = Path(os.getenv("PERMANENCE_WORKING_DIR", str(BASE_DIR / "memory" / "working")))
PIPELINE_PATH = Path(os.getenv("PERMANENCE_SALES_PIPELINE_PATH", str(WORKING_DIR / "sales_pipeline.json")))

OPEN_STAGES = {"lead", "qualified", "call_scheduled", "proposal_sent", "negotiation"}
CLOSED_STAGES = {"won", "lost"}
ALL_STAGES = sorted(OPEN_STAGES | CLOSED_STAGES)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_pipeline() -> list[dict[str, Any]]:
    if not PIPELINE_PATH.exists():
        return []
    try:
        data = json.loads(PIPELINE_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    rows: list[dict[str, Any]] = []
    for row in data:
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _save_pipeline(rows: list[dict[str, Any]]) -> None:
    PIPELINE_PATH.parent.mkdir(parents=True, exist_ok=True)
    PIPELINE_PATH.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")


def _lead_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return f"L-{stamp}"


def _find(rows: list[dict[str, Any]], lead_id: str) -> dict[str, Any] | None:
    for row in rows:
        if str(row.get("lead_id")) == lead_id:
            return row
    return None


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def cmd_init(_args: argparse.Namespace) -> int:
    rows = _load_pipeline()
    _save_pipeline(rows)
    print(f"Pipeline initialized: {PIPELINE_PATH}")
    print(f"Leads: {len(rows)}")
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    rows = _load_pipeline()
    if args.stage:
        rows = [r for r in rows if str(r.get("stage")) == args.stage]
    if args.open_only:
        rows = [r for r in rows if str(r.get("stage")) in OPEN_STAGES]
    rows.sort(key=lambda r: str(r.get("updated_at", "")), reverse=True)
    if not rows:
        print("No leads found.")
        return 0

    print("Sales Pipeline")
    print("==============")
    for row in rows:
        lead_id = row.get("lead_id", "unknown")
        name = row.get("name", "unknown")
        stage = row.get("stage", "unknown")
        est_value = _as_float(row.get("est_value"), 0.0)
        next_action = row.get("next_action") or "-"
        due = row.get("next_action_due") or "-"
        print(f"- {lead_id} | {name} | stage={stage} | est=${est_value:,.0f} | due={due} | next={next_action}")
    return 0


def cmd_add(args: argparse.Namespace) -> int:
    if args.stage not in OPEN_STAGES:
        print(f"Invalid stage for add: {args.stage}. Use one of: {', '.join(sorted(OPEN_STAGES))}")
        return 2
    rows = _load_pipeline()
    row = {
        "lead_id": _lead_id(),
        "name": args.name.strip(),
        "source": args.source.strip(),
        "stage": args.stage,
        "offer": args.offer,
        "est_value": float(args.est_value),
        "actual_value": None,
        "next_action": args.next_action,
        "next_action_due": args.next_action_due,
        "notes": args.notes or "",
        "created_at": _now(),
        "updated_at": _now(),
        "closed_at": None,
    }
    rows.append(row)
    _save_pipeline(rows)
    print(f"Lead added: {row['lead_id']} ({row['name']})")
    return 0


def cmd_update(args: argparse.Namespace) -> int:
    rows = _load_pipeline()
    row = _find(rows, args.lead_id)
    if not row:
        print(f"Lead not found: {args.lead_id}")
        return 3

    if args.stage:
        if args.stage not in OPEN_STAGES and args.stage not in CLOSED_STAGES:
            print(f"Invalid stage: {args.stage}. Use one of: {', '.join(ALL_STAGES)}")
            return 2
        row["stage"] = args.stage
    if args.offer is not None:
        row["offer"] = args.offer
    if args.est_value is not None:
        row["est_value"] = float(args.est_value)
    if args.next_action is not None:
        row["next_action"] = args.next_action
    if args.next_action_due is not None:
        row["next_action_due"] = args.next_action_due
    if args.notes is not None:
        row["notes"] = args.notes
    row["updated_at"] = _now()
    _save_pipeline(rows)
    print(f"Lead updated: {args.lead_id}")
    return 0


def cmd_close(args: argparse.Namespace) -> int:
    rows = _load_pipeline()
    row = _find(rows, args.lead_id)
    if not row:
        print(f"Lead not found: {args.lead_id}")
        return 3

    row["stage"] = args.result
    row["actual_value"] = float(args.actual_value) if args.actual_value is not None else _as_float(row.get("est_value"))
    row["next_action"] = args.next_action or ""
    row["next_action_due"] = ""
    row["closed_at"] = _now()
    row["updated_at"] = _now()
    _save_pipeline(rows)
    print(f"Lead closed: {args.lead_id} -> {args.result} (${_as_float(row.get('actual_value')):,.0f})")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage sales pipeline leads.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    init_p = sub.add_parser("init", help="Initialize pipeline file")
    init_p.set_defaults(func=cmd_init)

    list_p = sub.add_parser("list", help="List pipeline leads")
    list_p.add_argument("--stage", choices=ALL_STAGES, help="Filter by stage")
    list_p.add_argument("--open-only", action="store_true", help="Show only open leads")
    list_p.set_defaults(func=cmd_list)

    add_p = sub.add_parser("add", help="Add a new lead")
    add_p.add_argument("--name", required=True, help="Lead/client name")
    add_p.add_argument("--source", default="inbound", help="Lead source")
    add_p.add_argument("--stage", default="lead", choices=sorted(OPEN_STAGES), help="Initial stage")
    add_p.add_argument("--offer", default="Permanence OS Foundation Setup", help="Offer name")
    add_p.add_argument("--est-value", type=float, default=1500.0, help="Estimated deal value")
    add_p.add_argument("--next-action", default="Send intake + book fit call", help="Next action text")
    add_p.add_argument("--next-action-due", default="", help="Due date (YYYY-MM-DD)")
    add_p.add_argument("--notes", default="", help="Notes")
    add_p.set_defaults(func=cmd_add)

    upd_p = sub.add_parser("update", help="Update an existing lead")
    upd_p.add_argument("--lead-id", required=True, help="Lead ID")
    upd_p.add_argument("--stage", choices=ALL_STAGES, help="New stage")
    upd_p.add_argument("--offer", help="Offer name")
    upd_p.add_argument("--est-value", type=float, help="Estimated value")
    upd_p.add_argument("--next-action", help="Next action text")
    upd_p.add_argument("--next-action-due", help="Due date (YYYY-MM-DD)")
    upd_p.add_argument("--notes", help="Notes")
    upd_p.set_defaults(func=cmd_update)

    close_p = sub.add_parser("close", help="Close a lead as won/lost")
    close_p.add_argument("--lead-id", required=True, help="Lead ID")
    close_p.add_argument("--result", required=True, choices=sorted(CLOSED_STAGES), help="Outcome")
    close_p.add_argument("--actual-value", type=float, help="Final value")
    close_p.add_argument("--next-action", default="", help="Optional post-close note")
    close_p.set_defaults(func=cmd_close)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
