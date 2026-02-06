#!/usr/bin/env python3
"""
Generate a governed synthesis brief (draft + optional approval).
"""

from __future__ import annotations

import argparse
import os
import sys

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(BASE_DIR)

from agents.synthesis_agent import SynthesisAgent  # noqa: E402
from agents.utils import log  # noqa: E402


def _prompt_approve(draft_path: str) -> bool:
    try:
        answer = input(f"Review draft at {draft_path}. Approve? (y/n): ").strip().lower()
    except EOFError:
        return False
    return answer in {"y", "yes"}


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a governed synthesis brief")
    parser.add_argument(
        "--days",
        type=int,
        default=30,
        choices=[7, 30, 90],
        help="Lookback window for sources (7, 30, 90)",
    )
    parser.add_argument("--max-sources", type=int, default=50, help="Max sources to include")
    parser.add_argument(
        "--no-prompt",
        action="store_true",
        help="Skip approval prompt (leave draft only)",
    )
    parser.add_argument(
        "--approve",
        action="store_true",
        help="Auto-approve draft into final",
    )
    args = parser.parse_args()

    agent = SynthesisAgent(days=args.days, max_sources=args.max_sources)
    try:
        draft_path, final_path = agent.generate(auto_detect=True)
    except Exception as exc:
        log(f"Synthesis generation failed: {exc}", level="ERROR")
        print(f"Error: {exc}")
        return 1

    print(f"Synthesis draft written to {draft_path}")

    if args.approve:
        agent.approve(draft_path, final_path)
        print(f"Synthesis final written to {final_path}")
        return 0

    if args.no_prompt:
        log("Approval prompt skipped; draft retained only.", level="INFO")
        return 0

    if sys.stdin.isatty():
        if _prompt_approve(str(draft_path)):
            agent.approve(draft_path, final_path)
            print(f"Synthesis final written to {final_path}")
        else:
            print("Draft retained; not approved.")
    else:
        log("Non-interactive session; draft retained only.", level="INFO")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
