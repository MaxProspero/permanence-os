#!/usr/bin/env python3
"""
Run the Ophtxn daily operations shortcut pack.

Shortcut pack includes:
- daily cycle brief
- no-spend guardrail audit
- approvals top view
- optional safe batch approval decision
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
    return _now().isoformat().replace("+00:00", "Z")


def _tail(text: str, max_chars: int = 1200) -> str:
    payload = str(text or "").strip()
    if len(payload) <= max_chars:
        return payload
    return "...(truncated)...\n" + payload[-max_chars:]


def _run_step(cmd: list[str], timeout_sec: int) -> dict[str, Any]:
    started = _now()
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(BASE_DIR),
            env=os.environ.copy(),
            capture_output=True,
            text=True,
            timeout=max(15, int(timeout_sec)),
        )
        combined = "\n".join(part for part in [proc.stdout, proc.stderr] if part)
        return {
            "command": cmd,
            "status": "OK" if int(proc.returncode) == 0 else "FAILED",
            "return_code": int(proc.returncode),
            "started_at": started.isoformat(),
            "elapsed_ms": int((_now() - started).total_seconds() * 1000),
            "output_tail": _tail(combined),
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


def _build_steps(
    *,
    approval_sources: list[str],
    approval_limit: int,
    approval_decision: str,
    approval_batch_size: int,
    safe_max_priority: str,
    safe_max_risk: str,
) -> list[list[str]]:
    cli_path = str(BASE_DIR / "cli.py")
    python_bin = sys.executable
    steps: list[list[str]] = [
        [python_bin, cli_path, "ophtxn-daily-ops", "--action", "cycle"],
        [python_bin, cli_path, "no-spend-audit", "--strict"],
        [python_bin, cli_path, "approval-triage", "--action", "top", "--limit", str(max(1, int(approval_limit)))],
    ]
    for source in approval_sources:
        steps[-1].extend(["--source", source])

    decision = str(approval_decision or "").strip().lower()
    if decision in {"approve", "reject", "defer"}:
        safe_cmd = [
            python_bin,
            cli_path,
            "approval-triage",
            "--action",
            "decide-batch-safe",
            "--decision",
            decision,
            "--batch-size",
            str(max(1, int(approval_batch_size))),
            "--safe-max-priority",
            str(safe_max_priority).strip().lower() or "low",
            "--safe-max-risk",
            str(safe_max_risk).strip().lower() or "medium",
            "--decided-by",
            "ops_pack",
        ]
        for source in approval_sources:
            safe_cmd.extend(["--source", source])
        steps.append(safe_cmd)
    return steps


def _write_outputs(
    *,
    action: str,
    strict: bool,
    steps: list[list[str]],
    results: list[dict[str, Any]],
    approval_sources: list[str],
    approval_decision: str,
    approval_batch_size: int,
    safe_max_priority: str,
    safe_max_risk: str,
) -> tuple[Path, Path]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    TOOL_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _now().strftime("%Y%m%d-%H%M%S")
    md_path = OUTPUT_DIR / f"ophtxn_ops_pack_{stamp}.md"
    latest_md = OUTPUT_DIR / "ophtxn_ops_pack_latest.md"
    json_path = TOOL_DIR / f"ophtxn_ops_pack_{stamp}.json"

    failed = [row for row in results if str(row.get("status")).upper() != "OK"]
    lines = [
        "# Ophtxn Ops Pack",
        "",
        f"Generated (UTC): {_now_iso()}",
        f"Action: {action}",
        f"Strict mode: {strict}",
        f"Overall status: {'PASS' if not failed else 'FAIL'}",
        f"Approval sources: {', '.join(approval_sources) if approval_sources else '-'}",
        f"Approval decision: {approval_decision or 'none'}",
        f"Safe batch size: {max(1, int(approval_batch_size))}",
        f"Safe max priority: {safe_max_priority}",
        f"Safe max risk: {safe_max_risk}",
        "",
        "## Planned Steps",
    ]
    for idx, cmd in enumerate(steps, start=1):
        lines.append(f"{idx}. {' '.join(str(part) for part in cmd)}")

    if results:
        lines.extend(["", "## Step Results"])
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
            "- No-spend audit step runs in strict mode by design.",
            "- Safe batch decision is optional and only runs when a decision is explicitly set.",
            "- Safe batch always requires source scope and priority/risk ceilings.",
            "",
        ]
    )

    markdown = "\n".join(lines) + "\n"
    md_path.write_text(markdown, encoding="utf-8")
    latest_md.write_text(markdown, encoding="utf-8")

    payload = {
        "generated_at": _now_iso(),
        "action": action,
        "strict": bool(strict),
        "overall_status": "PASS" if not failed else "FAIL",
        "approval_sources": approval_sources,
        "approval_decision": approval_decision,
        "safe_batch_size": max(1, int(approval_batch_size)),
        "safe_max_priority": str(safe_max_priority),
        "safe_max_risk": str(safe_max_risk),
        "step_count": len(results),
        "failed_count": len(failed),
        "steps": results,
        "latest_markdown": str(latest_md),
    }
    json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return md_path, json_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Ophtxn daily operations shortcut pack.")
    parser.add_argument("--action", choices=["status", "run"], default="run")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero when any step fails")
    parser.add_argument("--timeout", type=int, default=300, help="Per-step timeout seconds")
    parser.add_argument(
        "--approval-source",
        action="append",
        default=[],
        help="Approval source scope for top/safe batch (repeatable)",
    )
    parser.add_argument("--approval-limit", type=int, default=12, help="Limit for top approvals list step")
    parser.add_argument(
        "--approval-decision",
        choices=["approve", "reject", "defer"],
        help="Optional safe batch decision to apply",
    )
    parser.add_argument("--approval-batch-size", type=int, default=3, help="Safe batch size when decision is set")
    parser.add_argument(
        "--safe-max-priority",
        choices=["low", "medium", "high", "critical"],
        default="low",
        help="Safe batch priority ceiling",
    )
    parser.add_argument(
        "--safe-max-risk",
        choices=["low", "medium", "high", "critical"],
        default="medium",
        help="Safe batch risk ceiling",
    )
    args = parser.parse_args(argv)

    sources = [str(item).strip().lower() for item in args.approval_source if str(item).strip()]
    if not sources:
        sources = [str(os.getenv("PERMANENCE_OPS_PACK_APPROVAL_SOURCE", "phase3_opportunity_queue")).strip().lower()]
    sources = [item for item in sources if item]
    sources = list(dict.fromkeys(sources))

    steps = _build_steps(
        approval_sources=sources,
        approval_limit=max(1, int(args.approval_limit)),
        approval_decision=str(args.approval_decision or ""),
        approval_batch_size=max(1, int(args.approval_batch_size)),
        safe_max_priority=str(args.safe_max_priority),
        safe_max_risk=str(args.safe_max_risk),
    )

    results: list[dict[str, Any]] = []
    if args.action == "run":
        for cmd in steps:
            row = _run_step(cmd, timeout_sec=max(30, int(args.timeout)))
            results.append(row)
            if args.strict and str(row.get("status")).upper() != "OK":
                break

    md_path, json_path = _write_outputs(
        action=str(args.action),
        strict=bool(args.strict),
        steps=steps,
        results=results,
        approval_sources=sources,
        approval_decision=str(args.approval_decision or ""),
        approval_batch_size=max(1, int(args.approval_batch_size)),
        safe_max_priority=str(args.safe_max_priority),
        safe_max_risk=str(args.safe_max_risk),
    )
    failed = [row for row in results if str(row.get("status")).upper() != "OK"]
    print(f"Ophtxn ops-pack report: {md_path}")
    print(f"Ophtxn ops-pack latest: {OUTPUT_DIR / 'ophtxn_ops_pack_latest.md'}")
    print(f"Tool payload: {json_path}")
    if args.action == "status":
        print(f"Planned steps: {len(steps)}")
    else:
        print(f"Executed steps: {len(results)} | failed: {len(failed)}")
    if args.strict and failed:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
