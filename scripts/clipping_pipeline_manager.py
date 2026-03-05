#!/usr/bin/env python3
"""
Generate a governed clipping pipeline queue and candidate clip recommendations.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parents[1]
WORKING_DIR = Path(os.getenv("PERMANENCE_WORKING_DIR", str(BASE_DIR / "memory" / "working")))
OUTPUT_DIR = Path(os.getenv("PERMANENCE_OUTPUT_DIR", str(BASE_DIR / "outputs")))
TOOL_DIR = Path(os.getenv("PERMANENCE_TOOL_DIR", str(BASE_DIR / "memory" / "tool")))
QUEUE_PATH = Path(os.getenv("PERMANENCE_CLIPPING_QUEUE_PATH", str(WORKING_DIR / "clipping_jobs.json")))

MARKERS = [
    "here is the key",
    "the real reason",
    "three steps",
    "first",
    "second",
    "third",
    "mistake",
    "lesson",
    "framework",
]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def _default_jobs() -> list[dict[str, Any]]:
    return [
        {
            "job_id": "CLIP-001",
            "title": "Sample long-form episode",
            "source_url": "https://example.com/video",
            "niche": "ai-business",
            "status": "queued",
            "notes": "Add transcript segments for automatic scoring.",
            "transcript_segments": [],
        }
    ]


def _load_jobs() -> list[dict[str, Any]]:
    payload = _read_json(QUEUE_PATH, [])
    if not isinstance(payload, list):
        payload = []
    rows = [row for row in payload if isinstance(row, dict)]
    if not rows:
        rows = _default_jobs()
    return rows


def _segment_score(text: str, duration_seconds: float) -> float:
    score = 0.0
    lower = text.lower()
    for marker in MARKERS:
        if marker in lower:
            score += 1.5
    word_count = len([w for w in text.split() if w.strip()])
    if 35 <= word_count <= 140:
        score += 2.0
    if 15 <= duration_seconds <= 45:
        score += 2.5
    if "?" in text:
        score += 0.5
    return round(score, 2)


def _to_seconds(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _build_candidates(job: dict[str, Any]) -> list[dict[str, Any]]:
    segments = job.get("transcript_segments")
    if not isinstance(segments, list):
        return []
    rows: list[dict[str, Any]] = []
    for idx, segment in enumerate(segments, start=1):
        if not isinstance(segment, dict):
            continue
        text = str(segment.get("text") or "").strip()
        if not text:
            continue
        start = _to_seconds(segment.get("start"), 0.0)
        end = _to_seconds(segment.get("end"), start + 30.0)
        duration = max(1.0, end - start)
        rows.append(
            {
                "candidate_id": f"{job.get('job_id', 'job')}-{idx}",
                "start": round(start, 2),
                "end": round(end, 2),
                "duration_seconds": round(duration, 2),
                "score": _segment_score(text, duration),
                "text_preview": text[:180],
            }
        )
    rows.sort(key=lambda row: row.get("score", 0), reverse=True)
    return rows[:8]


def _write_outputs(jobs: list[dict[str, Any]], candidates_by_job: dict[str, list[dict[str, Any]]]) -> tuple[Path, Path]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    TOOL_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _now().strftime("%Y%m%d-%H%M%S")
    md_path = OUTPUT_DIR / f"clipping_pipeline_{stamp}.md"
    latest_md = OUTPUT_DIR / "clipping_pipeline_latest.md"
    json_path = TOOL_DIR / f"clipping_pipeline_{stamp}.json"

    total_candidates = sum(len(items) for items in candidates_by_job.values())

    lines = [
        "# Clipping Pipeline Manager",
        "",
        f"Generated (UTC): {_now().isoformat()}",
        f"Queue source: {QUEUE_PATH}",
        "",
        "## Queue Summary",
        f"- Jobs in queue: {len(jobs)}",
        f"- Candidate clips scored: {total_candidates}",
        "",
        "## Job Breakdown",
    ]

    if not jobs:
        lines.append("- No clipping jobs configured.")
    for idx, job in enumerate(jobs, start=1):
        job_id = str(job.get("job_id") or f"job-{idx}")
        job_candidates = candidates_by_job.get(job_id, [])
        lines.extend(
            [
                f"{idx}. {job.get('title', 'Untitled')} ({job_id})",
                f"   - niche={job.get('niche', 'general')} | status={job.get('status', 'queued')} | source={job.get('source_url', '-')}",
            ]
        )
        if job_candidates:
            lines.append("   - top_candidates:")
            for item in job_candidates[:3]:
                lines.append(
                    "     - "
                    f"{item.get('candidate_id')} | {item.get('start')}s-{item.get('end')}s | "
                    f"score={item.get('score')} | preview={item.get('text_preview')}"
                )
        else:
            lines.append("   - top_candidates: none (add transcript_segments with start/end/text)")

    lines.extend(
        [
            "",
            "## Governance Notes",
            "- Human approval required before publishing any clip.",
            "- Verify content rights and platform policy compliance for every source.",
            "- Candidate scoring is heuristic and must be reviewed by editorial judgment.",
            "",
        ]
    )

    report = "\n".join(lines)
    md_path.write_text(report, encoding="utf-8")
    latest_md.write_text(report, encoding="utf-8")

    payload = {
        "generated_at": _now().isoformat(),
        "queue_path": str(QUEUE_PATH),
        "job_count": len(jobs),
        "candidate_count": total_candidates,
        "jobs": jobs,
        "candidates_by_job": candidates_by_job,
        "latest_markdown": str(latest_md),
    }
    json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return md_path, json_path


def main() -> int:
    jobs = _load_jobs()
    normalized: list[dict[str, Any]] = []
    candidates_by_job: dict[str, list[dict[str, Any]]] = {}
    for idx, row in enumerate(jobs, start=1):
        job = dict(row)
        job_id = str(job.get("job_id") or f"CLIP-{idx:03d}")
        job["job_id"] = job_id
        normalized.append(job)
        candidates_by_job[job_id] = _build_candidates(job)

    md_path, json_path = _write_outputs(normalized, candidates_by_job)
    print(f"Clipping pipeline written: {md_path}")
    print(f"Clipping pipeline latest: {OUTPUT_DIR / 'clipping_pipeline_latest.md'}")
    print(f"Tool payload written: {json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
