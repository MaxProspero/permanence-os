#!/usr/bin/env python3
"""
Generate a Canon promotion review checklist from the queue.
"""

import argparse
import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MEMORY_DIR = os.getenv("PERMANENCE_MEMORY_DIR", os.path.join(BASE_DIR, "memory"))
EPISODIC_DIR = os.path.join(MEMORY_DIR, "episodic")
QUEUE_PATH = os.getenv(
    "PERMANENCE_PROMOTION_QUEUE",
    os.path.join(MEMORY_DIR, "working", "promotion_queue.json"),
)
OUTPUT_DIR = os.getenv("PERMANENCE_OUTPUT_DIR", os.path.join(BASE_DIR, "outputs"))
DEFAULT_OUTPUT = os.getenv(
    "PERMANENCE_PROMOTION_REVIEW_OUTPUT",
    os.path.join(OUTPUT_DIR, "promotion_review.md"),
)
RUBRIC_PATH = os.getenv(
    "PERMANENCE_PROMOTION_RUBRIC", os.path.join(BASE_DIR, "docs", "promotion_rubric.md")
)


def _load_queue() -> List[Dict[str, Any]]:
    if not os.path.exists(QUEUE_PATH):
        return []
    with open(QUEUE_PATH, "r") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError("Queue file must contain a list")
    return data


def _load_episode(task_id: str) -> Dict[str, Any]:
    path = os.path.join(EPISODIC_DIR, f"{task_id}.json")
    if not os.path.exists(path):
        return {}
    with open(path, "r") as f:
        return json.load(f)


def _render_checklist(queue: List[Dict[str, Any]], min_count: int, rubric: str) -> str:
    now = datetime.now(timezone.utc).isoformat()
    lines: List[str] = []
    lines.append("# Canon Promotion Review")
    lines.append("")
    lines.append(f"Generated (UTC): {now}")
    lines.append("")

    lines.append("## Queue Summary")
    lines.append(f"- Queue items: {len(queue)}")
    lines.append(f"- Minimum required for pattern promotion: {min_count}")
    lines.append(f"- Requirement met: {'YES' if len(queue) >= min_count else 'NO'}")
    lines.append("")

    lines.append("## Episodes")
    if not queue:
        lines.append("- None")
    else:
        for entry in queue:
            task_id = entry.get("task_id", "unknown")
            episode = _load_episode(task_id)
            status = episode.get("status", "unknown")
            stage = episode.get("stage", "unknown")
            goal = episode.get("task_goal", entry.get("goal", ""))
            lines.append(f"- {task_id} | {status}/{stage} | {goal}")
            if entry.get("reason"):
                lines.append(f"  - Reason: {entry.get('reason')}")
    lines.append("")

    lines.append("## Checklist (Preflight)")
    lines.append("- [ ] Pattern appears in at least two independent episodes")
    lines.append("- [ ] Impact is concrete and documented")
    lines.append("- [ ] Proposed rule can be expressed as invariant/heuristic/tradeoff/value")
    lines.append("- [ ] No conflicts with existing Canon values/invariants")
    lines.append("- [ ] Rollback plan defined")
    lines.append("- [ ] Changelog entry prepared")
    lines.append("- [ ] Human approval scheduled")
    lines.append("")

    if rubric:
        lines.append("## Promotion Rubric")
        lines.append(rubric.strip())
        lines.append("")

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate Canon promotion review checklist")
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help="Output markdown path")
    parser.add_argument("--min-count", type=int, default=2, help="Minimum queue size")
    parser.add_argument("--rubric", default=RUBRIC_PATH, help="Rubric path")

    args = parser.parse_args()
    queue = _load_queue()
    rubric = ""
    if args.rubric and os.path.exists(args.rubric):
        with open(args.rubric, "r") as f:
            rubric = f.read()

    report = _render_checklist(queue, args.min_count, rubric)
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, "w") as f:
        f.write(report)

    print(f"Promotion review written to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
