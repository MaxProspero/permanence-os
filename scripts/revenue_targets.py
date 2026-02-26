#!/usr/bin/env python3
"""
Manage locked revenue targets for Revenue Ops.
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parents[1]
WORKING_DIR = Path(os.getenv("PERMANENCE_WORKING_DIR", str(BASE_DIR / "memory" / "working")))
TARGETS_PATH = Path(os.getenv("PERMANENCE_REVENUE_TARGETS_PATH", str(WORKING_DIR / "revenue_targets.json")))


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _week_start_iso(today: date | None = None) -> str:
    today = today or date.today()
    monday = today - timedelta(days=today.weekday())
    return monday.isoformat()


def default_targets() -> dict[str, Any]:
    weekly_revenue_target = int(os.getenv("PERMANENCE_REVENUE_WEEKLY_TARGET", "3000"))
    monthly_revenue_target = int(os.getenv("PERMANENCE_REVENUE_MONTHLY_TARGET", str(max(12000, weekly_revenue_target * 4))))
    return {
        "week_of": _week_start_iso(),
        "weekly_revenue_target": weekly_revenue_target,
        "monthly_revenue_target": monthly_revenue_target,
        "weekly_leads_target": int(os.getenv("PERMANENCE_REVENUE_WEEKLY_LEADS_TARGET", "10")),
        "weekly_calls_target": int(os.getenv("PERMANENCE_REVENUE_WEEKLY_CALLS_TARGET", "5")),
        "weekly_closes_target": int(os.getenv("PERMANENCE_REVENUE_WEEKLY_CLOSES_TARGET", "2")),
        "daily_outreach_target": int(os.getenv("PERMANENCE_REVENUE_DAILY_OUTREACH_TARGET", "10")),
        "updated_at": _utc_now_iso(),
        "source": "default",
    }


def load_targets() -> dict[str, Any]:
    default = default_targets()
    if not TARGETS_PATH.exists():
        return default
    try:
        payload = json.loads(TARGETS_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default
    if not isinstance(payload, dict):
        return default
    merged = dict(default)
    merged.update(payload)
    return merged


def save_targets(targets: dict[str, Any]) -> None:
    out = dict(targets)
    out["updated_at"] = _utc_now_iso()
    TARGETS_PATH.parent.mkdir(parents=True, exist_ok=True)
    TARGETS_PATH.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")


def _as_non_negative_int(value: Any, fallback: int = 0) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return max(0, int(fallback))


def cmd_show(_args: argparse.Namespace) -> int:
    print(json.dumps(load_targets(), indent=2))
    return 0


def cmd_init(args: argparse.Namespace) -> int:
    if TARGETS_PATH.exists() and not args.force:
        print(f"Targets already exist: {TARGETS_PATH}")
        print("Use --force to overwrite.")
        return 0
    payload = default_targets()
    payload["source"] = "init"
    save_targets(payload)
    print(f"Targets initialized: {TARGETS_PATH}")
    return 0


def cmd_set(args: argparse.Namespace) -> int:
    targets = load_targets()
    if args.week_of is not None:
        targets["week_of"] = str(args.week_of).strip()
    if args.weekly_revenue_target is not None:
        targets["weekly_revenue_target"] = _as_non_negative_int(args.weekly_revenue_target, 3000)
    if args.monthly_revenue_target is not None:
        targets["monthly_revenue_target"] = _as_non_negative_int(args.monthly_revenue_target, 12000)
    if args.weekly_leads_target is not None:
        targets["weekly_leads_target"] = _as_non_negative_int(args.weekly_leads_target, 10)
    if args.weekly_calls_target is not None:
        targets["weekly_calls_target"] = _as_non_negative_int(args.weekly_calls_target, 5)
    if args.weekly_closes_target is not None:
        targets["weekly_closes_target"] = _as_non_negative_int(args.weekly_closes_target, 2)
    if args.daily_outreach_target is not None:
        targets["daily_outreach_target"] = max(1, _as_non_negative_int(args.daily_outreach_target, 10))
    targets["source"] = "set"
    save_targets(targets)
    print(f"Targets updated: {TARGETS_PATH}")
    print(json.dumps(targets, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage locked revenue targets.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    show_p = sub.add_parser("show", help="Show current targets")
    show_p.set_defaults(func=cmd_show)

    init_p = sub.add_parser("init", help="Write default targets file")
    init_p.add_argument("--force", action="store_true", help="Overwrite existing targets")
    init_p.set_defaults(func=cmd_init)

    set_p = sub.add_parser("set", help="Update target fields")
    set_p.add_argument("--week-of")
    set_p.add_argument("--weekly-revenue-target", type=int)
    set_p.add_argument("--monthly-revenue-target", type=int)
    set_p.add_argument("--weekly-leads-target", type=int)
    set_p.add_argument("--weekly-calls-target", type=int)
    set_p.add_argument("--weekly-closes-target", type=int)
    set_p.add_argument("--daily-outreach-target", type=int)
    set_p.set_defaults(func=cmd_set)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
