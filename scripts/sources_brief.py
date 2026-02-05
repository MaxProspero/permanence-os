#!/usr/bin/env python3
"""
Generate a lightweight synthesis brief from sources.json without LLMs.
"""

import json
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(BASE_DIR)

from agents.utils import BASE_DIR as PROJECT_ROOT, log  # noqa: E402


STOPWORDS = {
    "the",
    "and",
    "of",
    "to",
    "in",
    "a",
    "for",
    "on",
    "is",
    "with",
    "as",
    "that",
    "by",
    "this",
    "are",
    "be",
    "or",
    "from",
    "at",
    "it",
    "an",
    "not",
    "we",
    "you",
    "your",
    "our",
    "they",
    "their",
    "was",
    "were",
    "has",
    "have",
    "had",
    "but",
    "will",
    "can",
    "should",
    "may",
}


def _load_sources(path: str) -> list[dict]:
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return []
    return data if isinstance(data, list) else []


def _tokenize(text: str) -> list[str]:
    text = re.sub(r"[^a-zA-Z0-9\\s]", " ", text or "")
    tokens = [t.lower() for t in text.split() if len(t) > 2]
    return [t for t in tokens if t not in STOPWORDS]


def _first_sentence(text: str) -> str:
    text = (text or "").strip()
    if not text:
        return ""
    parts = re.split(r"(?<=[.!?])\\s+", text)
    return parts[0].strip() if parts else text[:200]


def main() -> int:
    sources_path = os.path.join(PROJECT_ROOT, "memory", "working", "sources.json")
    sources = _load_sources(sources_path)
    if not sources:
        print("No sources found.")
        return 1

    now = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    out_path = os.path.join(PROJECT_ROOT, "outputs", f"sources_brief_{now}.md")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    notes_text = " ".join([s.get("notes", "") or "" for s in sources])
    token_counts = Counter(_tokenize(notes_text))
    top_terms = [t for t, _ in token_counts.most_common(12)]

    by_origin = defaultdict(list)
    for src in sources:
        origin = src.get("origin") or "unknown"
        by_origin[origin].append(src)

    lines = [
        "# Sources Synthesis Brief",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        f"Total sources: {len(sources)}",
        "",
        "## Themes (heuristic)",
        "- " + ", ".join(top_terms) if top_terms else "- (no dominant terms found)",
        "",
        "## Key Points (from excerpts)",
    ]

    for idx, src in enumerate(sources, 1):
        title = src.get("title") or src.get("source") or "Untitled"
        excerpt = _first_sentence(src.get("notes") or "")
        if not excerpt:
            continue
        lines.append(f"{idx}. **{title}** — {excerpt}")

    lines.extend(
        [
            "",
            "## Source Breakdown",
        ]
    )
    for origin, items in sorted(by_origin.items(), key=lambda x: x[0]):
        lines.append(f"- {origin}: {len(items)}")

    lines.extend(
        [
            "",
            "## Suggested Next Actions",
            "1. Review the top 5 sources and mark high‑value items for canon promotion.",
            "2. Run a governed task using these sources for a focused brief.",
            "3. Identify duplicates or weak sources and prune.",
        ]
    )

    with open(out_path, "w") as f:
        f.write("\n".join(lines).strip() + "\n")

    log(f"Sources brief written to {out_path}", level="INFO")
    print(f"Sources brief written to {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
