#!/usr/bin/env python3
"""Tests for money-first feature gate."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import scripts.money_first_gate as gate_mod  # noqa: E402


def test_money_first_gate_passes_with_won_revenue() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        working = root / "working"
        outputs = root / "outputs"
        tool = root / "tool"
        working.mkdir(parents=True, exist_ok=True)
        outputs.mkdir(parents=True, exist_ok=True)
        tool.mkdir(parents=True, exist_ok=True)

        pipeline = working / "sales_pipeline.json"
        pipeline.write_text(
            json.dumps(
                [
                    {"lead_id": "L-1", "stage": "won", "actual_value": 900},
                    {"lead_id": "L-2", "stage": "lead", "est_value": 1200},
                ]
            )
            + "\n",
            encoding="utf-8",
        )

        original = {
            "PIPELINE_PATH": gate_mod.PIPELINE_PATH,
            "OUTPUT_DIR": gate_mod.OUTPUT_DIR,
            "TOOL_DIR": gate_mod.TOOL_DIR,
        }
        try:
            gate_mod.PIPELINE_PATH = pipeline
            gate_mod.OUTPUT_DIR = outputs
            gate_mod.TOOL_DIR = tool
            rc = gate_mod.main(["--strict", "--milestone-usd", "500", "--min-won-deals", "1"])
        finally:
            gate_mod.PIPELINE_PATH = original["PIPELINE_PATH"]
            gate_mod.OUTPUT_DIR = original["OUTPUT_DIR"]
            gate_mod.TOOL_DIR = original["TOOL_DIR"]

        assert rc == 0
        latest = outputs / "money_first_gate_latest.md"
        assert latest.exists()
        text = latest.read_text(encoding="utf-8")
        assert "Feature work unlocked: True" in text


def test_money_first_gate_fails_in_strict_mode_when_closed() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        working = root / "working"
        outputs = root / "outputs"
        tool = root / "tool"
        working.mkdir(parents=True, exist_ok=True)
        outputs.mkdir(parents=True, exist_ok=True)
        tool.mkdir(parents=True, exist_ok=True)

        pipeline = working / "sales_pipeline.json"
        pipeline.write_text(json.dumps([{"lead_id": "L-1", "stage": "lead", "est_value": 1200}]) + "\n", encoding="utf-8")

        original = {
            "PIPELINE_PATH": gate_mod.PIPELINE_PATH,
            "OUTPUT_DIR": gate_mod.OUTPUT_DIR,
            "TOOL_DIR": gate_mod.TOOL_DIR,
        }
        try:
            gate_mod.PIPELINE_PATH = pipeline
            gate_mod.OUTPUT_DIR = outputs
            gate_mod.TOOL_DIR = tool
            rc = gate_mod.main(["--strict", "--milestone-usd", "500", "--min-won-deals", "1"])
        finally:
            gate_mod.PIPELINE_PATH = original["PIPELINE_PATH"]
            gate_mod.OUTPUT_DIR = original["OUTPUT_DIR"]
            gate_mod.TOOL_DIR = original["TOOL_DIR"]

        assert rc == 1
        latest = outputs / "money_first_gate_latest.md"
        assert latest.exists()
        text = latest.read_text(encoding="utf-8")
        assert "Feature work unlocked: False" in text


if __name__ == "__main__":
    test_money_first_gate_passes_with_won_revenue()
    test_money_first_gate_fails_in_strict_mode_when_closed()
    print("✓ Money-first gate tests passed")
