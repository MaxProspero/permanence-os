#!/usr/bin/env python3
"""Tests for Telegram provider control commands."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import scripts.telegram_control as mod  # noqa: E402


def _base_memory_call_kwargs(store: dict[str, object]) -> dict[str, object]:
    return {
        "store": store,
        "memory_key": "chat:123",
        "chat_id": "123",
        "sender_user_id": "123",
        "sender_name": "tester",
        "max_notes": 50,
        "prefix": "/",
    }


def test_provider_status_command_reports_active_provider() -> None:
    snapshot = os.environ.get("PERMANENCE_MODEL_PROVIDER")
    try:
        os.environ["PERMANENCE_MODEL_PROVIDER"] = "openai"
        store: dict[str, object] = {"profiles": {}, "updated_at": ""}
        result = mod._execute_memory_command(  # type: ignore[attr-defined]
            command="provider-status",
            command_args="",
            **_base_memory_call_kwargs(store),
        )
        assert result.get("handled") is True
        assert result.get("ok") is True
        summary = str(result.get("summary") or "")
        assert "Active model provider: openai" in summary
    finally:
        if snapshot is None:
            os.environ.pop("PERMANENCE_MODEL_PROVIDER", None)
        else:
            os.environ["PERMANENCE_MODEL_PROVIDER"] = snapshot


def test_provider_set_command_updates_env_file() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        env_path = root / ".env"
        env_path.write_text("PERMANENCE_MODEL_PROVIDER=anthropic\n", encoding="utf-8")

        original_base = mod.BASE_DIR
        original_provider = os.environ.get("PERMANENCE_MODEL_PROVIDER")
        try:
            mod.BASE_DIR = root
            os.environ["PERMANENCE_MODEL_PROVIDER"] = "anthropic"
            store: dict[str, object] = {"profiles": {}, "updated_at": ""}
            result = mod._execute_memory_command(  # type: ignore[attr-defined]
                command="provider-set",
                command_args="ollama",
                **_base_memory_call_kwargs(store),
            )
        finally:
            mod.BASE_DIR = original_base
            if original_provider is None:
                os.environ.pop("PERMANENCE_MODEL_PROVIDER", None)
            else:
                os.environ["PERMANENCE_MODEL_PROVIDER"] = original_provider

        assert result.get("handled") is True
        assert result.get("ok") is True
        text = env_path.read_text(encoding="utf-8")
        assert "PERMANENCE_MODEL_PROVIDER=ollama" in text


if __name__ == "__main__":
    test_provider_status_command_reports_active_provider()
    test_provider_set_command_updates_env_file()
    print("✓ Telegram provider command tests passed")
