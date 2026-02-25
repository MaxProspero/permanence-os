#!/usr/bin/env python3
"""
Manage a promotion queue for Canon change consideration.
"""

import argparse
import json
import os
import re
from datetime import datetime, timedelta, timezone
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
STATUS_JSON_PATH = os.getenv("PERMANENCE_STATUS_TODAY_JSON", os.path.join(LOG_DIR, "status_today.json"))
PHASE_RESULT_RE = re.compile(r"- Phase gate:\s*(PASS|FAIL)")


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


def _all_episodes() -> List[Dict[str, Any]]:
    if not os.path.isdir(EPISODIC_DIR):
        return []
    records: List[Dict[str, Any]] = []
    for name in os.listdir(EPISODIC_DIR):
        if not name.endswith(".json"):
            continue
        path = os.path.join(EPISODIC_DIR, name)
        try:
            with open(path, "r") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(data, dict):
            continue
        sort_ts = _parse_dt(data.get("updated_at")) or _parse_dt(data.get("created_at"))
        if sort_ts is None:
            sort_ts = datetime.fromtimestamp(os.path.getmtime(path), tz=timezone.utc)
        records.append({"data": data, "path": path, "sort_ts": sort_ts})
    records.sort(key=lambda r: r["sort_ts"], reverse=True)
    return records


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _candidate_log_dirs() -> List[str]:
    storage_root = os.getenv("PERMANENCE_STORAGE_ROOT", os.path.join(BASE_DIR, "permanence_storage"))
    status_parent = os.path.dirname(STATUS_JSON_PATH)
    raw_candidates = [
        LOG_DIR,
        status_parent,
        os.path.join(os.path.expanduser(storage_root), "logs"),
        os.path.join(BASE_DIR, "permanence_storage", "logs"),
    ]
    deduped: List[str] = []
    seen: set[str] = set()
    for candidate in raw_candidates:
        path = os.path.abspath(os.path.expanduser(candidate))
        if path in seen:
            continue
        seen.add(path)
        deduped.append(path)
    return deduped


def _load_today_state(path: str) -> Optional[str]:
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    return str(data.get("today_state", "")).upper() or None


def _glance_passes(status_json_path: str) -> bool:
    candidates = [status_json_path]
    for log_dir in _candidate_log_dirs():
        candidate = os.path.join(log_dir, "status_today.json")
        if candidate not in candidates:
            candidates.append(candidate)
    for candidate in candidates:
        today_state = _load_today_state(candidate)
        if today_state is None:
            continue
        return today_state == "PASS"
    return False


def _phase_gate_passes(log_dir: str) -> bool:
    candidate_dirs = [log_dir, *_candidate_log_dirs()]
    paths: List[str] = []
    for candidate_dir in candidate_dirs:
        if not os.path.isdir(candidate_dir):
            continue
        for name in os.listdir(candidate_dir):
            if name.startswith("phase_gate_") and name.endswith(".md"):
                paths.append(os.path.join(candidate_dir, name))
    if not paths:
        return False
    paths.sort(key=lambda p: os.path.getmtime(p), reverse=True)
    latest = paths[0]
    try:
        with open(latest, "r") as f:
            text = f.read()
    except OSError:
        return False
    match = PHASE_RESULT_RE.search(text)
    return bool(match and match.group(1) == "PASS")


def _episode_eligible(
    episode: Dict[str, Any],
    allow_medium_risk: bool,
    min_sources: int,
) -> tuple[bool, str]:
    status = str(episode.get("status", "")).upper()
    stage = str(episode.get("stage", "")).upper()
    risk = str(episode.get("risk_tier", "")).upper()
    escalation = episode.get("escalation")
    sources = episode.get("sources")
    source_count = len(sources) if isinstance(sources, list) else 0

    if status != "DONE" or stage != "DONE":
        return False, "episode not complete"
    if escalation:
        return False, "episode escalated"
    if risk not in {"LOW", "MEDIUM"}:
        return False, f"risk tier {risk or 'UNKNOWN'} not eligible"
    if risk == "MEDIUM" and not allow_medium_risk:
        return False, "medium risk blocked by policy"
    if source_count < min_sources:
        return False, f"insufficient sources ({source_count}<{min_sources})"
    return True, ""


