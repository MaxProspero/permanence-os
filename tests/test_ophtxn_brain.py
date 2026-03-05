#!/usr/bin/env python3
"""Tests for Ophtxn brain vault sync/recall."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import scripts.ophtxn_brain as brain_mod  # noqa: E402


def test_ophtxn_brain_sync_writes_vault_and_report() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        outputs = root / "outputs"
        tool = root / "tool"
        working = root / "working"
        inbox = root / "inbox"
        outputs.mkdir(parents=True, exist_ok=True)
        tool.mkdir(parents=True, exist_ok=True)
        working.mkdir(parents=True, exist_ok=True)
        inbox.mkdir(parents=True, exist_ok=True)

        doc_path = root / "vision.md"
        doc_path.write_text(
            "# Vision\nOphtxn should learn and recall user systems memory over time.\n",
            encoding="utf-8",
        )
        intake_path = inbox / "telegram_share_intake.jsonl"
        intake_path.write_text(
            json.dumps({"text": "Build a personal intelligence system with governance."}) + "\n",
            encoding="utf-8",
        )

        original = {
            "OUTPUT_DIR": brain_mod.OUTPUT_DIR,
            "TOOL_DIR": brain_mod.TOOL_DIR,
            "WORKING_DIR": brain_mod.WORKING_DIR,
            "BRAIN_PATH": brain_mod.BRAIN_PATH,
            "SHARE_INTAKE_PATH": brain_mod.SHARE_INTAKE_PATH,
        }
        try:
            brain_mod.OUTPUT_DIR = outputs
            brain_mod.TOOL_DIR = tool
            brain_mod.WORKING_DIR = working
            brain_mod.BRAIN_PATH = working / "ophtxn_brain_vault.json"
            brain_mod.SHARE_INTAKE_PATH = intake_path
            with patch.object(brain_mod, "_source_candidates", return_value=[doc_path, intake_path]):
                rc = brain_mod.main(["--action", "sync"])
        finally:
            brain_mod.OUTPUT_DIR = original["OUTPUT_DIR"]
            brain_mod.TOOL_DIR = original["TOOL_DIR"]
            brain_mod.WORKING_DIR = original["WORKING_DIR"]
            brain_mod.BRAIN_PATH = original["BRAIN_PATH"]
            brain_mod.SHARE_INTAKE_PATH = original["SHARE_INTAKE_PATH"]

        assert rc == 0
        vault = json.loads((working / "ophtxn_brain_vault.json").read_text(encoding="utf-8"))
        chunks = vault.get("chunks") or []
        assert chunks
        text_blob = " ".join(str(row.get("text") or "") for row in chunks if isinstance(row, dict)).lower()
        assert "personal intelligence system" in text_blob
        latest = outputs / "ophtxn_brain_latest.md"
        assert latest.exists()
        assert "Ophtxn Brain" in latest.read_text(encoding="utf-8")


def test_ophtxn_brain_recall_returns_matches() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        outputs = root / "outputs"
        tool = root / "tool"
        working = root / "working"
        outputs.mkdir(parents=True, exist_ok=True)
        tool.mkdir(parents=True, exist_ok=True)
        working.mkdir(parents=True, exist_ok=True)

        vault_path = working / "ophtxn_brain_vault.json"
        vault_path.write_text(
            json.dumps(
                {
                    "version": "1.0",
                    "updated_at": "2026-03-04T00:00:00+00:00",
                    "sources_count": 1,
                    "chunks": [
                        {
                            "id": "BRAIN-TEST0001",
                            "source": "docs/vision.md",
                            "text": "Ophtxn runs finance research and strategy updates daily.",
                            "tokens": ["ophtxn", "finance", "research", "strategy"],
                            "source_updated_at": "2026-03-04T00:00:00+00:00",
                            "ingested_at": "2026-03-04T00:00:00+00:00",
                        }
                    ],
                }
            )
            + "\n",
            encoding="utf-8",
        )

        original = {
            "OUTPUT_DIR": brain_mod.OUTPUT_DIR,
            "TOOL_DIR": brain_mod.TOOL_DIR,
            "WORKING_DIR": brain_mod.WORKING_DIR,
            "BRAIN_PATH": brain_mod.BRAIN_PATH,
        }
        try:
            brain_mod.OUTPUT_DIR = outputs
            brain_mod.TOOL_DIR = tool
            brain_mod.WORKING_DIR = working
            brain_mod.BRAIN_PATH = vault_path
            rc = brain_mod.main(["--action", "recall", "--query", "finance strategy"])
        finally:
            brain_mod.OUTPUT_DIR = original["OUTPUT_DIR"]
            brain_mod.TOOL_DIR = original["TOOL_DIR"]
            brain_mod.WORKING_DIR = original["WORKING_DIR"]
            brain_mod.BRAIN_PATH = original["BRAIN_PATH"]

        assert rc == 0
        latest = outputs / "ophtxn_brain_latest.md"
        text = latest.read_text(encoding="utf-8")
        assert "Recall Results" in text
        assert "finance research" in text.lower()


if __name__ == "__main__":
    test_ophtxn_brain_sync_writes_vault_and_report()
    test_ophtxn_brain_recall_returns_matches()
    print("✓ Ophtxn brain tests passed")
