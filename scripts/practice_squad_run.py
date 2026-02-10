#!/usr/bin/env python3
"""
Run Practice Squad scrimmage or hyper-sim.
"""

from __future__ import annotations

import argparse
import os
import sys

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(BASE_DIR)

from special.practice_squad import PracticeSquad  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Practice Squad")
    parser.add_argument("--mode", choices=["scrimmage", "hyper-sim"], default="scrimmage")
    parser.add_argument("--last-hours", type=int, default=24, help="Lookback window for scrimmage")
    parser.add_argument("--replays", type=int, default=10, help="Replay count per entry")
    parser.add_argument("--iterations", type=int, default=10000, help="Hyper-sim iterations")
    parser.add_argument("--warp-speed", action="store_true", help="Enable hyper-chamber mode")
    args = parser.parse_args()

    squad = PracticeSquad()
    if args.mode == "scrimmage":
        result = squad.scrimmage(last_hours=args.last_hours, replays=args.replays)
    else:
        result = squad.hyper_sim(
            iterations=args.iterations, warp_speed=args.warp_speed, last_hours=args.last_hours
        )
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
