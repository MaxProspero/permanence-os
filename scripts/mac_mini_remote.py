#!/usr/bin/env python3
"""
MacBook → Mac Mini remote bridge via SSH/rsync.

Provides a safe, governed channel to:
- test SSH connectivity and service health
- run commands on Mac Mini in the repo (with optional venv activation)
- sync code from MacBook → Mac Mini
- check launchd service status, logs, restart services
- BLOCKED_COMMANDS prevent accidentally severing SSH or destroying data

Based on scripts/dell_remote.py pattern.
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
from typing import Any

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DEFAULT_CONFIG_PATH = os.path.join(
    os.path.expanduser("~"), ".permanence", "mac_mini_remote.json"
)

DEFAULT_CONFIG = {
    "host": "192.168.40.232",
    "user": "permanence-os",
    "key_path": "~/.ssh/id_ed25519_mac_mini",
    "repo_path": "~/Code/permanence-os",
    "port": None,
}

DEFAULT_SYNC_EXCLUDES = [
    ".git/",
    "venv/",
    ".venv/",
    "__pycache__/",
    ".pytest_cache/",
    "*.pyc",
    "logs/",
    "outputs/",
    "memory/tool/",
    "memory/working/research/",
    "memory/working/sources.json",
    ".DS_Store",
    ".env",
    "permanence_storage/",
    ".claude/",
    "node_modules/",
]

# ── Safety: commands that could sever SSH or destroy data ─────────────
BLOCKED_COMMAND_PATTERNS = [
    r"\bnetworksetup\b",
    r"\bifconfig\s+\w+\s+(down|delete)",
    r"launchctl\s+unload.*ssh",
    r"systemsetup.*RemoteLogin.*off",
    r"\bshutdown\b(?!.*-r)",  # shutdown without -r (reboot ok)
    r"\bhalt\b",
    r"\brm\s+-rf\s+/\s*$",
    r"\brm\s+-rf\s+~/?\s*$",
    r"\brm\s+-rf\s+\$HOME",
    r"\bpasswd\b",
    r"\bsudo\s+dscl\b",
    r"\bsudo\s+fdesetup\b",
    r"\blaunchctl\s+bootout\b.*system",
]

PERMANENCE_SERVICES = [
    "com.permanence.command-center",
    "com.permanence.foundation-site",
    "com.permanence.foundation-api",
    "com.permanence.cloudflare-tunnel",
    "com.permanence.git-sync",
    "com.permanence.open-webui",
]


def _load_json(path: str, fallback: dict[str, Any]) -> dict[str, Any]:
    path = os.path.expanduser(path)
    if not os.path.exists(path):
        return dict(fallback)
    try:
        with open(path, "r") as handle:
            parsed = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return dict(fallback)
    return parsed if isinstance(parsed, dict) else dict(fallback)


def _save_json(path: str, payload: dict[str, Any]) -> None:
    path = os.path.expanduser(path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as handle:
        json.dump(payload, handle, indent=2)


def _require(cfg: dict[str, Any], fields: list[str]) -> None:
    missing = [f for f in fields if not cfg.get(f)]
    if missing:
        raise ValueError(f"Missing required Mac Mini remote fields: {', '.join(missing)}")


def _is_blocked(command: str) -> str | None:
    """Return the matched pattern if command is blocked, else None."""
    for pattern in BLOCKED_COMMAND_PATTERNS:
        if re.search(pattern, command, re.IGNORECASE):
            return pattern
    return None


def _remote_target(cfg: dict[str, Any]) -> str:
    return f"{cfg['user']}@{cfg['host']}"


def _ssh_prefix(cfg: dict[str, Any]) -> list[str]:
    cmd = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10"]
    if cfg.get("port"):
        cmd += ["-p", str(cfg["port"])]
    key = cfg.get("key_path", "")
    if key:
        cmd += ["-i", os.path.expanduser(str(key))]
    cmd += [_remote_target(cfg)]
    return cmd


def _rsync_ssh_transport(cfg: dict[str, Any]) -> str:
    parts = ["ssh", "-o", "BatchMode=yes"]
    if cfg.get("port"):
        parts += ["-p", str(cfg["port"])]
    key = cfg.get("key_path", "")
    if key:
        parts += ["-i", os.path.expanduser(str(key))]
    return " ".join(parts)


def _brew_env_prefix() -> str:
    """Shell prefix to ensure Homebrew is on PATH for non-interactive SSH."""
    return 'export PATH="/opt/homebrew/bin:/opt/homebrew/sbin:$PATH"'


def build_remote_shell(
    command: str,
    repo_path: str | None = None,
    use_repo: bool = True,
    use_venv: bool = True,
) -> str:
    steps: list[str] = [_brew_env_prefix()]
    if use_repo and repo_path:
        # Use $HOME expansion for ~ paths so zsh can resolve them
        resolved = repo_path.replace("~", "$HOME") if repo_path.startswith("~") else repo_path
        steps.append(f"cd {resolved}")
        if use_venv:
            steps.append("if [ -f venv/bin/activate ]; then . venv/bin/activate; fi")
    steps.append(command)
    return " && ".join(steps)


def run_remote(
    cfg: dict[str, Any],
    command: str,
    use_repo: bool = True,
    use_venv: bool = True,
    print_cmd: bool = False,
    check_blocked: bool = True,
) -> int:
    _require(cfg, ["host", "user", "repo_path"])

    if check_blocked:
        blocked = _is_blocked(command)
        if blocked:
            print(f"⛔ BLOCKED: Command matches safety pattern: {blocked}")
            print(f"   Command: {command}")
            print("   This command could sever SSH access or destroy data.")
            return 99

    remote_shell = build_remote_shell(
        command=command,
        repo_path=cfg.get("repo_path"),
        use_repo=use_repo,
        use_venv=use_venv,
    )
    cmd = _ssh_prefix(cfg) + [remote_shell]
    if print_cmd:
        print("Running:", " ".join(shlex.quote(p) for p in cmd))
    return subprocess.call(cmd)


def sync_code(
    cfg: dict[str, Any],
    local_path: str = BASE_DIR,
    dry_run: bool = False,
    print_cmd: bool = False,
) -> int:
    _require(cfg, ["host", "user", "repo_path"])
    local = os.path.abspath(os.path.expanduser(local_path))
    if not os.path.isdir(local):
        raise ValueError(f"Local path not found: {local}")

    remote_repo = cfg["repo_path"]
    resolved_repo = remote_repo.replace("~", "$HOME") if remote_repo.startswith("~") else remote_repo
    mkdir_cmd = _ssh_prefix(cfg) + [f"{_brew_env_prefix()} && mkdir -p {resolved_repo}"]
    code = subprocess.call(mkdir_cmd)
    if code != 0:
        return code

    rsync_cmd = ["rsync", "-az", "--progress"]
    if dry_run:
        rsync_cmd.append("--dry-run")
    for pattern in DEFAULT_SYNC_EXCLUDES:
        rsync_cmd += ["--exclude", pattern]
    rsync_cmd += ["-e", _rsync_ssh_transport(cfg)]
    rsync_cmd += [f"{local.rstrip('/')}/", f"{_remote_target(cfg)}:{remote_repo.rstrip('/')}/"]
    if print_cmd:
        print("Running:", " ".join(shlex.quote(p) for p in rsync_cmd))
    return subprocess.call(rsync_cmd)


def check_status(cfg: dict[str, Any], print_cmd: bool = False) -> int:
    """Check all Permanence services, Ollama, and system health on Mac Mini."""
    _require(cfg, ["host", "user"])
    status_script = r"""
