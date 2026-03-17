#!/usr/bin/env python3
"""
Analyze X bookmarks for themes, trends, and actionable ideas.
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parents[1]


def _load_local_env() -> None:
    env_path = BASE_DIR / ".env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key or key in os.environ:
            continue
        value = value.strip()
        if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
            value = value[1:-1]
        os.environ[key] = value


_load_local_env()
WORKING_DIR = Path(os.getenv("PERMANENCE_WORKING_DIR", str(BASE_DIR / "memory" / "working")))
OUTPUT_DIR = Path(os.getenv("PERMANENCE_OUTPUT_DIR", str(BASE_DIR / "outputs")))
TOOL_DIR = Path(os.getenv("PERMANENCE_TOOL_DIR", str(BASE_DIR / "memory" / "tool")))
INBOX_DIR = Path(os.getenv("PERMANENCE_INBOX_DIR", str(BASE_DIR / "memory" / "inbox")))
BOOKMARK_INTAKE_PATH = INBOX_DIR / "bookmark_intake.jsonl"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now().isoformat()


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Load latest bookmark ingest output
# ---------------------------------------------------------------------------


def _load_latest_bookmarks() -> tuple[list[dict[str, Any]], str]:
    """Load the most recent x_bookmark_ingest tool JSON output.

    Returns (top_items list, source_path string).
    """
    pattern = "x_bookmark_ingest_*.json"
    try:
        candidates = sorted(TOOL_DIR.glob(pattern), key=lambda p: p.stat().st_mtime)
    except OSError:
        return [], ""
    if not candidates:
        return [], ""

    latest = candidates[-1]
    payload = _read_json(latest, {})
    if not isinstance(payload, dict):
        return [], str(latest)

    items = payload.get("top_items", [])
    if not isinstance(items, list):
        return [], str(latest)
    return items, str(latest)


# ---------------------------------------------------------------------------
# Clustering
# ---------------------------------------------------------------------------


def _cluster_by_topic(bookmarks: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Group bookmarks by topic tag. Returns dict sorted by cluster size descending."""
    clusters: dict[str, list[dict[str, Any]]] = {}
    for bm in bookmarks:
        tags = bm.get("topic_tags", [])
        if not isinstance(tags, list):
            continue
        for tag in tags:
            tag = str(tag).strip()
            if not tag:
                continue
            if tag not in clusters:
                clusters[tag] = []
            clusters[tag].append(bm)

    # Sort by cluster size descending
    sorted_clusters: dict[str, list[dict[str, Any]]] = {}
    for tag in sorted(clusters.keys(), key=lambda t: len(clusters[t]), reverse=True):
        sorted_clusters[tag] = clusters[tag]
    return sorted_clusters


# ---------------------------------------------------------------------------
# Author analysis
# ---------------------------------------------------------------------------


def _identify_key_authors(bookmarks: list[dict[str, Any]]) -> list[tuple[str, int]]:
    """Find the most frequently bookmarked authors.

    Returns sorted list of (handle, count) tuples.
    """
    author_counts: dict[str, int] = {}
    for bm in bookmarks:
        handle = str(bm.get("handle") or "").strip()
        if not handle:
            continue
        author_counts[handle] = author_counts.get(handle, 0) + 1
    return sorted(author_counts.items(), key=lambda x: x[1], reverse=True)


# ---------------------------------------------------------------------------
# Idea extraction
# ---------------------------------------------------------------------------


