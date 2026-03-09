#!/usr/bin/env python3
"""Tests for scripts/ghost_os_bridge.py — Ghost OS MCP Bridge."""

import json
import os
import sys
import tempfile

import pytest

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, BASE_DIR)

from scripts.ghost_os_bridge import (
    GhostOSBridge,
    GHOST_TOOL_REGISTRY,
    DANGEROUS_TOOL_PARAMS,
    RATE_LIMIT_MAX_CALLS,
)


# ── Fixtures ────────────────────────────────────────────────────────────

@pytest.fixture
def bridge(tmp_path):
    """Create a bridge with a temp log path."""
    return GhostOSBridge(
        log_path=str(tmp_path / "ghost_bridge.jsonl"),
    )


# ── Tool Registry Tests ────────────────────────────────────────────────

def test_tool_registry_not_empty():
    """Registry has tools defined."""
    assert len(GHOST_TOOL_REGISTRY) > 0


def test_all_tools_have_required_fields():
    """Every tool has category, description, and risk."""
    for name, info in GHOST_TOOL_REGISTRY.items():
        assert "category" in info, f"{name} missing category"
        assert "description" in info, f"{name} missing description"
        assert "risk" in info, f"{name} missing risk"
        assert info["risk"] in ("low", "medium", "high"), f"{name} has invalid risk: {info['risk']}"


def test_tool_categories_are_valid():
    """All tool categories map to valid ActionCategory values."""
    valid_categories = {
        "system_info", "file_read", "process_status", "service_status",
        "app_management", "file_operations", "service_management",
        "network_query", "automation_run", "cron_management",
        "clipboard", "notification", "file_delete", "system_config",
        "user_management", "security_config",
    }
    for name, info in GHOST_TOOL_REGISTRY.items():
        assert info["category"] in valid_categories, \
            f"{name} has unknown category: {info['category']}"


def test_perception_tools_are_low_risk():
    """Perception tools should be low risk."""
    perception_tools = ["ax_tree", "screenshot", "find_element", "get_element_text",
                        "ghost_ground", "list_windows"]
    for tool in perception_tools:
        if tool in GHOST_TOOL_REGISTRY:
            assert GHOST_TOOL_REGISTRY[tool]["risk"] == "low", \
                f"{tool} should be low risk"


def test_interaction_tools_are_medium_risk():
    """Interaction tools should be medium risk."""
    interaction_tools = ["click", "type_text", "key_press", "scroll", "drag",
                         "focus_app", "resize_window", "move_window"]
    for tool in interaction_tools:
        if tool in GHOST_TOOL_REGISTRY:
            assert GHOST_TOOL_REGISTRY[tool]["risk"] == "medium", \
                f"{tool} should be medium risk"


# ── Permission Check Tests ──────────────────────────────────────────────

def test_unknown_tool_denied(bridge):
    """Unknown tools are always denied."""
    result = bridge.check_tool("nonexistent_tool")
    assert not result["allowed"]
    assert "Unknown" in result["reason"]


def test_known_tool_check_returns_tool_name(bridge):
    """Check result includes the tool name."""
    result = bridge.check_tool("ax_tree")
    assert result["tool"] == "ax_tree"


def test_dangerous_key_press_blocked(bridge):
    """Dangerous keyboard shortcuts are blocked."""
    for shortcut in ["cmd+q", "cmd+shift+delete", "cmd+option+esc"]:
        result = bridge.check_tool("key_press", {"keys": shortcut})
        assert not result["allowed"], f"{shortcut} should be blocked"
        assert "Blocked" in result["reason"]


def test_safe_key_press_not_blocked(bridge):
    """Normal keyboard shortcuts are not blocked by param check."""
    # The param check should pass (device_control may still deny)
    result = bridge._check_dangerous_params("key_press", {"keys": "cmd+c"})
    assert result is None  # No danger detected


