#!/usr/bin/env python3
"""
Permanence OS — Mac Control Bridge

System automation layer for Mac Mini. Provides governed access to:
- App management (Homebrew install/uninstall/update)
- Service management (launchd start/stop/restart)
- File operations (safe create/move/copy)
- AppleScript execution (UI automation)
- System info (CPU, RAM, disk, network status)
- Notification sending
- Clipboard read/write

Every action goes through the DeviceController permission model.
Actions on Mac Mini are executed via SSH; local actions are direct.

Inspired by ghost-os (accessibility tree + MCP) but implemented as a
Python bridge with SSH and AppleScript, governed by Polemarch.

Usage:
    python scripts/mac_control.py status           # System overview
    python scripts/mac_control.py install <app>     # Brew install (with permission)
    python scripts/mac_control.py notify <msg>      # Send notification
    python scripts/mac_control.py run-apple <file>  # Run AppleScript
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, BASE_DIR)

# Import device controller for permission checks
from core.device_control import device_controller, ActionCategory, DeviceMode, BLOCKED_ACTIONS


# ── SSH Configuration ─────────────────────────────────────────────────

DEFAULT_MAC_MINI_CONFIG = {
    "host": "192.168.40.232",
    "user": "permanence-os",
    "key_path": os.path.expanduser("~/.ssh/id_ed25519_mac_mini"),
    "brew_path": "/opt/homebrew/bin/brew",
}

# ── Safety: blocked AppleScript patterns ──────────────────────────────

BLOCKED_APPLESCRIPT_PATTERNS = [
    r"do shell script.*rm\s+-rf",
    r"do shell script.*shutdown",
    r"do shell script.*halt",
    r"do shell script.*passwd",
    r"do shell script.*networksetup",
    r"System Preferences.*Network",
    r"System Preferences.*Security",
    r"System Settings.*Network",
    r"System Settings.*Privacy",
    r"delete\s+every\s+",              # Bulk delete operations
    r"keystroke.*password",            # Typing passwords
]

# ── Safe app list (pre-approved for installation) ─────────────────────

SAFE_BREW_CASKS = frozenset({
    "google-chrome", "firefox", "visual-studio-code", "discord",
    "slack", "telegram", "whatsapp", "signal", "zoom",
    "obsidian", "notion", "figma", "chatgpt", "cursor",
    "tailscale", "nordvpn", "docker", "iterm2", "warp",
    "arc", "1password", "raycast", "rectangle", "karabiner-elements",
    "perplexity",
})

SAFE_BREW_FORMULAE = frozenset({
    "gh", "jq", "ripgrep", "fd", "bat", "eza", "fzf", "tmux",
    "htop", "wget", "curl", "git", "node", "python", "python@3.12",
    "cloudflared", "ffmpeg", "imagemagick", "sqlite", "redis",
    "ollama", "tree", "rsync",
})


def _is_remote() -> bool:
    """Check if we're running on the MacBook (remote to Mac Mini)."""
    import socket
    hostname = socket.gethostname().lower()
    # Mac Mini hostname check
    return "mac-mini" not in hostname and "permanence" not in hostname


def _ssh_command(cmd: str, config: Optional[Dict] = None) -> Tuple[int, str, str]:
    """Execute a command on Mac Mini via SSH."""
    cfg = config or DEFAULT_MAC_MINI_CONFIG
    ssh_cmd = [
        "ssh",
        "-o", "BatchMode=yes",
        "-o", "ConnectTimeout=10",
        "-o", "StrictHostKeyChecking=accept-new",
    ]
    key_path = os.path.expanduser(cfg["key_path"])
    if os.path.exists(key_path):
        ssh_cmd.extend(["-i", key_path])
    ssh_cmd.append(f"{cfg['user']}@{cfg['host']}")
    ssh_cmd.append(cmd)

    try:
        result = subprocess.run(
            ssh_cmd,
            capture_output=True,
            text=True,
            timeout=120,
        )
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except subprocess.TimeoutExpired:
        return -1, "", "SSH command timed out"
    except OSError as e:
        return -1, "", str(e)


def _local_command(cmd: str) -> Tuple[int, str, str]:
    """Execute a command locally."""
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=120,
        )
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except subprocess.TimeoutExpired:
        return -1, "", "Command timed out"
    except OSError as e:
        return -1, "", str(e)


def _run_on_mini(cmd: str) -> Tuple[int, str, str]:
    """Run command — SSH if remote, local if on Mini."""
    if _is_remote():
        return _ssh_command(cmd)
    return _local_command(cmd)


