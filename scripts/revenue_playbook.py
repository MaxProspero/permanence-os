#!/usr/bin/env python3
"""
Manage locked revenue offer + CTA playbook.
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
PLAYBOOK_PATH = Path(os.getenv("PERMANENCE_REVENUE_PLAYBOOK_PATH", str(WORKING_DIR / "revenue_playbook.json")))


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def default_playbook() -> dict[str, Any]:
    return {
        "offer_name": "Permanence OS Foundation Setup",
        "offer_promise": "Install and operationalize a governed AI operating system on a client's Mac in 7 days.",
        "delivery_window_days": 7,
        "cta_keyword": "FOUNDATION",
        "cta_public": 'DM me "FOUNDATION".',
        "cta_direct": 'If you want this set up for you, DM "FOUNDATION" and I will send the intake + call link.',
        "pricing_tier": "Core",
        "price_usd": 1500,
        "updated_at": _utc_now_iso(),
        "source": "default",
    }


def load_playbook() -> dict[str, Any]:
    default = default_playbook()
    if not PLAYBOOK_PATH.exists():
        return default
    try:
        payload = json.loads(PLAYBOOK_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default
    if not isinstance(payload, dict):
        return default
    merged = dict(default)
    merged.update(payload)
    return merged


def save_playbook(playbook: dict[str, Any]) -> None:
    out = dict(playbook)
    out["updated_at"] = _utc_now_iso()
    PLAYBOOK_PATH.parent.mkdir(parents=True, exist_ok=True)
    PLAYBOOK_PATH.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")


def cmd_show(_args: argparse.Namespace) -> int:
    print(json.dumps(load_playbook(), indent=2))
    return 0


def cmd_init(args: argparse.Namespace) -> int:
    if PLAYBOOK_PATH.exists() and not args.force:
        print(f"Playbook already exists: {PLAYBOOK_PATH}")
        print("Use --force to overwrite.")
        return 0
    pb = default_playbook()
    pb["source"] = "init"
    save_playbook(pb)
    print(f"Playbook initialized: {PLAYBOOK_PATH}")
    return 0


def cmd_set(args: argparse.Namespace) -> int:
    pb = load_playbook()
    if args.offer_name is not None:
        pb["offer_name"] = str(args.offer_name).strip()
    if args.offer_promise is not None:
        pb["offer_promise"] = str(args.offer_promise).strip()
    if args.delivery_window_days is not None:
        pb["delivery_window_days"] = max(1, int(args.delivery_window_days))
    if args.cta_keyword is not None:
        pb["cta_keyword"] = str(args.cta_keyword).strip().upper()
    if args.cta_public is not None:
        pb["cta_public"] = str(args.cta_public).strip()
    if args.cta_direct is not None:
        pb["cta_direct"] = str(args.cta_direct).strip()
    if args.pricing_tier is not None:
        pb["pricing_tier"] = str(args.pricing_tier).strip()
    if args.price_usd is not None:
        pb["price_usd"] = max(0, int(args.price_usd))
    pb["source"] = "set"
    save_playbook(pb)
    print(f"Playbook updated: {PLAYBOOK_PATH}")
    print(json.dumps(pb, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage locked revenue offer + CTA playbook.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    show_p = sub.add_parser("show", help="Show current playbook")
    show_p.set_defaults(func=cmd_show)

    init_p = sub.add_parser("init", help="Write default playbook file")
    init_p.add_argument("--force", action="store_true", help="Overwrite existing playbook")
    init_p.set_defaults(func=cmd_init)

    set_p = sub.add_parser("set", help="Update playbook fields")
    set_p.add_argument("--offer-name")
    set_p.add_argument("--offer-promise")
    set_p.add_argument("--delivery-window-days", type=int)
    set_p.add_argument("--cta-keyword")
    set_p.add_argument("--cta-public")
    set_p.add_argument("--cta-direct")
    set_p.add_argument("--pricing-tier")
    set_p.add_argument("--price-usd", type=int)
    set_p.set_defaults(func=cmd_set)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
