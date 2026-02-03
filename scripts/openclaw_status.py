#!/usr/bin/env python3
"""
OpenClaw status helper.
Runs the local OpenClaw CLI and writes output to a file for auditability.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from datetime import datetime, timezone

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(BASE_DIR)

from agents.utils import log  # noqa: E402


def _default_output_path(kind: str) -> str:
    output_dir = os.getenv("PERMANENCE_OUTPUT_DIR", os.path.join(BASE_DIR, "outputs"))
    os.makedirs(output_dir, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return os.path.join(output_dir, f"openclaw_{kind}_{stamp}.txt")


def _tool_memory_path(kind: str) -> str:
    tool_dir = os.getenv("PERMANENCE_TOOL_DIR", os.path.join(BASE_DIR, "memory", "tool"))
    os.makedirs(tool_dir, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return os.path.join(tool_dir, f"openclaw_{kind}_{stamp}.txt")


def _parse_reachable(output: str) -> bool:
    return "reachable" in output.lower()


def _parse_gateway(output: str) -> str:
    for line in output.splitlines():
        if line.strip().startswith("Gateway"):
            return line.strip()
    return ""


def capture_openclaw_status(health: bool = False, output: str | None = None) -> dict:
    openclaw_cli = os.getenv("OPENCLAW_CLI", os.path.expanduser("~/.openclaw/bin/openclaw"))
    cmd = [openclaw_cli, "health" if health else "status"]
    timestamp = datetime.now(timezone.utc).isoformat()
    if not os.path.exists(openclaw_cli):
        return {
            "status": "error",
            "reachable": False,
            "health": "unknown",
            "timestamp": timestamp,
            "gateway": "",
            "message": f"OpenClaw CLI not found at {openclaw_cli}",
        }

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    except OSError as exc:
        return {
            "status": "error",
            "reachable": False,
            "health": "unknown",
            "timestamp": timestamp,
            "gateway": "",
            "message": str(exc),
        }

    kind = "health" if health else "status"
    output_path = output or _default_output_path(kind)
    tool_path = _tool_memory_path(kind)
    payload = result.stdout
    if result.stderr:
        payload += "\n--- STDERR ---\n" + result.stderr

    with open(output_path, "w") as f:
        f.write(payload)
    with open(tool_path, "w") as f:
        f.write(payload)

    log(f"OpenClaw {cmd[-1]} captured: {output_path}", level="INFO")
    log(f"OpenClaw {cmd[-1]} tool memory: {tool_path}", level="INFO")

    return {
        "status": "ok" if result.returncode == 0 else "error",
        "reachable": _parse_reachable(result.stdout),
        "health": "healthy" if health and result.returncode == 0 else "unknown",
        "timestamp": timestamp,
        "gateway": _parse_gateway(result.stdout),
        "message": result.stderr.strip() if result.stderr else "",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch OpenClaw status/health output.")
    parser.add_argument("--health", action="store_true", help="Run openclaw health instead of status")
    parser.add_argument("--output", help="Write output to path (default: outputs/...)")
    args = parser.parse_args()

    result = capture_openclaw_status(health=args.health, output=args.output)
    if result.get("status") == "error" and result.get("message"):
        print(result["message"], file=sys.stderr)
    return 0 if result.get("status") == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
