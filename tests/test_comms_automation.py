#!/usr/bin/env python3
"""Tests for comms_automation helpers."""

from __future__ import annotations

import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import scripts.comms_automation as mod  # noqa: E402


def test_parse_launchd_print_extracts_fields() -> None:
    text = """
state = not running
runs = 12
last exit code = 0
run interval = 300 seconds
path = /Users/paytonhicks/Library/LaunchAgents/com.permanence.comms_loop.plist
"""
    parsed = mod._parse_launchd_print(text)
    assert parsed["state"] == "not running"
    assert parsed["runs"] == 12
    assert parsed["last_exit_code"] == 0
    assert parsed["run_interval_seconds"] == 300
    assert parsed["path"].endswith("com.permanence.comms_loop.plist")


def test_parse_launchd_print_handles_missing_fields() -> None:
    parsed = mod._parse_launchd_print("irrelevant")
    assert parsed["state"] == "unknown"
    assert parsed["runs"] == 0
    assert parsed["last_exit_code"] is None
    assert parsed["run_interval_seconds"] is None
    assert parsed["path"] == ""


def test_status_label_for_action_digest_defaults_to_digest_label() -> None:
    assert mod._status_label_for_action("digest-status", "com.example.custom") == mod.DEFAULT_DIGEST_LABEL
    assert mod._status_label_for_action("doctor-status", "com.example.custom") == mod.DEFAULT_DOCTOR_LABEL
    assert mod._status_label_for_action("escalation-status", "com.example.custom") == mod.DEFAULT_ESCALATION_LABEL
    assert mod._status_label_for_action("status", "com.example.custom") == "com.example.custom"


def test_command_for_action_includes_digest_now_send() -> None:
    cmd = mod._command_for_action("digest-now")
    assert cmd[-1] == "--send"
    assert "comms_digest.py" in " ".join(cmd)


def test_command_for_action_includes_doctor_now_allow_warnings() -> None:
    cmd = mod._command_for_action("doctor-now")
    assert cmd[-1] == "--allow-warnings"
    assert "comms_doctor.py" in " ".join(cmd)


def test_command_for_action_includes_escalation_digest_send() -> None:
    cmd = mod._command_for_action("escalation-digest-now")
    assert cmd[-1] == "--send"
    assert "comms_escalation_digest.py" in " ".join(cmd)


def test_command_for_action_includes_escalation_enable_disable_scripts() -> None:
    enable_cmd = mod._command_for_action("escalation-enable")
    disable_cmd = mod._command_for_action("escalation-disable")
    assert "setup_comms_escalation_digest_automation.sh" in " ".join(enable_cmd)
    assert "disable_comms_escalation_digest_automation.sh" in " ".join(disable_cmd)


if __name__ == "__main__":
    test_parse_launchd_print_extracts_fields()
    test_parse_launchd_print_handles_missing_fields()
    test_status_label_for_action_digest_defaults_to_digest_label()
    test_command_for_action_includes_digest_now_send()
    test_command_for_action_includes_doctor_now_allow_warnings()
    test_command_for_action_includes_escalation_digest_send()
    test_command_for_action_includes_escalation_enable_disable_scripts()
    print("✓ Comms automation tests passed")
