#!/usr/bin/env python3
"""
Unified ingestion entrypoint using Researcher adapter registry.
"""

import argparse
import os
import sys

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(BASE_DIR)

from agents.researcher_adapters import list_adapters, run_adapter  # noqa: E402
from agents.researcher import TOOL_DIR, DOC_DIR  # noqa: E402
from agents.utils import BASE_DIR as PROJECT_ROOT  # noqa: E402

try:
    from dotenv import load_dotenv  # noqa: E402

    load_dotenv(os.path.join(PROJECT_ROOT, ".env"))
except Exception:
    pass


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest sources via adapter registry")
    parser.add_argument("--adapter", default="tool_memory", help="Adapter name")
    parser.add_argument("--list", action="store_true", help="List available adapters")
    parser.add_argument("--urls", nargs="*", help="URLs to fetch (url_fetch adapter)")
    parser.add_argument("--urls-path", help="File containing URLs (url_fetch adapter)")
    parser.add_argument("--query", help="Search query (web_search adapter)")
    parser.add_argument("--doc-ids", nargs="*", help="Google Doc IDs (google_docs adapter)")
    parser.add_argument("--doc-ids-path", help="File containing Google Doc IDs")
    parser.add_argument("--folder-id", help="Google Drive folder ID (google_docs adapter)")
    parser.add_argument("--file-ids", nargs="*", help="Google Drive file IDs (drive_pdfs adapter)")
    parser.add_argument("--file-ids-path", help="File containing Drive file IDs (drive_pdfs adapter)")
    parser.add_argument("--credentials", help="Google OAuth credentials.json path")
    parser.add_argument("--token", help="Google OAuth token.json path")
    parser.add_argument("--tool-dir", default=TOOL_DIR, help="Tool memory directory")
    parser.add_argument("--doc-dir", default=DOC_DIR, help="Documents directory")
    parser.add_argument(
        "--output",
        default=os.path.join(PROJECT_ROOT, "memory", "working", "sources.json"),
        help="Output sources.json path",
    )
    parser.add_argument(
        "--append",
        action="store_true",
        help="Append to existing sources.json instead of overwriting",
    )
    parser.add_argument("--confidence", type=float, default=0.5, help="Default confidence")
    parser.add_argument("--max", type=int, default=100, help="Max entries")
    parser.add_argument("--excerpt", type=int, default=280, help="Excerpt length")
    parser.add_argument("--timeout", type=int, default=20, help="Web search timeout (seconds)")
    parser.add_argument("--url-timeout", type=int, default=15, help="URL fetch timeout (seconds)")
    parser.add_argument("--max-bytes", type=int, default=1_000_000, help="Max bytes per URL")
    parser.add_argument("--user-agent", default="PermanenceOS-Researcher/0.2", help="URL fetch user agent")

    args = parser.parse_args()

    if args.list:
        for adapter in list_adapters():
            print(f"{adapter.name}: {adapter.description} (default confidence {adapter.default_confidence})")
        return 0

    def _maybe_output() -> str | None:
        return None if args.append else args.output

    if args.adapter == "tool_memory":
        new_sources = run_adapter(
            "tool_memory",
            tool_dir=args.tool_dir,
            output_path=_maybe_output(),
            default_confidence=args.confidence,
            max_entries=args.max,
        )
    elif args.adapter == "documents":
        new_sources = run_adapter(
            "documents",
            doc_dir=args.doc_dir,
            output_path=_maybe_output(),
            default_confidence=args.confidence,
            max_entries=args.max,
            excerpt_chars=args.excerpt,
        )
    elif args.adapter == "url_fetch":
        new_sources = run_adapter(
            "url_fetch",
            urls=args.urls,
            urls_path=args.urls_path,
            output_path=_maybe_output(),
            default_confidence=args.confidence,
            max_entries=args.max,
            excerpt_chars=args.excerpt,
            timeout_sec=args.url_timeout,
            max_bytes=args.max_bytes,
            user_agent=args.user_agent,
            tool_dir=args.tool_dir,
        )
    elif args.adapter == "web_search":
        new_sources = run_adapter(
            "web_search",
            query=args.query or "",
            output_path=_maybe_output(),
            default_confidence=args.confidence,
            max_entries=args.max,
            excerpt_chars=args.excerpt,
            timeout_sec=args.timeout,
            tool_dir=args.tool_dir,
        )
    elif args.adapter == "google_docs":
        new_sources = run_adapter(
            "google_docs",
            doc_ids=args.doc_ids,
            doc_ids_path=args.doc_ids_path,
            folder_id=args.folder_id,
            output_path=_maybe_output(),
            default_confidence=args.confidence,
            max_entries=args.max,
            excerpt_chars=args.excerpt,
            credentials_path=args.credentials,
            token_path=args.token,
            tool_dir=args.tool_dir,
        )
    elif args.adapter == "drive_pdfs":
        new_sources = run_adapter(
            "drive_pdfs",
            file_ids=args.file_ids,
            file_ids_path=args.file_ids_path,
            folder_id=args.folder_id,
            output_path=_maybe_output(),
            default_confidence=args.confidence,
            max_entries=args.max,
            excerpt_chars=args.excerpt,
            credentials_path=args.credentials,
            token_path=args.token,
            tool_dir=args.tool_dir,
        )
    else:
        new_sources = run_adapter(
            args.adapter,
            output_path=_maybe_output(),
            default_confidence=args.confidence,
            max_entries=args.max,
        )

    if args.append:
        existing = _load_existing_sources(args.output)
        merged = _merge_sources(existing, new_sources)
        os.makedirs(os.path.dirname(args.output), exist_ok=True)
        with open(args.output, "w") as f:
            json.dump(merged, f, indent=2)
    print(f"Sources written to {args.output}")
    return 0


def _load_existing_sources(path: str) -> list[dict]:
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return []
    return data if isinstance(data, list) else []


def _merge_sources(existing: list[dict], new: list[dict]) -> list[dict]:
    merged: list[dict] = []
    seen: set[tuple[str, str, str]] = set()

    def _key(item: dict) -> tuple[str, str, str]:
        return (
            str(item.get("source") or ""),
            str(item.get("origin") or ""),
            str(item.get("hash") or ""),
        )

    for item in existing + new:
        key = _key(item)
        if key in seen:
            continue
        seen.add(key)
        merged.append(item)
    return merged


if __name__ == "__main__":
    raise SystemExit(main())
