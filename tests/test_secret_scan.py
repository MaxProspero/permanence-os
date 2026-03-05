#!/usr/bin/env python3
"""Tests for secret scan helper."""

import os
import sys
import tempfile
from pathlib import Path

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import scripts.secret_scan as scan_mod  # noqa: E402


def test_secret_scan_detects_raw_keys():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        project = root / "repo"
        project.mkdir(parents=True, exist_ok=True)
        file_path = project / "config.txt"
        file_path.write_text("ANTHROPIC_API_KEY=sk-ant-abcdefghijklmnopqrstuvwxyz123456\n", encoding="utf-8")

        original = {"BASE_DIR": scan_mod.BASE_DIR}
        try:
            scan_mod.BASE_DIR = project
            findings = scan_mod.scan_paths([file_path])
        finally:
            scan_mod.BASE_DIR = original["BASE_DIR"]

        assert findings
        assert any(row.get("type") in {"key_assignment", "anthropic"} for row in findings)


def test_secret_scan_ignores_placeholders():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        project = root / "repo"
        project.mkdir(parents=True, exist_ok=True)
        file_path = project / "config.txt"
        file_path.write_text("ANTHROPIC_API_KEY=sk-ant-YOUR_KEY_HERE\n", encoding="utf-8")

        original = {"BASE_DIR": scan_mod.BASE_DIR}
        try:
            scan_mod.BASE_DIR = project
            findings = scan_mod.scan_paths([file_path])
        finally:
            scan_mod.BASE_DIR = original["BASE_DIR"]

        assert findings == []


if __name__ == "__main__":
    test_secret_scan_detects_raw_keys()
    test_secret_scan_ignores_placeholders()
    print("✓ Secret scan tests passed")
