#!/usr/bin/env python3
"""
Check away-from-home remote readiness for Permanence OS.

Signals checked:
- Tailscale running + online
- Local SSH port open (Remote Login enabled)
- Automation schedule present
- Keep-awake process active (optional requirement)
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parents[1]


def _run(cmd: list[str]) -> tuple[int, str]:
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    except Exception:
        return 1, ""
    out = (proc.stdout or "").strip()
    err = (proc.stderr or "").strip()
    return proc.returncode, out if out else err


def _tailscale_status() -> dict[str, Any]:
    code, out = _run(["tailscale", "status", "--json"])
    if code != 0 or not out:
        return {
            "installed": False,
            "backend_state": "unknown",
            "online": False,
            "ip4": None,
            "dns_name": None,
        }
    try:
        payload = json.loads(out)
    except json.JSONDecodeError:
        return {
            "installed": True,
            "backend_state": "unknown",
            "online": False,
            "ip4": None,
            "dns_name": None,
        }
    self_info = payload.get("Self") or {}
    ip4 = None
    for ip in payload.get("TailscaleIPs", []) or []:
        if isinstance(ip, str) and "." in ip:
            ip4 = ip
            break
    return {
        "installed": True,
        "backend_state": payload.get("BackendState", "unknown"),
        "online": bool(self_info.get("Online")),
        "ip4": ip4,
        "dns_name": self_info.get("DNSName"),
    }


def _ssh_port_open(host: str = "127.0.0.1", port: int = 22) -> bool:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(1.0)
    try:
        sock.connect((host, port))
        return True
    except Exception:
        return False
    finally:
        sock.close()


def _caffeinate_running() -> bool:
    # Match any active caffeinate process; flags can vary by invocation order.
    code, out = _run(["pgrep", "-fl", "caffeinate"])
    return code == 0 and bool(out.strip())


def _automation_scheduled() -> bool:
    cron_line = "automation/run_briefing.sh"
    code, out = _run(["crontab", "-l"])
    if code != 0 or not out:
        return False
    return cron_line in out


@dataclass
class ReadinessResult:
    ready: bool
    tailscale_ok: bool
    ssh_ok: bool
    awake_ok: bool
    automation_ok: bool
    details: dict[str, Any]


def evaluate_readiness(details: dict[str, Any], require_awake: bool) -> ReadinessResult:
    tailscale = details["tailscale"]
    tailscale_ok = tailscale["installed"] and tailscale["backend_state"] == "Running" and tailscale["online"]
    ssh_ok = bool(details["ssh_port_open"])
    awake_ok = bool(details["caffeinate_running"])
    automation_ok = bool(details["automation_scheduled"])
    ready = tailscale_ok and ssh_ok and automation_ok and (awake_ok if require_awake else True)
    return ReadinessResult(
        ready=ready,
        tailscale_ok=tailscale_ok,
        ssh_ok=ssh_ok,
        awake_ok=awake_ok,
        automation_ok=automation_ok,
        details=details,
    )


def _manual_steps(result: ReadinessResult, require_awake: bool) -> list[str]:
    steps: list[str] = []
    if not result.tailscale_ok:
        steps.append("Start Tailscale and confirm status shows Running/Online.")
    if not result.ssh_ok:
        steps.append("Enable macOS Remote Login: System Settings > General > Sharing > Remote Login ON.")
    if require_awake and not result.awake_ok:
        steps.append("Start keep-awake: `nohup caffeinate -dims >/tmp/permanence_caffeinate.log 2>&1 &`")
    if not result.automation_ok:
        steps.append("Install automation schedule: run `crontab -l` and add run_briefing entry.")
    return steps


def main() -> int:
    parser = argparse.ArgumentParser(description="Check away-mode remote readiness.")
    parser.add_argument("--skip-awake-check", action="store_true", help="Do not require caffeinate keep-awake.")
    parser.add_argument("--json-output", help="Optional path to write JSON result.")
    args = parser.parse_args()

    details = {
        "checked_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "tailscale": _tailscale_status(),
        "ssh_port_open": _ssh_port_open(),
        "caffeinate_running": _caffeinate_running(),
        "automation_scheduled": _automation_scheduled(),
    }

    result = evaluate_readiness(details, require_awake=not args.skip_awake_check)
    next_steps = _manual_steps(result, require_awake=not args.skip_awake_check)

    payload = {
        "ready": result.ready,
        "tailscale_ok": result.tailscale_ok,
        "ssh_ok": result.ssh_ok,
        "awake_ok": result.awake_ok,
        "automation_ok": result.automation_ok,
        "details": result.details,
        "next_steps": next_steps,
    }

    if args.json_output:
        output_path = Path(os.path.expanduser(args.json_output))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print(f"REMOTE READY: {'YES' if result.ready else 'NO'}")
    ts = details["tailscale"]
    print(f"- Tailscale: {'OK' if result.tailscale_ok else 'MISSING'} ({ts.get('backend_state')}, online={ts.get('online')}, ip={ts.get('ip4')})")
    print(f"- SSH Remote Login: {'OK' if result.ssh_ok else 'OFF'} (local port 22)")
    print(f"- Keep Awake: {'OK' if result.awake_ok else 'OFF'}")
    print(f"- Automation: {'OK' if result.automation_ok else 'MISSING'}")
    if next_steps:
        print("Next steps:")
        for step in next_steps:
            print(f"- {step}")
    return 0 if result.ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