def test_dangerous_url_blocked(bridge):
    """URLs with blocked patterns are denied."""
    blocked_urls = [
        "https://mybank.com/login",
        "https://accounts.google.com/signin",
        "https://example.com/oauth/callback",
    ]
    for url in blocked_urls:
        result = bridge.check_tool("open_url", {"url": url})
        assert not result["allowed"], f"{url} should be blocked"


def test_safe_url_not_blocked(bridge):
    """Normal URLs pass the param check."""
    result = bridge._check_dangerous_params("open_url", {"url": "https://github.com"})
    assert result is None


# ── Rate Limiting Tests ─────────────────────────────────────────────────

def test_rate_limit_within_bounds(bridge):
    """Calls within rate limit are allowed."""
    assert bridge._check_rate_limit() is True


def test_rate_limit_exceeded(bridge):
    """Rate limit blocks after max calls."""
    import time
    now = time.time()
    bridge._call_timestamps = [now] * RATE_LIMIT_MAX_CALLS
    assert bridge._check_rate_limit() is False


def test_rate_limit_expired_cleared(bridge):
    """Old timestamps are cleaned up."""
    import time
    old = time.time() - 120  # 2 minutes ago
    bridge._call_timestamps = [old] * 50
    assert bridge._check_rate_limit() is True
    # Old timestamps should be cleaned
    assert len(bridge._call_timestamps) == 0


# ── Tool Listing Tests ──────────────────────────────────────────────────

def test_list_tools_returns_all(bridge):
    """list_tools returns all registered tools."""
    tools = bridge.list_tools()
    assert len(tools) == len(GHOST_TOOL_REGISTRY)


def test_list_tools_has_required_fields(bridge):
    """Each tool in listing has name, description, category."""
    tools = bridge.list_tools()
    for t in tools:
        assert "name" in t
        assert "description" in t
        assert "category" in t
        assert "risk" in t
        assert "allowed" in t


# ── Audit Logging Tests ────────────────────────────────────────────────

def test_denied_action_logged(bridge, tmp_path):
    """Denied actions are logged to audit file."""
    bridge.log_path = str(tmp_path / "audit.jsonl")
    # Execute unknown tool (will be denied)
    bridge.execute_tool("fake_tool")

    with open(bridge.log_path) as f:
        lines = f.readlines()
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["event"] == "denied"
    assert entry["tool"] == "fake_tool"


def test_log_contains_timestamp(bridge, tmp_path):
    """Log entries contain ISO timestamp."""
    bridge.log_path = str(tmp_path / "audit.jsonl")
    bridge.execute_tool("unknown_tool")

    with open(bridge.log_path) as f:
        entry = json.loads(f.readline())
    assert "timestamp" in entry
    assert "T" in entry["timestamp"]  # ISO format


# ── Status Tests ────────────────────────────────────────────────────────

def test_status_has_required_fields(bridge):
    """Status includes device, tools, rate limit info."""
    status = bridge.get_status()
    assert "device" in status
    assert "tools_registered" in status
    assert "rate_limit" in status
    assert status["tools_registered"] == len(GHOST_TOOL_REGISTRY)


# ── Bridge Initialization Tests ─────────────────────────────────────────

def test_bridge_defaults():
    """Bridge initializes with correct defaults."""
    b = GhostOSBridge()
    assert b.device == "mac_mini"
    assert b.ghost_binary == "/opt/homebrew/bin/ghost"
    assert b.ssh_host == "192.168.40.232"
    assert b.ssh_user == "permanence-os"


def test_bridge_custom_config():
    """Bridge accepts custom configuration."""
    b = GhostOSBridge(
        device="test_device",
        ghost_binary="/usr/bin/ghost",
        ssh_host="10.0.0.1",
        ssh_user="testuser",
    )
    assert b.device == "test_device"
    assert b.ghost_binary == "/usr/bin/ghost"
    assert b.ssh_host == "10.0.0.1"
    assert b.ssh_user == "testuser"


def test_record_call_increments(bridge):
    """Recording a call adds to timestamps."""
    initial = len(bridge._call_timestamps)
    bridge._record_call()
    assert len(bridge._call_timestamps) == initial + 1
