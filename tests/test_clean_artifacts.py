#!/usr/bin/env python3
"""Tests for scripts.clean_artifacts."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import scripts.clean_artifacts as mod  # noqa: E402


def test_matches_dedup_and_skips_gitkeep(monkeypatch) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "logs").mkdir(parents=True, exist_ok=True)
        (root / "outputs").mkdir(parents=True, exist_ok=True)
        (root / "logs" / "a.log").write_text("x", encoding="utf-8")
        (root / "outputs" / "a.md").write_text("x", encoding="utf-8")
        (root / "outputs" / ".gitkeep").write_text("", encoding="utf-8")

        monkeypatch.setattr(mod, "BASE_DIR", root)
        monkeypatch.setattr(
            mod,
            "PATTERNS",
            {
                "logs": ["logs/*.log", "logs/*.log"],
                "outputs": ["outputs/*.md", "outputs/.gitkeep"],
            },
        )

        rows = mod._matches(["logs", "outputs"])
        names = {p.name for p in rows}
        assert "a.log" in names
        assert "a.md" in names
        assert ".gitkeep" not in names
        assert len(rows) == 2


def test_delete_dry_run_keeps_files() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        row = Path(tmp) / "sample.txt"
        row.write_text("ok", encoding="utf-8")
        removed = mod._delete([row], dry_run=True)
        assert removed == 1
        assert row.exists()


def test_delete_removes_files() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        row = Path(tmp) / "sample.txt"
        row.write_text("ok", encoding="utf-8")
        removed = mod._delete([row], dry_run=False)
        assert removed == 1
        assert not row.exists()
