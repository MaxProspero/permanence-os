#!/usr/bin/env python3
"""Tests for ophtxn_launchpad readiness and strict gating."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import scripts.ophtxn_launchpad as mod  # noqa: E402


def _make_file(path: Path, text: str = "ok\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_launchpad_status_strict_passes_when_surface_connectors_and_ops_ready() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        outputs = root / "outputs"
        tool = root / "tool"

        _make_file(root / "site" / "foundation" / "index.html")
        _make_file(root / "site" / "foundation" / "official_app.html")
        _make_file(root / "site" / "foundation" / "press_kit.html")
        _make_file(root / "site" / "foundation" / "assets" / "ophtxn_mark.svg")
        _make_file(root / "docs" / "ophtxn_operator_command_guide.md")
        _make_file(root / "docs" / "ophtxn_official_launch_path_20260305.md")
        _make_file(root / "docs" / "ophtxn_venture_radar_20260305.md")
        _make_file(
            root / "app" / "foundation" / "server.py",
            "\n".join(["@app.get('/app/official')", "@app.get('/app/studio')", "@app.get('/app/press')"]) + "\n",
        )

        original = {
            "BASE_DIR": mod.BASE_DIR,
            "OUTPUT_DIR": mod.OUTPUT_DIR,
            "TOOL_DIR": mod.TOOL_DIR,
            "SURFACE_FILES": list(mod.SURFACE_FILES),
            "DOC_FILES": list(mod.DOC_FILES),
        }
        old_env = dict(os.environ)
        try:
            mod.BASE_DIR = root
            mod.OUTPUT_DIR = outputs
            mod.TOOL_DIR = tool
            mod.SURFACE_FILES = [
                ("Official landing", root / "site" / "foundation" / "index.html"),
                ("Official app studio", root / "site" / "foundation" / "official_app.html"),
                ("Press kit", root / "site" / "foundation" / "press_kit.html"),
                ("Logo mark", root / "site" / "foundation" / "assets" / "ophtxn_mark.svg"),
            ]
            mod.DOC_FILES = [
                ("Operator command guide", root / "docs" / "ophtxn_operator_command_guide.md"),
                ("Official launch path", root / "docs" / "ophtxn_official_launch_path_20260305.md"),
                ("Venture radar", root / "docs" / "ophtxn_venture_radar_20260305.md"),
            ]

            os.environ["PERMANENCE_TELEGRAM_BOT_TOKEN"] = "token"
            os.environ["PERMANENCE_TELEGRAM_CHAT_ID"] = "-1001"
            os.environ["PERMANENCE_DISCORD_BOT_TOKEN"] = "discord"
            os.environ["PERMANENCE_NO_SPEND_MODE"] = "1"
            os.environ["PERMANENCE_LOW_COST_MODE"] = "1"
            os.environ["PERMANENCE_MODEL_PROVIDER"] = "ollama"
            os.environ["PERMANENCE_MODEL_PROVIDER_CAPS_USD"] = "anthropic=0,openai=0,xai=0,ollama=0"

            rc = mod.main(["--action", "status", "--strict", "--min-score", "80"])
        finally:
            mod.BASE_DIR = original["BASE_DIR"]
            mod.OUTPUT_DIR = original["OUTPUT_DIR"]
            mod.TOOL_DIR = original["TOOL_DIR"]
            mod.SURFACE_FILES = original["SURFACE_FILES"]
            mod.DOC_FILES = original["DOC_FILES"]
            os.environ.clear()
            os.environ.update(old_env)

        assert rc == 0
        latest = outputs / "ophtxn_launchpad_latest.md"
        assert latest.exists()
        text = latest.read_text(encoding="utf-8")
        assert "Overall score:" in text
        assert "Launch Next 10" in text


def test_launchpad_strict_fails_when_readiness_low() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        outputs = root / "outputs"
        tool = root / "tool"

        original = {
            "BASE_DIR": mod.BASE_DIR,
            "OUTPUT_DIR": mod.OUTPUT_DIR,
            "TOOL_DIR": mod.TOOL_DIR,
            "SURFACE_FILES": list(mod.SURFACE_FILES),
            "DOC_FILES": list(mod.DOC_FILES),
        }
        old_env = dict(os.environ)
        try:
            mod.BASE_DIR = root
            mod.OUTPUT_DIR = outputs
            mod.TOOL_DIR = tool
            mod.SURFACE_FILES = [("Official landing", root / "site" / "foundation" / "index.html")]
            mod.DOC_FILES = [("Operator command guide", root / "docs" / "ophtxn_operator_command_guide.md")]
            os.environ.pop("PERMANENCE_TELEGRAM_BOT_TOKEN", None)
            os.environ.pop("PERMANENCE_TELEGRAM_CHAT_ID", None)
            os.environ.pop("PERMANENCE_DISCORD_BOT_TOKEN", None)
            os.environ["PERMANENCE_NO_SPEND_MODE"] = "0"
            os.environ["PERMANENCE_LOW_COST_MODE"] = "0"
            os.environ["PERMANENCE_MODEL_PROVIDER"] = "anthropic"
            os.environ["PERMANENCE_MODEL_PROVIDER_CAPS_USD"] = ""

            rc = mod.main(["--action", "status", "--strict", "--min-score", "80"])
        finally:
            mod.BASE_DIR = original["BASE_DIR"]
            mod.OUTPUT_DIR = original["OUTPUT_DIR"]
            mod.TOOL_DIR = original["TOOL_DIR"]
            mod.SURFACE_FILES = original["SURFACE_FILES"]
            mod.DOC_FILES = original["DOC_FILES"]
            os.environ.clear()
            os.environ.update(old_env)

        assert rc == 2
        latest = outputs / "ophtxn_launchpad_latest.md"
        assert latest.exists()


if __name__ == "__main__":
    test_launchpad_status_strict_passes_when_surface_connectors_and_ops_ready()
    test_launchpad_strict_fails_when_readiness_low()
    print("✓ ophtxn_launchpad tests passed")
