#!/usr/bin/env python3
"""
Manage queued terminal tasks captured from Telegram.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parents[1]
WORKING_DIR = Path(os.getenv("PERMANENCE_WORKING_DIR", str(BASE_DIR / "memory" / "working")))
OUTPUT_DIR = Path(os.getenv("PERMANENCE_OUTPUT_DIR", str(BASE_DIR / "outputs")))
TOOL_DIR = Path(os.getenv("PERMANENCE_TOOL_DIR", str(BASE_DIR / "memory" / "tool")))
QUEUE_PATH = Path(
    os.getenv(
        "PERMANENCE_TERMINAL_TASK_QUEUE_PATH",
        str(WORKING_DIR / "telegram_terminal_tasks.jsonl"),
    )
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now().isoformat()


def _safe_text(text: str, max_chars: int = 220) -> str:
    payload = " ".join(str(text or "").split())
    if len(payload) <= max_chars:
        return payload
    return payload[: max_chars - 3].rstrip() + "..."


def _load_rows(path: Path) -> list[dict[str, Any]]:
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


def _write_rows(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=True) + "\n")


def _task_id(text: str) -> str:
    token = f"{_now_iso()}|{text}"
    return "TERM-" + hashlib.sha1(token.encode("utf-8")).hexdigest()[:12]


def _add_task(
    *,
    path: Path,
    text: str,
    source: str,
    sender: str,
    sender_user_id: str,
    chat_id: str,
) -> tuple[bool, str]:
    payload = " ".join(str(text or "").split())
    if not payload:
        return False, "task text is required"
    row = {
        "task_id": _task_id(payload),
        "timestamp": _now_iso(),
        "status": "PENDING",
        "source": str(source or "manual").strip() or "manual",
        "sender": str(sender or "").strip(),
        "sender_user_id": str(sender_user_id or "").strip(),
        "chat_id": str(chat_id or "").strip(),
        "text": payload,
        "char_count": len(payload),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=True) + "\n")
    return True, str(row["task_id"])


def _complete_task(path: Path, task_id: str) -> tuple[bool, str]:
    token = str(task_id or "").strip()
    if not token:
        return False, "task id is required"
    rows = _load_rows(path)
    if not rows:
        return False, "queue is empty"
    matched = False
    for row in rows:
        rid = str(row.get("task_id") or "").strip()
        if rid != token:
            continue
        row["status"] = "DONE"
        row["completed_at"] = _now_iso()
        matched = True
        break
    if not matched:
        return False, f"task id not found: {token}"
    _write_rows(path, rows)
    return True, token


def _write_outputs(
    *,
    action: str,
    queue_path: Path,
    rows: list[dict[str, Any]],
    added_task_id: str,
    completed_task_id: str,
    warnings: list[str],
    limit: int,
) -> tuple[Path, Path]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    TOOL_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _now().strftime("%Y%m%d-%H%M%S")
    md_path = OUTPUT_DIR / f"terminal_task_queue_{stamp}.md"
    latest_md = OUTPUT_DIR / "terminal_task_queue_latest.md"
    json_path = TOOL_DIR / f"terminal_task_queue_{stamp}.json"

    pending = [row for row in rows if str(row.get("status") or "PENDING").strip().upper() == "PENDING"]
    done = [row for row in rows if str(row.get("status") or "").strip().upper() == "DONE"]
    head = rows[-max(1, int(limit)) :] if rows else []

    lines = [
        "# Terminal Task Queue",
        "",
        f"Generated (UTC): {_now_iso()}",
        f"Action: {action}",
        f"Queue path: {queue_path}",
        "",
        "## Summary",
        f"- Total tasks: {len(rows)}",
        f"- Pending: {len(pending)}",
        f"- Done: {len(done)}",
        f"- Added task id: {added_task_id or '-'}",
        f"- Completed task id: {completed_task_id or '-'}",
        "",
        "## Recent Tasks",
    ]
    if not head:
        lines.append("- No tasks yet.")
    for idx, row in enumerate(reversed(head), start=1):
        lines.append(
            f"{idx}. {row.get('task_id')} [{str(row.get('status') or 'PENDING').upper()}] "
            f"{_safe_text(str(row.get('text') or ''))}"
        )

    if warnings:
        lines.extend(["", "## Warnings"])
        for row in warnings:
            lines.append(f"- {row}")

    report = "\n".join(lines) + "\n"
    md_path.write_text(report, encoding="utf-8")
    latest_md.write_text(report, encoding="utf-8")

    payload = {
        "generated_at": _now_iso(),
        "action": action,
        "queue_path": str(queue_path),
        "task_count": len(rows),
        "pending_count": len(pending),
        "done_count": len(done),
        "added_task_id": added_task_id,
        "completed_task_id": completed_task_id,
        "warnings": warnings,
        "recent_tasks": head,
        "latest_markdown": str(latest_md),
    }
    json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return md_path, json_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Manage queued terminal tasks from Telegram.")
    parser.add_argument("--action", choices=["status", "list", "add", "complete"], default="status")
    parser.add_argument("--queue-path", help="Override queue JSONL path")
    parser.add_argument("--text", help="Task text for add action")
    parser.add_argument("--task-id", help="Task id for complete action")
    parser.add_argument("--source", default="manual", help="Task source label")
    parser.add_argument("--sender", default="", help="Sender label")
    parser.add_argument("--sender-user-id", default="", help="Sender user id")
    parser.add_argument("--chat-id", default="", help="Chat id")
    parser.add_argument("--limit", type=int, default=12, help="Recent rows to include in report")
    args = parser.parse_args(argv)

    queue_path = Path(args.queue_path).expanduser() if args.queue_path else QUEUE_PATH
    warnings: list[str] = []
    added_task_id = ""
    completed_task_id = ""

    if args.action == "add":
        ok, detail = _add_task(
            path=queue_path,
            text=str(args.text or ""),
            source=str(args.source or "manual"),
            sender=str(args.sender or ""),
            sender_user_id=str(args.sender_user_id or ""),
            chat_id=str(args.chat_id or ""),
        )
        if ok:
            added_task_id = detail
        else:
            warnings.append(detail)
    if args.action == "complete":
        ok, detail = _complete_task(queue_path, str(args.task_id or ""))
        if ok:
            completed_task_id = detail
        else:
            warnings.append(detail)

    rows = _load_rows(queue_path)
    md_path, json_path = _write_outputs(
        action=args.action,
        queue_path=queue_path,
        rows=rows,
        added_task_id=added_task_id,
        completed_task_id=completed_task_id,
        warnings=warnings,
        limit=max(1, int(args.limit)),
    )
    print(f"Terminal task queue report: {md_path}")
    print(f"Terminal task queue latest: {OUTPUT_DIR / 'terminal_task_queue_latest.md'}")
    print(f"Tool payload: {json_path}")
    print(f"Tasks total: {len(rows)}")
    print(f"Pending: {sum(1 for row in rows if str(row.get('status') or 'PENDING').upper() == 'PENDING')}")
    if warnings:
        print(f"Warnings: {len(warnings)}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
