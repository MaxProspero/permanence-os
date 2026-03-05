#!/usr/bin/env python3
"""
Run a money-first execution lane before feature-expansion loops.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parents[1]
OUTPUT_DIR = Path(os.getenv("PERMANENCE_OUTPUT_DIR", str(BASE_DIR / "outputs")))
TOOL_DIR = Path(os.getenv("PERMANENCE_TOOL_DIR", str(BASE_DIR / "memory" / "tool")))


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now().isoformat()


def _tail(text: str, max_chars: int = 1200) -> str:
    cleaned = (text or "").strip()
    if len(cleaned) <= max_chars:
        return cleaned
    return "...(truncated)...\n" + cleaned[-max_chars:]


def _run_step(cmd: list[str], timeout_sec: int) -> dict[str, Any]:
    started = _now()
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(BASE_DIR),
            env=os.environ.copy(),
            capture_output=True,
            text=True,
            timeout=timeout_sec,
        )
        output = "\n".join(part for part in [proc.stdout, proc.stderr] if part)
        return {
            "command": cmd,
            "status": "OK" if int(proc.returncode) == 0 else "FAILED",
            "return_code": int(proc.returncode),
            "started_at": started.isoformat(),
            "elapsed_ms": int((_now() - started).total_seconds() * 1000),
            "output_tail": _tail(output),
        }
    except subprocess.TimeoutExpired as exc:
        timeout_output = "\n".join(str(part) for part in [exc.stdout, exc.stderr] if part)
        return {
            "command": cmd,
            "status": "FAILED",
            "return_code": 124,
            "started_at": started.isoformat(),
            "elapsed_ms": int((_now() - started).total_seconds() * 1000),
            "output_tail": _tail(f"Timeout after {timeout_sec}s.\n{timeout_output}"),
        }
    except OSError as exc:
        return {
            "command": cmd,
            "status": "FAILED",
            "return_code": 127,
            "started_at": started.isoformat(),
            "elapsed_ms": int((_now() - started).total_seconds() * 1000),
            "output_tail": _tail(f"Command launch failed: {exc}"),
        }


def _write_outputs(results: list[dict[str, Any]], strict: bool) -> tuple[Path, Path]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    TOOL_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _now().strftime("%Y%m%d-%H%M%S")
    md_path = OUTPUT_DIR / f"money_first_lane_{stamp}.md"
    latest_md = OUTPUT_DIR / "money_first_lane_latest.md"
    json_path = TOOL_DIR / f"money_first_lane_{stamp}.json"

    failed = [row for row in results if str(row.get("status")).upper() != "OK"]
    lines = [
        "# Money First Lane",
        "",
        f"Generated (UTC): {_now_iso()}",
        f"Strict mode: {strict}",
        f"Overall status: {'PASS' if not failed else 'FAIL'}",
        "",
        "## Step Results",
    ]
    for idx, row in enumerate(results, start=1):
        cmd = " ".join(str(part) for part in (row.get("command") or []))
        lines.extend(
            [
                f"{idx}. {row.get('status')} | rc={row.get('return_code')} | {cmd}",
                f"   - elapsed_ms={row.get('elapsed_ms')}",
            ]
        )
        output_tail = str(row.get("output_tail") or "").strip()
        if output_tail:
            lines.append("   - output_tail:")
            for raw in output_tail.splitlines()[:12]:
                lines.append(f"     {raw}")

    lines.extend(
        [
            "",
            "## Purpose",
            "- Prioritize immediate revenue operations and budget recovery.",
            "- Keep execution focused before expanding feature-work scope.",
            "",
        ]
    )

    report = "\n".join(lines)
    md_path.write_text(report, encoding="utf-8")
    latest_md.write_text(report, encoding="utf-8")

    payload = {
        "generated_at": _now_iso(),
        "strict": bool(strict),
        "overall_status": "PASS" if not failed else "FAIL",
        "step_count": len(results),
        "failed_count": len(failed),
        "steps": results,
        "latest_markdown": str(latest_md),
    }
    json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return md_path, json_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run money-first execution lane.")
    parser.add_argument("--strict", action="store_true", help="Return non-zero when any step fails")
    parser.add_argument("--timeout", type=int, default=900, help="Per-step timeout seconds")
    parser.add_argument("--skip-init", action="store_true", help="Skip playbook/targets/pipeline init checks")
    args = parser.parse_args(argv)

    cli_path = str(BASE_DIR / "cli.py")
    python_bin = sys.executable

    steps: list[list[str]] = []
    if not args.skip_init:
        steps.extend(
            [
                [python_bin, cli_path, "revenue-playbook", "init"],
                [python_bin, cli_path, "revenue-targets", "init"],
                [python_bin, cli_path, "sales-pipeline", "init"],
            ]
        )
    steps.extend(
        [
            [python_bin, cli_path, "revenue-action-queue"],
            [python_bin, cli_path, "revenue-execution-board"],
            [python_bin, cli_path, "revenue-outreach-pack"],
            [python_bin, cli_path, "revenue-followup-queue"],
            [python_bin, cli_path, "revenue-cost-recovery"],
            [python_bin, cli_path, "revenue-eval"],
            [python_bin, cli_path, "money-first-gate", "--strict"],
        ]
    )

    results: list[dict[str, Any]] = []
    for cmd in steps:
        result = _run_step(cmd, timeout_sec=max(60, int(args.timeout)))
        results.append(result)
        if args.strict and str(result.get("status", "")).upper() != "OK":
            break

    md_path, json_path = _write_outputs(results, strict=args.strict)
    print(f"Money-first lane written: {md_path}")
    print(f"Money-first lane latest: {OUTPUT_DIR / 'money_first_lane_latest.md'}")
    print(f"Tool payload written: {json_path}")
    failed = [row for row in results if str(row.get("status")).upper() != "OK"]
    return 1 if (args.strict and failed) else 0


if __name__ == "__main__":
    raise SystemExit(main())