def _extract_idea_candidates(
    clusters: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    """For clusters with 2+ bookmarks, generate actionable idea candidates."""
    ideas: list[dict[str, Any]] = []
    for topic, bm_list in clusters.items():
        if len(bm_list) < 2:
            continue

        texts = []
        for bm in bm_list:
            text = str(bm.get("text") or "").strip()
            if text:
                preview = text if len(text) <= 200 else text[:197] + "..."
                texts.append(preview)

        ideas.append({
            "topic": topic,
            "title": f"Opportunity cluster: {topic} ({len(bm_list)} bookmarks)",
            "summary": " | ".join(texts[:5]),
            "bookmark_count": len(bm_list),
            "recommended_action": "Research this cluster and identify one buildable prototype.",
            "generated_at": _now_iso(),
        })
    return ideas


# ---------------------------------------------------------------------------
# Intelligence brief output
# ---------------------------------------------------------------------------


def _write_intelligence_brief(
    clusters: dict[str, list[dict[str, Any]]],
    authors: list[tuple[str, int]],
    ideas: list[dict[str, Any]],
    bookmarks: list[dict[str, Any]],
) -> tuple[Path, Path]:
    """Write markdown intelligence brief and structured JSON output."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    TOOL_DIR.mkdir(parents=True, exist_ok=True)
    date_stamp = _now().strftime("%Y%m%d")
    md_path = OUTPUT_DIR / f"bookmark_intelligence_{date_stamp}.md"
    json_path = TOOL_DIR / f"bookmark_intelligence_{date_stamp}.json"

    lines = [
        "# Bookmark Intelligence Brief",
        "",
        f"Generated (UTC): {_now_iso()}",
        f"Bookmarks analyzed: {len(bookmarks)}",
        f"Topic clusters: {len(clusters)}",
        f"Idea candidates: {len(ideas)}",
        "",
        "## Summary",
        "",
        f"Analyzed {len(bookmarks)} bookmarks across {len(clusters)} topic clusters.",
    ]

    top_topics = list(clusters.keys())[:5]
    if top_topics:
        lines.append(f"Top themes: {', '.join(top_topics)}.")
    if authors:
        top_handles = [f"@{h}" for h, _ in authors[:5]]
        lines.append(f"Key voices: {', '.join(top_handles)}.")

    # Topic clusters section
    lines.extend(["", "## Topic Clusters"])
    if not clusters:
        lines.append("- No topic clusters detected.")
    for topic, bm_list in clusters.items():
        lines.append(f"### {topic} ({len(bm_list)} bookmarks)")
        for bm in bm_list[:5]:
            handle = bm.get("handle") or "unknown"
            text = str(bm.get("text") or "")
            preview = text if len(text) <= 100 else text[:97] + "..."
            lines.append(f"- @{handle}: {preview}")
        if len(bm_list) > 5:
            lines.append(f"- ... and {len(bm_list) - 5} more")
        lines.append("")

    # Key authors section
    lines.extend(["## Key Authors"])
    if not authors:
        lines.append("- No authors identified.")
    for handle, count in authors[:15]:
        lines.append(f"- @{handle}: {count} bookmarks")

    # Idea candidates section
    lines.extend(["", "## Idea Candidates"])
    if not ideas:
        lines.append("- No idea candidates generated (need 2+ bookmarks per topic).")
    for idx, idea in enumerate(ideas, start=1):
        lines.append(f"### {idx}. {idea['title']}")
        lines.append(f"- Action: {idea['recommended_action']}")
        summary = idea.get("summary", "")
        if len(summary) > 300:
            summary = summary[:297] + "..."
        lines.append(f"- Signal: {summary}")
        lines.append("")

    # Governance section
    lines.extend([
        "## Governance Notes",
        "- Analysis derived from read-only bookmark data.",
        "- All idea candidates require human review before execution.",
        "- No external API calls made during analysis phase.",
        "",
    ])

    report = "\n".join(lines)
    try:
        md_path.write_text(report, encoding="utf-8")
    except OSError:
        pass

    payload = {
        "generated_at": _now_iso(),
        "bookmark_count": len(bookmarks),
        "cluster_count": len(clusters),
        "cluster_sizes": {topic: len(bm_list) for topic, bm_list in clusters.items()},
        "key_authors": [{"handle": h, "count": c} for h, c in authors[:20]],
        "idea_candidates": ideas,
        "top_items": bookmarks[:30],
    }
    try:
        json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    except OSError:
        pass

    return md_path, json_path


# ---------------------------------------------------------------------------
# Queue ideas to intake
# ---------------------------------------------------------------------------


def _queue_ideas_to_intake(ideas: list[dict[str, Any]]) -> int:
    """Write idea candidates to bookmark_intake.jsonl for idea_intake processing."""
    if not ideas:
        return 0
    INBOX_DIR.mkdir(parents=True, exist_ok=True)
    written = 0
    try:
        with BOOKMARK_INTAKE_PATH.open("a", encoding="utf-8") as fh:
            for idea in ideas:
                entry = {
                    "url": "",
                    "text": idea.get("title", ""),
                    "source": "bookmark_analysis",
                    "captured_at": _now_iso(),
                    "topic": idea.get("topic", ""),
                    "recommended_action": idea.get("recommended_action", ""),
                }
                fh.write(json.dumps(entry) + "\n")
                written += 1
    except OSError:
        pass
    return written


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Analyze X bookmarks for themes and ideas.")
    parser.add_argument(
        "--action",
        choices=["analyze", "status"],
        default="analyze",
        help="Action to perform (default: analyze)",
    )
    args = parser.parse_args(argv)

    # -- Status action --
    if args.action == "status":
        bookmarks, source_path = _load_latest_bookmarks()
        if not bookmarks:
            print("No bookmark ingest data found.")
            print(f"  Looked in: {TOOL_DIR}")
            return 0
        clusters = _cluster_by_topic(bookmarks)
        authors = _identify_key_authors(bookmarks)
        print(f"Bookmark analysis status:")
        print(f"  Latest ingest source: {source_path}")
        print(f"  Bookmarks available: {len(bookmarks)}")
        print(f"  Topic clusters: {len(clusters)}")
        print(f"  Unique authors: {len(authors)}")
        return 0

    # -- Analyze action (default) --
    bookmarks, source_path = _load_latest_bookmarks()
    if not bookmarks:
        print("No bookmark ingest data found. Run x_bookmark_ingest.py first.")
        print(f"  Looked in: {TOOL_DIR}")
        return 1

    clusters = _cluster_by_topic(bookmarks)
    authors = _identify_key_authors(bookmarks)
    ideas = _extract_idea_candidates(clusters)

    md_path, json_path = _write_intelligence_brief(clusters, authors, ideas, bookmarks)
    queued = _queue_ideas_to_intake(ideas)

    print(f"Bookmark intelligence brief generated.")
    print(f"  Bookmarks analyzed: {len(bookmarks)}")
    print(f"  Topic clusters: {len(clusters)}")
    print(f"  Key authors: {len(authors)}")
    print(f"  Idea candidates: {len(ideas)}")
    print(f"  Ideas queued to intake: {queued}")
    print(f"  Report: {md_path}")
    print(f"  Tool payload: {json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
