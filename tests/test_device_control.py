#!/usr/bin/env python3
"""Tests for core.device_control — Permission model and device governance."""

import json
import os
import sys
import tempfile
from datetime import datetime, timezone, timedelta

os.environ.setdefault("PERMANENCE_LOG_DIR", "/tmp/permanence-os-test-logs")

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.device_control import (
    DeviceController,
    DeviceMode,
    ActionCategory,
    PermissionGrant,
    BLOCKED_ACTIONS,
    LOW_RISK_ACTIONS,
    MEDIUM_RISK_ACTIONS,
    HIGH_RISK_ACTIONS,
)


def _make_controller(tmp):
    """Create a fresh DeviceController with temp state/log paths."""
    state_path = os.path.join(tmp, "device_control_state.json")
    log_path = os.path.join(tmp, "device_control.jsonl")
    return DeviceController(state_path=state_path, log_path=log_path)


# ── Device Initialization ─────────────────────────────────────────────

def test_default_devices_initialized():
    """Default devices (mac_mini, macbook, dell) are created on init."""
    with tempfile.TemporaryDirectory() as tmp:
        dc = _make_controller(tmp)
        assert "mac_mini" in dc.devices
        assert "macbook" in dc.devices
        assert "dell" in dc.devices


def test_mac_mini_is_full_control():
    """Mac Mini defaults to full_control mode."""
    with tempfile.TemporaryDirectory() as tmp:
        dc = _make_controller(tmp)
        assert dc.devices["mac_mini"].mode == DeviceMode.FULL_CONTROL.value


def test_macbook_is_suggest_only():
    """MacBook defaults to suggest_only mode."""
    with tempfile.TemporaryDirectory() as tmp:
        dc = _make_controller(tmp)
        assert dc.devices["macbook"].mode == DeviceMode.SUGGEST_ONLY.value


def test_dell_is_expansion():
    """Dell defaults to expansion mode."""
    with tempfile.TemporaryDirectory() as tmp:
        dc = _make_controller(tmp)
        assert dc.devices["dell"].mode == DeviceMode.EXPANSION.value


# ── Blocked Actions ───────────────────────────────────────────────────

def test_blocked_actions_always_denied():
    """Blocked action categories are NEVER allowed on any device."""
    with tempfile.TemporaryDirectory() as tmp:
        dc = _make_controller(tmp)
        for blocked_cat in BLOCKED_ACTIONS:
            result = dc.check_permission(
                device="mac_mini",
                action_category=blocked_cat.value,
                action="test_blocked",
            )
            assert not result["allowed"], f"{blocked_cat.value} should be blocked"
            assert "permanently blocked" in result["reason"].lower()


def test_blocked_on_macbook_too():
    """Blocked actions are denied on MacBook as well (different reason)."""
    with tempfile.TemporaryDirectory() as tmp:
        dc = _make_controller(tmp)
        for blocked_cat in BLOCKED_ACTIONS:
            result = dc.check_permission(
                device="macbook",
                action_category=blocked_cat.value,
                action="test_blocked",
            )
            assert not result["allowed"]


# ── MacBook Suggest-Only Mode ─────────────────────────────────────────

def test_macbook_never_allows_execution():
    """MacBook in suggest_only mode never allows any action execution."""
    with tempfile.TemporaryDirectory() as tmp:
        dc = _make_controller(tmp)
        for cat in ActionCategory:
            if cat in BLOCKED_ACTIONS:
                continue  # blocked actions have different error path
            result = dc.check_permission(
                device="macbook",
                action_category=cat.value,
                action="test_suggest",
            )
            assert not result["allowed"], f"MacBook should deny {cat.value}"


def test_macbook_returns_suggestions():
    """MacBook returns a suggestion string instead of executing."""
    with tempfile.TemporaryDirectory() as tmp:
        dc = _make_controller(tmp)
        result = dc.check_permission(
            device="macbook",
            action_category=ActionCategory.APP_MANAGEMENT.value,
            action="install_discord",
            details={"app": "discord"},
        )
        assert not result["allowed"]
        assert result["suggestion"] is not None
        assert "install_discord" in result["suggestion"]
        assert "suggest-only" in result["reason"].lower()


