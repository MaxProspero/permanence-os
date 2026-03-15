#!/usr/bin/env python3
"""
Permanence OS — Device Control & Permission Model

Governs agent access to physical devices. Two modes:

  MAC_MINI  = "full_control"   — Agent can act autonomously (within guardrails)
  MACBOOK   = "suggest_only"   — Agent can only suggest actions; human executes
  DELL      = "expansion"      — Expansion compute; task dispatch only (future)

Permission grants are:
  - Time-limited (expires after N minutes)
  - Task-limited (expires after specific task completes)
  - Scope-limited (restricted to specific action categories)
  - Revocable (human can revoke at any time)

Inspired by ghost-os (macOS accessibility + MCP tools) but with Permanence OS
governance: every action is auditable, gated, and canon-compliant.

Security model:
  - No action without explicit grant (even on full_control devices)
  - Destructive actions ALWAYS require fresh approval
  - Audit log for every action taken
  - Blocked action categories that can never be automated
  - One agent identity across all devices (single principal, restricted)

Usage:
    from core.device_control import device_controller

    # Check if an action is allowed
    result = device_controller.check_permission(
        device="mac_mini",
        action_category="app_management",
        action="install_app",
        details={"app": "discord"},
    )

    if result["allowed"]:
        # proceed
        device_controller.log_action(device="mac_mini", action="install_app", ...)
    else:
        # suggest to user
        print(result["suggestion"])

    # Grant time-limited permission
    device_controller.grant_permission(
        device="mac_mini",
        scope=["app_management", "file_operations"],
        duration_minutes=60,
        granted_by="human",
    )

    # Grant task-limited permission
    device_controller.grant_task_permission(
        device="mac_mini",
        task_id="install-chrome-extensions",
        scope=["app_management"],
        granted_by="human",
    )
"""

from __future__ import annotations

import json
import os
import threading
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from dataclasses import dataclass, field, asdict
from enum import Enum

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

DEFAULT_STATE_PATH = os.path.join(BASE_DIR, "memory", "working", "device_control_state.json")
DEFAULT_LOG_PATH = os.path.join(BASE_DIR, "logs", "device_control.jsonl")


# ── Device Modes ──────────────────────────────────────────────────────

class DeviceMode(Enum):
    """How the agent interacts with each device."""
    FULL_CONTROL = "full_control"      # Mac Mini: autonomous within guardrails
    SUGGEST_ONLY = "suggest_only"      # MacBook: suggest, never execute
    EXPANSION = "expansion"            # Dell: task dispatch only
    DISABLED = "disabled"              # Not connected / offline


# ── Action Categories ─────────────────────────────────────────────────

class ActionCategory(Enum):
    """Categories of device actions with different risk levels."""
    # Low risk — routine operations
    FILE_READ = "file_read"                    # Read files, list directories
    PROCESS_STATUS = "process_status"          # Check running processes
    SERVICE_STATUS = "service_status"          # Check service health
    SYSTEM_INFO = "system_info"               # Get system info (CPU, RAM, disk)

    # Medium risk — modifications that are reversible
    APP_MANAGEMENT = "app_management"          # Install/update/uninstall apps
    FILE_OPERATIONS = "file_operations"        # Create, move, copy files
    SERVICE_MANAGEMENT = "service_management"  # Start/stop/restart services
    NETWORK_QUERY = "network_query"            # Check network status, DNS
    AUTOMATION_RUN = "automation_run"          # Run AppleScript/Automator workflows
    CRON_MANAGEMENT = "cron_management"        # Manage launchd/cron jobs
    CLIPBOARD = "clipboard"                    # Read/write clipboard
    NOTIFICATION = "notification"              # Send system notifications

    # High risk — potentially destructive or irreversible
    FILE_DELETE = "file_delete"                # Delete files permanently
    SYSTEM_CONFIG = "system_config"            # Change system preferences
    USER_MANAGEMENT = "user_management"        # Manage user accounts
    SECURITY_CONFIG = "security_config"        # Change security settings

    # BLOCKED — never automatable, human must do manually
    NETWORK_CONFIG = "network_config"          # Change network settings
    SSH_CONFIG = "ssh_config"                  # Modify SSH access
    DISK_FORMAT = "disk_format"                # Format/partition disks
    FIRMWARE = "firmware"                      # Update firmware/BIOS
    CREDENTIAL_ACCESS = "credential_access"    # Access keychain/passwords