# ── System Info ───────────────────────────────────────────────────────

def get_system_info() -> Dict[str, Any]:
    """Get Mac Mini system information (low-risk, auto-granted)."""
    perm = device_controller.check_permission(
        device="mac_mini",
        action_category=ActionCategory.SYSTEM_INFO.value,
        action="get_system_info",
    )
    if not perm["allowed"]:
        return {"error": perm["reason"]}

    info: Dict[str, Any] = {}

    # CPU info
    rc, out, _ = _run_on_mini("sysctl -n hw.ncpu")
    if rc == 0:
        info["cpu_cores"] = int(out.strip())

    # Memory
    rc, out, _ = _run_on_mini("sysctl -n hw.memsize")
    if rc == 0:
        info["memory_gb"] = round(int(out.strip()) / (1024**3), 1)

    # Disk
    rc, out, _ = _run_on_mini("df -h / | tail -1")
    if rc == 0:
        parts = out.split()
        if len(parts) >= 5:
            info["disk_total"] = parts[1]
            info["disk_used"] = parts[2]
            info["disk_available"] = parts[3]
            info["disk_used_pct"] = parts[4]

    # macOS version
    rc, out, _ = _run_on_mini("sw_vers -productVersion")
    if rc == 0:
        info["macos_version"] = out.strip()

    # Hostname
    rc, out, _ = _run_on_mini("hostname")
    if rc == 0:
        info["hostname"] = out.strip()

    # Uptime
    rc, out, _ = _run_on_mini("uptime")
    if rc == 0:
        info["uptime"] = out.strip()

    # Ollama status
    rc, out, _ = _run_on_mini("curl -s http://localhost:11434/api/tags 2>/dev/null | head -1")
    info["ollama_running"] = rc == 0 and "models" in out

    device_controller.log_action(
        device="mac_mini",
        action="get_system_info",
        action_category=ActionCategory.SYSTEM_INFO.value,
        grant_id="auto_low_risk",
        success=True,
        details=info,
    )
    return info


def get_service_status() -> Dict[str, Any]:
    """Check Permanence OS service status."""
    perm = device_controller.check_permission(
        device="mac_mini",
        action_category=ActionCategory.SERVICE_STATUS.value,
        action="get_service_status",
    )
    if not perm["allowed"]:
        return {"error": perm["reason"]}

    services = [
        "com.permanence.command-center",
        "com.permanence.foundation-site",
        "com.permanence.foundation-api",
        "com.permanence.git-sync",
    ]

    status = {}
    for svc in services:
        rc, out, err = _run_on_mini(f"launchctl list | grep {svc}")
        if rc == 0 and out:
            parts = out.split()
            pid = parts[0] if parts else "-"
            exit_code = parts[1] if len(parts) > 1 else "-"
            status[svc] = {
                "running": pid != "-" and pid != "0",
                "pid": pid,
                "last_exit": exit_code,
            }
        else:
            status[svc] = {"running": False, "pid": "-", "last_exit": "-"}

    device_controller.log_action(
        device="mac_mini",
        action="get_service_status",
        action_category=ActionCategory.SERVICE_STATUS.value,
        grant_id="auto_low_risk",
        success=True,
    )
    return status


# ── App Management ────────────────────────────────────────────────────

def install_app(app_name: str, is_cask: bool = True) -> Dict[str, Any]:
    """Install an app via Homebrew (requires medium-risk permission)."""
    perm = device_controller.check_permission(
        device="mac_mini",
        action_category=ActionCategory.APP_MANAGEMENT.value,
        action=f"install_app:{app_name}",
        details={"app": app_name, "type": "cask" if is_cask else "formula"},
    )
    if not perm["allowed"]:
        return {"error": perm["reason"], "requires_approval": perm.get("requires_approval")}

    # Validate against safe lists
    safe_list = SAFE_BREW_CASKS if is_cask else SAFE_BREW_FORMULAE
    if app_name not in safe_list:
        return {
            "error": f"App '{app_name}' is not in the pre-approved safe list. "
                     f"Approved {'casks' if is_cask else 'formulae'}: {sorted(safe_list)}",
        }

    brew = DEFAULT_MAC_MINI_CONFIG["brew_path"]
    install_type = "--cask" if is_cask else ""
    cmd = f"{brew} install {install_type} {shlex.quote(app_name)} 2>&1"

    rc, out, err = _run_on_mini(cmd)
    success = rc == 0

    device_controller.log_action(
        device="mac_mini",
        action=f"install_app:{app_name}",
        action_category=ActionCategory.APP_MANAGEMENT.value,
        grant_id=perm.get("grant_id"),
        success=success,
        details={"output": out[:500], "type": "cask" if is_cask else "formula"},
        error=err[:300] if not success else None,
    )

    return {
        "success": success,
        "app": app_name,
        "output": out[:500],
        "error": err[:300] if not success else None,
    }


