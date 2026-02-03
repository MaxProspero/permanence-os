#!/usr/bin/env python3
"""
Run the Briefing Agent and write its notes to outputs.
"""

import argparse
import os
import sys
from datetime import datetime, timezone

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(BASE_DIR)

from agents.departments.briefing_agent import BriefingAgent  # noqa: E402
from scripts.openclaw_status import capture_openclaw_status  # noqa: E402


def _default_output_path() -> str:
    output_dir = os.getenv("PERMANENCE_OUTPUT_DIR", os.path.join(BASE_DIR, "outputs"))
    os.makedirs(output_dir, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return os.path.join(output_dir, f"briefing_{stamp}.md")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Briefing Agent")
    parser.add_argument("--output", help="Output path (default: outputs/briefing_*.md)")
    args = parser.parse_args()

    capture_openclaw_status()
    capture_openclaw_status(health=True)
    briefing = BriefingAgent()
    result = briefing.execute({})
    output_path = args.output or _default_output_path()
    with open(output_path, "w") as f:
        f.write("\n".join(result.notes) + "\n")

    print(f"Briefing written to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
