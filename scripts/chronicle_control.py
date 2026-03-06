#!/usr/bin/env python3
"""
Control plane for chronicle refinement pipeline.

Actions:
- status: summarize chronicle pipeline artifacts + approval state
- run: execute chronicle-refinement -> chronicle-approval-queue -> chronicle-execution-board
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
APPROVALS_PATH = Path(os.getenv("PERMANENCE_APPROVALS_PATH", str(BASE_DIR / "memory" / "approvals.json")))
DEFAULT_SOURCE = "chronicle_refinement_queue"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now().isoformat().replace("+00:00", "Z")


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def _latest_tool(pattern: str) -> Path | None:
    if not TOOL_DIR.exists():
        return None
    rows = sorted(TOOL_DIR.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    return rows[0] if rows else None


def _safe_int(value: Any) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def _tail(text: str, max_chars: int = 1200) -> str:
    cleaned = (text or "").strip()
    if len(cleaned) <= max_chars:
        return cleaned
    return "...(truncated)...\n" + cleaned[-max_chars:]


def _load_approvals(path: Path) -> list[dict[str, Any]]:
    payload = _read_json(path, [])
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict) and isinstance(payload.get("approvals"), list):
        return [row for row in payload["approvals"] if isinstance(row, dict)]
    return []


def _status_snapshot(source_filter: str) -> dict[str, Any]:
    refinement_path = _latest_tool("chronicle_refinement_*.json")
    queue_path = _latest_tool("chronicle_approval_queue_*.json")
    exec_path = _latest_tool("chronicle_execution_board_*.json")
    approve_path = _latest_tool("chronicle_approve_*.json")

    refinement = _read_json(refinement_path, {}) if refinement_path else {}
    queue = _read_json(queue_path, {}) if queue_path else {}
    execution = _read_json(exec_path, {}) if exec_path else {}
    approve = _read_json(approve_path, {}) if approve_path else {}

    approvals = _load_approvals(APPROVALS_PATH)
    scoped = [row for row in approvals if str(row.get("source") or "").strip().lower() == source_filter.lower()]
    pending = [row for row in scoped if str(row.get("status") or "").strip().upper() == "PENDING_HUMAN_REVIEW"]
    approved = [row for row in scoped if str(row.get("status") or "").strip().upper() == "APPROVED"]
    queued_exec = [row for row in scoped if str(row.get("execution_status") or "").strip().upper() == "QUEUED_FOR_EXECUTION"]

    return {
        "generated_at": _now_iso(),
        "source_filter": source_filter,
        "artifacts": {
            "refinement_payload": str(refinement_path) if refinement_path else "none",
            "queue_payload": str(queue_path) if queue_path else "none",
            "execution_payload": str(exec_path) if exec_path else "none",
            "decision_payload": str(approve_path) if approve_path else "none",
        },
        "pipeline_metrics": {
            "refinement_backlog_updates": _safe_int(refinement.get("backlog_updates_count")),
            "refinement_canon_checks": _safe_int(refinement.get("canon_checks_count")),
            "queue_added_now": _safe_int(queue.get("queued_count")),
            "queue_pending_total": _safe_int(queue.get("pending_total")),
            "execution_tasks": _safe_int(execution.get("task_count")),
            "execution_marked_queued": _safe_int(execution.get("marked_queued_count")),
        },
        "approval_state": {
            "scoped_total": len(scoped),
            "pending_count": len(pending),
            "approved_count": len(approved),
            "execution_queued_count": len(queued_exec),
        },
    }


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


def _write_outputs(
    *,
    action: str,
    status_snapshot: dict[str, Any],
    run_steps: list[dict[str, Any]],
    strict: bool,
) -> tuple[Path, Path]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    TOOL_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _now().strftime("%Y%m%d-%H%M%S")
    md_path = OUTPUT_DIR / f"chronicle_control_{stamp}.md"
    latest_md = OUTPUT_DIR / "chronicle_control_latest.md"
    json_path = TOOL_DIR / f"chronicle_control_{stamp}.json"

    pipeline = status_snapshot.get("pipeline_metrics") if isinstance(status_snapshot.get("pipeline_metrics"), dict) else {}
    approvals = status_snapshot.get("approval_state") if isinstance(status_snapshot.get("approval_state"), dict) else {}
    artifacts = status_snapshot.get("artifacts") if isinstance(status_snapshot.get("artifacts"), dict) else {}

    failed = [row for row in run_steps if str(row.get("status") or "").upper() != "OK"]
    lines = [
        "# Chronicle Control",
        "",
        f"Generated (UTC): {_now_iso()}",
        f"Action: {action}",
        f"Strict mode: {strict}",
        f"Overall status: {'PASS' if not failed else 'FAIL'}",
        "",
        "## Pipeline Snapshot",
        f"- Source filter: {status_snapshot.get('source_filter')}",
        f"- Refinement backlog updates: {_safe_int(pipeline.get('refinement_backlog_updates'))}",
        f"- Refinement canon checks: {_safe_int(pipeline.get('refinement_canon_checks'))}",
        f"- Queue added now: {_safe_int(pipeline.get('queue_added_now'))}",
        f"- Queue pending total: {_safe_int(pipeline.get('queue_pending_total'))}",
        f"- Execution tasks: {_safe_int(pipeline.get('execution_tasks'))}",
        f"- Execution marked queued: {_safe_int(pipeline.get('execution_marked_queued'))}",
        "",
        "## Approval State",
        f"- Scoped total: {_safe_int(approvals.get('scoped_total'))}",
        f"- Pending: {_safe_int(approvals.get('pending_count'))}",
        f"- Approved: {_safe_int(approvals.get('approved_count'))}",
        f"- Execution queued: {_safe_int(approvals.get('execution_queued_count'))}",
        "",
        "## Artifacts",
        f"- Refinement payload: {artifacts.get('refinement_payload', 'none')}",
        f"- Queue payload: {artifacts.get('queue_payload', 'none')}",
        f"- Execution payload: {artifacts.get('execution_payload', 'none')}",
        f"- Decision payload: {artifacts.get('decision_payload', 'none')}",
        "",
        "## Run Steps",
    ]
    if not run_steps:
        lines.append("- No run steps executed (status mode).")
    for idx, row in enumerate(run_steps, start=1):
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
            "## Next Operator Step",
                (
                    "- Pending approvals remain. Run: "
                    "`python cli.py chronicle-approve --action decide --decision approve --decided-by <you>`"
                    if _safe_int(approvals.get("pending_count")) > 0
                    else "- No pending chronicle approvals right now."
                ),
            "",
            "## Governance Notes",
            "- This command orchestrates planning queues only; it does not auto-approve or auto-execute tasks.",
            "- Human decision remains required before execution board tasks can be acted on.",
            "",
        ]
    )

    report = "\n".join(lines)
    md_path.write_text(report, encoding="utf-8")
    latest_md.write_text(report, encoding="utf-8")

    payload = {
        "generated_at": _now_iso(),
        "action": action,
        "strict": bool(strict),
        "overall_status": "PASS" if not failed else "FAIL",
        "status_snapshot": status_snapshot,
        "run_steps": run_steps,
        "failed_count": len(failed),
        "latest_markdown": str(latest_md),
    }
    json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return md_path, json_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Chronicle control plane (status + local run orchestration).")
    parser.add_argument("--action", choices=["status", "run"], default="status")
    parser.add_argument("--strict", action="store_true", help="Return non-zero when run step fails")
    parser.add_argument("--timeout", type=int, default=900, help="Per-step timeout seconds")
    parser.add_argument("--source-filter", default=DEFAULT_SOURCE, help="Source filter for approval status summary")
    parser.add_argument("--skip-refinement", action="store_true", help="Skip chronicle-refinement in run mode")
    parser.add_argument("--skip-queue", action="store_true", help="Skip chronicle-approval-queue in run mode")
    parser.add_argument("--skip-execution", action="store_true", help="Skip chronicle-execution-board in run mode")
    parser.add_argument("--queue-max-items", type=int, help="Forward to chronicle-approval-queue --max-items")
    parser.add_argument("--execution-limit", type=int, help="Forward to chronicle-execution-board --limit")
    parser.add_argument("--no-canon", action="store_true", help="Forward to chronicle-execution-board --no-canon")
    args = parser.parse_args(argv)

    run_steps: list[dict[str, Any]] = []
    python_bin = sys.executable
    cli_path = str(BASE_DIR / "cli.py")

    if args.action == "run":
        steps: list[list[str]] = []
        if not args.skip_refinement:
            steps.append([python_bin, cli_path, "chronicle-refinement"])
        if not args.skip_queue:
            steps.append(
                [
                    python_bin,
                    cli_path,
                    "chronicle-approval-queue",
                    *(["--max-items", str(args.queue_max_items)] if args.queue_max_items else []),
                ]
            )
        if not args.skip_execution:
            steps.append(
                [
                    python_bin,
                    cli_path,
                    "chronicle-execution-board",
                    *(["--limit", str(args.execution_limit)] if args.execution_limit else []),
                    *(["--no-canon"] if args.no_canon else []),
                ]
            )

        for cmd in steps:
            result = _run_step(cmd, timeout_sec=max(60, int(args.timeout)))
            run_steps.append(result)
            if args.strict and str(result.get("status", "")).upper() != "OK":
                break

    snapshot = _status_snapshot(source_filter=str(args.source_filter or DEFAULT_SOURCE))
    md_path, json_path = _write_outputs(
        action=args.action,
        status_snapshot=snapshot,
        run_steps=run_steps,
        strict=args.strict,
    )
    print(f"Chronicle control written: {md_path}")
    print(f"Chronicle control latest: {OUTPUT_DIR / 'chronicle_control_latest.md'}")
    print(f"Tool payload written: {json_path}")
    failed = [row for row in run_steps if str(row.get('status') or '').upper() != 'OK']
    print(f"Run steps executed: {len(run_steps)} | failed: {len(failed)}")
    if args.strict and failed:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