def list_installed_apps() -> Dict[str, Any]:
    """List installed Homebrew apps."""
    perm = device_controller.check_permission(
        device="mac_mini",
        action_category=ActionCategory.SYSTEM_INFO.value,
        action="list_installed_apps",
    )
    if not perm["allowed"]:
        return {"error": perm["reason"]}

    brew = DEFAULT_MAC_MINI_CONFIG["brew_path"]

    casks, formulae = [], []
    rc, out, _ = _run_on_mini(f"{brew} list --cask 2>/dev/null")
    if rc == 0:
        casks = [c.strip() for c in out.split("\n") if c.strip()]

    rc, out, _ = _run_on_mini(f"{brew} list --formula 2>/dev/null")
    if rc == 0:
        formulae = [f.strip() for f in out.split("\n") if f.strip()]

    return {"casks": casks, "formulae": formulae}


def update_app(app_name: str) -> Dict[str, Any]:
    """Update a specific app via Homebrew."""
    perm = device_controller.check_permission(
        device="mac_mini",
        action_category=ActionCategory.APP_MANAGEMENT.value,
        action=f"update_app:{app_name}",
        details={"app": app_name},
    )
    if not perm["allowed"]:
        return {"error": perm["reason"], "requires_approval": perm.get("requires_approval")}

    brew = DEFAULT_MAC_MINI_CONFIG["brew_path"]
    rc, out, err = _run_on_mini(f"{brew} upgrade {shlex.quote(app_name)} 2>&1")

    return {
        "success": rc == 0,
        "app": app_name,
        "output": out[:500],
        "error": err[:300] if rc != 0 else None,
    }


# ── Service Management ────────────────────────────────────────────────

def restart_service(service_name: str) -> Dict[str, Any]:
    """Restart a Permanence OS service."""
    perm = device_controller.check_permission(
        device="mac_mini",
        action_category=ActionCategory.SERVICE_MANAGEMENT.value,
        action=f"restart_service:{service_name}",
        details={"service": service_name},
    )
    if not perm["allowed"]:
        return {"error": perm["reason"], "requires_approval": perm.get("requires_approval")}

    # Only allow restarting Permanence services
    allowed_prefixes = ("com.permanence.",)
    if not any(service_name.startswith(p) for p in allowed_prefixes):
        return {"error": f"Can only restart Permanence services (com.permanence.*), got: {service_name}"}

    plist_path = f"~/Library/LaunchAgents/{service_name}.plist"
    rc_stop, _, err_stop = _run_on_mini(f"launchctl unload {plist_path} 2>&1")
    rc_start, _, err_start = _run_on_mini(f"launchctl load {plist_path} 2>&1")

    success = rc_start == 0
    device_controller.log_action(
        device="mac_mini",
        action=f"restart_service:{service_name}",
        action_category=ActionCategory.SERVICE_MANAGEMENT.value,
        grant_id=perm.get("grant_id"),
        success=success,
        details={"service": service_name},
    )

    return {
        "success": success,
        "service": service_name,
        "stop_error": err_stop if rc_stop != 0 else None,
        "start_error": err_start if rc_start != 0 else None,
    }


# ── AppleScript Execution ────────────────────────────────────────────

def run_applescript(script: str) -> Dict[str, Any]:
    """
    Execute an AppleScript on Mac Mini.

    The script is validated against blocked patterns before execution.
    Requires AUTOMATION_RUN permission.
    """
    perm = device_controller.check_permission(
        device="mac_mini",
        action_category=ActionCategory.AUTOMATION_RUN.value,
        action="run_applescript",
        details={"script_length": len(script)},
    )
    if not perm["allowed"]:
        return {"error": perm["reason"], "requires_approval": perm.get("requires_approval")}

    # Validate script against blocked patterns
    for pattern in BLOCKED_APPLESCRIPT_PATTERNS:
        if re.search(pattern, script, re.IGNORECASE):
            return {
                "error": f"AppleScript blocked: contains dangerous pattern matching '{pattern}'",
                "blocked": True,
            }

    # Escape and run
    escaped = script.replace("'", "'\\''")
    cmd = f"osascript -e '{escaped}' 2>&1"
    rc, out, err = _run_on_mini(cmd)

    success = rc == 0
    device_controller.log_action(
        device="mac_mini",
        action="run_applescript",
        action_category=ActionCategory.AUTOMATION_RUN.value,
        grant_id=perm.get("grant_id"),
        success=success,
        details={"script_preview": script[:200], "output": out[:300]},
        error=err[:300] if not success else None,
    )

    return {
        "success": success,
        "output": out[:1000],
        "error": err[:300] if not success else None,
    }


