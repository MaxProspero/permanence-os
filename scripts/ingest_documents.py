#!/usr/bin/env python3
"""
Ingest local documents into memory/working/sources.json.
"""

import argparse
import os

from agents.researcher import ResearcherAgent, DOC_DIR
from agents.utils import BASE_DIR


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest documents into sources.json")
    parser.add_argument("--doc-dir", default=DOC_DIR, help="Document directory")
    parser.add_argument(
        "--output",
        default=os.path.join(BASE_DIR, "memory", "working", "sources.json"),
        help="Output sources.json path",
    )
    parser.add_argument("--confidence", type=float, default=0.6, help="Default confidence")
    parser.add_argument("--max", type=int, default=100, help="Max entries")
    parser.add_argument("--excerpt", type=int, default=280, help="Excerpt length")

    args = parser.parse_args()
    ra = ResearcherAgent()
    ra.compile_sources_from_documents(
        doc_dir=args.doc_dir,
        output_path=args.output,
        default_confidence=args.confidence,
        max_entries=args.max,
        excerpt_chars=args.excerpt,
    )
    print(f"Sources written to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
