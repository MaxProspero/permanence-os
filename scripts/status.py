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


if __name__ == "__main__":
    raise SystemExit(main())
