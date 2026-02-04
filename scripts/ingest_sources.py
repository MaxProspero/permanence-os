#!/usr/bin/env python3
"""
Unified ingestion entrypoint using Researcher adapter registry.
"""

import argparse
import os

from agents.researcher_adapters import list_adapters, run_adapter
from agents.researcher import TOOL_DIR, DOC_DIR
from agents.utils import BASE_DIR


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest sources via adapter registry")
    parser.add_argument("--adapter", default="tool_memory", help="Adapter name")
    parser.add_argument("--list", action="store_true", help="List available adapters")
    parser.add_argument("--urls", nargs="*", help="URLs to fetch (url_fetch adapter)")
    parser.add_argument("--urls-path", help="File containing URLs (url_fetch adapter)")
    parser.add_argument("--query", help="Search query (web_search adapter)")
    parser.add_argument("--tool-dir", default=TOOL_DIR, help="Tool memory directory")
    parser.add_argument("--doc-dir", default=DOC_DIR, help="Documents directory")
    parser.add_argument(
        "--output",
        default=os.path.join(BASE_DIR, "memory", "working", "sources.json"),
        help="Output sources.json path",
    )
    parser.add_argument("--confidence", type=float, default=0.5, help="Default confidence")
    parser.add_argument("--max", type=int, default=100, help="Max entries")
    parser.add_argument("--excerpt", type=int, default=280, help="Excerpt length")
    parser.add_argument("--timeout", type=int, default=20, help="Web search timeout (seconds)")
    parser.add_argument("--timeout", type=int, default=15, help="URL fetch timeout (seconds)")
    parser.add_argument("--max-bytes", type=int, default=1_000_000, help="Max bytes per URL")
    parser.add_argument("--user-agent", default="PermanenceOS-Researcher/0.2", help="URL fetch user agent")

    args = parser.parse_args()

    if args.list:
        for adapter in list_adapters():
            print(f"{adapter.name}: {adapter.description} (default confidence {adapter.default_confidence})")
        return 0

    if args.adapter == "tool_memory":
        run_adapter(
            "tool_memory",
            tool_dir=args.tool_dir,
            output_path=args.output,
            default_confidence=args.confidence,
            max_entries=args.max,
        )
    elif args.adapter == "documents":
        run_adapter(
            "documents",
            doc_dir=args.doc_dir,
            output_path=args.output,
            default_confidence=args.confidence,
            max_entries=args.max,
            excerpt_chars=args.excerpt,
        )
    elif args.adapter == "url_fetch":
        run_adapter(
            "url_fetch",
            urls=args.urls,
            urls_path=args.urls_path,
            output_path=args.output,
            default_confidence=args.confidence,
            max_entries=args.max,
            excerpt_chars=args.excerpt,
            timeout_sec=args.timeout,
            max_bytes=args.max_bytes,
            user_agent=args.user_agent,
            tool_dir=args.tool_dir,
        )
    elif args.adapter == "web_search":
        run_adapter(
            "web_search",
            query=args.query or "",
            output_path=args.output,
            default_confidence=args.confidence,
            max_entries=args.max,
            excerpt_chars=args.excerpt,
            timeout_sec=args.timeout,
            tool_dir=args.tool_dir,
        )
    else:
        run_adapter(
            args.adapter,
            output_path=args.output,
            default_confidence=args.confidence,
            max_entries=args.max,
        )

    print(f"Sources written to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
