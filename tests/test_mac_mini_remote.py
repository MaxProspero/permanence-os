#!/usr/bin/env python3
"""Tests for Mac Mini remote bridge helpers (pure functions, no SSH)."""

import os
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from scripts.mac_mini_remote import (  # noqa: E402
    BLOCKED_COMMAND_PATTERNS,
    DEFAULT_CONFIG,
    PERMANENCE_SERVICES,
    _is_blocked,
    _merge_cli_config,
    build_remote_shell,
)


# ── Blocked command safety checks ──────────────────────────────────────


class TestBlockedCommands:
    """Each BLOCKED_COMMAND_PATTERN must catch dangerous variants and
    pass through harmless ones."""

    def test_networksetup_blocked(self):
        assert _is_blocked("networksetup -setmanual Wi-Fi 10.0.0.1") is not None

    def test_ifconfig_down_blocked(self):
        assert _is_blocked("ifconfig en0 down") is not None

    def test_ifconfig_delete_blocked(self):
        assert _is_blocked("ifconfig en0 delete") is not None

    def test_ifconfig_show_allowed(self):
        assert _is_blocked("ifconfig en0") is None

    def test_launchctl_unload_ssh_blocked(self):
        assert _is_blocked("launchctl unload /System/Library/LaunchDaemons/ssh.plist") is not None

    def test_launchctl_unload_permanence_allowed(self):
        assert _is_blocked("launchctl unload ~/Library/LaunchAgents/com.permanence.command-center.plist") is None

    def test_shutdown_halt_blocked(self):
        assert _is_blocked("shutdown -h now") is not None
        assert _is_blocked("shutdown now") is not None

    def test_shutdown_reboot_allowed(self):
        assert _is_blocked("shutdown -r now") is None

    def test_halt_blocked(self):
        assert _is_blocked("halt") is not None

    def test_rm_rf_root_blocked(self):
        assert _is_blocked("rm -rf / ") is not None

    def test_rm_rf_home_blocked(self):
        assert _is_blocked("rm -rf ~ ") is not None
        assert _is_blocked("rm -rf $HOME") is not None

    def test_rm_rf_specific_dir_allowed(self):
        assert _is_blocked("rm -rf /tmp/test_output") is None

    def test_passwd_blocked(self):
        assert _is_blocked("passwd root") is not None

    def test_sudo_dscl_blocked(self):
        assert _is_blocked("sudo dscl . -create /Users/test") is not None

    def test_sudo_fdesetup_blocked(self):
        assert _is_blocked("sudo fdesetup disable") is not None

    def test_launchctl_bootout_system_blocked(self):
        assert _is_blocked("launchctl bootout system/com.apple.sshd") is not None

    def test_systemsetup_remote_login_off_blocked(self):
        assert _is_blocked("systemsetup -setremotelogin off") is not None
        assert _is_blocked("systemsetup -f -setRemoteLogin Off") is not None

    def test_normal_commands_allowed(self):
        assert _is_blocked("python cli.py status") is None
        assert _is_blocked("ls -la") is None
        assert _is_blocked("cat /tmp/permanence-cc.log") is None
        assert _is_blocked("launchctl list") is None
        assert _is_blocked("brew update") is None
        assert _is_blocked("git pull --ff-only") is None


# ── Shell composition ──────────────────────────────────────────────────


class TestBuildRemoteShell:
    """build_remote_shell() should compose correct shell strings."""

    def test_with_repo_and_venv(self):
        cmd = build_remote_shell(
            command="python cli.py status",
            repo_path="~/Code/permanence-os",
            use_repo=True,
            use_venv=True,
        )
        assert "PATH" in cmd
        assert "$HOME/Code/permanence-os" in cmd
        assert "venv/bin/activate" in cmd
        assert cmd.endswith("python cli.py status")

    def test_without_repo(self):
        cmd = build_remote_shell(
            command="uname -a",
            repo_path="~/Code/permanence-os",
            use_repo=False,
            use_venv=False,
        )
        assert "uname -a" in cmd
        assert "permanence-os" not in cmd

    def test_tilde_expansion(self):
        cmd = build_remote_shell(
            command="ls",
            repo_path="~/Code/permanence-os",
            use_repo=True,
        )
        assert "$HOME/Code/permanence-os" in cmd


# ── Config merge ───────────────────────────────────────────────────────


class TestMergeConfig:
    """_merge_cli_config() should update only provided values."""

    def test_updates_only_provided_values(self):
        existing = {"host": "old-host", "user": "old-user", "repo_path": "/old"}
        args = SimpleNamespace(host="new-host", user=None, repo_path=None, port=None, key_path=None)
        merged = _merge_cli_config(existing, args)
        assert merged["host"] == "new-host"
        assert merged["user"] == "old-user"

    def test_applies_defaults_for_missing(self):
        args = SimpleNamespace(host=None, user=None, repo_path=None, port=None, key_path=None)
        merged = _merge_cli_config({}, args)
        assert merged["host"] == DEFAULT_CONFIG["host"]
        assert merged["user"] == DEFAULT_CONFIG["user"]
        assert merged["key_path"] == DEFAULT_CONFIG["key_path"]

    def test_cli_overrides_default(self):
        args = SimpleNamespace(host="custom-ip", user=None, repo_path=None, port=2222, key_path=None)
        merged = _merge_cli_config({}, args)
        assert merged["host"] == "custom-ip"
        assert merged["port"] == 2222


# ── Constants ──────────────────────────────────────────────────────────


class TestConstants:
    """Required constants should be present and well-formed."""

    def test_permanence_services_minimum(self):
        assert len(PERMANENCE_SERVICES) >= 3
        names = {s if isinstance(s, str) else s[0] for s in PERMANENCE_SERVICES}
        assert "com.permanence.command-center" in names
        assert "com.permanence.foundation-site" in names
        assert "com.permanence.foundation-api" in names

    def test_blocked_patterns_minimum(self):
        assert len(BLOCKED_COMMAND_PATTERNS) >= 6

    def test_default_config_has_required_fields(self):
        for key in ("host", "user", "key_path", "repo_path"):
            assert key in DEFAULT_CONFIG, f"Missing key: {key}"