def test_macbook_cannot_be_granted_execution():
    """Cannot grant execution permissions on suggest_only device."""
    with tempfile.TemporaryDirectory() as tmp:
        dc = _make_controller(tmp)
        result = dc.grant_permission(
            device="macbook",
            scope=["app_management"],
            duration_minutes=60,
        )
        assert "error" in result
        assert "suggest-only" in result["error"].lower()


# ── Mac Mini Full Control ─────────────────────────────────────────────

def test_mac_mini_low_risk_auto_granted():
    """Low-risk actions are auto-granted on Mac Mini (full_control)."""
    with tempfile.TemporaryDirectory() as tmp:
        dc = _make_controller(tmp)
        for cat in LOW_RISK_ACTIONS:
            result = dc.check_permission(
                device="mac_mini",
                action_category=cat.value,
                action="test_auto",
            )
            assert result["allowed"], f"{cat.value} should be auto-granted"
            assert result["grant_id"] == "auto_low_risk"


def test_mac_mini_medium_risk_needs_grant():
    """Medium-risk actions require explicit grant on Mac Mini."""
    with tempfile.TemporaryDirectory() as tmp:
        dc = _make_controller(tmp)
        result = dc.check_permission(
            device="mac_mini",
            action_category=ActionCategory.APP_MANAGEMENT.value,
            action="install_app",
        )
        assert not result["allowed"]
        assert result["requires_approval"]


def test_mac_mini_high_risk_needs_grant():
    """High-risk actions require explicit grant on Mac Mini."""
    with tempfile.TemporaryDirectory() as tmp:
        dc = _make_controller(tmp)
        result = dc.check_permission(
            device="mac_mini",
            action_category=ActionCategory.FILE_DELETE.value,
            action="delete_temp_files",
        )
        assert not result["allowed"]
        assert result["requires_approval"]


def test_mac_mini_medium_risk_allowed_with_grant():
    """Medium-risk action succeeds after granting permission."""
    with tempfile.TemporaryDirectory() as tmp:
        dc = _make_controller(tmp)

        # Grant app_management for 60 minutes
        grant = dc.grant_permission(
            device="mac_mini",
            scope=["app_management"],
            duration_minutes=60,
            granted_by="human_test",
        )
        assert "error" not in grant
        grant_id = grant["grant_id"]

        # Now check — should be allowed
        result = dc.check_permission(
            device="mac_mini",
            action_category=ActionCategory.APP_MANAGEMENT.value,
            action="install_discord",
        )
        assert result["allowed"]
        assert result["grant_id"] == grant_id


def test_mac_mini_high_risk_allowed_with_grant():
    """High-risk action succeeds after granting permission."""
    with tempfile.TemporaryDirectory() as tmp:
        dc = _make_controller(tmp)

        grant = dc.grant_permission(
            device="mac_mini",
            scope=["file_delete"],
            duration_minutes=30,
            granted_by="human_test",
        )
        assert "error" not in grant

        result = dc.check_permission(
            device="mac_mini",
            action_category=ActionCategory.FILE_DELETE.value,
            action="delete_temp",
        )
        assert result["allowed"]


# ── Permission Grants ─────────────────────────────────────────────────

def test_grant_time_limited_expires():
    """Time-limited grants expire after their duration."""
    with tempfile.TemporaryDirectory() as tmp:
        dc = _make_controller(tmp)

        grant = dc.grant_permission(
            device="mac_mini",
            scope=["app_management"],
            duration_minutes=60,
        )
        grant_obj = dc.grants[grant["grant_id"]]

        # Force expire by setting expires_at to the past
        past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        grant_obj.expires_at = past

        assert not grant_obj.is_active()

        # Check permission — should be denied now
        result = dc.check_permission(
            device="mac_mini",
            action_category=ActionCategory.APP_MANAGEMENT.value,
            action="test_expired",
        )
        assert not result["allowed"]


