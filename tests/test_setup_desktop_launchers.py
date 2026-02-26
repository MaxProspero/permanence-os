#!/usr/bin/env python3
"""Tests for desktop launcher setup."""

import os
import sys
import tempfile
from pathlib import Path

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import scripts.setup_desktop_launchers as launcher_mod  # noqa: E402


def test_setup_desktop_launchers_writes_expected_files():
    with tempfile.TemporaryDirectory() as tmp:
        target_dir = Path(tmp)
        rc = launcher_mod.main(["--desktop-dir", str(target_dir)])
        assert rc == 0

        expected = {
            "Run_Permanence_Operator_Surface.command",
            "Run_Permanence_Command_Center.command",
            "Run_Permanence_Foundation_Site.command",
            "Run_Permanence_Money_Loop.command",
        }
        actual = {p.name for p in target_dir.glob("*.command")}
        assert expected.issubset(actual)

        for name in expected:
            content = (target_dir / name).read_text(encoding="utf-8")
            assert "#!/bin/zsh" in content
            assert "set -euo pipefail" in content


def test_setup_desktop_launchers_skip_without_force():
    with tempfile.TemporaryDirectory() as tmp:
        target_dir = Path(tmp)
        first_rc = launcher_mod.main(["--desktop-dir", str(target_dir)])
        second_rc = launcher_mod.main(["--desktop-dir", str(target_dir)])
        assert first_rc == 0
        assert second_rc == 0


if __name__ == "__main__":
    test_setup_desktop_launchers_writes_expected_files()
    test_setup_desktop_launchers_skip_without_force()
    print("✓ desktop launcher setup tests passed")
