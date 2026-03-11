#!/usr/bin/env python3
"""
OpenClaw status helper.
Runs the local OpenClaw CLI and writes output to a file for auditability.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from datetime import datetime, timezone

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(BASE_DIR)

from agents.utils import log  # noqa: E402


SAFE_OPENCLAW_ENV_KEYS = (
    "HOME",
    "PATH",
    "USER",
    "LOGNAME",
    "SHELL",
    "LANG",
    "LC_ALL",
    "LC_CTYPE",
    "TMPDIR",
    "XDG_CONFIG_HOME",
    "XDG_DATA_HOME",
    "XDG_STATE_HOME",
    "OPENCLAW_HOME",
    "OPENCLAW_CONFIG",
    "OPENCLAW_CLI",
)

AUTH_HEADER_RE = re.compile(r"(?im)(authorization\s*:\s*bearer\s+)([^\s]+)")
SECRET_ASSIGNMENT_RE = re.compile(
    r"(?im)\b(api[_ -]?key|access[_ -]?token|refresh[_ -]?token|token|secret|password)\b(\s*[:=]\s*)(\"[^\"]*\"|'[^']*'|[^\s,;]+)"
)
SECRET_QUERY_RE = re.compile(r"(?i)([?&](?:api[_-]?key|access_token|token|secret|password)=)[^&\s]+")
LONG_SECRET_RE = re.compile(r"\b(?:sk-[A-Za-z0-9_-]{12,}|gh[pousr]_[A-Za-z0-9_]{12,}|xai-[A-Za-z0-9_-]{12,})\b")


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


def _openclaw_env() -> dict[str, str]:
    env: dict[str, str] = {}
    for key in SAFE_OPENCLAW_ENV_KEYS:
        value = os.getenv(key)
        if value:
            env[key] = value
    env.setdefault("PATH", os.getenv("PATH", os.defpath))
    env.setdefault("HOME", os.path.expanduser("~"))
    return env


def _redact_openclaw_output(text: str) -> str:
    payload = str(text or "")
    if not payload:
        return ""
    scrubbed = AUTH_HEADER_RE.sub(r"\1[REDACTED]", payload)
    scrubbed = SECRET_QUERY_RE.sub(r"\1[REDACTED]", scrubbed)
    scrubbed = SECRET_ASSIGNMENT_RE.sub(lambda match: f"{match.group(1)}{match.group(2)}[REDACTED]", scrubbed)
    scrubbed = LONG_SECRET_RE.sub("[REDACTED_SECRET]", scrubbed)
    return scrubbed


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
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
            env=_openclaw_env(),
        )
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
    payload = _redact_openclaw_output(payload)

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
