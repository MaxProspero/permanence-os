#!/usr/bin/env python3
"""
Permanence OS — Ghost OS MCP Bridge

Routes ghost-os MCP tools through the device_control permission model.
Ghost-os provides 22 macOS automation tools via MCP; this bridge ensures
every tool call is:
  1. Permission-checked against the device_control model
  2. Audit-logged
  3. Rate-limited
  4. Blocked if the action category is forbidden

Architecture:
  Agent → ghost_os_bridge.execute_tool() → device_control.check_permission()
       → if allowed → SSH to Mac Mini → ghost mcp tool call
       → audit log entry

Ghost-os tool categories mapped to device_control ActionCategory:
  - Perception (ax_tree, screenshot, find_element) → SYSTEM_INFO (low risk)
  - Interaction (click, type, key_press, scroll) → AUTOMATION_RUN (medium risk)
  - Window mgmt (list_windows, focus_app, resize) → AUTOMATION_RUN (medium risk)
  - File ops (open_file, save_file) → FILE_OPERATIONS (medium risk)
  - Clipboard (get_clipboard, set_clipboard) → CLIPBOARD (medium risk)
  - Recipes (run_recipe) → AUTOMATION_RUN (medium risk)
  - Vision (ghost_ground) → SYSTEM_INFO (low risk)

Usage:
    from scripts.ghost_os_bridge import GhostOSBridge

    bridge = GhostOSBridge()

    # Check if a tool is allowed
    result = bridge.check_tool("click", params={"x": 100, "y": 200})

    # Execute a tool (with permission check)
    result = bridge.execute_tool("ax_tree", params={"app": "Safari"})

    # List available tools
    tools = bridge.list_tools()

CLI:
    python scripts/ghost_os_bridge.py --action list-tools
    python scripts/ghost_os_bridge.py --action check --tool click
    python scripts/ghost_os_bridge.py --action execute --tool ax_tree --params '{"app": "Safari"}'
    python scripts/ghost_os_bridge.py --action status
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, BASE_DIR)

try:
    from core.device_control import (
        device_controller,
        ActionCategory,
        DeviceMode,
    )
except ImportError:
    device_controller = None
    ActionCategory = None
    DeviceMode = None

# ── Ghost-OS Tool Registry ─────────────────────────────────────────────

# Maps ghost-os MCP tool names → device_control ActionCategory + metadata
GHOST_TOOL_REGISTRY: dict[str, dict[str, Any]] = {
    # Perception tools (low risk)
    "ax_tree": {
        "category": "system_info",
        "description": "Read accessibility tree for an app",
        "risk": "low",
        "requires_accessibility": True,
    },
    "screenshot": {
        "category": "system_info",
        "description": "Take screenshot of screen or window",
        "risk": "low",
        "requires_screen_recording": True,
    },
    "find_element": {
        "category": "system_info",
        "description": "Find UI element by description",
        "risk": "low",
        "requires_accessibility": True,
    },
    "get_element_text": {
        "category": "system_info",
        "description": "Get text content of UI element",
        "risk": "low",
        "requires_accessibility": True,
    },
    "ghost_ground": {
        "category": "system_info",
        "description": "Visual element grounding via ShowUI-2B",
        "risk": "low",
        "requires_vision": True,
    },

    # Interaction tools (medium risk)
    "click": {
        "category": "automation_run",
        "description": "Click at coordinates or element",
        "risk": "medium",
        "requires_accessibility": True,
    },
    "type_text": {
        "category": "automation_run",
        "description": "Type text into focused element",
        "risk": "medium",
        "requires_accessibility": True,
    },
    "key_press": {
        "category": "automation_run",
        "description": "Press keyboard shortcut",
        "risk": "medium",
        "requires_accessibility": True,
        "dangerous_keys": ["cmd+q", "cmd+shift+delete", "cmd+option+esc"],
    },
    "scroll": {
        "category": "automation_run",
        "description": "Scroll in window",
        "risk": "medium",
        "requires_accessibility": True,
    },
    "drag": {
        "category": "automation_run",
        "description": "Drag from one point to another",
        "risk": "medium",
        "requires_accessibility": True,
    },

    # Window management (medium risk)
    "list_windows": {
        "category": "system_info",
        "description": "List all open windows",
        "risk": "low",
        "requires_accessibility": True,
    },
    "focus_app": {
        "category": "automation_run",
        "description": "Bring app to foreground",
        "risk": "medium",
        "requires_accessibility": True,
    },
    "resize_window": {
        "category": "automation_run",
        "description": "Resize a window",
        "risk": "medium",
        "requires_accessibility": True,
    },
    "move_window": {
        "category": "automation_run",
        "description": "Move a window",
        "risk": "medium",
        "requires_accessibility": True,
    },

    # File operations (medium risk)
    "open_file": {
        "category": "file_operations",
        "description": "Open file with default app",
        "risk": "medium",
    },
    "open_url": {
        "category": "automation_run",
        "description": "Open URL in browser",
        "risk": "medium",
        "blocked_domains": ["*.bank.*", "*.login.*", "accounts.google.com"],
    },

    # Clipboard (medium risk)
    "get_clipboard": {
        "category": "clipboard",
        "description": "Read clipboard content",
        "risk": "medium",
    },
    "set_clipboard": {
        "category": "clipboard",
        "description": "Write to clipboard",
        "risk": "medium",
    },

    # Recipes (medium risk — pre-defined workflows)
    "run_recipe": {
        "category": "automation_run",
        "description": "Execute a ghost-os recipe",
        "risk": "medium",
        "requires_accessibility": True,
    },
}

# Ghost-os tools that should NEVER be executed without human present
DANGEROUS_TOOL_PARAMS = {
    "key_press": {
        "blocked_shortcuts": [
            "cmd+q",           # Quit app
            "cmd+shift+delete",  # Empty trash
            "cmd+option+esc",  # Force quit
            "cmd+shift+q",    # Log out
        ],
    },
    "open_url": {
        "blocked_patterns": [
            "bank",
            "login",
            "signin",
            "accounts.google",
            "oauth",
            "password",
        ],
    },
}

# Rate limiting
RATE_LIMIT_WINDOW = 60  # seconds
RATE_LIMIT_MAX_CALLS = 30  # max calls per window


class GhostOSBridge:
    """Bridge between Permanence OS agents and ghost-os MCP tools."""

    def __init__(
        self,
        device: str = "mac_mini",
        ghost_binary: str = "/opt/homebrew/bin/ghost",
        ssh_host: str = "192.168.40.232",
        ssh_user: str = "permanence-os",
        ssh_key: str = "~/.ssh/id_ed25519_mac_mini",
        log_path: Optional[str] = None,
    ):
        self.device = device
        self.ghost_binary = ghost_binary
        self.ssh_host = ssh_host
        self.ssh_user = ssh_user
        self.ssh_key = os.path.expanduser(ssh_key)
        self.log_path = log_path or os.path.join(BASE_DIR, "logs", "ghost_os_bridge.jsonl")

        # Rate limiting state
        self._call_timestamps: list[float] = []

        # Capabilities detected on init
        self._capabilities: dict[str, bool] = {}

    # ── Permission Checking ──────────────────────────────────────────

    def check_tool(
        self,
        tool_name: str,
        params: Optional[dict[str, Any]] = None,
        agent_id: str = "ghost_bridge",
    ) -> dict[str, Any]:
        """Check if a ghost-os tool call is permitted."""
        # Unknown tool
        if tool_name not in GHOST_TOOL_REGISTRY:
            return {
                "allowed": False,
                "reason": f"Unknown ghost-os tool: {tool_name}",
                "tool": tool_name,
            }

        tool_info = GHOST_TOOL_REGISTRY[tool_name]
        category = tool_info["category"]

        # Check dangerous params
        danger_check = self._check_dangerous_params(tool_name, params or {})
        if danger_check:
            return {
                "allowed": False,
                "reason": danger_check,
                "tool": tool_name,
            }

        # Rate limit check
        if not self._check_rate_limit():
            return {
                "allowed": False,
                "reason": f"Rate limit exceeded ({RATE_LIMIT_MAX_CALLS} calls per {RATE_LIMIT_WINDOW}s)",
                "tool": tool_name,
            }

        # Device control permission check
        if device_controller is not None:
            result = device_controller.check_permission(
                device=self.device,
                action_category=category,
                action=f"ghost_{tool_name}",
                details={
                    "tool": tool_name,
                    "params": params or {},
                    "agent_id": agent_id,
                    "risk": tool_info.get("risk", "medium"),
                },
            )
            return {
                **result,
                "tool": tool_name,
                "category": category,
                "risk": tool_info.get("risk", "medium"),
            }

        # No device_controller available — deny by default
        return {
            "allowed": False,
            "reason": "device_controller not available",
            "tool": tool_name,
        }

    def _check_dangerous_params(self, tool_name: str, params: dict[str, Any]) -> Optional[str]:
        """Check if tool params contain dangerous values."""
        danger = DANGEROUS_TOOL_PARAMS.get(tool_name)
        if not danger:
            return None

        if tool_name == "key_press":
            shortcut = str(params.get("keys", params.get("shortcut", ""))).lower()
            for blocked in danger.get("blocked_shortcuts", []):
                if shortcut == blocked.lower():
                    return f"Blocked keyboard shortcut: {shortcut}"

        if tool_name == "open_url":
            url = str(params.get("url", "")).lower()
            for pattern in danger.get("blocked_patterns", []):
                if pattern in url:
                    return f"URL contains blocked pattern: {pattern}"

        return None

    def _check_rate_limit(self) -> bool:
        """Check rate limit. Returns True if within limit."""
        now = time.time()
        # Clean old timestamps
        self._call_timestamps = [
            t for t in self._call_timestamps
            if now - t < RATE_LIMIT_WINDOW
        ]
        return len(self._call_timestamps) < RATE_LIMIT_MAX_CALLS

    def _record_call(self) -> None:
        """Record a tool call for rate limiting."""
        self._call_timestamps.append(time.time())

    # ── Tool Execution ───────────────────────────────────────────────

    def execute_tool(
        self,
        tool_name: str,
        params: Optional[dict[str, Any]] = None,
        agent_id: str = "ghost_bridge",
    ) -> dict[str, Any]:
        """Execute a ghost-os tool with full permission + audit chain."""
        # 1. Permission check
        check = self.check_tool(tool_name, params, agent_id)
        if not check.get("allowed"):
            self._log_event("denied", tool_name, params, check)
            return check

        # 2. Execute via SSH
        try:
            result = self._run_ghost_tool(tool_name, params or {})
        except Exception as e:
            error_result = {
                "ok": False,
                "error": str(e),
                "tool": tool_name,
            }
            self._log_event("error", tool_name, params, error_result)
            return error_result

        # 3. Record for rate limiting
        self._record_call()

        # 4. Audit log
        self._log_event("executed", tool_name, params, result)

        return result

    def _run_ghost_tool(self, tool_name: str, params: dict[str, Any]) -> dict[str, Any]:
        """Execute ghost-os tool on Mac Mini via SSH."""
        # Build ghost MCP command
        # ghost-os MCP tools are invoked via: ghost mcp --tool <name> --params '<json>'
        params_json = json.dumps(params)
        cmd = [
            "ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10",
            "-i", self.ssh_key,
            f"{self.ssh_user}@{self.ssh_host}",
            f"{self.ghost_binary} mcp --tool {tool_name} --params '{params_json}'",
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
            )
        except subprocess.TimeoutExpired:
            return {"ok": False, "error": "SSH command timed out (30s)"}

        if result.returncode != 0:
            return {
                "ok": False,
                "error": result.stderr.strip() or f"ghost tool returned exit code {result.returncode}",
                "stdout": result.stdout.strip(),
            }

        # Try to parse JSON output
        stdout = result.stdout.strip()
        try:
            parsed = json.loads(stdout)
            return {"ok": True, "data": parsed, "tool": tool_name}
        except json.JSONDecodeError:
            return {"ok": True, "data": stdout, "tool": tool_name}

    # ── Tool Discovery ───────────────────────────────────────────────

    def list_tools(self) -> list[dict[str, Any]]:
        """List all available ghost-os tools with their permission status."""
        tools = []
        for name, info in GHOST_TOOL_REGISTRY.items():
            check = self.check_tool(name)
            tools.append({
                "name": name,
                "description": info["description"],
                "category": info["category"],
                "risk": info.get("risk", "medium"),
                "allowed": check.get("allowed", False),
                "reason": check.get("reason", ""),
                "requires_accessibility": info.get("requires_accessibility", False),
                "requires_screen_recording": info.get("requires_screen_recording", False),
                "requires_vision": info.get("requires_vision", False),
            })
        return tools

    def get_status(self) -> dict[str, Any]:
        """Get bridge status including ghost-os health."""
        status = {
            "device": self.device,
            "ghost_binary": self.ghost_binary,
            "ssh_host": self.ssh_host,
            "tools_registered": len(GHOST_TOOL_REGISTRY),
            "rate_limit": {
                "window_seconds": RATE_LIMIT_WINDOW,
                "max_calls": RATE_LIMIT_MAX_CALLS,
                "current_calls": len(self._call_timestamps),
            },
        }

        # Check ghost-os availability on Mac Mini
        try:
            check_cmd = [
                "ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=5",
                "-i", self.ssh_key,
                f"{self.ssh_user}@{self.ssh_host}",
                f"{self.ghost_binary} --version 2>/dev/null || echo UNAVAILABLE",
            ]
            result = subprocess.run(check_cmd, capture_output=True, text=True, timeout=10)
            version = result.stdout.strip()
            status["ghost_version"] = version
            status["ghost_available"] = "UNAVAILABLE" not in version
        except Exception as e:
            status["ghost_version"] = None
            status["ghost_available"] = False
            status["ghost_error"] = str(e)

        # Device mode
        if device_controller is not None:
            devices = device_controller.status()
            mini = devices.get("devices", {}).get(self.device, {})
            status["device_mode"] = mini.get("mode", "unknown")
            status["device_connected"] = mini.get("connected", False)
        else:
            status["device_mode"] = "unknown"
            status["device_connected"] = False

        return status

    # ── Logging ──────────────────────────────────────────────────────

    def _log_event(
        self,
        event_type: str,
        tool_name: str,
        params: Optional[dict[str, Any]],
        result: dict[str, Any],
    ) -> None:
        """Log a bridge event to the audit log."""
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event": event_type,
            "tool": tool_name,
            "device": self.device,
            "params": params,
            "result_ok": result.get("ok", result.get("allowed")),
            "result_summary": result.get("reason", result.get("error", "ok")),
        }
        try:
            os.makedirs(os.path.dirname(self.log_path), exist_ok=True)
            with open(self.log_path, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except OSError:
            pass


# ── Module-level singleton ───────────────────────────────────────────

ghost_bridge = GhostOSBridge()


# ── CLI ──────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Permanence OS — Ghost OS MCP Bridge",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--action",
        choices=["list-tools", "check", "execute", "status"],
        required=True,
    )
    parser.add_argument("--tool", help="Ghost-os tool name")
    parser.add_argument("--params", default="{}", help="Tool params as JSON string")
    parser.add_argument("--agent", default="cli", help="Agent ID")
    args = parser.parse_args()

    bridge = GhostOSBridge()

    if args.action == "list-tools":
        tools = bridge.list_tools()
        print(f"Ghost-OS Tools ({len(tools)} registered):\n")
        for t in tools:
            status = "✓" if t["allowed"] else "✗"
            risk_tag = {"low": "🟢", "medium": "🟡", "high": "🔴"}.get(t["risk"], "⚪")
            print(f"  {status} {risk_tag} {t['name']:<20} {t['description']}")
            if not t["allowed"]:
                print(f"      reason: {t['reason']}")
        return 0

    if args.action == "check":
        if not args.tool:
            print("--tool is required for check action")
            return 2
        params = json.loads(args.params) if args.params != "{}" else {}
        result = bridge.check_tool(args.tool, params, args.agent)
        print(json.dumps(result, indent=2))
        return 0 if result.get("allowed") else 1

    if args.action == "execute":
        if not args.tool:
            print("--tool is required for execute action")
            return 2
        params = json.loads(args.params) if args.params != "{}" else {}
        result = bridge.execute_tool(args.tool, params, args.agent)
        print(json.dumps(result, indent=2, default=str))
        return 0 if result.get("ok") or result.get("allowed") else 1

    if args.action == "status":
        status = bridge.get_status()
        print(json.dumps(status, indent=2, default=str))
        return 0

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