def test_grant_action_limited():
    """Action-limited grants expire after N actions consumed."""
    with tempfile.TemporaryDirectory() as tmp:
        dc = _make_controller(tmp)

        grant = dc.grant_permission(
            device="mac_mini",
            scope=["app_management"],
            max_actions=3,
        )
        grant_id = grant["grant_id"]

        # Use 3 actions
        for i in range(3):
            result = dc.check_permission(
                device="mac_mini",
                action_category=ActionCategory.APP_MANAGEMENT.value,
                action=f"action_{i}",
            )
            assert result["allowed"], f"Action {i} should be allowed"

        # 4th should be denied
        result = dc.check_permission(
            device="mac_mini",
            action_category=ActionCategory.APP_MANAGEMENT.value,
            action="action_3",
        )
        assert not result["allowed"]


def test_grant_revocation():
    """Grants can be revoked immediately."""
    with tempfile.TemporaryDirectory() as tmp:
        dc = _make_controller(tmp)

        grant = dc.grant_permission(
            device="mac_mini",
            scope=["app_management"],
            duration_minutes=120,
        )
        grant_id = grant["grant_id"]

        # Verify it works
        result = dc.check_permission(
            device="mac_mini",
            action_category=ActionCategory.APP_MANAGEMENT.value,
            action="test_revoke",
        )
        assert result["allowed"]

        # Revoke
        revoke_result = dc.revoke_grant(grant_id)
        assert revoke_result["status"] == "revoked"

        # Should be denied now
        result = dc.check_permission(
            device="mac_mini",
            action_category=ActionCategory.APP_MANAGEMENT.value,
            action="test_after_revoke",
        )
        assert not result["allowed"]


def test_grant_task_limited():
    """Task-limited grants work and can be completed."""
    with tempfile.TemporaryDirectory() as tmp:
        dc = _make_controller(tmp)

        grant = dc.grant_task_permission(
            device="mac_mini",
            task_id="install-chrome-ext",
            scope=["app_management"],
        )
        grant_id = grant["grant_id"]

        # Check — allowed
        result = dc.check_permission(
            device="mac_mini",
            action_category=ActionCategory.APP_MANAGEMENT.value,
            action="test_task",
        )
        assert result["allowed"]

        # Complete the task — should auto-revoke
        count = dc.complete_task_grants("install-chrome-ext")
        assert count == 1

        # Should be denied now
        result = dc.check_permission(
            device="mac_mini",
            action_category=ActionCategory.APP_MANAGEMENT.value,
            action="test_after_complete",
        )
        assert not result["allowed"]


def test_grant_wildcard_scope():
    """Wildcard scope (*) covers all non-blocked actions."""
    with tempfile.TemporaryDirectory() as tmp:
        dc = _make_controller(tmp)

        grant = dc.grant_permission(
            device="mac_mini",
            scope=["*"],
            duration_minutes=30,
        )

        # Medium risk — should be allowed
        result = dc.check_permission(
            device="mac_mini",
            action_category=ActionCategory.APP_MANAGEMENT.value,
            action="test_wildcard",
        )
        assert result["allowed"]

        # High risk — should also be allowed with wildcard
        result = dc.check_permission(
            device="mac_mini",
            action_category=ActionCategory.FILE_DELETE.value,
            action="test_wildcard_high",
        )
        assert result["allowed"]

        # Blocked — should STILL be denied even with wildcard
        result = dc.check_permission(
            device="mac_mini",
            action_category=ActionCategory.NETWORK_CONFIG.value,
            action="test_wildcard_blocked",
        )
        assert not result["allowed"]


def test_grant_blocked_actions_silently_removed():
    """Blocked actions are silently removed from grant scope."""
    with tempfile.TemporaryDirectory() as tmp:
        dc = _make_controller(tmp)

        grant = dc.grant_permission(
            device="mac_mini",
            scope=["app_management", "network_config", "ssh_config"],
            duration_minutes=30,
        )
        # network_config and ssh_config should be stripped
        assert "app_management" in grant["scope"]
        assert "network_config" not in grant["scope"]
        assert "ssh_config" not in grant["scope"]


