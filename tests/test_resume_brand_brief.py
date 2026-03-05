#!/usr/bin/env python3
"""Tests for resume + brand brief generator."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import scripts.resume_brand_brief as brief_mod  # noqa: E402


def test_resume_brand_brief_writes_outputs() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        working = root / "working"
        output = root / "outputs"
        tool = root / "tool"
        brand_dir = root / "docs" / "brand"
        working.mkdir(parents=True, exist_ok=True)
        output.mkdir(parents=True, exist_ok=True)
        tool.mkdir(parents=True, exist_ok=True)
        brand_dir.mkdir(parents=True, exist_ok=True)

        (working / "life_profile.json").write_text(
            json.dumps(
                {
                    "owner": "Payton",
                    "north_star": "Build a governed second brain that compounds outcomes.",
                }
            ),
            encoding="utf-8",
        )
        (working / "life_tasks.json").write_text(
            json.dumps(
                [
                    {
                        "task_id": "LIFE-1",
                        "title": "Ship workflow module",
                        "domain": "business",
                        "priority": "high",
                        "status": "open",
                    }
                ]
            ),
            encoding="utf-8",
        )
        (brand_dir / "brand_notes.md").write_text("# Brand\n\nClear system-first positioning.", encoding="utf-8")
        (tool / "attachment_pipeline_20260303-000000.json").write_text(
            json.dumps(
                {
                    "counts": {"total": 3, "document": 1, "image": 1, "audio": 1, "video": 0},
                    "transcription_queue_pending": 1,
                }
            ),
            encoding="utf-8",
        )

        original = {
            "WORKING_DIR": brief_mod.WORKING_DIR,
            "OUTPUT_DIR": brief_mod.OUTPUT_DIR,
            "TOOL_DIR": brief_mod.TOOL_DIR,
            "PROFILE_PATH": brief_mod.PROFILE_PATH,
            "TASKS_PATH": brief_mod.TASKS_PATH,
            "BRAND_DOC_DIR": brief_mod.BRAND_DOC_DIR,
        }
        try:
            brief_mod.WORKING_DIR = working
            brief_mod.OUTPUT_DIR = output
            brief_mod.TOOL_DIR = tool
            brief_mod.PROFILE_PATH = working / "life_profile.json"
            brief_mod.TASKS_PATH = working / "life_tasks.json"
            brief_mod.BRAND_DOC_DIR = brand_dir
            rc = brief_mod.main(["--focus", "both"])
        finally:
            brief_mod.WORKING_DIR = original["WORKING_DIR"]
            brief_mod.OUTPUT_DIR = original["OUTPUT_DIR"]
            brief_mod.TOOL_DIR = original["TOOL_DIR"]
            brief_mod.PROFILE_PATH = original["PROFILE_PATH"]
            brief_mod.TASKS_PATH = original["TASKS_PATH"]
            brief_mod.BRAND_DOC_DIR = original["BRAND_DOC_DIR"]

        assert rc == 0
        assert (output / "resume_brand_brief_latest.md").exists()
        payload_files = sorted(tool.glob("resume_brand_brief_*.json"))
        assert payload_files
        payload = json.loads(payload_files[-1].read_text(encoding="utf-8"))
        assert int(payload.get("brand_doc_count", 0)) == 1
        assert isinstance(payload.get("resume_bullets"), list)
        assert payload.get("resume_bullets")
        assert isinstance(payload.get("brand_actions"), list)
        assert payload.get("brand_actions")


if __name__ == "__main__":
    test_resume_brand_brief_writes_outputs()
    print("✓ Resume brand brief tests passed")

