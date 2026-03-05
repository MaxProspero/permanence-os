#!/usr/bin/env python3
"""
Run Phase 3 opportunity-pipeline modules in one governed sequence.
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


def _is_true(value: str) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


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
    md_path = OUTPUT_DIR / f"phase3_refresh_{stamp}.md"
    latest_md = OUTPUT_DIR / "phase3_refresh_latest.md"
    json_path = TOOL_DIR / f"phase3_refresh_{stamp}.json"

    failed = [row for row in results if str(row.get("status")).upper() != "OK"]
    lines = [
        "# Phase 3 Refresh",
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
            "## Governance Notes",
            "- Optional money-first gate can block this sequence until revenue milestone is reached.",
            "- This sequence creates ranked opportunities and manual approval queue entries only.",
            "- No autonomous publishing, payments, or live trading is executed.",
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
    parser = argparse.ArgumentParser(description="Run Phase 3 refresh sequence.")
    parser.add_argument("--strict", action="store_true", help="Return non-zero when any step fails")
    parser.add_argument("--timeout", type=int, default=900, help="Per-step timeout seconds")
    args = parser.parse_args(argv)

    cli_path = str(BASE_DIR / "cli.py")
    python_bin = sys.executable
    require_money_gate = _is_true(os.getenv("PERMANENCE_FEATURE_WORK_REQUIRE_REVENUE_MILESTONE", "0"))

    results: list[dict[str, Any]] = []
    if require_money_gate:
        gate_result = _run_step(
            [python_bin, cli_path, "money-first-gate", "--strict"],
            timeout_sec=max(60, min(300, int(args.timeout))),
        )
        results.append(gate_result)
        if str(gate_result.get("status", "")).upper() != "OK":
            md_path, json_path = _write_outputs(results, strict=args.strict)
            print(f"Phase3 refresh written: {md_path}")
            print(f"Phase3 refresh latest: {OUTPUT_DIR / 'phase3_refresh_latest.md'}")
            print(f"Tool payload written: {json_path}")
            print("Phase3 refresh blocked by money-first gate.")
            return 1

    steps = [
        [python_bin, cli_path, "social-research-ingest"],
        [python_bin, cli_path, "github-research-ingest"],
        [python_bin, cli_path, "github-trending-ingest"],
        [python_bin, cli_path, "ecosystem-research-ingest"],
        [python_bin, cli_path, "side-business-portfolio"],
        [python_bin, cli_path, "prediction-ingest"],
        [python_bin, cli_path, "prediction-lab"],
        [python_bin, cli_path, "world-watch"],
        [python_bin, cli_path, "world-watch-alerts"],
        [python_bin, cli_path, "market-backtest-queue"],
        [python_bin, cli_path, "narrative-tracker"],
        [python_bin, cli_path, "opportunity-ranker"],
        [python_bin, cli_path, "opportunity-approval-queue"],
        [python_bin, cli_path, "second-brain-report"],
    ]

    for cmd in steps:
        result = _run_step(cmd, timeout_sec=max(60, int(args.timeout)))
        results.append(result)
        if args.strict and str(result.get("status", "")).upper() != "OK":
            break

    md_path, json_path = _write_outputs(results, strict=args.strict)
    print(f"Phase3 refresh written: {md_path}")
    print(f"Phase3 refresh latest: {OUTPUT_DIR / 'phase3_refresh_latest.md'}")
    print(f"Tool payload written: {json_path}")
    failed = [row for row in results if str(row.get("status")).upper() != "OK"]
    return 1 if (args.strict and failed) else 0


if __name__ == "__main__":
    raise SystemExit(main())
