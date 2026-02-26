#!/usr/bin/env python3
"""Tests for revenue playbook management script."""

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import scripts.revenue_playbook as playbook_mod  # noqa: E402


def test_revenue_playbook_init_set_show():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        working_dir = root / "working"
        working_dir.mkdir(parents=True, exist_ok=True)
        path = working_dir / "revenue_playbook.json"

        original = {
            "WORKING_DIR": playbook_mod.WORKING_DIR,
            "PLAYBOOK_PATH": playbook_mod.PLAYBOOK_PATH,
        }
        try:
            playbook_mod.WORKING_DIR = working_dir
            playbook_mod.PLAYBOOK_PATH = path

            assert playbook_mod.cmd_init(type("Args", (), {"force": False})()) == 0
            assert path.exists()

            set_args = type(
                "Args",
                (),
                {
                    "offer_name": "Operator System Install",
                    "offer_promise": "Install and run your governed operator stack in 5 days.",
                    "delivery_window_days": 5,
                    "cta_keyword": "OPERATOR",
                    "cta_public": 'DM me "OPERATOR".',
                    "cta_direct": 'DM "OPERATOR" and I will send intake + calendar link.',
                    "pricing_tier": "Pilot",
                    "price_usd": 900,
                },
            )()
            assert playbook_mod.cmd_set(set_args) == 0

            payload = json.loads(path.read_text(encoding="utf-8"))
            assert payload["offer_name"] == "Operator System Install"
            assert payload["cta_keyword"] == "OPERATOR"
            assert payload["price_usd"] == 900

            loaded = playbook_mod.load_playbook()
            assert loaded["pricing_tier"] == "Pilot"
            assert loaded["delivery_window_days"] == 5
        finally:
            playbook_mod.WORKING_DIR = original["WORKING_DIR"]
            playbook_mod.PLAYBOOK_PATH = original["PLAYBOOK_PATH"]


if __name__ == "__main__":
    test_revenue_playbook_init_set_show()
    print("✓ Revenue playbook tests passed")
