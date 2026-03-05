#!/usr/bin/env python3
"""
Scan attachment inbox files and produce governed processing queues.

This module is read-only on source files. It writes:
- outputs/attachment_pipeline_*.md (+ latest symlink copy)
- memory/tool/attachment_pipeline_*.json
- memory/working/transcription_queue.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parents[1]
WORKING_DIR = Path(os.getenv("PERMANENCE_WORKING_DIR", str(BASE_DIR / "memory" / "working")))
OUTPUT_DIR = Path(os.getenv("PERMANENCE_OUTPUT_DIR", str(BASE_DIR / "outputs")))
TOOL_DIR = Path(os.getenv("PERMANENCE_TOOL_DIR", str(BASE_DIR / "memory" / "tool")))
INBOX_DIR = Path(os.getenv("PERMANENCE_ATTACHMENT_INBOX_DIR", str(BASE_DIR / "memory" / "inbox" / "attachments")))
TRANSCRIPTION_QUEUE_PATH = Path(
    os.getenv("PERMANENCE_TRANSCRIPTION_QUEUE_PATH", str(WORKING_DIR / "transcription_queue.json"))
)

DOC_EXTS = {".txt", ".md", ".markdown", ".json", ".pdf", ".doc", ".docx", ".rtf"}
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".heic", ".bmp", ".tiff"}
AUDIO_EXTS = {".wav", ".mp3", ".m4a", ".aac", ".flac", ".ogg", ".aiff"}
VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"}


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


def _safe_int(value: Any) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def _attachment_kind(ext: str) -> str:
    token = str(ext or "").strip().lower()
    if token in DOC_EXTS:
        return "document"
    if token in IMAGE_EXTS:
        return "image"
    if token in AUDIO_EXTS:
        return "audio"
    if token in VIDEO_EXTS:
        return "video"
    return "other"


def _hash_file(path: Path) -> str:
    hasher = hashlib.sha1()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(64 * 1024), b""):
                hasher.update(chunk)
    except OSError:
        return ""
    return hasher.hexdigest()


def _short_excerpt(path: Path, limit: int = 220) -> str:
    ext = path.suffix.lower()
    if ext not in {".txt", ".md", ".markdown"}:
        return ""
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""
    normalized = " ".join(text.split())
    if len(normalized) <= limit:
        return normalized
    return normalized[: max(0, limit - 3)].rstrip() + "..."


def _collect_entries(inbox_dir: Path, max_files: int) -> list[dict[str, Any]]:
    if not inbox_dir.exists():
        inbox_dir.mkdir(parents=True, exist_ok=True)
    files: list[Path] = []
    for path in inbox_dir.rglob("*"):
        if path.is_file():
            files.append(path)
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    files = files[: max(1, max_files)]

    entries: list[dict[str, Any]] = []
    for path in files:
        ext = path.suffix.lower()
        kind = _attachment_kind(ext)
        stat = path.stat()
        digest = _hash_file(path)
        rel = str(path.relative_to(inbox_dir))
        entry = {
            "attachment_id": f"AT-{digest[:12]}" if digest else f"AT-{hash(rel) & 0xFFFFFFFF:08x}",
            "filename": path.name,
            "relative_path": rel,
            "path": str(path),
            "kind": kind,
            "extension": ext or "",
            "size_bytes": int(stat.st_size),
            "modified_at": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
            "sha1": digest,
            "excerpt": _short_excerpt(path),
        }
        entries.append(entry)
    return entries


def _build_counts(entries: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"total": len(entries), "document": 0, "image": 0, "audio": 0, "video": 0, "other": 0}
    for item in entries:
        kind = str(item.get("kind") or "other").strip().lower()
        if kind not in counts:
            kind = "other"
        counts[kind] += 1
    return counts


def _build_transcription_queue(entries: list[dict[str, Any]], path: Path) -> tuple[list[dict[str, Any]], int]:
    existing = _read_json(path, [])
    rows = existing if isinstance(existing, list) else []
    by_source: dict[str, dict[str, Any]] = {}
    for row in rows:
        if isinstance(row, dict) and row.get("source_path"):
            by_source[str(row.get("source_path"))] = row

    created = 0
    for item in entries:
        kind = str(item.get("kind") or "").lower()
        if kind not in {"audio", "video"}:
            continue
        source_path = str(item.get("path") or "")
        if not source_path:
            continue
        existing_row = by_source.get(source_path)
        if existing_row:
            existing_row["updated_at"] = _now_iso()
            continue
        created += 1
        by_source[source_path] = {
            "queue_id": f"TQ-{hashlib.sha1(source_path.encode('utf-8')).hexdigest()[:12]}",
            "source_path": source_path,
            "kind": kind,
            "status": "pending_manual_transcribe",
            "notes": "Transcribe to memory/working/clipping_transcripts then run clipping-transcript-ingest.",
            "created_at": _now_iso(),
            "updated_at": _now_iso(),
        }

    queue = sorted(by_source.values(), key=lambda row: str(row.get("updated_at") or ""), reverse=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(queue, indent=2) + "\n", encoding="utf-8")
    return queue, created


def _write_outputs(
    *,
    inbox_dir: Path,
    entries: list[dict[str, Any]],
    counts: dict[str, int],
    queue: list[dict[str, Any]],
    queue_created: int,
    queue_path: Path,
) -> tuple[Path, Path]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    TOOL_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _now().strftime("%Y%m%d-%H%M%S")
    md_path = OUTPUT_DIR / f"attachment_pipeline_{stamp}.md"
    latest_md = OUTPUT_DIR / "attachment_pipeline_latest.md"
    json_path = TOOL_DIR / f"attachment_pipeline_{stamp}.json"

    lines = [
        "# Attachment Pipeline",
        "",
        f"Generated (UTC): {_now_iso()}",
        f"Inbox directory: {inbox_dir}",
        "",
        "## Attachment Inventory",
        f"- Total files: {_safe_int(counts.get('total'))}",
        f"- Documents: {_safe_int(counts.get('document'))}",
        f"- Images: {_safe_int(counts.get('image'))}",
        f"- Audio: {_safe_int(counts.get('audio'))}",
        f"- Video: {_safe_int(counts.get('video'))}",
        f"- Other: {_safe_int(counts.get('other'))}",
        "",
        "## Recent Files",
    ]
    if not entries:
        lines.append("- Inbox is empty. Upload files to activate this module.")
    for row in entries[:25]:
        lines.append(
            f"- [{row.get('kind')}] {row.get('relative_path')} | size={row.get('size_bytes')} | modified={row.get('modified_at')}"
        )
        excerpt = str(row.get("excerpt") or "").strip()
        if excerpt:
            lines.append(f"  excerpt: {excerpt}")

    pending_transcribe = sum(1 for row in queue if str(row.get("status") or "").startswith("pending"))
    lines.extend(
        [
            "",
            "## Transcription Queue",
            f"- Queue file: {queue_path}",
            f"- Total queue items: {len(queue)}",
            f"- Pending transcription items: {pending_transcribe}",
            f"- Newly queued this run: {queue_created}",
            "",
            "## Next Actions",
            f"1. Run `python cli.py ingest-docs --doc-dir \"{inbox_dir}\"` to ingest document attachments.",
            "2. For audio/video files, transcribe into `memory/working/clipping_transcripts`.",
            "3. Run `python cli.py clipping-transcript-ingest` then `python cli.py clipping-pipeline`.",
            "",
            "## Governance Notes",
            "- Attachment indexing is read-only on source files.",
            "- External publishing remains manual approval only.",
            "",
        ]
    )

    report = "\n".join(lines)
    md_path.write_text(report, encoding="utf-8")
    latest_md.write_text(report, encoding="utf-8")

    payload = {
        "generated_at": _now_iso(),
        "inbox_dir": str(inbox_dir),
        "counts": counts,
        "entries": entries[:150],
        "transcription_queue_path": str(queue_path),
        "transcription_queue_total": len(queue),
        "transcription_queue_pending": pending_transcribe,
        "transcription_queue_created": queue_created,
        "latest_markdown": str(latest_md),
    }
    json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return md_path, json_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Index attachment inbox and build processing queues.")
    parser.add_argument("--inbox-dir", default=str(INBOX_DIR), help="Attachment inbox directory")
    parser.add_argument("--max-files", type=int, default=250, help="Max files to index per run")
    parser.add_argument("--queue-path", default=str(TRANSCRIPTION_QUEUE_PATH), help="Transcription queue JSON path")
    args = parser.parse_args(argv)

    inbox_dir = Path(args.inbox_dir).expanduser().resolve()
    queue_path = Path(args.queue_path).expanduser().resolve()

    entries = _collect_entries(inbox_dir=inbox_dir, max_files=max(1, int(args.max_files)))
    counts = _build_counts(entries)
    queue, created = _build_transcription_queue(entries, queue_path)
    md_path, json_path = _write_outputs(
        inbox_dir=inbox_dir,
        entries=entries,
        counts=counts,
        queue=queue,
        queue_created=created,
        queue_path=queue_path,
    )
    print(f"Attachment pipeline written: {md_path}")
    print(f"Attachment pipeline latest: {OUTPUT_DIR / 'attachment_pipeline_latest.md'}")
    print(f"Tool payload written: {json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