# Risk tiers
LOW_RISK_ACTIONS: frozenset = frozenset({
    ActionCategory.FILE_READ,
    ActionCategory.PROCESS_STATUS,
    ActionCategory.SERVICE_STATUS,
    ActionCategory.SYSTEM_INFO,
})

MEDIUM_RISK_ACTIONS: frozenset = frozenset({
    ActionCategory.APP_MANAGEMENT,
    ActionCategory.FILE_OPERATIONS,
    ActionCategory.SERVICE_MANAGEMENT,
    ActionCategory.NETWORK_QUERY,
    ActionCategory.AUTOMATION_RUN,
    ActionCategory.CRON_MANAGEMENT,
    ActionCategory.CLIPBOARD,
    ActionCategory.NOTIFICATION,
})

HIGH_RISK_ACTIONS: frozenset = frozenset({
    ActionCategory.FILE_DELETE,
    ActionCategory.SYSTEM_CONFIG,
    ActionCategory.USER_MANAGEMENT,
    ActionCategory.SECURITY_CONFIG,
})

# These can NEVER be automated — human must do manually
BLOCKED_ACTIONS: frozenset = frozenset({
    ActionCategory.NETWORK_CONFIG,
    ActionCategory.SSH_CONFIG,
    ActionCategory.DISK_FORMAT,
    ActionCategory.FIRMWARE,
    ActionCategory.CREDENTIAL_ACCESS,
})


# ── Permission Grants ─────────────────────────────────────────────────

@dataclass
class PermissionGrant:
    """A time-limited or task-limited permission grant."""
    grant_id: str
    device: str
    scope: List[str]                     # List of ActionCategory values
    granted_by: str                       # "human" or specific approver
    granted_at: str                       # ISO timestamp
    expires_at: Optional[str] = None      # ISO timestamp (time-limited)
    task_id: Optional[str] = None         # Task ID (task-limited)
    max_actions: Optional[int] = None     # Max number of actions allowed
    actions_used: int = 0                 # Actions consumed so far
    revoked: bool = False                 # Human can revoke at any time
    revoked_at: Optional[str] = None
    notes: str = ""

    def is_active(self) -> bool:
        """Check if this grant is still valid."""
        if self.revoked:
            return False
        if self.max_actions is not None and self.actions_used >= self.max_actions:
            return False
        if self.expires_at:
            try:
                exp = datetime.fromisoformat(self.expires_at)
                if exp.tzinfo is None:
                    exp = exp.replace(tzinfo=timezone.utc)
                if datetime.now(timezone.utc) > exp:
                    return False
            except (ValueError, TypeError):
                return False
        return True

    def covers_action(self, action_category: str) -> bool:
        """Check if this grant covers a specific action category."""
        return action_category in self.scope or "*" in self.scope

    def consume(self) -> None:
        """Record one action consumed against this grant."""
        self.actions_used += 1


# ── Device Config ─────────────────────────────────────────────────────

@dataclass
class DeviceConfig:
    """Configuration for a managed device."""
    device_id: str
    name: str
    mode: str                             # DeviceMode value
    host: Optional[str] = None            # IP/hostname for remote devices
    ssh_user: Optional[str] = None
    ssh_key: Optional[str] = None
    repo_path: Optional[str] = None
    capabilities: List[str] = field(default_factory=list)  # What this device can do
    auto_grant_low_risk: bool = False     # Auto-allow low-risk actions (full_control only)
    connected: bool = False
    last_seen: Optional[str] = None


# ── Default Device Configs ────────────────────────────────────────────

DEFAULT_DEVICES: Dict[str, Dict[str, Any]] = {
    "mac_mini": {
        "device_id": "mac_mini",
        "name": "Mac Mini M4",
        "mode": DeviceMode.FULL_CONTROL.value,
        "host": "192.168.40.232",
        "ssh_user": "permanence-os",
        "ssh_key": "~/.ssh/id_ed25519_mac_mini",
        "repo_path": "~/Code/permanence-os",
        "capabilities": [
            "applescript", "automator", "brew_install", "launchd",
            "ollama", "mlx", "cloudflared", "gh_cli", "python",
            "node", "git", "docker_future",
        ],
        "auto_grant_low_risk": True,
        "connected": True,
    },
    "macbook": {
        "device_id": "macbook",
        "name": "MacBook (Primary)",
        "mode": DeviceMode.SUGGEST_ONLY.value,
        "host": None,
        "capabilities": [
            "suggestion", "notification", "clipboard_read",
        ],
        "auto_grant_low_risk": False,
        "connected": True,
    },
    "dell": {
        "device_id": "dell",
        "name": "Dell (Expansion Compute)",
        "mode": DeviceMode.EXPANSION.value,
        "host": None,
        "capabilities": ["task_dispatch", "compute"],
        "auto_grant_low_risk": False,
        "connected": False,
    },
}


