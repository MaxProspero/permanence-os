#!/usr/bin/env python3
"""
Manage comms-loop automation lifecycle.

Actions:
- status: inspect launchd registration/state for com.permanence.comms_loop
- enable: run automation/setup_comms_loop_automation.sh
- disable: run automation/disable_comms_loop_automation.sh
- run-now: execute scripts/run_comms_loop.sh immediately
- digest-*: manage com.permanence.comms_digest
- doctor-*: manage com.permanence.comms_doctor
- escalation-*: manage com.permanence.comms_escalation_digest
- escalation-digest-now: run scripts/comms_escalation_digest.py --send
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parents[1]
OUTPUT_DIR = Path(os.getenv("PERMANENCE_OUTPUT_DIR", str(BASE_DIR / "outputs")))
TOOL_DIR = Path(os.getenv("PERMANENCE_TOOL_DIR", str(BASE_DIR / "memory" / "tool")))

DEFAULT_LABEL = "com.permanence.comms_loop"
DEFAULT_DIGEST_LABEL = "com.permanence.comms_digest"
DEFAULT_DOCTOR_LABEL = "com.permanence.comms_doctor"
DEFAULT_ESCALATION_LABEL = "com.permanence.comms_escalation_digest"
SETUP_SCRIPT = BASE_DIR / "automation" / "setup_comms_loop_automation.sh"
DISABLE_SCRIPT = BASE_DIR / "automation" / "disable_comms_loop_automation.sh"
RUN_SCRIPT = BASE_DIR / "scripts" / "run_comms_loop.sh"
DIGEST_SETUP_SCRIPT = BASE_DIR / "automation" / "setup_comms_digest_automation.sh"
DIGEST_DISABLE_SCRIPT = BASE_DIR / "automation" / "disable_comms_digest_automation.sh"
DIGEST_RUN_SCRIPT = BASE_DIR / "scripts" / "comms_digest.py"
DOCTOR_SETUP_SCRIPT = BASE_DIR / "automation" / "setup_comms_doctor_automation.sh"
DOCTOR_DISABLE_SCRIPT = BASE_DIR / "automation" / "disable_comms_doctor_automation.sh"
DOCTOR_RUN_SCRIPT = BASE_DIR / "scripts" / "comms_doctor.py"
ESCALATION_SETUP_SCRIPT = BASE_DIR / "automation" / "setup_comms_escalation_digest_automation.sh"
ESCALATION_DISABLE_SCRIPT = BASE_DIR / "automation" / "disable_comms_escalation_digest_automation.sh"
ESCALATION_DIGEST_RUN_SCRIPT = BASE_DIR / "scripts" / "comms_escalation_digest.py"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now().isoformat()


def _run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, check=False, capture_output=True, text=True)


def _parse_launchd_print(text: str) -> dict[str, Any]:
    state_match = re.search(r"state = ([^\n]+)", text or "")
    runs_match = re.search(r"runs = (\d+)", text or "")
    exit_match = re.search(r"last exit code = (\d+)", text or "")
    interval_match = re.search(r"run interval = (\d+) seconds", text or "")
    path_match = re.search(r"path = ([^\n]+)", text or "")
    return {
        "state": (state_match.group(1).strip() if state_match else "unknown"),
        "runs": int(runs_match.group(1)) if runs_match else 0,
        "last_exit_code": int(exit_match.group(1)) if exit_match else None,
        "run_interval_seconds": int(interval_match.group(1)) if interval_match else None,
        "path": (path_match.group(1).strip() if path_match else ""),
    }


def _launchd_status(label: str = DEFAULT_LABEL) -> dict[str, Any]:
    uid = os.getuid()
    target = f"gui/{uid}/{label}"
    proc = _run(["launchctl", "print", target])
    if proc.returncode != 0:
        return {
            "installed": False,
            "label": label,
            "state": "missing",
            "runs": 0,
            "last_exit_code": None,
            "run_interval_seconds": None,
            "path": "",
        }
    parsed = _parse_launchd_print(proc.stdout or "")
    parsed["installed"] = True
    parsed["label"] = label
    return parsed


def _status_label_for_action(action: str, explicit_label: str) -> str:
    if str(action or "").startswith("digest-"):
        return DEFAULT_DIGEST_LABEL
    if str(action or "").startswith("doctor-"):
        return DEFAULT_DOCTOR_LABEL
    if str(action or "").startswith("escalation-"):
        return DEFAULT_ESCALATION_LABEL
    return str(explicit_label or DEFAULT_LABEL)


def _command_for_action(action: str) -> list[str]:
    if action == "enable":
        return ["/bin/bash", str(SETUP_SCRIPT), str(BASE_DIR)]
    if action == "disable":
        return ["/bin/bash", str(DISABLE_SCRIPT), str(BASE_DIR)]
    if action == "run-now":
        return ["/bin/bash", str(RUN_SCRIPT)]
    if action == "digest-enable":
        return ["/bin/bash", str(DIGEST_SETUP_SCRIPT), str(BASE_DIR)]
    if action == "digest-disable":
        return ["/bin/bash", str(DIGEST_DISABLE_SCRIPT), str(BASE_DIR)]
    if action == "digest-now":
        return ["/usr/bin/env", "python3", str(DIGEST_RUN_SCRIPT), "--send"]
    if action == "doctor-enable":
        return ["/bin/bash", str(DOCTOR_SETUP_SCRIPT), str(BASE_DIR)]
    if action == "doctor-disable":
        return ["/bin/bash", str(DOCTOR_DISABLE_SCRIPT), str(BASE_DIR)]
    if action == "doctor-now":
        return ["/usr/bin/env", "python3", str(DOCTOR_RUN_SCRIPT), "--allow-warnings"]
    if action == "escalation-enable":
        return ["/bin/bash", str(ESCALATION_SETUP_SCRIPT), str(BASE_DIR)]
    if action == "escalation-disable":
        return ["/bin/bash", str(ESCALATION_DISABLE_SCRIPT), str(BASE_DIR)]
    if action == "escalation-digest-now":
        return ["/usr/bin/env", "python3", str(ESCALATION_DIGEST_RUN_SCRIPT), "--send"]
    return []


def _write_report(
    *,
    action: str,
    status: dict[str, Any],
    command: list[str],
    command_rc: int,
    command_stdout: str,
    command_stderr: str,
    warnings: list[str],
) -> tuple[Path, Path]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    TOOL_DIR.mkdir(parents=True, exist_ok=True)

    stamp = _now().strftime("%Y%m%d-%H%M%S")
    md_path = OUTPUT_DIR / f"comms_automation_{stamp}.md"
    latest_md = OUTPUT_DIR / "comms_automation_latest.md"
    json_path = TOOL_DIR / f"comms_automation_{stamp}.json"

    lines = [
        "# Comms Automation",
        "",
        f"Generated (UTC): {_now_iso()}",
        f"Action: {action}",
        "",
        "## Launchd Status",
        f"- Installed: {bool(status.get('installed'))}",
        f"- Label: {status.get('label')}",
        f"- State: {status.get('state')}",
        f"- Runs: {status.get('runs')}",
        f"- Last exit: {status.get('last_exit_code')}",
        f"- Interval seconds: {status.get('run_interval_seconds')}",
        f"- Plist path: {status.get('path') or '-'}",
        "",
        "## Command",
        f"- Exit code: {command_rc}",
        f"- argv: {' '.join(command) if command else '-'}",
        "",
    ]

    if command_stdout.strip():
        lines.append("## Command Stdout")
        for row in command_stdout.strip().splitlines()[:120]:
            lines.append(f"- {row}")
        lines.append("")

    if command_stderr.strip():
        lines.append("## Command Stderr")
        for row in command_stderr.strip().splitlines()[:120]:
            lines.append(f"- {row}")
        lines.append("")

    lines.append("## Warnings")
    if warnings:
        for row in warnings:
            lines.append(f"- {row}")
    else:
        lines.append("- None")

    report = "\n".join(lines) + "\n"
    md_path.write_text(report, encoding="utf-8")
    latest_md.write_text(report, encoding="utf-8")

    payload = {
        "generated_at": _now_iso(),
        "action": action,
        "launchd_status": status,
        "command": command,
        "command_exit_code": command_rc,
        "command_stdout": command_stdout,
        "command_stderr": command_stderr,
        "warnings": warnings,
        "latest_markdown": str(latest_md),
    }
    json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return md_path, json_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Manage comms-loop automation")
    parser.add_argument(
        "--action",
        choices=[
            "status",
            "enable",
            "disable",
            "run-now",
            "digest-status",
            "digest-enable",
            "digest-disable",
            "digest-now",
            "doctor-status",
            "doctor-enable",
            "doctor-disable",
            "doctor-now",
            "escalation-status",
            "escalation-enable",
            "escalation-disable",
            "escalation-digest-now",
        ],
        default="status",
    )
    parser.add_argument("--label", default=DEFAULT_LABEL, help="launchd label")
    args = parser.parse_args(argv)

    command: list[str] = []
    command_rc = 0
    command_stdout = ""
    command_stderr = ""
    warnings: list[str] = []

    status_label = _status_label_for_action(args.action, str(args.label or DEFAULT_LABEL))
    command = _command_for_action(args.action)

    if command:
        proc = _run(command)
        command_rc = int(proc.returncode)
        command_stdout = proc.stdout or ""
        command_stderr = proc.stderr or ""
        if command_rc != 0:
            warnings.append(f"command exited non-zero: {command_rc}")

    status = _launchd_status(label=status_label)
    if args.action == "enable" and not status.get("installed"):
        warnings.append("enable completed but launchd label is not installed.")
    if args.action == "digest-enable" and not status.get("installed"):
        warnings.append("digest-enable completed but launchd label is not installed.")
    if args.action == "status" and not status.get("installed"):
        warnings.append("comms loop automation is not installed.")
    if args.action == "digest-status" and not status.get("installed"):
        warnings.append("comms digest automation is not installed.")
    if args.action == "doctor-enable" and not status.get("installed"):
        warnings.append("doctor-enable completed but launchd label is not installed.")
    if args.action == "doctor-status" and not status.get("installed"):
        warnings.append("comms doctor automation is not installed.")
    if args.action == "escalation-enable" and not status.get("installed"):
        warnings.append("escalation-enable completed but launchd label is not installed.")
    if args.action == "escalation-status" and not status.get("installed"):
        warnings.append("comms escalation digest automation is not installed.")

    md_path, json_path = _write_report(
        action=args.action,
        status=status,
        command=command,
        command_rc=command_rc,
        command_stdout=command_stdout,
        command_stderr=command_stderr,
        warnings=warnings,
    )

    print(f"Comms automation written: {md_path}")
    print(f"Comms automation latest: {OUTPUT_DIR / 'comms_automation_latest.md'}")
    print(f"Tool payload written: {json_path}")
    print(f"Launchd installed: {bool(status.get('installed'))}")
    print(f"Launchd state: {status.get('state')}")
    if warnings:
        print(f"Warnings: {len(warnings)}")

    return 0 if command_rc == 0 else command_rc


if __name__ == "__main__":
    raise SystemExit(main())
