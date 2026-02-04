#!/usr/bin/env python3
"""
Manage a promotion queue for Canon change consideration.
"""

import argparse
import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MEMORY_DIR = os.getenv("PERMANENCE_MEMORY_DIR", os.path.join(BASE_DIR, "memory"))
EPISODIC_DIR = os.path.join(MEMORY_DIR, "episodic")
QUEUE_PATH = os.getenv(
    "PERMANENCE_PROMOTION_QUEUE",
    os.path.join(MEMORY_DIR, "working", "promotion_queue.json"),
)
LOG_DIR = os.getenv("PERMANENCE_LOG_DIR", os.path.join(BASE_DIR, "logs"))
MAX_QUEUE = int(os.getenv("PERMANENCE_PROMOTION_QUEUE_MAX", "50"))


def log(message: str, level: str = "INFO") -> None:
    timestamp = datetime.now(timezone.utc).isoformat()
    entry = f"[{timestamp}] [{level}] {message}"
    os.makedirs(LOG_DIR, exist_ok=True)
    log_file = os.path.join(LOG_DIR, f"{datetime.now(timezone.utc).strftime('%Y-%m-%d')}.log")
    with open(log_file, "a") as f:
        f.write(entry + "\n")
    print(entry)


def _load_queue() -> List[Dict[str, Any]]:
    if not os.path.exists(QUEUE_PATH):
        return []
    with open(QUEUE_PATH, "r") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError("Queue file must contain a list")
    return data


def _save_queue(queue: List[Dict[str, Any]]) -> None:
    os.makedirs(os.path.dirname(QUEUE_PATH), exist_ok=True)
    with open(QUEUE_PATH, "w") as f:
        json.dump(queue, f, indent=2)


def _latest_episode() -> Optional[Dict[str, Any]]:
    if not os.path.isdir(EPISODIC_DIR):
        return None
    files = [f for f in os.listdir(EPISODIC_DIR) if f.endswith(".json")]
    if not files:
        return None
    files.sort(key=lambda f: os.path.getmtime(os.path.join(EPISODIC_DIR, f)), reverse=True)
    path = os.path.join(EPISODIC_DIR, files[0])
    with open(path, "r") as f:
        return json.load(f)


def _episode_by_id(task_id: str) -> Optional[Dict[str, Any]]:
    path = os.path.join(EPISODIC_DIR, f"{task_id}.json")
    if not os.path.exists(path):
        return None
    with open(path, "r") as f:
        return json.load(f)


def _format_entry(entry: Dict[str, Any]) -> str:
    reason = entry.get("reason", "")
    pattern = entry.get("pattern", "")
    extra = f" | pattern: {pattern}" if pattern else ""
    return (
        f"{entry.get('task_id', 'unknown')} | {entry.get('goal', '')} | "
        f"added: {entry.get('added_at', '')} | reason: {reason}{extra}"
    )


def list_queue() -> int:
    queue = _load_queue()
    if not queue:
        print("Promotion queue is empty")
        return 0
    print("Promotion Queue")
    print("==============")
    for entry in queue:
        print("- " + _format_entry(entry))
    return 0


def add_entry(task_id: Optional[str], reason: str, latest: bool, pattern: str) -> int:
    queue = _load_queue()
    if latest:
        episode = _latest_episode()
        if not episode:
            print("No episodic entries found")
            return 2
    else:
        if not task_id:
            print("Task id required unless --latest is used")
            return 2
        episode = _episode_by_id(task_id)
        if not episode:
            print(f"Task not found: {task_id}")
            return 2

    task_id = episode.get("task_id", task_id or "unknown")
    if any(entry.get("task_id") == task_id for entry in queue):
        print(f"Task already in queue: {task_id}")
        return 0

    entry = {
        "task_id": task_id,
        "goal": episode.get("task_goal", ""),
        "stage": episode.get("stage"),
        "status": episode.get("status"),
        "risk_tier": episode.get("risk_tier"),
        "added_at": datetime.now(timezone.utc).isoformat(),
        "reason": reason,
        "pattern": pattern or "",
    }
    queue.append(entry)
    if len(queue) > MAX_QUEUE:
        queue = queue[-MAX_QUEUE:]
        log(f"Promotion queue trimmed to max size {MAX_QUEUE}", level="WARNING")
    _save_queue(queue)
    log(f"Promotion queue add: {task_id}")
    print(f"Added {task_id} to promotion queue")
    return 0


def remove_entry(task_id: str) -> int:
    queue = _load_queue()
    new_queue = [entry for entry in queue if entry.get("task_id") != task_id]
    if len(new_queue) == len(queue):
        print(f"Task not found in queue: {task_id}")
        return 2
    _save_queue(new_queue)
    log(f"Promotion queue remove: {task_id}")
    print(f"Removed {task_id} from promotion queue")
    return 0


def clear_queue() -> int:
    _save_queue([])
    log("Promotion queue cleared")
    print("Promotion queue cleared")
    return 0


def audit_queue(prune: bool) -> int:
    queue = _load_queue()
    if not queue:
        print("Promotion queue is empty")
        return 0
    missing: List[Dict[str, Any]] = []
    for entry in queue:
        task_id = entry.get("task_id")
        if not task_id or not _episode_by_id(task_id):
            missing.append(entry)

    if not missing:
        print("Promotion queue audit: no missing episodes")
        return 0

    print("Promotion queue audit: missing episodes")
    for entry in missing:
        print("- " + _format_entry(entry))

    if prune:
        remaining = [e for e in queue if e not in missing]
        _save_queue(remaining)
        log(f"Promotion queue pruned missing episodes: {len(missing)}", level="WARNING")
        print(f"Pruned {len(missing)} entries")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Manage Canon promotion queue")
    sub = parser.add_subparsers(dest="command", required=True)

    list_p = sub.add_parser("list", help="List queued episodes")
    list_p.set_defaults(func=lambda _args: list_queue())

    add_p = sub.add_parser("add", help="Add episodic task to queue")
    add_p.add_argument("--task-id", help="Task id to enqueue")
    add_p.add_argument("--latest", action="store_true", help="Use latest episodic entry")
    add_p.add_argument("--reason", default="", help="Reason for promotion consideration")
    add_p.add_argument("--pattern", default="", help="Optional pattern label")
    add_p.set_defaults(func=lambda args: add_entry(args.task_id, args.reason, args.latest, args.pattern))

    remove_p = sub.add_parser("remove", help="Remove task from queue")
    remove_p.add_argument("task_id", help="Task id to remove")
    remove_p.set_defaults(func=lambda args: remove_entry(args.task_id))

    clear_p = sub.add_parser("clear", help="Clear the queue")
    clear_p.set_defaults(func=lambda _args: clear_queue())

    audit_p = sub.add_parser("audit", help="Audit queue for missing episodes")
    audit_p.add_argument("--prune", action="store_true", help="Remove missing entries")
    audit_p.set_defaults(func=lambda args: audit_queue(args.prune))

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
