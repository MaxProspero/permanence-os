#!/usr/bin/env python3
"""
Ingest transcript files and sync them into clipping job working state.

Advisory only: this script prepares clip candidates for manual editorial review.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parents[1]
WORKING_DIR = Path(os.getenv("PERMANENCE_WORKING_DIR", str(BASE_DIR / "memory" / "working")))
OUTPUT_DIR = Path(os.getenv("PERMANENCE_OUTPUT_DIR", str(BASE_DIR / "outputs")))
TOOL_DIR = Path(os.getenv("PERMANENCE_TOOL_DIR", str(BASE_DIR / "memory" / "tool")))
TRANSCRIPT_DIR = Path(
    os.getenv("PERMANENCE_CLIPPING_TRANSCRIPT_DIR", str(WORKING_DIR / "clipping_transcripts"))
)
QUEUE_PATH = Path(os.getenv("PERMANENCE_CLIPPING_QUEUE_PATH", str(WORKING_DIR / "clipping_jobs.json")))
MAX_SEGMENTS_PER_JOB = int(os.getenv("PERMANENCE_CLIPPING_MAX_SEGMENTS", "120"))

RANGE_PATTERN = re.compile(
    r"^\s*(?:\[)?(?P<start>\d{1,2}:\d{2}(?::\d{2}(?:\.\d+)?)?)(?:\])?\s*"
    r"(?:-->|-|to)\s*(?:\[)?(?P<end>\d{1,2}:\d{2}(?::\d{2}(?:\.\d+)?)?)(?:\])?"
    r"\s*[:\-]?\s*(?P<text>.+)$",
    re.IGNORECASE,
)
POINT_PATTERN = re.compile(
    r"^\s*(?:\[)?(?P<start>\d{1,2}:\d{2}(?::\d{2}(?:\.\d+)?)?)(?:\])?\s*[:\-]\s*(?P<text>.+)$"
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _parse_clock(value: str) -> float | None:
    text = value.strip()
    parts = text.split(":")
    try:
        if len(parts) == 3:
            hours = int(parts[0])
            minutes = int(parts[1])
            seconds = float(parts[2])
            return (hours * 3600.0) + (minutes * 60.0) + seconds
        if len(parts) == 2:
            minutes = int(parts[0])
            seconds = float(parts[1])
            return (minutes * 60.0) + seconds
    except ValueError:
        return None
    return None


def _slug(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    return cleaned or "transcript"


def _job_id_for_path(path: Path) -> str:
    slug = _slug(path.stem).upper()
    return f"CLIP-AUTO-{slug[:28]}"


def _list_transcript_files(transcript_dir: Path) -> list[Path]:
    if not transcript_dir.exists():
        return []
    rows: list[Path] = []
    for path in transcript_dir.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() not in {".txt", ".md", ".json", ".srt"}:
            continue
        rows.append(path)
    rows.sort(key=lambda p: str(p).lower())
    return rows


def _chunk_text(text: str, max_chars: int = 220) -> list[str]:
    words = [word for word in text.split() if word]
    if not words:
        return []
    chunks: list[str] = []
    current: list[str] = []
    for word in words:
        trial = " ".join([*current, word]).strip()
        if current and len(trial) > max_chars:
            chunks.append(" ".join(current).strip())
            current = [word]
        else:
            current.append(word)
    if current:
        chunks.append(" ".join(current).strip())
    return chunks


def _parse_text_segments(text: str) -> list[dict[str, Any]]:
    segments: list[dict[str, Any]] = []
    fallback_lines: list[str] = []
    for raw_line in text.splitlines():
        line = " ".join(raw_line.strip().split())
        if not line:
            continue

        match = RANGE_PATTERN.match(line)
        if match:
            start = _parse_clock(match.group("start"))
            end = _parse_clock(match.group("end"))
            body = match.group("text").strip()
            if start is None or end is None or not body:
                continue
            if end <= start:
                end = start + 22.0
            segments.append({"start": start, "end": end, "text": body})
            continue

        match = POINT_PATTERN.match(line)
        if match:
            start = _parse_clock(match.group("start"))
            body = match.group("text").strip()
            if start is None or not body:
                continue
            segments.append({"start": start, "end": start + 22.0, "text": body})
            continue

        fallback_lines.append(line)

    if segments:
        return segments

    synthesized: list[dict[str, Any]] = []
    cursor = 0.0
    for line in fallback_lines:
        for chunk in _chunk_text(line):
            words = len(chunk.split())
            duration = max(12.0, min(60.0, words * 0.45))
            synthesized.append(
                {
                    "start": round(cursor, 2),
                    "end": round(cursor + duration, 2),
                    "text": chunk,
                }
            )
            cursor += duration + 1.0
    return synthesized


def _parse_json_transcript(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    payload = _read_json(path, {})
    metadata: dict[str, Any] = {}
    raw_segments: list[Any] = []
    if isinstance(payload, dict):
        metadata = {
            "title": payload.get("title"),
            "source_url": payload.get("source_url"),
            "niche": payload.get("niche"),
            "job_id": payload.get("job_id"),
            "status": payload.get("status"),
            "notes": payload.get("notes"),
        }
        for key in ("segments", "transcript_segments", "items"):
            value = payload.get(key)
            if isinstance(value, list):
                raw_segments = value
                break
    elif isinstance(payload, list):
        raw_segments = payload

    segments: list[dict[str, Any]] = []
    for row in raw_segments:
        if isinstance(row, dict):
            text = str(row.get("text") or row.get("content") or "").strip()
            if not text:
                continue
            start = _as_float(row.get("start"), 0.0)
            end = _as_float(row.get("end"), start + 22.0)
            if end <= start:
                end = start + 22.0
            segments.append({"start": start, "end": end, "text": text})
        elif isinstance(row, str):
            segments.extend(_parse_text_segments(row))

    return metadata, segments


def _normalize_segments(segments: list[dict[str, Any]], max_segments: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in segments:
        text = str(row.get("text") or "").strip()
        if not text:
            continue
        start = _as_float(row.get("start"), 0.0)
        end = _as_float(row.get("end"), start + 22.0)
        if end <= start:
            end = start + 22.0
        rows.append(
            {
                "start": round(start, 2),
                "end": round(end, 2),
                "text": " ".join(text.split()),
            }
        )
    rows.sort(key=lambda item: (item.get("start", 0.0), item.get("end", 0.0)))
    if max_segments > 0:
        rows = rows[:max_segments]
    return rows


def _infer_niche(path: Path, transcript_dir: Path) -> str:
    parent = path.parent
    if parent == transcript_dir:
        return "general"
    return _slug(parent.name)


def _load_existing_jobs(queue_path: Path) -> list[dict[str, Any]]:
    payload = _read_json(queue_path, [])
    if not isinstance(payload, list):
        payload = []
    return [row for row in payload if isinstance(row, dict)]


def _build_job(path: Path, transcript_dir: Path, max_segments: int) -> tuple[dict[str, Any] | None, str | None]:
    if path.suffix.lower() == ".json":
        metadata, raw_segments = _parse_json_transcript(path)
    else:
        metadata = {}
        text = path.read_text(encoding="utf-8", errors="ignore")
        raw_segments = _parse_text_segments(text)

    segments = _normalize_segments(raw_segments, max_segments=max_segments)
    if not segments:
        return None, "no segments parsed"

    title = str(metadata.get("title") or path.stem.replace("_", " ").replace("-", " ").title())
    source_url = str(metadata.get("source_url") or f"file://{path}")
    niche = str(metadata.get("niche") or _infer_niche(path, transcript_dir))
    job_id = str(metadata.get("job_id") or _job_id_for_path(path))
    notes = str(metadata.get("notes") or "Generated from transcript ingest.")

    job = {
        "job_id": job_id,
        "title": title,
        "source_url": source_url,
        "niche": niche,
        "status": str(metadata.get("status") or "queued"),
        "notes": notes,
        "manual_approval_required": True,
        "transcript_source_file": str(path),
        "transcript_segments": segments,
        "updated_at": _now().isoformat(),
    }
    return job, None


def _merge_jobs(
    existing_rows: list[dict[str, Any]], incoming_rows: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], int, int]:
    merged = [dict(row) for row in existing_rows]
    index_by_job_id: dict[str, int] = {}
    for idx, row in enumerate(merged):
        job_id = str(row.get("job_id") or "")
        if job_id:
            index_by_job_id[job_id] = idx

    created = 0
    updated = 0
    for row in incoming_rows:
        job_id = str(row.get("job_id") or "")
        if not job_id:
            continue
        if job_id in index_by_job_id:
            idx = index_by_job_id[job_id]
            current = dict(merged[idx])
            current.update(row)
            merged[idx] = current
            updated += 1
        else:
            merged.append(row)
            index_by_job_id[job_id] = len(merged) - 1
            created += 1
    return merged, created, updated


def _write_outputs(
    queue_path: Path,
    transcript_dir: Path,
    jobs: list[dict[str, Any]],
    ingested: list[dict[str, Any]],
    warnings: list[str],
    scanned_files: int,
    created: int,
    updated: int,
) -> tuple[Path, Path]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    TOOL_DIR.mkdir(parents=True, exist_ok=True)
    queue_path.parent.mkdir(parents=True, exist_ok=True)
    queue_path.write_text(json.dumps(jobs, indent=2) + "\n", encoding="utf-8")

    stamp = _now().strftime("%Y%m%d-%H%M%S")
    md_path = OUTPUT_DIR / f"clipping_transcript_ingest_{stamp}.md"
    latest_md = OUTPUT_DIR / "clipping_transcript_ingest_latest.md"
    json_path = TOOL_DIR / f"clipping_transcript_ingest_{stamp}.json"

    lines = [
        "# Clipping Transcript Ingest",
        "",
        f"Generated (UTC): {_now().isoformat()}",
        f"Transcript dir: {transcript_dir}",
        f"Queue path: {queue_path}",
        "",
        "## Summary",
        f"- Transcript files scanned: {scanned_files}",
        f"- Jobs created: {created}",
        f"- Jobs updated: {updated}",
        f"- Total clipping jobs: {len(jobs)}",
    ]
    if warnings:
        lines.append(f"- Warnings: {len(warnings)}")

    lines.extend(["", "## Ingested Files"])
    if not ingested:
        lines.append("- No transcript files ingested.")
    for row in ingested:
        lines.append(
            "- "
            f"{row.get('path')} | job_id={row.get('job_id')} | segments={row.get('segment_count')} | "
            f"status={row.get('operation')}"
        )

    if warnings:
        lines.extend(["", "## Warnings"])
        for warning in warnings:
            lines.append(f"- {warning}")

    lines.extend(
        [
            "",
            "## Governance Notes",
            "- Ingest prepares clipping candidates only; publishing is always manual approval.",
            "- Verify rights and platform policy before editing or posting content.",
            "",
        ]
    )

    report = "\n".join(lines)
    md_path.write_text(report, encoding="utf-8")
    latest_md.write_text(report, encoding="utf-8")

    payload = {
        "generated_at": _now().isoformat(),
        "transcript_dir": str(transcript_dir),
        "queue_path": str(queue_path),
        "scanned_files": scanned_files,
        "jobs_created": created,
        "jobs_updated": updated,
        "job_count": len(jobs),
        "ingested": ingested,
        "warnings": warnings,
        "latest_markdown": str(latest_md),
    }
    json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return md_path, json_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ingest transcripts into clipping queue.")
    parser.add_argument(
        "--transcript-dir",
        default=str(TRANSCRIPT_DIR),
        help="Directory containing transcript files (.txt/.md/.json/.srt)",
    )
    parser.add_argument(
        "--queue-path",
        default=str(QUEUE_PATH),
        help="Path to clipping_jobs.json working file",
    )
    parser.add_argument("--max-files", type=int, default=50, help="Maximum transcript files to scan")
    parser.add_argument(
        "--max-segments",
        type=int,
        default=MAX_SEGMENTS_PER_JOB,
        help="Maximum segments saved per job",
    )
    args = parser.parse_args(argv)

    transcript_dir = Path(args.transcript_dir).expanduser()
    queue_path = Path(args.queue_path).expanduser()

    files = _list_transcript_files(transcript_dir)
    if args.max_files > 0:
        files = files[: args.max_files]

    existing = _load_existing_jobs(queue_path)
    incoming: list[dict[str, Any]] = []
    ingested: list[dict[str, Any]] = []
    warnings: list[str] = []

    existing_ids = {str(row.get("job_id") or "") for row in existing}
    for path in files:
        job, error = _build_job(path, transcript_dir, max_segments=max(1, args.max_segments))
        if error:
            warnings.append(f"{path}: {error}")
            continue
        assert job is not None
        operation = "updated" if str(job.get("job_id") or "") in existing_ids else "created"
        incoming.append(job)
        ingested.append(
            {
                "path": str(path),
                "job_id": str(job.get("job_id") or ""),
                "segment_count": len(job.get("transcript_segments") or []),
                "operation": operation,
            }
        )

    merged, created, updated = _merge_jobs(existing, incoming)
    md_path, json_path = _write_outputs(
        queue_path=queue_path,
        transcript_dir=transcript_dir,
        jobs=merged,
        ingested=ingested,
        warnings=warnings,
        scanned_files=len(files),
        created=created,
        updated=updated,
    )

    print(f"Transcript ingest written: {md_path}")
    print(f"Transcript ingest latest: {OUTPUT_DIR / 'clipping_transcript_ingest_latest.md'}")
    print(f"Tool payload written: {json_path}")
    print(f"Jobs created: {created} | updated: {updated} | total_jobs: {len(merged)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
