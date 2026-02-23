#!/usr/bin/env python3
"""Tests for Dell remote bridge helpers."""

import os
import sys
from types import SimpleNamespace

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from scripts.dell_remote import _merge_cli_config, build_remote_shell  # noqa: E402


def test_build_remote_shell_with_repo_and_venv():
    cmd = build_remote_shell(
        command="python cli.py status",
        repo_path="~/permanence-os",
        use_repo=True,
        use_venv=True,
    )
    assert "cd " in cmd
    assert ".venv/bin/activate" in cmd
    assert cmd.endswith("python cli.py status")


def test_build_remote_shell_without_repo():
    cmd = build_remote_shell(
        command="uname -a",
        repo_path="~/permanence-os",
        use_repo=False,
        use_venv=False,
    )
    assert cmd == "uname -a"


def test_merge_cli_config_updates_only_provided_values():
    existing = {
        "host": "old-host",
        "user": "old-user",
        "repo_path": "/old/repo",
        "port": 22,
    }
    args = SimpleNamespace(
        host="new-host",
        user=None,
        repo_path="/new/repo",
        port=2222,
        key_path=None,
    )
    merged = _merge_cli_config(existing, args)
    assert merged["host"] == "new-host"
    assert merged["user"] == "old-user"
    assert merged["repo_path"] == "/new/repo"
    assert merged["port"] == 2222


if __name__ == "__main__":
    test_build_remote_shell_with_repo_and_venv()
    test_build_remote_shell_without_repo()
    test_merge_cli_config_updates_only_provided_values()
    print("ok")
