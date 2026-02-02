#!/usr/bin/env python3
"""
Show current system status (latest episodic state, recent logs, outputs count).
"""

import json
import os
from datetime import datetime, timezone

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
LOG_DIR = os.getenv("PERMANENCE_LOG_DIR", os.path.join(BASE_DIR, "logs"))
MEMORY_DIR = os.getenv("PERMANENCE_MEMORY_DIR", os.path.join(BASE_DIR, "memory"))
OUTPUT_DIR = os.getenv("PERMANENCE_OUTPUT_DIR", os.path.join(BASE_DIR, "outputs"))


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
        print(f"Goal: {state.get('task_goal')}")
    else:
        print("Latest Task: none")

    print(f"Latest Log: {os.path.basename(latest_log) if latest_log else 'none'}")

    output_count = 0
    if os.path.isdir(OUTPUT_DIR):
        output_count = len([f for f in os.listdir(OUTPUT_DIR) if f.endswith('.md')])
    print(f"Outputs: {output_count} markdown files")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
