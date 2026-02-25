#!/usr/bin/env python3
"""Run the daily promotion cycle: queue auto + promotion review."""

import argparse
import os
import subprocess
import sys

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _run(cmd: list[str]) -> int:
    env = os.environ.copy()
    current = env.get("PYTHONPATH", "")
    paths = [p for p in current.split(os.pathsep) if p]
    if BASE_DIR not in paths:
        env["PYTHONPATH"] = os.pathsep.join([BASE_DIR, *paths]) if paths else BASE_DIR
    proc = subprocess.run(cmd, cwd=BASE_DIR, env=env, text=True, capture_output=True, check=False)
    if proc.stdout:
        print(proc.stdout, end="")
    if proc.stderr:
        print(proc.stderr, end="", file=sys.stderr)
    return proc.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description="Run daily queue auto + promotion review")
    parser.add_argument("--since-hours", type=int, default=24, help="Window for queue auto candidates")
    parser.add_argument("--max-add", type=int, default=5, help="Maximum episodes to add to queue")
    parser.add_argument(
        "--reason",
        default="auto: daily gated promotion candidate",
        help="Reason text for queue entries",
    )
    parser.add_argument("--pattern", default="automation_success", help="Pattern label for queue entries")
    parser.add_argument("--allow-medium-risk", action="store_true", help="Allow MEDIUM-risk episodes")
    parser.add_argument("--min-sources", type=int, default=2, help="Minimum source count required")
    parser.add_argument("--no-require-glance-pass", action="store_true", help="Do not require status_today PASS")
    parser.add_argument("--no-require-phase-pass", action="store_true", help="Do not require latest phase gate PASS")
    parser.add_argument("--dry-run", action="store_true", help="Show queue candidates without writing")
    parser.add_argument("--output", help="Promotion review output path")
    parser.add_argument("--min-count", type=int, default=2, help="Minimum queue size target in review")
    parser.add_argument("--rubric", help="Rubric path for promotion review")
    parser.add_argument(
        "--strict-gates",
        action="store_true",
        help="Fail when queue auto is blocked by governance gates",
    )

    args = parser.parse_args()

    queue_cmd = [
        sys.executable,
        os.path.join(BASE_DIR, "scripts", "promotion_queue.py"),
        "auto",
        "--since-hours",
        str(args.since_hours),
        "--max-add",
        str(args.max_add),
        "--reason",
        args.reason,
        "--pattern",
        args.pattern,
        "--min-sources",
        str(args.min_sources),
        *(["--allow-medium-risk"] if args.allow_medium_risk else []),
        *(["--no-require-glance-pass"] if args.no_require_glance_pass else []),
        *(["--no-require-phase-pass"] if args.no_require_phase_pass else []),
        *(["--dry-run"] if args.dry_run else []),
    ]
    queue_rc = _run(queue_cmd)
    if queue_rc not in {0, 3}:
        print(f"promotion-daily: queue auto failed with exit code {queue_rc}")
        return queue_rc
    if queue_rc == 3 and args.strict_gates:
        print("promotion-daily: queue auto blocked by governance gates (strict mode)")
        return 3

    review_cmd = [
        sys.executable,
        os.path.join(BASE_DIR, "scripts", "promotion_review.py"),
        "--min-count",
        str(args.min_count),
        *(["--output", args.output] if args.output else []),
        *(["--rubric", args.rubric] if args.rubric else []),
    ]
    review_rc = _run(review_cmd)
    if review_rc != 0:
        print(f"promotion-daily: promotion review failed with exit code {review_rc}")
        return review_rc

    if queue_rc == 3:
        print("promotion-daily: queue auto skipped by governance gates; review generated from existing queue")
    else:
        print("promotion-daily: completed queue auto and promotion review")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
