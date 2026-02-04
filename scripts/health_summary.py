#!/usr/bin/env python3
"""
Run the Health Agent summary and write report to outputs.
"""

import argparse
import os
import sys

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(BASE_DIR)

from agents.departments.health_agent import HealthAgent  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Health Agent summary")
    parser.add_argument("--data-dir", help="Health data directory (default: memory/working/health)")
    parser.add_argument("--max-days", type=int, default=14, help="Max days to analyze")
    args = parser.parse_args()

    agent = HealthAgent()
    task = {
        "data_dir": args.data_dir,
        "max_days": args.max_days,
    }
    result = agent.execute(task)
    for note in result.notes:
        print(note)
    return 0 if result.status in {"SUMMARIZED", "NO_DATA"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
