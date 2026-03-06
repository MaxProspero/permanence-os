#!/usr/bin/env python3
"""Tests for chronicle refinement workflow."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import scripts.chronicle_refinement as refine_mod  # noqa: E402


def test_chronicle_refinement_builds_backlog_and_canon_checks() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        output = root / "outputs"
        tool = root / "tool"
        working = root / "working"
        chronicle = root / "chronicle"
        output.mkdir(parents=True, exist_ok=True)
        tool.mkdir(parents=True, exist_ok=True)
        working.mkdir(parents=True, exist_ok=True)
        chronicle.mkdir(parents=True, exist_ok=True)

        report_path = chronicle / "chronicle_report_20260305_010027.json"
        report_path.write_text(
            json.dumps(
                {
                    "generated_at": "2026-03-05T01:00:27Z",
                    "events_count": 20,
                    "commit_count": 1,
                    "signal_totals": {
                        "issue_hits": 3,
                        "direction_hits": 2,
                        "log_error_hits": 2,
                        "log_warning_hits": 1,
                    },
                    "issue_events": [
                        {
                            "timestamp": "2026-03-05T00:40:00Z",
                            "summary": "terminal queue backlog still open and blocking closeout",
                        },
                        {
                            "timestamp": "2026-03-05T00:42:00Z",
                            "summary": "telegram relay timeout error on retry path",
                        },
                    ],
                    "direction_events": [
                        {
                            "timestamp": "2026-03-05T00:50:00Z",
                            "summary": "new direction: roadmap priority should focus on stability first",
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )

        original = {
            "OUTPUT_DIR": refine_mod.OUTPUT_DIR,
            "TOOL_DIR": refine_mod.TOOL_DIR,
            "WORKING_DIR": refine_mod.WORKING_DIR,
            "DEFAULT_BACKLOG_PATH": refine_mod.DEFAULT_BACKLOG_PATH,
            "CHRONICLE_OUTPUT_DIR": refine_mod.CHRONICLE_OUTPUT_DIR,
        }
        try:
            refine_mod.OUTPUT_DIR = output
            refine_mod.TOOL_DIR = tool
            refine_mod.WORKING_DIR = working
            refine_mod.DEFAULT_BACKLOG_PATH = working / "chronicle_backlog_refinement.json"
            refine_mod.CHRONICLE_OUTPUT_DIR = chronicle
            rc = refine_mod.main([])
        finally:
            refine_mod.OUTPUT_DIR = original["OUTPUT_DIR"]
            refine_mod.TOOL_DIR = original["TOOL_DIR"]
            refine_mod.WORKING_DIR = original["WORKING_DIR"]
            refine_mod.DEFAULT_BACKLOG_PATH = original["DEFAULT_BACKLOG_PATH"]
            refine_mod.CHRONICLE_OUTPUT_DIR = original["CHRONICLE_OUTPUT_DIR"]

        assert rc == 0
        assert (output / "chronicle_refinement_latest.md").exists()
        assert (working / "chronicle_backlog_refinement.json").exists()

        payload_files = sorted(tool.glob("chronicle_refinement_*.json"))
        assert payload_files
        payload = json.loads(payload_files[-1].read_text(encoding="utf-8"))
        assert int(payload.get("backlog_updates_count", 0)) == 3
        assert int(payload.get("canon_checks_count", 0)) == 1
        titles = [str(row.get("title")) for row in (payload.get("backlog_updates") or [])]
        assert "Queue hygiene and backlog compression" in titles
        assert "Failure-path hardening and regression coverage" in titles
        assert "Stability sprint from chronicle friction totals" in titles


def test_chronicle_refinement_strict_fails_when_report_missing() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        output = root / "outputs"
        tool = root / "tool"
        chronicle = root / "chronicle"
        output.mkdir(parents=True, exist_ok=True)
        tool.mkdir(parents=True, exist_ok=True)
        chronicle.mkdir(parents=True, exist_ok=True)

        original = {
            "OUTPUT_DIR": refine_mod.OUTPUT_DIR,
            "TOOL_DIR": refine_mod.TOOL_DIR,
            "CHRONICLE_OUTPUT_DIR": refine_mod.CHRONICLE_OUTPUT_DIR,
        }
        try:
            refine_mod.OUTPUT_DIR = output
            refine_mod.TOOL_DIR = tool
            refine_mod.CHRONICLE_OUTPUT_DIR = chronicle
            rc = refine_mod.main(["--strict", "--no-sync-backlog"])
        finally:
            refine_mod.OUTPUT_DIR = original["OUTPUT_DIR"]
            refine_mod.TOOL_DIR = original["TOOL_DIR"]
            refine_mod.CHRONICLE_OUTPUT_DIR = original["CHRONICLE_OUTPUT_DIR"]

        assert rc == 1
        latest = output / "chronicle_refinement_latest.md"
        assert latest.exists()
        text = latest.read_text(encoding="utf-8")
        assert "No chronicle report JSON found" in text


if __name__ == "__main__":
    test_chronicle_refinement_builds_backlog_and_canon_checks()
    test_chronicle_refinement_strict_fails_when_report_missing()
    print("✓ Chronicle refinement tests passed")
