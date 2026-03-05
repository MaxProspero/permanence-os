#!/usr/bin/env python3
"""Tests for low-cost mode profile manager."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import scripts.low_cost_mode as mod  # noqa: E402


def test_low_cost_mode_enable_writes_profile() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        env_path = root / ".env"
        outputs = root / "outputs"
        tool = root / "tool"
        outputs.mkdir(parents=True, exist_ok=True)
        tool.mkdir(parents=True, exist_ok=True)
        env_path.write_text("PERMANENCE_MODEL_PROVIDER=anthropic\n", encoding="utf-8")

        original = {
            "ENV_PATH": mod.ENV_PATH,
            "OUTPUT_DIR": mod.OUTPUT_DIR,
            "TOOL_DIR": mod.TOOL_DIR,
        }
        try:
            mod.ENV_PATH = env_path
            mod.OUTPUT_DIR = outputs
            mod.TOOL_DIR = tool
            rc = mod.main(["--action", "enable", "--monthly-budget", "12", "--milestone-usd", "700"])
        finally:
            mod.ENV_PATH = original["ENV_PATH"]
            mod.OUTPUT_DIR = original["OUTPUT_DIR"]
            mod.TOOL_DIR = original["TOOL_DIR"]

        assert rc == 0
        text = env_path.read_text(encoding="utf-8")
        assert "PERMANENCE_LOW_COST_MODE=1" in text
        assert "PERMANENCE_MODEL_PROVIDER=ollama" in text
        assert "PERMANENCE_MODEL_PROVIDER_FALLBACKS=ollama" in text
        assert "PERMANENCE_MODEL_SONNET=qwen2.5:3b" in text
        assert "PERMANENCE_DEFAULT_MODEL=qwen2.5:3b" in text
        assert "PERMANENCE_LLM_MONTHLY_BUDGET_USD=12.0" in text
        assert "PERMANENCE_FEATURE_WORK_REQUIRE_REVENUE_MILESTONE=1" in text
        assert "PERMANENCE_FEATURE_GATE_MILESTONE_USD=700" in text
        assert (outputs / "low_cost_mode_latest.md").exists()


def test_low_cost_mode_disable_turns_flags_off() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        env_path = root / ".env"
        outputs = root / "outputs"
        tool = root / "tool"
        outputs.mkdir(parents=True, exist_ok=True)
        tool.mkdir(parents=True, exist_ok=True)
        env_path.write_text(
            "PERMANENCE_LOW_COST_MODE=1\nPERMANENCE_FEATURE_WORK_REQUIRE_REVENUE_MILESTONE=1\n",
            encoding="utf-8",
        )

        original = {
            "ENV_PATH": mod.ENV_PATH,
            "OUTPUT_DIR": mod.OUTPUT_DIR,
            "TOOL_DIR": mod.TOOL_DIR,
        }
        try:
            mod.ENV_PATH = env_path
            mod.OUTPUT_DIR = outputs
            mod.TOOL_DIR = tool
            rc = mod.main(["--action", "disable"])
        finally:
            mod.ENV_PATH = original["ENV_PATH"]
            mod.OUTPUT_DIR = original["OUTPUT_DIR"]
            mod.TOOL_DIR = original["TOOL_DIR"]

        assert rc == 0
        text = env_path.read_text(encoding="utf-8")
        assert "PERMANENCE_LOW_COST_MODE=0" in text
        assert "PERMANENCE_FEATURE_WORK_REQUIRE_REVENUE_MILESTONE=0" in text


if __name__ == "__main__":
    test_low_cost_mode_enable_writes_profile()
    test_low_cost_mode_disable_turns_flags_off()
    print("✓ Low cost mode tests passed")