def test_revoke_all_grants():
    """Emergency revoke all grants works."""
    with tempfile.TemporaryDirectory() as tmp:
        dc = _make_controller(tmp)

        dc.grant_permission(device="mac_mini", scope=["app_management"], duration_minutes=60)
        dc.grant_permission(device="mac_mini", scope=["service_management"], duration_minutes=60)
        dc.grant_permission(device="mac_mini", scope=["file_operations"], duration_minutes=60)

        assert len(dc.list_active_grants()) == 3

        count = dc.revoke_all_grants()
        assert count == 3
        assert len(dc.list_active_grants()) == 0


def test_revoke_all_for_specific_device():
    """Emergency revoke for a specific device only."""
    with tempfile.TemporaryDirectory() as tmp:
        dc = _make_controller(tmp)
        # Note: We can't grant to macbook (suggest_only), so use mac_mini only
        dc.grant_permission(device="mac_mini", scope=["app_management"], duration_minutes=60)
        dc.grant_permission(device="mac_mini", scope=["service_management"], duration_minutes=60)

        count = dc.revoke_all_grants(device="mac_mini")
        assert count == 2


# ── State Persistence ─────────────────────────────────────────────────

def test_state_persists_across_restarts():
    """Device state and grants persist to disk and reload."""
    with tempfile.TemporaryDirectory() as tmp:
        state_path = os.path.join(tmp, "state.json")
        log_path = os.path.join(tmp, "log.jsonl")

        # Create controller and add a grant
        dc1 = DeviceController(state_path=state_path, log_path=log_path)
        grant = dc1.grant_permission(
            device="mac_mini",
            scope=["app_management"],
            duration_minutes=120,
        )
        grant_id = grant["grant_id"]

        # Create a new controller pointing at same state
        dc2 = DeviceController(state_path=state_path, log_path=log_path)

        # Grant should be restored
        assert grant_id in dc2.grants
        assert dc2.grants[grant_id].is_active()

        # Permission should work
        result = dc2.check_permission(
            device="mac_mini",
            action_category=ActionCategory.APP_MANAGEMENT.value,
            action="test_persist",
        )
        assert result["allowed"]


def test_state_file_created():
    """State file is created after first save."""
    with tempfile.TemporaryDirectory() as tmp:
        state_path = os.path.join(tmp, "state.json")
        log_path = os.path.join(tmp, "log.jsonl")
        dc = DeviceController(state_path=state_path, log_path=log_path)
        dc.grant_permission(device="mac_mini", scope=["app_management"], duration_minutes=60)
        assert os.path.exists(state_path)


# ── Device Mode Changes ───────────────────────────────────────────────

def test_set_device_mode():
    """Can change device mode."""
    with tempfile.TemporaryDirectory() as tmp:
        dc = _make_controller(tmp)
        result = dc.set_device_mode("mac_mini", DeviceMode.SUGGEST_ONLY.value)
        assert result["new_mode"] == DeviceMode.SUGGEST_ONLY.value

        # Now actions should be denied
        perm = dc.check_permission(
            device="mac_mini",
            action_category=ActionCategory.SYSTEM_INFO.value,
            action="test",
        )
        assert not perm["allowed"]


def test_switching_to_suggest_revokes_grants():
    """Switching to suggest_only revokes all active grants for that device."""
    with tempfile.TemporaryDirectory() as tmp:
        dc = _make_controller(tmp)
        dc.grant_permission(device="mac_mini", scope=["app_management"], duration_minutes=60)
        assert len(dc.list_active_grants(device="mac_mini")) == 1

        dc.set_device_mode("mac_mini", DeviceMode.SUGGEST_ONLY.value)
        assert len(dc.list_active_grants(device="mac_mini")) == 0


# ── Edge Cases ────────────────────────────────────────────────────────

def test_unknown_device_denied():
    """Unknown device ID is denied."""
    with tempfile.TemporaryDirectory() as tmp:
        dc = _make_controller(tmp)
        result = dc.check_permission(
            device="nonexistent",
            action_category=ActionCategory.SYSTEM_INFO.value,
            action="test",
        )
        assert not result["allowed"]
        assert "unknown device" in result["reason"].lower()


