#!/usr/bin/env python3
"""
Generate a simple digest from sources.json without LLM synthesis.
"""

import json
import os
import sys
from datetime import datetime, timezone

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(BASE_DIR)

from agents.utils import BASE_DIR as PROJECT_ROOT, log  # noqa: E402
from core.storage import storage  # noqa: E402


def _load_sources(path: str) -> list[dict]:
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return []
    return data if isinstance(data, list) else []


def main() -> int:
    sources_path = os.path.join(PROJECT_ROOT, "memory", "working", "sources.json")
    sources = _load_sources(sources_path)
    if not sources:
        print("No sources found.")
        return 1

    now = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    out_path = storage.paths.outputs_digests / f"sources_digest_{now}.md"
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    lines = [
        "# Sources Digest",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        f"Total sources: {len(sources)}",
        "",
    ]

    for idx, src in enumerate(sources, 1):
        title = src.get("title") or src.get("source") or "Untitled"
        notes = src.get("notes") or ""
        origin = src.get("origin") or "unknown"
        ts = src.get("timestamp") or "unknown"
        lines.extend(
            [
                f"## {idx}. {title}",
                f"- Source: {src.get('source','')}",
                f"- Origin: {origin}",
                f"- Timestamp: {ts}",
                "",
                notes.strip(),
                "",
            ]
        )

    try:
        with open(out_path, "w") as f:
            f.write("\n".join(lines).strip() + "\n")
    except OSError:
        fallback_dir = os.path.join(PROJECT_ROOT, "permanence_storage", "outputs", "digests")
        os.makedirs(fallback_dir, exist_ok=True)
        fallback_path = os.path.join(fallback_dir, os.path.basename(str(out_path)))
        with open(fallback_path, "w") as f:
            f.write("\n".join(lines).strip() + "\n")
        out_path = fallback_path

    log(f"Sources digest written to {out_path}", level="INFO")
    print(f"Sources digest written to {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
