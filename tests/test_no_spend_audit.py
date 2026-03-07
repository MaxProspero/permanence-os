#!/usr/bin/env python3
"""Tests for no_spend_audit guardrail checks."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import scripts.no_spend_audit as mod  # noqa: E402


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")


def test_no_spend_audit_passes_when_guardrails_hold() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        outputs = root / "outputs"
        tool = root / "tool"
        env_path = root / ".env"
        calls_log = root / "logs" / "model_calls.jsonl"
        outputs.mkdir(parents=True, exist_ok=True)
        tool.mkdir(parents=True, exist_ok=True)
        env_path.write_text(
            "\n".join(
                [
                    "PERMANENCE_NO_SPEND_MODE=1",
                    "PERMANENCE_LOW_COST_MODE=1",
                    "PERMANENCE_MODEL_PROVIDER=ollama",
                    "PERMANENCE_MODEL_PROVIDER_CAPS_USD=anthropic=0,openai=0,xai=0,ollama=0",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        _write_jsonl(
            calls_log,
            [
                {
                    "timestamp": "2026-03-05T00:00:00Z",
                    "model": "qwen2.5:3b",
                    "input_tokens": 21,
                    "output_tokens": 10,
                }
            ],
        )

        original = {
            "OUTPUT_DIR": mod.OUTPUT_DIR,
            "TOOL_DIR": mod.TOOL_DIR,
            "ENV_PATH": mod.ENV_PATH,
            "MODEL_CALLS_PATH": mod.MODEL_CALLS_PATH,
        }
        try:
            mod.OUTPUT_DIR = outputs
            mod.TOOL_DIR = tool
            mod.ENV_PATH = env_path
            mod.MODEL_CALLS_PATH = calls_log
            rc = mod.main(["--lookback-hours", "48", "--strict"])
        finally:
            mod.OUTPUT_DIR = original["OUTPUT_DIR"]
            mod.TOOL_DIR = original["TOOL_DIR"]
            mod.ENV_PATH = original["ENV_PATH"]
            mod.MODEL_CALLS_PATH = original["MODEL_CALLS_PATH"]

        assert rc == 0
        latest = outputs / "no_spend_audit_latest.md"
        assert latest.exists()
        text = latest.read_text(encoding="utf-8")
        assert "No-spend mode: True" in text
        payload_files = sorted(tool.glob("no_spend_audit_*.json"))
        assert payload_files
        payload = json.loads(payload_files[-1].read_text(encoding="utf-8"))
        assert payload.get("violations") == []


def test_no_spend_audit_strict_fails_on_paid_provider_violation() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        outputs = root / "outputs"
        tool = root / "tool"
        env_path = root / ".env"
        calls_log = root / "logs" / "model_calls.jsonl"
        outputs.mkdir(parents=True, exist_ok=True)
        tool.mkdir(parents=True, exist_ok=True)
        env_path.write_text(
            "\n".join(
                [
                    "PERMANENCE_NO_SPEND_MODE=1",
                    "PERMANENCE_LOW_COST_MODE=1",
                    "PERMANENCE_MODEL_PROVIDER=anthropic",
                    "PERMANENCE_MODEL_PROVIDER_CAPS_USD=anthropic=1,openai=0,xai=0,ollama=0",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        _write_jsonl(
            calls_log,
            [
                {
                    "timestamp": "2026-03-05T00:00:00Z",
                    "model": "claude-sonnet-4-6",
                    "input_tokens": 120,
                    "output_tokens": 80,
                }
            ],
        )

        original = {
            "OUTPUT_DIR": mod.OUTPUT_DIR,
            "TOOL_DIR": mod.TOOL_DIR,
            "ENV_PATH": mod.ENV_PATH,
            "MODEL_CALLS_PATH": mod.MODEL_CALLS_PATH,
        }
        try:
            mod.OUTPUT_DIR = outputs
            mod.TOOL_DIR = tool
            mod.ENV_PATH = env_path
            mod.MODEL_CALLS_PATH = calls_log
            rc = mod.main(["--lookback-hours", "48", "--strict"])
        finally:
            mod.OUTPUT_DIR = original["OUTPUT_DIR"]
            mod.TOOL_DIR = original["TOOL_DIR"]
            mod.ENV_PATH = original["ENV_PATH"]
            mod.MODEL_CALLS_PATH = original["MODEL_CALLS_PATH"]

        assert rc == 2
        payload_files = sorted(tool.glob("no_spend_audit_*.json"))
        assert payload_files
        payload = json.loads(payload_files[-1].read_text(encoding="utf-8"))
        violations = payload.get("violations") or []
        assert isinstance(violations, list) and len(violations) >= 2


if __name__ == "__main__":
    test_no_spend_audit_passes_when_guardrails_hold()
    test_no_spend_audit_strict_fails_on_paid_provider_violation()
    print("✓ No-spend audit tests passed")
