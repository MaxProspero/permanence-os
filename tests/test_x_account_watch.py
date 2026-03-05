#!/usr/bin/env python3
"""Tests for X account watch feed manager."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import scripts.x_account_watch as x_watch_mod  # noqa: E402


def test_x_account_watch_add_and_list() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        outputs = root / "outputs"
        tool = root / "tool"
        working = root / "working"
        outputs.mkdir(parents=True, exist_ok=True)
        tool.mkdir(parents=True, exist_ok=True)
        working.mkdir(parents=True, exist_ok=True)

        feeds_path = working / "social_research_feeds.json"
        feeds_path.write_text(
            json.dumps(
                [
                    {"name": "HN Frontpage", "platform": "hackernews", "url": "https://hnrss.org/frontpage"},
                ]
            )
            + "\n",
            encoding="utf-8",
        )

        original = {
            "OUTPUT_DIR": x_watch_mod.OUTPUT_DIR,
            "TOOL_DIR": x_watch_mod.TOOL_DIR,
            "WORKING_DIR": x_watch_mod.WORKING_DIR,
            "FEEDS_PATH": x_watch_mod.FEEDS_PATH,
        }
        try:
            x_watch_mod.OUTPUT_DIR = outputs
            x_watch_mod.TOOL_DIR = tool
            x_watch_mod.WORKING_DIR = working
            x_watch_mod.FEEDS_PATH = feeds_path
            rc_add = x_watch_mod.main(
                [
                    "--action",
                    "add",
                    "--handle",
                    "@PaytonHicks",
                    "--max-results",
                    "30",
                ]
            )
            rc_list = x_watch_mod.main(["--action", "list"])
        finally:
            x_watch_mod.OUTPUT_DIR = original["OUTPUT_DIR"]
            x_watch_mod.TOOL_DIR = original["TOOL_DIR"]
            x_watch_mod.WORKING_DIR = original["WORKING_DIR"]
            x_watch_mod.FEEDS_PATH = original["FEEDS_PATH"]

        assert rc_add == 0
        assert rc_list == 0
        feeds = json.loads(feeds_path.read_text(encoding="utf-8"))
        x_rows = [row for row in feeds if isinstance(row, dict) and str(row.get("platform") or "") == "x"]
        assert x_rows
        row = x_rows[0]
        assert row.get("x_handle") == "paytonhicks"
        assert "from:paytonhicks" in str(row.get("query") or "")
        assert "-is:retweet" in str(row.get("query") or "")
        assert row.get("read_only") is True
        latest = outputs / "x_account_watch_latest.md"
        assert latest.exists()
        assert "@paytonhicks" in latest.read_text(encoding="utf-8").lower()


def test_x_account_watch_remove() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        outputs = root / "outputs"
        tool = root / "tool"
        working = root / "working"
        outputs.mkdir(parents=True, exist_ok=True)
        tool.mkdir(parents=True, exist_ok=True)
        working.mkdir(parents=True, exist_ok=True)

        feeds_path = working / "social_research_feeds.json"
        feeds_path.write_text(
            json.dumps(
                [
                    {
                        "name": "X Personal @paytonhicks",
                        "platform": "x",
                        "query": "from:paytonhicks -is:reply -is:retweet lang:en",
                        "max_results": 25,
                        "x_handle": "paytonhicks",
                        "read_only": True,
                    },
                ]
            )
            + "\n",
            encoding="utf-8",
        )

        original = {
            "OUTPUT_DIR": x_watch_mod.OUTPUT_DIR,
            "TOOL_DIR": x_watch_mod.TOOL_DIR,
            "WORKING_DIR": x_watch_mod.WORKING_DIR,
            "FEEDS_PATH": x_watch_mod.FEEDS_PATH,
        }
        try:
            x_watch_mod.OUTPUT_DIR = outputs
            x_watch_mod.TOOL_DIR = tool
            x_watch_mod.WORKING_DIR = working
            x_watch_mod.FEEDS_PATH = feeds_path
            rc_remove = x_watch_mod.main(["--action", "remove", "--handle", "paytonhicks"])
        finally:
            x_watch_mod.OUTPUT_DIR = original["OUTPUT_DIR"]
            x_watch_mod.TOOL_DIR = original["TOOL_DIR"]
            x_watch_mod.WORKING_DIR = original["WORKING_DIR"]
            x_watch_mod.FEEDS_PATH = original["FEEDS_PATH"]

        assert rc_remove == 0
        feeds = json.loads(feeds_path.read_text(encoding="utf-8"))
        assert not any(str(row.get("platform") or "") == "x" for row in feeds if isinstance(row, dict))


if __name__ == "__main__":
    test_x_account_watch_add_and_list()
    test_x_account_watch_remove()
    print("✓ X account watch tests passed")
