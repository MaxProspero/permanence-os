#!/usr/bin/env python3
"""
Show current system status (latest episodic state, recent logs, outputs count).
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
LOG_DIR = os.getenv("PERMANENCE_LOG_DIR", os.path.join(BASE_DIR, "logs"))
MEMORY_DIR = os.getenv("PERMANENCE_MEMORY_DIR", os.path.join(BASE_DIR, "memory"))
OUTPUT_DIR = os.getenv("PERMANENCE_OUTPUT_DIR", os.path.join(BASE_DIR, "outputs"))
QUEUE_PATH = os.getenv(
    "PERMANENCE_PROMOTION_QUEUE", os.path.join(MEMORY_DIR, "working", "promotion_queue.json")
)
STATUS_JSON_PATH = os.getenv("PERMANENCE_STATUS_TODAY_JSON", os.path.join(LOG_DIR, "status_today.json"))
PROMOTION_REVIEW_PATH = os.getenv(
    "PERMANENCE_PROMOTION_REVIEW_OUTPUT",
    os.path.join(OUTPUT_DIR, "promotion_review.md"),
)


def _latest_file(path: str, ext: str) -> str:
    if not os.path.isdir(path):
        return ""
    files = [f for f in os.listdir(path) if f.endswith(ext)]
    if not files:
        return ""
    files.sort(key=lambda f: os.path.getmtime(os.path.join(path, f)), reverse=True)
    return os.path.join(path, files[0])


def main() -> int:
    episodic_path = os.path.join(MEMORY_DIR, "episodic")
    latest_state = _latest_file(episodic_path, ".json")
    latest_log = _latest_file(LOG_DIR, ".log")

    print("Permanence OS Status")
    print("=====================")
    print(f"Time (UTC): {datetime.now(timezone.utc).isoformat()}")

    if latest_state:
        with open(latest_state, "r") as f:
            state = json.load(f)
        print(f"Latest Task: {state.get('task_id', 'unknown')}")
        print(f"Stage/Status: {state.get('stage')} / {state.get('status')}")
        print(f"Risk Tier: {state.get('risk_tier', 'unknown')}")
        print(f"Goal: {state.get('task_goal')}")
        artifacts = state.get("artifacts", {}) if isinstance(state.get("artifacts"), dict) else {}
        model_routes = artifacts.get("model_routes") if isinstance(artifacts, dict) else None
        if isinstance(model_routes, dict) and model_routes:
            print(f"Model Routes: {_format_model_routes(model_routes)}")
        if artifacts.get("single_source_override"):
            print("Single-Source Override: True")
    else:
        print("Latest Task: none")

    print(f"Latest Log: {os.path.basename(latest_log) if latest_log else 'none'}")

    output_count = 0
    if os.path.isdir(OUTPUT_DIR):
        output_count = len([f for f in os.listdir(OUTPUT_DIR) if f.endswith('.md')])
    print(f"Outputs: {output_count} markdown files")

    openclaw_status = _latest_openclaw_status()
    if openclaw_status:
        print(f"OpenClaw Status: {openclaw_status}")

    queue_count = 0
    if os.path.exists(QUEUE_PATH):
        try:
            with open(QUEUE_PATH, "r") as f:
                data = json.load(f)
            if isinstance(data, list):
                queue_count = len(data)
        except (json.JSONDecodeError, OSError):
            queue_count = 0
    print(f"Promotion Queue: {queue_count} items")
    glance_state = _latest_glance_state()
    phase_state = _latest_phase_gate_state()
    print(f"Promotion Gates: glance={glance_state} | phase={phase_state}")
    review_info = _promotion_review_info()
    if review_info:
        print(f"Promotion Review: {review_info}")
    model_assist = os.getenv("PERMANENCE_ENABLE_MODEL_ASSIST", "").lower() in {"1", "true", "yes", "on"}
    print(f"Model Assist: {'enabled' if model_assist else 'disabled'}")

    return 0


def _latest_openclaw_status() -> str:
    output_dir = os.getenv("PERMANENCE_OUTPUT_DIR", os.path.join(BASE_DIR, "outputs"))
    try:
        candidates = sorted(
            Path(output_dir).glob("openclaw_status_*.txt"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
    except FileNotFoundError:
        return ""
    if not candidates:
        return ""
    return str(candidates[0])


def _format_model_routes(routes: dict) -> str:
    preferred = ["planning", "research", "execution", "review", "conciliation"]
    ordered_keys = [k for k in preferred if k in routes]
    extras = sorted([k for k in routes.keys() if k not in ordered_keys])
    keys = [*ordered_keys, *extras]
    parts = [f"{k}={routes[k]}" for k in keys]
    return ", ".join(parts)


def _candidate_log_dirs() -> list[Path]:
    storage_root = os.getenv("PERMANENCE_STORAGE_ROOT", os.path.join(BASE_DIR, "permanence_storage"))
    explicit_parent = os.path.dirname(STATUS_JSON_PATH)
    raw = [
        LOG_DIR,
        explicit_parent,
        os.path.join(os.path.expanduser(storage_root), "logs"),
        os.path.join(BASE_DIR, "permanence_storage", "logs"),
    ]
    deduped: list[Path] = []
    seen: set[str] = set()
    for candidate in raw:
        path = Path(os.path.abspath(os.path.expanduser(candidate)))
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(path)
    return deduped


def _latest_glance_state() -> str:
    candidates: list[Path] = [Path(os.path.expanduser(STATUS_JSON_PATH))]
    for log_dir in _candidate_log_dirs():
        candidate = log_dir / "status_today.json"
        if candidate not in candidates:
            candidates.append(candidate)

    latest_match: tuple[float, str] | None = None
    for path in candidates:
        if not path.exists():
            continue
        try:
            payload = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        if not isinstance(payload, dict):
            continue
        state = str(payload.get("today_state", "")).upper()
        if not state:
            continue
        mtime = path.stat().st_mtime
        if latest_match is None or mtime > latest_match[0]:
            latest_match = (mtime, state)
    return latest_match[1] if latest_match else "PENDING"


def _latest_phase_gate_state() -> str:
    latest_match: tuple[float, str] | None = None
    for log_dir in _candidate_log_dirs():
        if not log_dir.is_dir():
            continue
        for path in log_dir.glob("phase_gate_*.md"):
            try:
                text = path.read_text(errors="ignore")
            except OSError:
                continue
            if "- Phase gate: PASS" in text:
                state = "PASS"
            elif "- Phase gate: FAIL" in text:
                state = "FAIL"
            else:
                state = "PENDING"
            mtime = path.stat().st_mtime
            if latest_match is None or mtime > latest_match[0]:
                latest_match = (mtime, state)
    return latest_match[1] if latest_match else "PENDING"


def _promotion_review_info() -> str:
    candidates = [
        Path(os.path.expanduser(PROMOTION_REVIEW_PATH)),
        Path(OUTPUT_DIR) / "promotion_review.md",
        Path(BASE_DIR) / "outputs" / "promotion_review.md",
        Path(BASE_DIR) / "permanence_storage" / "outputs" / "promotion_review.md",
    ]
    seen: set[str] = set()
    existing: list[Path] = []
    for path in candidates:
        key = str(path.resolve()) if path.exists() else str(path)
        if key in seen:
            continue
        seen.add(key)
        if path.exists():
            existing.append(path)
    if not existing:
        return ""
    latest = max(existing, key=lambda p: p.stat().st_mtime)
    updated = datetime.fromtimestamp(latest.stat().st_mtime, tz=timezone.utc).isoformat()
    return f"{latest.name} ({updated})"


if __name__ == "__main__":
    raise SystemExit(main())
