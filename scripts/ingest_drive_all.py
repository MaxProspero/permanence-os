#!/usr/bin/env python3
"""
Batch ingest Google Drive PDFs and Docs with resume support.
"""

import argparse
import json
import os
import subprocess
import time

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SOURCES_PATH = os.path.join(BASE_DIR, "memory", "working", "sources.json")


def _count_sources(path: str) -> int:
    if not os.path.exists(path):
        return 0
    try:
        with open(path, "r") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return 0
    return len(data) if isinstance(data, list) else 0


def _run_ingest(cmd: list[str]) -> int:
    return subprocess.call(cmd)


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest Drive PDFs + Docs in batches")
    parser.add_argument("--folder-id", required=True, help="Google Drive folder ID")
    parser.add_argument("--max", type=int, default=10, help="Max items per batch")
    parser.add_argument("--max-batches", type=int, default=0, help="Stop after N batches (0 = no limit)")
    parser.add_argument("--sleep", type=int, default=2, help="Seconds to sleep between batches")
    args = parser.parse_args()

    batches = 0
    while True:
        before = _count_sources(SOURCES_PATH)

        pdf_cmd = [
            "python",
            os.path.join(BASE_DIR, "cli.py"),
            "ingest-sources",
            "--adapter",
            "drive_pdfs",
            "--folder-id",
            args.folder_id,
            "--max",
            str(args.max),
            "--append",
            "--resume",
        ]
        doc_cmd = [
            "python",
            os.path.join(BASE_DIR, "cli.py"),
            "ingest-sources",
            "--adapter",
            "google_docs",
            "--folder-id",
            args.folder_id,
            "--max",
            str(args.max),
            "--append",
            "--resume",
        ]

        _run_ingest(pdf_cmd)
        _run_ingest(doc_cmd)

        after = _count_sources(SOURCES_PATH)
        batches += 1

        if after <= before:
            print("No new sources added; stopping.")
            break
        if args.max_batches and batches >= args.max_batches:
            print("Max batches reached; stopping.")
            break
        time.sleep(args.sleep)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