echo "=== PERMANENCE SERVICES ==="
for svc in com.permanence.command-center com.permanence.foundation-site com.permanence.foundation-api com.permanence.cloudflare-tunnel com.permanence.open-webui; do
    if launchctl list "$svc" &>/dev/null 2>&1; then
        pid=$(launchctl list "$svc" 2>/dev/null | head -1 | awk '{print $1}')
        echo "  ✓ $svc (PID: $pid)"
    else
        echo "  ✗ $svc (not loaded)"
    fi
done

echo ""
echo "=== ENDPOINTS ==="
for url in "http://127.0.0.1:8000/api/status" "http://127.0.0.1:8787/" "http://127.0.0.1:8797/app/ophtxn" "http://127.0.0.1:3000/"; do
    http_code=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 3 "$url" 2>/dev/null || echo "000")
    if [ "$http_code" = "200" ]; then
        echo "  ✓ $url ($http_code)"
    else
        echo "  ✗ $url ($http_code)"
    fi
done

echo ""
echo "=== OLLAMA ==="
if pgrep -x ollama &>/dev/null; then
    echo "  ✓ Ollama running"
    ollama list 2>/dev/null | while read -r line; do echo "    $line"; done
else
    echo "  ✗ Ollama not running"
fi

echo ""
echo "=== SYSTEM ==="
echo "  Hostname: $(hostname)"
echo "  Uptime: $(uptime | sed 's/.*up /up /' | sed 's/,.*load/  load/')"
echo "  Disk: $(df -h / | tail -1 | awk '{print $3 " used / " $2 " total (" $5 " full)"}')"
echo "  Memory: $(vm_stat | head -5 | tail -4 | awk 'NR==1{free=$3} NR==2{act=$3} END{print "Active pages: " act}')"
"""
    remote_shell = f'{_brew_env_prefix()} && {status_script}'
    cmd = _ssh_prefix(cfg) + [remote_shell]
    if print_cmd:
        print("Running:", " ".join(shlex.quote(p) for p in cmd))
    return subprocess.call(cmd)


def tail_logs(cfg: dict[str, Any], service: str | None = None, lines: int = 30) -> int:
    """Tail service logs on Mac Mini."""
    _require(cfg, ["host", "user"])

    service_map = {
        "command-center": "/tmp/permanence-command-center.log",
        "foundation-site": "/tmp/permanence-foundation-site.log",
        "foundation-api": "/tmp/permanence-foundation-api.log",
        "tunnel": "/tmp/permanence-cloudflare-tunnel.log",
        "git-sync": "/tmp/permanence-git-sync.log",
        "open-webui": "/tmp/permanence-open-webui.log",
    }

    if service and service in service_map:
        log_file = service_map[service]
        cmd_str = f"tail -{lines} {log_file} 2>/dev/null || echo 'Log file not found: {log_file}'"
    else:
        # Show last few lines from all services
        parts = []
        for name, path in service_map.items():
            parts.append(f'echo "=== {name} ===" && tail -5 {path} 2>/dev/null || echo "(no log)" && echo ""')
        cmd_str = " && ".join(parts)

    return run_remote(cfg, cmd_str, use_repo=False, use_venv=False, check_blocked=False)


def restart_service(cfg: dict[str, Any], service: str) -> int:
    """Restart a specific Permanence launchd service."""
    _require(cfg, ["host", "user"])

    service_map = {
        "command-center": "com.permanence.command-center",
        "foundation-site": "com.permanence.foundation-site",
        "foundation-api": "com.permanence.foundation-api",
        "tunnel": "com.permanence.cloudflare-tunnel",
        "git-sync": "com.permanence.git-sync",
        "open-webui": "com.permanence.open-webui",
    }

    if service == "all":
        targets = list(service_map.values())
    elif service in service_map:
        targets = [service_map[service]]
    else:
        print(f"Unknown service: {service}")
        print(f"Available: {', '.join(list(service_map.keys()) + ['all'])}")
        return 2

    cmds = []
    for target in targets:
        plist = f"~/Library/LaunchAgents/{target}.plist"
        cmds.append(f'echo "Restarting {target}..." && launchctl unload {plist} 2>/dev/null; launchctl load {plist}')

    cmd_str = " && ".join(cmds)
    return run_remote(cfg, cmd_str, use_repo=False, use_venv=False, check_blocked=False)


def _merge_cli_config(existing: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    cfg = dict(existing)
    updates = {
        "host": getattr(args, "host", None),
        "user": getattr(args, "user", None),
        "repo_path": getattr(args, "repo_path", None),
        "port": getattr(args, "port", None),
        "key_path": getattr(args, "key_path", None),
    }
    for key, value in updates.items():
        if value is not None:
            cfg[key] = value
    # Apply defaults for missing fields
    for key, value in DEFAULT_CONFIG.items():
        if key not in cfg or cfg[key] is None:
            cfg[key] = value
    return cfg


def _safe_show(cfg: dict[str, Any]) -> dict[str, Any]:
    payload = dict(cfg)
    if payload.get("key_path"):
        payload["key_path"] = os.path.abspath(os.path.expanduser(str(payload["key_path"])))
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(
        description="MacBook → Mac Mini remote bridge (SSH + rsync)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Actions:
  configure   Set/update Mac Mini connection config
  show        Display current config
  test        Verify SSH connectivity + service health
  run         Execute a command on Mac Mini via SSH
  sync-code   rsync repo from MacBook → Mac Mini
  status      Check all services + Ollama + system health
  logs        Tail service logs
  restart     Restart a specific service
""",
    )
    parser.add_argument(
        "--action",
        choices=["configure", "show", "test", "run", "sync-code", "status", "logs", "restart"],
        default="show",
        help="Bridge action",
    )
    parser.add_argument("--config", default=DEFAULT_CONFIG_PATH, help="Config JSON path")
    parser.add_argument("--host", help="Mac Mini host or IP")
    parser.add_argument("--user", help="Mac Mini SSH user")
    parser.add_argument("--repo-path", help="Repo path on Mac Mini")
    parser.add_argument("--port", type=int, help="SSH port")
    parser.add_argument("--key-path", help="SSH private key path")
    parser.add_argument("--cmd", help="Remote command for --action run")
    parser.add_argument("--no-repo", action="store_true", help="Do not cd into repo before run")
    parser.add_argument("--no-venv", action="store_true", help="Do not auto-activate venv")
    parser.add_argument("--local-path", default=BASE_DIR, help="Local path for sync-code")
    parser.add_argument("--dry-run", action="store_true", help="Dry run for sync-code")
    parser.add_argument("--print-cmd", action="store_true", help="Print underlying command")
    parser.add_argument("--service", help="Service name for logs/restart (command-center, foundation-site, foundation-api, tunnel, git-sync, all)")
    parser.add_argument("--lines", type=int, default=30, help="Number of log lines to show")
    args = parser.parse_args()

    existing = _load_json(args.config, DEFAULT_CONFIG)
    cfg = _merge_cli_config(existing, args)

    if args.action == "configure":
        cfg["updated_at"] = datetime.now(timezone.utc).isoformat()
        _save_json(args.config, cfg)
        print(f"Mac Mini remote config saved: {os.path.abspath(os.path.expanduser(args.config))}")
        print(json.dumps(_safe_show(cfg), indent=2))
        return 0

    if args.action == "show":
        print(json.dumps(_safe_show(cfg), indent=2))
        return 0

    # All other actions require valid config
    _require(cfg, ["host", "user", "repo_path"])

    if args.action == "test":
        print("Testing Mac Mini connectivity...")
        code = run_remote(
            cfg=cfg,
            command='echo "Mac Mini OK — $(hostname) — $(date)"',
            use_repo=False,
            use_venv=False,
            print_cmd=args.print_cmd,
            check_blocked=False,
        )
        if code == 0:
            print("\n✓ SSH connection successful")
            print("\nChecking services...")
            return check_status(cfg, print_cmd=args.print_cmd)
        else:
            print("\n✗ SSH connection failed")
            return code

    if args.action == "run":
        if not args.cmd:
            print("Missing --cmd for --action run")
            return 2
        return run_remote(
            cfg=cfg,
            command=args.cmd,
            use_repo=not args.no_repo,
            use_venv=not args.no_venv,
            print_cmd=args.print_cmd,
        )

    if args.action == "sync-code":
        return sync_code(
            cfg=cfg,
            local_path=args.local_path,
            dry_run=args.dry_run,
            print_cmd=args.print_cmd,
        )

    if args.action == "status":
        return check_status(cfg, print_cmd=args.print_cmd)

    if args.action == "logs":
        return tail_logs(cfg, service=args.service, lines=args.lines)

    if args.action == "restart":
        if not args.service:
            print("Missing --service for restart action")
            print("Available: command-center, foundation-site, foundation-api, tunnel, git-sync, all")
            return 2
        return restart_service(cfg, service=args.service)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
