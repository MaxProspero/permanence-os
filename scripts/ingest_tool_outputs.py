#!/usr/bin/env python3
"""
Ingest tool outputs into memory/working/sources.json.
"""

import argparse
import os

from agents.researcher import ResearcherAgent, TOOL_DIR
from agents.utils import BASE_DIR


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest tool outputs into sources.json")
    parser.add_argument("--tool-dir", default=TOOL_DIR, help="Tool memory directory")
    parser.add_argument(
        "--output",
        default=os.path.join(BASE_DIR, "memory", "working", "sources.json"),
        help="Output sources.json path",
    )
    parser.add_argument("--confidence", type=float, default=0.5, help="Default confidence")
    parser.add_argument("--max", type=int, default=100, help="Max entries")

    args = parser.parse_args()
    ra = ResearcherAgent()
    ra.compile_sources_from_tool_memory(
        tool_dir=args.tool_dir,
        output_path=args.output,
        default_confidence=args.confidence,
        max_entries=args.max,
    )
    print(f"Sources written to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