def auto_add_entries(
    *,
    since_hours: int,
    max_add: int,
    reason: str,
    pattern: str,
    allow_medium_risk: bool,
    min_sources: int,
    require_glance_pass: bool,
    require_phase_pass: bool,
    dry_run: bool,
) -> int:
    queue = _load_queue()
    existing_ids = {entry.get("task_id") for entry in queue}
    now = datetime.now(timezone.utc)

    gate_failures: List[str] = []
    if require_glance_pass and not _glance_passes(STATUS_JSON_PATH):
        gate_failures.append("status_today.json gate is not PASS")
    if require_phase_pass and not _phase_gate_passes(LOG_DIR):
        gate_failures.append("latest phase gate is not PASS")
    if gate_failures:
        print("Auto promotion blocked:")
        for msg in gate_failures:
            print(f"- {msg}")
        return 3

    cutoff = now
    if since_hours > 0:
        cutoff = now - timedelta(hours=since_hours)

    added = 0
    skipped = 0
    for record in _all_episodes():
        if added >= max_add:
            break
        episode = record["data"]
        if since_hours > 0 and record["sort_ts"] < cutoff:
            continue
        task_id = episode.get("task_id")
        if not task_id:
            skipped += 1
            continue
        if task_id in existing_ids:
            skipped += 1
            continue
        ok, _skip_reason = _episode_eligible(
            episode,
            allow_medium_risk=allow_medium_risk,
            min_sources=min_sources,
        )
        if not ok:
            skipped += 1
            continue

        entry = {
            "task_id": task_id,
            "goal": episode.get("task_goal", ""),
            "stage": episode.get("stage"),
            "status": episode.get("status"),
            "risk_tier": episode.get("risk_tier"),
            "added_at": now.isoformat(),
            "reason": reason,
            "pattern": pattern or "auto_promotion_candidate",
            "auto": True,
        }
        if dry_run:
            print(f"[DRY RUN] would add: {task_id} ({entry['pattern']})")
        else:
            queue.append(entry)
            log(f"Promotion queue auto add: {task_id}")
        existing_ids.add(task_id)
        added += 1

    if not dry_run:
        if len(queue) > MAX_QUEUE:
            queue = queue[-MAX_QUEUE:]
            log(f"Promotion queue trimmed to max size {MAX_QUEUE}", level="WARNING")
        _save_queue(queue)
    print(f"Auto promotion candidates added: {added} | skipped: {skipped}")
    return 0


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

    auto_p = sub.add_parser("auto", help="Auto-enqueue eligible episodes with governance gates")
    auto_p.add_argument("--since-hours", type=int, default=24, help="Only consider episodes updated within N hours (0 for all)")
    auto_p.add_argument("--max-add", type=int, default=5, help="Maximum episodes to add")
    auto_p.add_argument("--reason", default="auto: gated promotion candidate", help="Reason text for queue entry")
    auto_p.add_argument("--pattern", default="automation_success", help="Pattern label")
    auto_p.add_argument("--allow-medium-risk", action="store_true", help="Allow MEDIUM-risk episodes (LOW always allowed)")
    auto_p.add_argument("--min-sources", type=int, default=2, help="Minimum source count required")
    auto_p.add_argument("--no-require-glance-pass", action="store_true", help="Do not require status_today PASS")
    auto_p.add_argument("--no-require-phase-pass", action="store_true", help="Do not require latest phase gate PASS")
    auto_p.add_argument("--dry-run", action="store_true", help="Show candidates without writing queue")
    auto_p.set_defaults(
        func=lambda args: auto_add_entries(
            since_hours=args.since_hours,
            max_add=args.max_add,
            reason=args.reason,
            pattern=args.pattern,
            allow_medium_risk=args.allow_medium_risk,
            min_sources=args.min_sources,
            require_glance_pass=not args.no_require_glance_pass,
            require_phase_pass=not args.no_require_phase_pass,
            dry_run=args.dry_run,
        )
    )

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
