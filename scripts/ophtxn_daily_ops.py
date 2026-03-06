#!/usr/bin/env python3
"""
Generate no-spend daily operating briefs for Ophtxn (morning/midday/evening).
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parents[1]


def _load_local_env() -> None:
    env_path = BASE_DIR / ".env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key or key in os.environ:
            continue
        value = value.strip()
        if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
            value = value[1:-1]
        os.environ[key] = value


_load_local_env()

OUTPUT_DIR = Path(os.getenv("PERMANENCE_OUTPUT_DIR", str(BASE_DIR / "outputs")))
TOOL_DIR = Path(os.getenv("PERMANENCE_TOOL_DIR", str(BASE_DIR / "memory" / "tool")))
WORKING_DIR = Path(os.getenv("PERMANENCE_WORKING_DIR", str(BASE_DIR / "memory" / "working")))
QUEUE_PATH = Path(
    os.getenv(
        "PERMANENCE_TERMINAL_TASK_QUEUE_PATH",
        str(WORKING_DIR / "telegram_terminal_tasks.jsonl"),
    )
)
APPROVALS_PATH = Path(os.getenv("PERMANENCE_APPROVALS_PATH", str(BASE_DIR / "memory" / "approvals.json")))


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now().isoformat()


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _is_true(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default
    return payload


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def _latest_tool_path(prefix: str) -> Path | None:
    if not TOOL_DIR.exists():
        return None
    rows = sorted(TOOL_DIR.glob(f"{prefix}_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    return rows[0] if rows else None


def _age_minutes(path: Path | None) -> int:
    if path is None or (not path.exists()):
        return -1
    try:
        seconds = max(0.0, _now().timestamp() - path.stat().st_mtime)
    except OSError:
        return -1
    return int(seconds // 60)


def _queue_metrics(path: Path, max_items: int) -> dict[str, Any]:
    rows = _read_jsonl(path)
    pending_rows = [row for row in rows if str(row.get("status") or "PENDING").strip().upper() != "DONE"]
    done_rows = [row for row in rows if str(row.get("status") or "").strip().upper() == "DONE"]
    recent_pending: list[dict[str, str]] = []
    for row in reversed(pending_rows[-max(1, int(max_items)) :]):
        task_id = str(row.get("task_id") or "TERM-UNKNOWN").strip()
        text = " ".join(str(row.get("text") or "").split())
        if len(text) > 120:
            text = text[:117].rstrip() + "..."
        recent_pending.append({"task_id": task_id, "text": text})
    return {
        "path": str(path),
        "total": len(rows),
        "pending": len(pending_rows),
        "done": len(done_rows),
        "recent_pending": recent_pending,
    }


def _approvals_metrics(path: Path, max_items: int) -> dict[str, Any]:
    payload = _read_json(path, [])
    rows: list[dict[str, Any]] = []
    if isinstance(payload, list):
        rows = [row for row in payload if isinstance(row, dict)]
    elif isinstance(payload, dict) and isinstance(payload.get("approvals"), list):
        rows = [row for row in payload.get("approvals", []) if isinstance(row, dict)]
    pending_rows = [row for row in rows if str(row.get("status") or "").strip().upper() == "PENDING_HUMAN_REVIEW"]
    approved_rows = [row for row in rows if str(row.get("status") or "").strip().upper() == "APPROVED"]
    recent_pending: list[dict[str, str]] = []
    for row in reversed(pending_rows[-max(1, int(max_items)) :]):
        item_id = str(row.get("approval_id") or row.get("proposal_id") or row.get("id") or "APPROVAL-UNKNOWN").strip()
        title = " ".join(str(row.get("title") or "").split())
        if len(title) > 120:
            title = title[:117].rstrip() + "..."
        recent_pending.append({"approval_id": item_id, "title": title})
    return {
        "path": str(path),
        "total": len(rows),
        "pending": len(pending_rows),
        "approved": len(approved_rows),
        "recent_pending": recent_pending,
    }


def _component_freshness(max_stale_minutes: int) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for prefix in ("comms_status", "comms_doctor", "chronicle_control", "low_cost_mode", "terminal_task_queue"):
        path = _latest_tool_path(prefix)
        age = _age_minutes(path)
        out[prefix] = {
            "path": str(path) if path else "",
            "age_minutes": age,
            "stale": bool(age < 0 or age > max(1, int(max_stale_minutes))),
        }
    return out


def _mode_snapshot() -> dict[str, Any]:
    provider = str(os.getenv("PERMANENCE_MODEL_PROVIDER", "anthropic")).strip().lower() or "anthropic"
    fallbacks = str(os.getenv("PERMANENCE_MODEL_PROVIDER_FALLBACKS", "")).strip() or "-"
    caps = str(os.getenv("PERMANENCE_MODEL_PROVIDER_CAPS_USD", "")).strip() or "-"
    return {
        "no_spend_mode": _is_true(os.getenv("PERMANENCE_NO_SPEND_MODE", "0")),
        "low_cost_mode": _is_true(os.getenv("PERMANENCE_LOW_COST_MODE", "0")),
        "provider": provider,
        "fallbacks": fallbacks,
        "provider_caps": caps,
    }


def _action_focus(action: str, queue: dict[str, Any], approvals: dict[str, Any], freshness: dict[str, dict[str, Any]]) -> list[str]:
    if action == "morning":
        focus = [
            "Lock no-spend mode and keep model provider on ollama before any chat runs.",
            "Clear highest-leverage terminal tasks first and keep pending queue near zero.",
            "Run comms and chronicle health checks before execution work.",
        ]
    elif action == "midday":
        focus = [
            "Do a correction pass: close stale tasks, adjust priorities, and remove dead work.",
            "Review pending approvals and decide approve/reject/defer with notes.",
            "Check freshness of comms/chronicle reports and refresh stale artifacts.",
        ]
    elif action == "evening":
        focus = [
            "Close the loop: complete remaining essential tasks or defer with explicit reason.",
            "Capture one chronicle update and review queue health for tomorrow.",
            "Confirm no-spend mode is still active for overnight automation.",
        ]
    elif action == "hygiene":
        focus = [
            "Queue hygiene pass: pending <= target and no duplicate low-signal tasks.",
            "Approval hygiene pass: process oldest pending approvals first.",
            "Freshness hygiene pass: stale status artifacts are refreshed.",
        ]
    elif action == "cycle":
        focus = [
            "Run a full-day cycle check: morning lock -> midday correction -> evening closure.",
            "Keep no-spend guardrails active for the entire cycle.",
            "Process approvals in controlled batches after queue hygiene.",
        ]
    else:
        focus = [
            "Maintain no-spend mode and local-first routing.",
            "Keep terminal queue and approvals queue controlled daily.",
            "Use freshness checks to avoid stale operating decisions.",
        ]

    if _safe_int(queue.get("pending"), 0) > 0:
        focus.append(f"Pending terminal tasks to close: {_safe_int(queue.get('pending'), 0)}.")
    if _safe_int(approvals.get("pending"), 0) > 0:
        focus.append(f"Pending approvals requiring decisions: {_safe_int(approvals.get('pending'), 0)}.")
    stale_count = sum(1 for row in freshness.values() if bool(row.get("stale")))
    if stale_count > 0:
        focus.append(f"Stale operation artifacts detected: {stale_count}. Refresh before major decisions.")
    return focus


def _write_outputs(
    *,
    action: str,
    mode: dict[str, Any],
    queue: dict[str, Any],
    approvals: dict[str, Any],
    freshness: dict[str, dict[str, Any]],
    focus: list[str],
    warnings: list[str],
    output_override: Path | None,
) -> tuple[Path, Path]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    TOOL_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _now().strftime("%Y%m%d-%H%M%S")
    md_path = output_override if output_override else OUTPUT_DIR / f"ophtxn_daily_ops_{stamp}.md"
    latest_md = OUTPUT_DIR / "ophtxn_daily_ops_latest.md"
    json_path = TOOL_DIR / f"ophtxn_daily_ops_{stamp}.json"

    lines = [
        "# Ophtxn Daily Ops",
        "",
        f"Generated (UTC): {_now_iso()}",
        f"Action: {action}",
        "",
        "## Operating Mode",
        f"- No-spend mode: {mode.get('no_spend_mode')}",
        f"- Low-cost mode: {mode.get('low_cost_mode')}",
        f"- Provider: {mode.get('provider')}",
        f"- Fallbacks: {mode.get('fallbacks')}",
        f"- Provider caps: {mode.get('provider_caps')}",
        "",
        "## Queue Metrics",
        f"- Terminal queue total: {queue.get('total')}",
        f"- Terminal queue pending: {queue.get('pending')}",
        f"- Terminal queue done: {queue.get('done')}",
        f"- Terminal queue path: {queue.get('path')}",
        f"- Approval queue total: {approvals.get('total')}",
        f"- Approval queue pending: {approvals.get('pending')}",
        f"- Approval queue approved: {approvals.get('approved')}",
        f"- Approval queue path: {approvals.get('path')}",
        "",
        "## Artifact Freshness",
    ]
    for name in ("comms_status", "comms_doctor", "chronicle_control", "low_cost_mode", "terminal_task_queue"):
        row = freshness.get(name, {})
        age = _safe_int(row.get("age_minutes"), -1)
        stale = bool(row.get("stale"))
        age_text = "missing" if age < 0 else f"{age} min"
        lines.append(f"- {name}: age={age_text}, stale={stale}")

    lines.extend(["", "## Focus"])
    for item in focus:
        lines.append(f"- {item}")

    lines.extend(["", "## Pending Terminal Tasks"])
    recent_pending = queue.get("recent_pending") if isinstance(queue.get("recent_pending"), list) else []
    if not recent_pending:
        lines.append("- No pending terminal tasks.")
    else:
        for item in recent_pending:
            if not isinstance(item, dict):
                continue
            lines.append(f"- {item.get('task_id')}: {item.get('text')}")

    lines.extend(["", "## Pending Approvals"])
    recent_approvals = approvals.get("recent_pending") if isinstance(approvals.get("recent_pending"), list) else []
    if not recent_approvals:
        lines.append("- No pending approvals.")
    else:
        for item in recent_approvals:
            if not isinstance(item, dict):
                continue
            lines.append(f"- {item.get('approval_id')}: {item.get('title') or '-'}")

    if warnings:
        lines.extend(["", "## Warnings"])
        for warning in warnings:
            lines.append(f"- {warning}")

    report = "\n".join(lines) + "\n"
    md_path.write_text(report, encoding="utf-8")
    latest_md.write_text(report, encoding="utf-8")

    payload = {
        "generated_at": _now_iso(),
        "action": action,
        "mode": mode,
        "queue": queue,
        "approvals": approvals,
        "freshness": freshness,
        "focus": focus,
        "warnings": warnings,
        "latest_markdown": str(latest_md),
    }
    json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return md_path, json_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate Ophtxn no-spend daily operating brief.")
    parser.add_argument("--action", choices=["status", "morning", "midday", "evening", "hygiene", "cycle"], default="status")
    parser.add_argument("--queue-path", help="Terminal task queue JSONL path override")
    parser.add_argument("--approvals-path", help="Approvals JSON path override")
    parser.add_argument("--target-pending", type=int, default=1, help="Target max pending terminal tasks")
    parser.add_argument("--max-items", type=int, default=5, help="Max pending queue items listed")
    parser.add_argument("--freshness-minutes", type=int, default=360, help="Max freshness age before stale")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero when hygiene checks fail")
    parser.add_argument("--output", help="Optional markdown output path")
    args = parser.parse_args(argv)

    queue_path = Path(args.queue_path).expanduser() if args.queue_path else QUEUE_PATH
    approvals_path = Path(args.approvals_path).expanduser() if args.approvals_path else APPROVALS_PATH
    output_override = Path(args.output).expanduser() if args.output else None

    mode = _mode_snapshot()
    queue = _queue_metrics(queue_path, max_items=max(1, int(args.max_items)))
    approvals = _approvals_metrics(approvals_path, max_items=max(1, int(args.max_items)))
    freshness = _component_freshness(max_stale_minutes=max(1, int(args.freshness_minutes)))
    focus = _action_focus(args.action, queue, approvals, freshness)

    warnings: list[str] = []
    if not bool(mode.get("no_spend_mode")):
        warnings.append("No-spend mode is disabled.")
    if str(mode.get("provider") or "").strip().lower() != "ollama":
        warnings.append("Provider is not set to ollama.")
    pending = _safe_int(queue.get("pending"), 0)
    if pending > max(0, int(args.target_pending)):
        warnings.append(f"Terminal queue pending {pending} exceeds target {max(0, int(args.target_pending))}.")
    stale_count = sum(1 for row in freshness.values() if bool(row.get("stale")))
    if stale_count > 0:
        warnings.append(f"{stale_count} required artifacts are stale/missing.")

    md_path, json_path = _write_outputs(
        action=args.action,
        mode=mode,
        queue=queue,
        approvals=approvals,
        freshness=freshness,
        focus=focus,
        warnings=warnings,
        output_override=output_override,
    )
    print(f"Ophtxn daily ops report: {md_path}")
    print(f"Ophtxn daily ops latest: {OUTPUT_DIR / 'ophtxn_daily_ops_latest.md'}")
    print(f"Tool payload: {json_path}")
    print(f"No-spend mode: {mode.get('no_spend_mode')}")
    print(f"Terminal queue pending: {queue.get('pending')}")
    print(f"Approvals pending: {approvals.get('pending')}")
    if warnings and args.strict:
        print(f"Warnings: {len(warnings)}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
