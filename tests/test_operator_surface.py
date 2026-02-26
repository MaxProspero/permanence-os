#!/usr/bin/env python3
"""Tests for operator surface launcher."""

import os
import sys
from types import SimpleNamespace

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import scripts.operator_surface as surface_mod  # noqa: E402


def test_build_command_center_cmd_includes_expected_flags():
    args = SimpleNamespace(
        host="127.0.0.1",
        dashboard_port=8000,
        run_horizon=True,
        demo_horizon=True,
    )
    cmd = surface_mod._build_command_center_cmd(args=args, python_bin="python3")
    assert cmd[:2] == ["python3", str(surface_mod.BASE_DIR / "scripts" / "command_center.py")]
    assert "--host" in cmd
    assert "--port" in cmd
    assert "--no-open" in cmd
    assert "--run-horizon" in cmd
    assert "--demo-horizon" in cmd


def test_operator_surface_dry_run_returns_zero():
    rc = surface_mod.main(["--dry-run", "--no-open", "--money-loop", "--run-horizon", "--demo-horizon"])
    assert rc == 0


def test_operator_surface_requires_run_horizon_for_demo():
    try:
        surface_mod.main(["--dry-run", "--demo-horizon"])
        assert False, "Expected SystemExit from argparse error"
    except SystemExit as exc:
        assert int(exc.code) == 2


if __name__ == "__main__":
    test_build_command_center_cmd_includes_expected_flags()
    test_operator_surface_dry_run_returns_zero()
    test_operator_surface_requires_run_horizon_for_demo()
    print("✓ operator surface tests passed")