def send_notification(title: str, message: str) -> Dict[str, Any]:
    """Send a macOS notification on Mac Mini."""
    perm = device_controller.check_permission(
        device="mac_mini",
        action_category=ActionCategory.NOTIFICATION.value,
        action="send_notification",
        details={"title": title},
    )
    if not perm["allowed"]:
        return {"error": perm["reason"], "requires_approval": perm.get("requires_approval")}

    # Use osascript to send notification
    safe_title = title.replace('"', '\\"')
    safe_msg = message.replace('"', '\\"')
    script = f'display notification "{safe_msg}" with title "{safe_title}"'

    escaped = script.replace("'", "'\\''")
    rc, out, err = _run_on_mini(f"osascript -e '{escaped}' 2>&1")

    return {"success": rc == 0, "error": err if rc != 0 else None}


# ── File Operations ───────────────────────────────────────────────────

def list_directory(path: str) -> Dict[str, Any]:
    """List directory contents on Mac Mini."""
    perm = device_controller.check_permission(
        device="mac_mini",
        action_category=ActionCategory.FILE_READ.value,
        action=f"list_dir:{path}",
    )
    if not perm["allowed"]:
        return {"error": perm["reason"]}

    rc, out, err = _run_on_mini(f"ls -la {shlex.quote(path)} 2>&1")
    return {"success": rc == 0, "contents": out, "error": err if rc != 0 else None}


def read_file(path: str, max_lines: int = 200) -> Dict[str, Any]:
    """Read a file on Mac Mini (first N lines)."""
    perm = device_controller.check_permission(
        device="mac_mini",
        action_category=ActionCategory.FILE_READ.value,
        action=f"read_file:{path}",
    )
    if not perm["allowed"]:
        return {"error": perm["reason"]}

    rc, out, err = _run_on_mini(f"head -n {max_lines} {shlex.quote(path)} 2>&1")
    return {"success": rc == 0, "content": out, "error": err if rc != 0 else None}


# ── MacBook Suggestion Mode ──────────────────────────────────────────

def suggest_action(action: str, details: Optional[Dict[str, Any]] = None) -> Dict[str, str]:
    """
    For MacBook (suggest_only mode): format a suggestion for the human.

    The agent NEVER executes on the MacBook, only suggests.
    """
    perm = device_controller.check_permission(
        device="macbook",
        action_category="app_management",
        action=action,
        details=details,
    )
    # Always returns not-allowed for macbook, but includes suggestion
    return {
        "mode": "suggest_only",
        "suggestion": perm.get("suggestion", f"Suggested action: {action}"),
        "reason": perm.get("reason", "MacBook is in suggest-only mode"),
    }


# ── CLI ───────────────────────────────────────────────────────────────

def _cli_status(args: argparse.Namespace) -> None:
    """Show device controller status and system info."""
    status = device_controller.status()
    print("\n═══ Device Control Status ═══\n")

    for dev_id, dev_info in status["devices"].items():
        mode_icon = {
            "full_control": "🟢",
            "suggest_only": "🟡",
            "expansion": "🔵",
            "disabled": "⚫",
        }.get(dev_info["mode"], "❓")
        conn = "✓ connected" if dev_info["connected"] else "✗ disconnected"
        print(f"  {mode_icon} {dev_info['name']} ({dev_id})")
        print(f"     Mode: {dev_info['mode']}  |  {conn}")
        if dev_info.get("capabilities"):
            print(f"     Capabilities: {', '.join(dev_info['capabilities'][:6])}...")
        print()

    grants = status["active_grants"]
    if grants:
        print(f"  Active Grants: {len(grants)}")
        for g in grants[:5]:
            print(f"    • {g['grant_id']}: {g['device']} [{', '.join(g['scope'][:3])}] "
                  f"by {g['granted_by']}")
    else:
        print("  Active Grants: 0")

    print()

    # System info (if Mac Mini is connected)
    if status["devices"].get("mac_mini", {}).get("connected"):
        info = get_system_info()
        if "error" not in info:
            print("═══ Mac Mini System Info ═══\n")
            for k, v in info.items():
                print(f"  {k}: {v}")
            print()