def test_unknown_action_category_denied():
    """Unknown action category is denied."""
    with tempfile.TemporaryDirectory() as tmp:
        dc = _make_controller(tmp)
        result = dc.check_permission(
            device="mac_mini",
            action_category="nonexistent_category",
            action="test",
        )
        assert not result["allowed"]
        assert "unknown action category" in result["reason"].lower()


def test_disconnected_device_denied():
    """Disconnected device is denied."""
    with tempfile.TemporaryDirectory() as tmp:
        dc = _make_controller(tmp)
        dc.set_device_connected("dell", False)
        result = dc.check_permission(
            device="dell",
            action_category=ActionCategory.SYSTEM_INFO.value,
            action="test",
        )
        assert not result["allowed"]
        assert "not connected" in result["reason"].lower()


def test_audit_log_written():
    """Actions are logged to the audit file."""
    with tempfile.TemporaryDirectory() as tmp:
        state_path = os.path.join(tmp, "state.json")
        log_path = os.path.join(tmp, "log.jsonl")
        dc = DeviceController(state_path=state_path, log_path=log_path)

        dc.grant_permission(device="mac_mini", scope=["app_management"], duration_minutes=60)
        dc.log_action(
            device="mac_mini",
            action="install_app:discord",
            action_category=ActionCategory.APP_MANAGEMENT.value,
            success=True,
        )

        assert os.path.exists(log_path)
        with open(log_path) as f:
            lines = [l.strip() for l in f if l.strip()]
        # At least the grant event and the action event
        assert len(lines) >= 2
        last_event = json.loads(lines[-1])
        assert last_event["event"] == "action_executed"
        assert last_event["action"] == "install_app:discord"


def test_cleanup_expired_grants():
    """Cleanup removes expired/revoked grants."""
    with tempfile.TemporaryDirectory() as tmp:
        dc = _make_controller(tmp)

        # Create a grant and immediately revoke it
        grant = dc.grant_permission(device="mac_mini", scope=["app_management"], duration_minutes=60)
        dc.revoke_grant(grant["grant_id"])

        # Create another grant that's still active
        dc.grant_permission(device="mac_mini", scope=["service_management"], duration_minutes=60)

        assert len(dc.grants) == 2

        # Cleanup should remove the revoked one
        removed = dc.cleanup_expired_grants()
        assert removed == 1
        assert len(dc.grants) == 1


def test_status_report():
    """Status report includes all relevant information."""
    with tempfile.TemporaryDirectory() as tmp:
        dc = _make_controller(tmp)
        dc.grant_permission(device="mac_mini", scope=["app_management"], duration_minutes=60)

        status = dc.status()
        assert "devices" in status
        assert "active_grants" in status
        assert "mac_mini" in status["devices"]
        assert status["devices"]["mac_mini"]["mode"] == "full_control"
        assert len(status["active_grants"]) == 1


if __name__ == "__main__":
    test_default_devices_initialized()
    test_mac_mini_is_full_control()
    test_macbook_is_suggest_only()
    test_dell_is_expansion()
    test_blocked_actions_always_denied()
    test_blocked_on_macbook_too()
    test_macbook_never_allows_execution()
    test_macbook_returns_suggestions()
    test_macbook_cannot_be_granted_execution()
    test_mac_mini_low_risk_auto_granted()
    test_mac_mini_medium_risk_needs_grant()
    test_mac_mini_high_risk_needs_grant()
    test_mac_mini_medium_risk_allowed_with_grant()
    test_mac_mini_high_risk_allowed_with_grant()
    test_grant_time_limited_expires()
    test_grant_action_limited()
    test_grant_revocation()
    test_grant_task_limited()
    test_grant_wildcard_scope()
    test_grant_blocked_actions_silently_removed()
    test_revoke_all_grants()
    test_revoke_all_for_specific_device()
    test_state_persists_across_restarts()
    test_state_file_created()
    test_set_device_mode()
    test_switching_to_suggest_revokes_grants()
    test_unknown_device_denied()
    test_unknown_action_category_denied()
    test_disconnected_device_denied()
    test_audit_log_written()
    test_cleanup_expired_grants()
    test_status_report()
    print("✓ All device control tests passed")