# ── Device Controller ─────────────────────────────────────────────────

class DeviceController:
    """
    Central controller for device access permissions.

    Enforces the permission model:
    - Mac Mini: full_control with auto-granted low-risk actions
    - MacBook: suggest_only — agent can never execute, only suggest
    - Dell: expansion — task dispatch only when connected

    All actions are audited. Blocked actions are never allowed.
    """

    def __init__(
        self,
        state_path: Optional[str] = None,
        log_path: Optional[str] = None,
    ):
        self.state_path = Path(
            state_path
            or os.getenv("PERMANENCE_DEVICE_CONTROL_STATE", DEFAULT_STATE_PATH)
        )
        self.log_path = Path(
            log_path
            or os.getenv("PERMANENCE_DEVICE_CONTROL_LOG", DEFAULT_LOG_PATH)
        )
        self._lock = threading.Lock()

        # Load or initialize state
        self.devices: Dict[str, DeviceConfig] = {}
        self.grants: Dict[str, PermissionGrant] = {}
        self._load_state()

    # ── State Management ──────────────────────────────────────────────

    def _load_state(self) -> None:
        """Load persisted state or initialize defaults."""
        if self.state_path.exists():
            try:
                data = json.loads(self.state_path.read_text(encoding="utf-8"))
                # Restore devices
                for dev_id, dev_data in data.get("devices", {}).items():
                    self.devices[dev_id] = DeviceConfig(**dev_data)
                # Restore grants
                for grant_id, grant_data in data.get("grants", {}).items():
                    self.grants[grant_id] = PermissionGrant(**grant_data)
                return
            except (json.JSONDecodeError, OSError, TypeError) as exc:
                pass  # Fall through to defaults

        # Initialize with defaults
        for dev_id, dev_data in DEFAULT_DEVICES.items():
            self.devices[dev_id] = DeviceConfig(**dev_data)

    def _save_state(self) -> None:
        """Persist state to disk."""
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "devices": {k: asdict(v) for k, v in self.devices.items()},
            "grants": {k: asdict(v) for k, v in self.grants.items()},
            "saved_at": datetime.now(timezone.utc).isoformat(),
        }
        tmp = self.state_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
        tmp.replace(self.state_path)

    # ── Permission Checks ─────────────────────────────────────────────

    def check_permission(
        self,
        device: str,
        action_category: str,
        action: str = "",
        details: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Check whether an action is permitted on a device.

        Returns:
            {
                "allowed": bool,
                "reason": str,
                "grant_id": str | None,      # Which grant authorized it
                "suggestion": str | None,     # For suggest_only mode
                "requires_approval": bool,    # Needs human approval
            }
        """
        with self._lock:
            # Device exists?
            dev = self.devices.get(device)
            if not dev:
                return {
                    "allowed": False,
                    "reason": f"Unknown device: {device}",
                    "grant_id": None,
                    "suggestion": None,
                    "requires_approval": False,
                }

            # Device connected?
            if not dev.connected:
                return {
                    "allowed": False,
                    "reason": f"Device {device} is not connected",
                    "grant_id": None,
                    "suggestion": None,
                    "requires_approval": False,
                }

            # Parse action category
            try:
                cat = ActionCategory(action_category)
            except ValueError:
                return {
                    "allowed": False,
                    "reason": f"Unknown action category: {action_category}",
                    "grant_id": None,
                    "suggestion": None,
                    "requires_approval": False,
                }

            # BLOCKED actions — never allowed on any device
            if cat in BLOCKED_ACTIONS:
                return {
                    "allowed": False,
                    "reason": f"Action category '{action_category}' is permanently blocked. "
                              f"Human must perform this action manually.",
                    "grant_id": None,
                    "suggestion": f"Please manually perform: {action}",
                    "requires_approval": False,
                }

            mode = DeviceMode(dev.mode)

            # SUGGEST_ONLY mode (MacBook) — never execute
            if mode == DeviceMode.SUGGEST_ONLY:
                suggestion = self._format_suggestion(action, action_category, details)
                return {
                    "allowed": False,
                    "reason": f"Device {device} is in suggest-only mode. "
                              f"Agent cannot execute actions on this device.",
                    "grant_id": None,
                    "suggestion": suggestion,
                    "requires_approval": False,
                }

            # DISABLED mode
            if mode == DeviceMode.DISABLED:
                return {
                    "allowed": False,
                    "reason": f"Device {device} is disabled",
                    "grant_id": None,
                    "suggestion": None,
                    "requires_approval": False,
                }

            # EXPANSION mode (Dell) — only task dispatch
            if mode == DeviceMode.EXPANSION:
                if action_category not in ("process_status", "system_info"):
                    return {
                        "allowed": False,
                        "reason": f"Device {device} only supports task dispatch",
                        "grant_id": None,
                        "suggestion": None,
                        "requires_approval": True,
                    }

            # FULL_CONTROL mode (Mac Mini)
            if mode == DeviceMode.FULL_CONTROL:
                # Low-risk auto-grant
                if cat in LOW_RISK_ACTIONS and dev.auto_grant_low_risk:
                    return {
                        "allowed": True,
                        "reason": "Low-risk action auto-granted on full_control device",
                        "grant_id": "auto_low_risk",
                        "suggestion": None,
                        "requires_approval": False,
                    }

                # High-risk always needs fresh approval
                if cat in HIGH_RISK_ACTIONS:
                    grant = self._find_active_grant(device, action_category)
                    if grant:
                        grant.consume()
                        self._save_state()
                        return {
                            "allowed": True,
                            "reason": f"High-risk action authorized by grant {grant.grant_id}",
                            "grant_id": grant.grant_id,
                            "suggestion": None,
                            "requires_approval": False,
                        }
                    return {
                        "allowed": False,
                        "reason": f"High-risk action '{action_category}' requires explicit approval",
                        "grant_id": None,
                        "suggestion": None,
                        "requires_approval": True,
                    }

                # Medium-risk — check for active grant
                if cat in MEDIUM_RISK_ACTIONS:
                    grant = self._find_active_grant(device, action_category)
                    if grant:
                        grant.consume()
                        self._save_state()
                        return {
                            "allowed": True,
                            "reason": f"Medium-risk action authorized by grant {grant.grant_id}",
                            "grant_id": grant.grant_id,
                            "suggestion": None,
                            "requires_approval": False,
                        }
                    return {
                        "allowed": False,
                        "reason": f"Medium-risk action '{action_category}' requires a permission grant",
                        "grant_id": None,
                        "suggestion": None,
                        "requires_approval": True,
                    }

            # Fallback — deny
            return {
                "allowed": False,
                "reason": "No matching permission found",
                "grant_id": None,
                "suggestion": None,
                "requires_approval": True,
            }

    def _find_active_grant(self, device: str, action_category: str) -> Optional[PermissionGrant]:
        """Find an active grant that covers this device + action."""
        for grant in self.grants.values():
            if (grant.device == device
                    and grant.is_active()
                    and grant.covers_action(action_category)):
                return grant
        return None

    def _format_suggestion(
        self,
        action: str,
        action_category: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Format a human-readable suggestion for suggest-only mode."""
        parts = [f"Suggested action: {action}"]
        if details:
            for k, v in details.items():
                parts.append(f"  {k}: {v}")
        parts.append(f"Category: {action_category}")
        parts.append("Please execute this action manually on your MacBook.")
        return "\n".join(parts)

    # ── Grant Management ──────────────────────────────────────────────

    def grant_permission(
        self,
        device: str,
        scope: List[str],
        duration_minutes: Optional[int] = None,
        max_actions: Optional[int] = None,
        granted_by: str = "human",
        notes: str = "",
    ) -> Dict[str, Any]:
        """
        Grant time-limited or action-limited permission.

        Args:
            device: Device ID
            scope: List of ActionCategory values (or ["*"] for all non-blocked)
            duration_minutes: How long the grant lasts (None = until revoked)
            max_actions: Max number of actions (None = unlimited within time)
            granted_by: Who approved this
            notes: Optional notes

        Returns:
            Grant details dict
        """
        with self._lock:
            # Validate device
            if device not in self.devices:
                return {"error": f"Unknown device: {device}"}

            dev = self.devices[device]
            if DeviceMode(dev.mode) == DeviceMode.SUGGEST_ONLY:
                return {"error": f"Cannot grant execution permissions on suggest-only device: {device}"}

            # Validate scope — filter out blocked actions
            clean_scope = []
            for s in scope:
                if s == "*":
                    clean_scope.append("*")
                    continue
                try:
                    cat = ActionCategory(s)
                    if cat in BLOCKED_ACTIONS:
                        continue  # silently skip blocked
                    clean_scope.append(s)
                except ValueError:
                    continue

            if not clean_scope:
                return {"error": "No valid action categories in scope"}

            now = datetime.now(timezone.utc)
            expires_at = None
            if duration_minutes is not None:
                expires_at = (now + timedelta(minutes=duration_minutes)).isoformat()

            grant = PermissionGrant(
                grant_id=str(uuid.uuid4())[:12],
                device=device,
                scope=clean_scope,
                granted_by=granted_by,
                granted_at=now.isoformat(),
                expires_at=expires_at,
                max_actions=max_actions,
                notes=notes,
            )
            self.grants[grant.grant_id] = grant
            self._save_state()

            self._log_event("grant_created", {
                "grant_id": grant.grant_id,
                "device": device,
                "scope": clean_scope,
                "duration_minutes": duration_minutes,
                "max_actions": max_actions,
                "granted_by": granted_by,
            })

            return asdict(grant)

    def grant_task_permission(
        self,
        device: str,
        task_id: str,
        scope: List[str],
        granted_by: str = "human",
        notes: str = "",
    ) -> Dict[str, Any]:
        """Grant permission that is bound to a specific task."""
        with self._lock:
            if device not in self.devices:
                return {"error": f"Unknown device: {device}"}

            dev = self.devices[device]
            if DeviceMode(dev.mode) == DeviceMode.SUGGEST_ONLY:
                return {"error": f"Cannot grant execution permissions on suggest-only device: {device}"}

            clean_scope = [
                s for s in scope
                if s == "*" or (
                    s in {c.value for c in ActionCategory}
                    and ActionCategory(s) not in BLOCKED_ACTIONS
                )
            ]
            if not clean_scope:
                return {"error": "No valid action categories in scope"}

            now = datetime.now(timezone.utc)
            grant = PermissionGrant(
                grant_id=str(uuid.uuid4())[:12],
                device=device,
                scope=clean_scope,
                granted_by=granted_by,
                granted_at=now.isoformat(),
                task_id=task_id,
                notes=notes,
            )
            self.grants[grant.grant_id] = grant
            self._save_state()

            self._log_event("task_grant_created", {
                "grant_id": grant.grant_id,
                "device": device,
                "task_id": task_id,
                "scope": clean_scope,
                "granted_by": granted_by,
            })

            return asdict(grant)

    def revoke_grant(self, grant_id: str, revoked_by: str = "human") -> Dict[str, Any]:
        """Revoke a permission grant immediately."""
        with self._lock:
            grant = self.grants.get(grant_id)
            if not grant:
                return {"error": f"Grant not found: {grant_id}"}

            grant.revoked = True
            grant.revoked_at = datetime.now(timezone.utc).isoformat()
            self._save_state()

            self._log_event("grant_revoked", {
                "grant_id": grant_id,
                "revoked_by": revoked_by,
            })

            return {"status": "revoked", "grant_id": grant_id}

    def complete_task_grants(self, task_id: str) -> int:
        """Revoke all grants for a completed task. Returns count revoked."""
        with self._lock:
            count = 0
            for grant in self.grants.values():
                if grant.task_id == task_id and not grant.revoked:
                    grant.revoked = True
                    grant.revoked_at = datetime.now(timezone.utc).isoformat()
                    count += 1
            if count:
                self._save_state()
                self._log_event("task_grants_completed", {
                    "task_id": task_id,
                    "grants_revoked": count,
                })
            return count

    def _revoke_all_grants_unlocked(self, device: Optional[str] = None) -> int:
        """Internal: revoke grants without acquiring lock (caller must hold lock)."""
        count = 0
        now = datetime.now(timezone.utc).isoformat()
        for grant in self.grants.values():
            if not grant.revoked:
                if device is None or grant.device == device:
                    grant.revoked = True
                    grant.revoked_at = now
                    count += 1
        if count:
            self._save_state()
            self._log_event("emergency_revoke", {
                "device": device,
                "grants_revoked": count,
            })
        return count

    def revoke_all_grants(self, device: Optional[str] = None) -> int:
        """Emergency: revoke all grants (or all for a specific device)."""
        with self._lock:
            return self._revoke_all_grants_unlocked(device)

    # ── Device Management ─────────────────────────────────────────────

    def set_device_mode(self, device: str, mode: str) -> Dict[str, Any]:
        """Change a device's operating mode."""
        with self._lock:
            dev = self.devices.get(device)
            if not dev:
                return {"error": f"Unknown device: {device}"}
            try:
                DeviceMode(mode)
            except ValueError:
                return {"error": f"Invalid mode: {mode}. Options: {[m.value for m in DeviceMode]}"}

            old_mode = dev.mode
            dev.mode = mode

            # If switching TO suggest_only, revoke all grants for this device
            if mode == DeviceMode.SUGGEST_ONLY.value and old_mode != mode:
                self._revoke_all_grants_unlocked(device)

            self._save_state()
            self._log_event("mode_changed", {
                "device": device,
                "old_mode": old_mode,
                "new_mode": mode,
            })
            return {"device": device, "old_mode": old_mode, "new_mode": mode}

    def set_device_connected(self, device: str, connected: bool) -> None:
        """Update device connectivity status."""
        with self._lock:
            dev = self.devices.get(device)
            if dev:
                dev.connected = connected
                dev.last_seen = datetime.now(timezone.utc).isoformat()
                self._save_state()

    def add_device(self, device_id: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """Register a new device."""
        with self._lock:
            if device_id in self.devices:
                return {"error": f"Device already exists: {device_id}"}
            config["device_id"] = device_id
            self.devices[device_id] = DeviceConfig(**config)
            self._save_state()
            return {"status": "added", "device_id": device_id}

    # ── Status & Reporting ────────────────────────────────────────────

    def status(self) -> Dict[str, Any]:
        """Get current status of all devices and active grants."""
        with self._lock:
            active_grants = [
                asdict(g) for g in self.grants.values() if g.is_active()
            ]
            devices = {
                dev_id: {
                    "name": dev.name,
                    "mode": dev.mode,
                    "connected": dev.connected,
                    "last_seen": dev.last_seen,
                    "auto_grant_low_risk": dev.auto_grant_low_risk,
                    "capabilities": dev.capabilities,
                }
                for dev_id, dev in self.devices.items()
            }
            return {
                "devices": devices,
                "active_grants": active_grants,
                "total_grants": len(self.grants),
                "expired_grants": len(self.grants) - len(active_grants),
            }

    def list_active_grants(self, device: Optional[str] = None) -> List[Dict[str, Any]]:
        """List all active (non-expired, non-revoked) grants."""
        with self._lock:
            grants = []
            for g in self.grants.values():
                if g.is_active():
                    if device is None or g.device == device:
                        grants.append(asdict(g))
            return grants

    # ── Action Logging ────────────────────────────────────────────────

    def log_action(
        self,
        device: str,
        action: str,
        action_category: str,
        grant_id: Optional[str] = None,
        success: bool = True,
        details: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
    ) -> None:
        """Log an executed action for audit trail."""
        self._log_event("action_executed", {
            "device": device,
            "action": action,
            "action_category": action_category,
            "grant_id": grant_id,
            "success": success,
            "details": details,
            "error": error,
        })

    def _log_event(self, event_type: str, data: Dict[str, Any]) -> None:
        """Append an event to the audit log."""
        try:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            entry = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "event": event_type,
                **data,
            }
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, default=str) + "\n")
        except OSError:
            pass

    # ── Cleanup ───────────────────────────────────────────────────────

    def cleanup_expired_grants(self) -> int:
        """Remove expired/revoked grants from state. Returns count removed."""
        with self._lock:
            expired_ids = [
                gid for gid, g in self.grants.items()
                if not g.is_active()
            ]
            for gid in expired_ids:
                del self.grants[gid]
            if expired_ids:
                self._save_state()
            return len(expired_ids)


# ── Module-level singleton ────────────────────────────────────────────

device_controller = DeviceController()