def _cli_services(args: argparse.Namespace) -> None:
    """Show service status."""
    status = get_service_status()
    if "error" in status:
        print(f"Error: {status['error']}")
        return

    print("\n═══ Services ═══\n")
    for svc, info in status.items():
        icon = "🟢" if info["running"] else "🔴"
        print(f"  {icon} {svc}  (PID: {info['pid']}, exit: {info['last_exit']})")
    print()


def _cli_install(args: argparse.Namespace) -> None:
    """Install an app via Homebrew."""
    result = install_app(args.app, is_cask=not args.formula)
    if result.get("error"):
        print(f"Error: {result['error']}")
        if result.get("requires_approval"):
            print("\nTo grant permission:")
            print(f'  python cli.py device grant mac_mini --scope app_management --duration 60')
    else:
        status = "✓ Installed" if result["success"] else "✗ Failed"
        print(f"{status}: {result['app']}")
        if result.get("output"):
            print(result["output"][:500])


def _cli_notify(args: argparse.Namespace) -> None:
    """Send a notification."""
    result = send_notification(args.title, args.message)
    if result.get("error"):
        print(f"Error: {result['error']}")
    else:
        print("✓ Notification sent")


def _cli_grant(args: argparse.Namespace) -> None:
    """Grant permission interactively."""
    result = device_controller.grant_permission(
        device=args.device,
        scope=args.scope.split(","),
        duration_minutes=args.duration,
        max_actions=args.max_actions,
        granted_by="human_cli",
        notes=args.notes or "",
    )
    if result.get("error"):
        print(f"Error: {result['error']}")
    else:
        print(f"✓ Grant created: {result['grant_id']}")
        print(f"  Device: {result['device']}")
        print(f"  Scope: {result['scope']}")
        if result.get("expires_at"):
            print(f"  Expires: {result['expires_at']}")
        if result.get("max_actions"):
            print(f"  Max actions: {result['max_actions']}")


def _cli_revoke(args: argparse.Namespace) -> None:
    """Revoke a grant."""
    if args.all:
        count = device_controller.revoke_all_grants(device=args.device)
        print(f"✓ Revoked {count} grants" + (f" for {args.device}" if args.device else ""))
    else:
        result = device_controller.revoke_grant(args.grant_id, revoked_by="human_cli")
        if result.get("error"):
            print(f"Error: {result['error']}")
        else:
            print(f"✓ Revoked: {result['grant_id']}")


def main():
    parser = argparse.ArgumentParser(
        description="Permanence OS — Mac Control Bridge",
    )
    sub = parser.add_subparsers(dest="command")

    # Status
    sub.add_parser("status", help="Show device and system status")

    # Services
    sub.add_parser("services", help="Show service status")

    # Install
    p_install = sub.add_parser("install", help="Install an app via Homebrew")
    p_install.add_argument("app", help="App name (e.g. discord, jq)")
    p_install.add_argument("--formula", action="store_true", help="Install as formula (not cask)")

    # Notify
    p_notify = sub.add_parser("notify", help="Send a macOS notification")
    p_notify.add_argument("title", help="Notification title")
    p_notify.add_argument("message", help="Notification message")

    # Grant
    p_grant = sub.add_parser("grant", help="Grant device permission")
    p_grant.add_argument("device", help="Device ID (mac_mini, macbook, dell)")
    p_grant.add_argument("--scope", required=True, help="Comma-separated action categories")
    p_grant.add_argument("--duration", type=int, default=60, help="Duration in minutes (default 60)")
    p_grant.add_argument("--max-actions", type=int, help="Max number of actions")
    p_grant.add_argument("--notes", help="Optional notes")

    # Revoke
    p_revoke = sub.add_parser("revoke", help="Revoke a permission grant")
    p_revoke.add_argument("grant_id", nargs="?", help="Grant ID to revoke")
    p_revoke.add_argument("--all", action="store_true", help="Revoke all grants")
    p_revoke.add_argument("--device", help="Device to revoke grants for (with --all)")

    args = parser.parse_args()

    handlers = {
        "status": _cli_status,
        "services": _cli_services,
        "install": _cli_install,
        "notify": _cli_notify,
        "grant": _cli_grant,
        "revoke": _cli_revoke,
    }

    handler = handlers.get(args.command)
    if handler:
        handler(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
