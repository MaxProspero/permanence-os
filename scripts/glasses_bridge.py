#!/usr/bin/env python3
"""
Bridge smart-glasses events into local Permanence OS pipelines.

Use cases:
- Ingest exported detection logs (e.g., Nearby Glasses JSON exports)
- Intake ad-hoc POV events from VisionClaw / Meta glasses workflows
- Copy media into attachment inbox for downstream processing
- Mirror inbound events into Ari reception + research inbox queues
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.append(str(BASE_DIR))

from agents.departments.reception_agent import ReceptionAgent  # noqa: E402
from scripts.research_inbox import add_entry as add_research_entry  # noqa: E402

URL_RE = re.compile(r"https?://[^\s<>\"]+")
MEDIA_PATH_KEYS = (
    "media",
    "media_path",
    "media_paths",
    "image",
    "image_path",
    "image_paths",
    "photo",
    "photo_path",
    "photo_paths",
    "video",
    "video_path",
    "video_paths",
    "audio",
    "audio_path",
    "audio_paths",
    "file",
    "file_path",
    "file_paths",
)
EMBEDDED_IMAGE_KEYS = (
    "photoData",
    "photo_data",
    "imageData",
    "image_data",
    "image_base64",
    "photo_base64",
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now().isoformat()


def _working_dir() -> Path:
    return Path(os.getenv("PERMANENCE_WORKING_DIR", str(BASE_DIR / "memory" / "working")))


def _output_dir() -> Path:
    return Path(os.getenv("PERMANENCE_OUTPUT_DIR", str(BASE_DIR / "outputs")))


def _tool_dir() -> Path:
    return Path(os.getenv("PERMANENCE_TOOL_DIR", str(BASE_DIR / "memory" / "tool")))


def _default_events_path() -> Path:
    return Path(
        os.getenv(
            "PERMANENCE_GLASSES_EVENTS_PATH",
            str(_working_dir() / "glasses" / "events.jsonl"),
        )
    )


def _default_attachment_inbox() -> Path:
    return Path(
        os.getenv(
            "PERMANENCE_ATTACHMENT_INBOX_DIR",
            str(BASE_DIR / "memory" / "inbox" / "attachments"),
        )
    )


def _default_reception_queue() -> Path:
    return Path(
        os.getenv(
            "PERMANENCE_RECEPTION_QUEUE_DIR",
            str(_working_dir() / "reception"),
        )
    )


def _default_research_inbox_path() -> Path:
    return Path(
        os.getenv(
            "PERMANENCE_RESEARCH_INBOX_PATH",
            str(_working_dir() / "research" / "inbox.jsonl"),
        )
    )


def _safe_json_load(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _iter_payload_events(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict):
        for key in ("detections", "events", "items", "records", "entries", "results"):
            rows = payload.get(key)
            if isinstance(rows, list):
                return [row for row in rows if isinstance(row, dict)]
        return [payload]
    return []


def _parse_timestamp(value: Any) -> str:
    if isinstance(value, (int, float)):
        number = float(value)
        if number > 10_000_000_000:
            number = number / 1000.0
        try:
            return datetime.fromtimestamp(number, tz=timezone.utc).isoformat()
        except (OverflowError, OSError, ValueError):
            return _now_iso()
    if isinstance(value, str):
        token = value.strip()
        if not token:
            return _now_iso()
        if token.isdigit():
            return _parse_timestamp(int(token))
        try:
            return datetime.fromisoformat(token.replace("Z", "+00:00")).astimezone(timezone.utc).isoformat()
        except ValueError:
            pass
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S"):
            try:
                dt = datetime.strptime(token, fmt).replace(tzinfo=timezone.utc)
                return dt.isoformat()
            except ValueError:
                continue
    return _now_iso()


def _event_source(raw: dict[str, Any], source_override: str | None) -> str:
    if source_override:
        return source_override.strip()
    explicit = str(raw.get("source") or "").strip()
    if explicit:
        return explicit
    lowered_keys = {str(key).strip().lower() for key in raw.keys()}
    if {"detectionreason", "rssi"} & lowered_keys:
        return "yj_nearbyglasses"
    if "companyid" in lowered_keys and "companyname" in lowered_keys:
        return "yj_nearbyglasses"
    if {"tool_call", "tool_calls", "gemini", "openclaw"} & lowered_keys:
        return "visionclaw"
    if {"photodata", "captured_media", "glasses"} & lowered_keys:
        return "meta_glasses"
    return "glasses"


def _extract_urls(text: str) -> list[str]:
    seen: set[str] = set()
    urls: list[str] = []
    for match in URL_RE.findall(text or ""):
        cleaned = match.rstrip(".,);]")
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            urls.append(cleaned)
    return urls


def _extract_urls_from_event(raw: dict[str, Any], message: str, cli_urls: list[str]) -> list[str]:
    merged = list(cli_urls)
    for key in ("url", "link", "source_url"):
        value = raw.get(key)
        if isinstance(value, str) and value.strip():
            merged.append(value.strip())
    for key in ("urls", "links"):
        value = raw.get(key)
        if isinstance(value, list):
            for item in value:
                if isinstance(item, str) and item.strip():
                    merged.append(item.strip())
    merged.extend(_extract_urls(message))
    unique: list[str] = []
    seen: set[str] = set()
    for url in merged:
        cleaned = url.rstrip(".,);]")
        if cleaned.startswith("http") and cleaned not in seen:
            seen.add(cleaned)
            unique.append(cleaned)
    return unique


def _event_message(raw: dict[str, Any], text_override: str | None) -> str:
    if text_override and text_override.strip():
        return text_override.strip()
    for key in ("message", "text", "prompt", "user_text", "assistant_text", "assistant_response", "note"):
        value = raw.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    if "detectionReason" in raw or "rssi" in raw:
        device = str(raw.get("deviceName") or "Unknown device").strip()
        reason = str(raw.get("detectionReason") or "smart-glasses proximity signal").strip()
        company = str(raw.get("companyName") or "Unknown company").strip()
        rssi = raw.get("rssi")
        if rssi is None:
            return f"Nearby-glasses detection: {device} | {company} | reason: {reason}"
        return f"Nearby-glasses detection: {device} ({rssi} dBm) | {company} | reason: {reason}"
    event_type = str(raw.get("type") or raw.get("event") or "event").strip()
    return f"Glasses event captured ({event_type})."


def _candidate_media_paths(raw: dict[str, Any], cli_media: list[str]) -> list[Path]:
    paths: list[str] = [item for item in cli_media if item.strip()]
    for key in MEDIA_PATH_KEYS:
        value = raw.get(key)
        if isinstance(value, str) and value.strip():
            paths.append(value.strip())
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, str) and item.strip():
                    paths.append(item.strip())
    resolved: list[Path] = []
    seen: set[str] = set()
    for item in paths:
        if item.startswith("file://"):
            item = item[7:]
        path = Path(item).expanduser()
        token = str(path)
        if token in seen:
            continue
        seen.add(token)
        resolved.append(path)
    return resolved


def _decode_base64_image(raw: dict[str, Any], event_id: str, attachments_dir: Path) -> list[Path]:
    written: list[Path] = []
    attachments_dir.mkdir(parents=True, exist_ok=True)
    for key in EMBEDDED_IMAGE_KEYS:
        value = raw.get(key)
        if not isinstance(value, str):
            continue
        token = value.strip()
        if not token:
            continue
        if token.startswith("data:image/") and "," in token:
            token = token.split(",", 1)[1]
        token = "".join(token.split())
        if len(token) < 120:
            continue
        padding = len(token) % 4
        if padding:
            token += "=" * (4 - padding)
        try:
            payload = base64.b64decode(token, validate=True)
        except (ValueError, base64.binascii.Error):
            continue
        if len(payload) < 64:
            continue
        ext = ".jpg"
        if payload.startswith(b"\x89PNG"):
            ext = ".png"
        elif payload.startswith(b"GIF8"):
            ext = ".gif"
        out = attachments_dir / f"glasses_{event_id}_{key}{ext}"
        out.write_bytes(payload)
        written.append(out)
    return written


def _copy_media_files(paths: list[Path], event_id: str, attachments_dir: Path) -> tuple[list[Path], list[str]]:
    attachments_dir.mkdir(parents=True, exist_ok=True)
    copied: list[Path] = []
    warnings: list[str] = []
    for src in paths:
        if not src.exists() or not src.is_file():
            warnings.append(f"media not found: {src}")
            continue
        safe_name = src.name.replace(" ", "_")
        dest = attachments_dir / f"glasses_{event_id}_{safe_name}"
        if dest.exists():
            stem = dest.stem
            suffix = dest.suffix
            dest = attachments_dir / f"{stem}_{int(_now().timestamp())}{suffix}"
        shutil.copy2(src, dest)
        copied.append(dest)
    return copied, warnings


def _entry_id(source: str, event_time: str, message: str, raw: dict[str, Any]) -> str:
    payload = json.dumps(raw, sort_keys=True, default=str)
    digest = hashlib.sha256(f"{source}|{event_time}|{message}|{payload}".encode("utf-8")).hexdigest()
    return f"gls_{digest[:12]}"


def _normalize_priority(value: Any) -> str:
    token = str(value or "").strip().lower()
    if token in {"urgent", "high"}:
        return "urgent"
    if token in {"normal", "low"}:
        return token
    return "normal"


def _append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=True) + "\n")


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        token = line.strip()
        if not token:
            continue
        try:
            parsed = json.loads(token)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            rows.append(parsed)
    return rows


def _process_one_event(
    *,
    raw_event: dict[str, Any],
    source_override: str | None,
    channel_override: str | None,
    sender_override: str | None,
    text_override: str | None,
    cli_urls: list[str],
    cli_media: list[str],
    to_reception: bool,
    to_research: bool,
    to_attachments: bool,
    events_path: Path,
    attachments_dir: Path,
    reception_queue_dir: Path,
    research_inbox_path: Path,
) -> tuple[dict[str, Any], list[str]]:
    source = _event_source(raw_event, source_override)
    event_time = _parse_timestamp(
        raw_event.get("timestamp")
        or raw_event.get("created_at")
        or raw_event.get("event_time")
        or raw_event.get("timestampFormatted")
    )
    message = _event_message(raw_event, text_override)
    channel = str(channel_override or raw_event.get("channel") or "glasses").strip()
    sender = str(sender_override or raw_event.get("sender") or raw_event.get("deviceName") or source).strip()
    urls = _extract_urls_from_event(raw_event, message, cli_urls)
    event_id = _entry_id(source=source, event_time=event_time, message=message, raw=raw_event)
    priority = _normalize_priority(raw_event.get("priority"))

    warnings: list[str] = []
    media_files: list[Path] = []
    if to_attachments:
        embedded = _decode_base64_image(raw_event, event_id=event_id, attachments_dir=attachments_dir)
        media_candidates = _candidate_media_paths(raw_event, cli_media=cli_media)
        copied, copy_warnings = _copy_media_files(media_candidates, event_id=event_id, attachments_dir=attachments_dir)
        media_files.extend(embedded)
        media_files.extend(copied)
        warnings.extend(copy_warnings)

    stored = {
        "event_id": event_id,
        "captured_at": _now_iso(),
        "event_time": event_time,
        "source": source,
        "channel": channel,
        "sender": sender,
        "priority": priority,
        "message": message,
        "urls": urls,
        "media_files": [str(path) for path in media_files],
        "raw_event": raw_event,
    }
    _append_jsonl(events_path, stored)

    if to_reception:
        agent = ReceptionAgent()
        agent.execute(
            {
                "action": "intake",
                "queue_dir": str(reception_queue_dir),
                "sender": sender,
                "message": message,
                "channel": channel,
                "source": source,
                "priority": priority,
            }
        )

    if to_research and urls:
        research_text = f"{message}\n" + "\n".join(urls)
        add_research_entry(
            text=research_text,
            source=source,
            channel=channel,
            inbox_path=str(research_inbox_path),
        )

    return stored, warnings


def _write_run_report(
    *,
    action: str,
    events_path: Path,
    processed: list[dict[str, Any]],
    warnings: list[str],
) -> tuple[Path, Path]:
    output_dir = _output_dir()
    tool_dir = _tool_dir()
    output_dir.mkdir(parents=True, exist_ok=True)
    tool_dir.mkdir(parents=True, exist_ok=True)
    stamp = _now().strftime("%Y%m%d-%H%M%S")
    md_path = output_dir / f"glasses_bridge_{stamp}.md"
    latest_md = output_dir / "glasses_bridge_latest.md"
    json_path = tool_dir / f"glasses_bridge_{stamp}.json"

    by_source: dict[str, int] = {}
    media_total = 0
    for item in processed:
        source = str(item.get("source") or "unknown")
        by_source[source] = by_source.get(source, 0) + 1
        media_total += len(item.get("media_files") or [])

    lines = [
        "# Glasses Bridge",
        "",
        f"Generated (UTC): {_now_iso()}",
        f"Action: {action}",
        f"Events path: {events_path}",
        "",
        "## Summary",
        f"- Events processed this run: {len(processed)}",
        f"- Media files copied this run: {media_total}",
        f"- Warnings: {len(warnings)}",
        "",
        "## Source Counts",
    ]
    if not by_source:
        lines.append("- none")
    else:
        for source, count in sorted(by_source.items()):
            lines.append(f"- {source}: {count}")
    lines.extend(["", "## Recent Events"])
    for row in processed[-20:]:
        lines.append(
            f"- [{row.get('source')}] {row.get('event_id')} | {row.get('channel')} | {row.get('message')}"
        )
        urls = row.get("urls") or []
        if urls:
            lines.append(f"  urls={len(urls)}")
        media = row.get("media_files") or []
        if media:
            lines.append(f"  media={len(media)}")
    if warnings:
        lines.extend(["", "## Warnings"])
        for item in warnings[:50]:
            lines.append(f"- {item}")
    lines.append("")
    report = "\n".join(lines)
    md_path.write_text(report, encoding="utf-8")
    latest_md.write_text(report, encoding="utf-8")

    payload = {
        "generated_at": _now_iso(),
        "action": action,
        "events_path": str(events_path),
        "processed_count": len(processed),
        "media_file_count": media_total,
        "warnings": warnings,
        "source_counts": by_source,
        "events": processed[-200:],
        "latest_markdown": str(latest_md),
    }
    json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return md_path, json_path


def _status(events_path: Path, max_items: int) -> int:
    rows = _read_jsonl(events_path)
    recent = rows[-max(1, max_items) :]
    by_source: dict[str, int] = {}
    for row in rows:
        source = str(row.get("source") or "unknown")
        by_source[source] = by_source.get(source, 0) + 1
    print(f"Events path: {events_path}")
    print(f"Total events: {len(rows)}")
    for source, count in sorted(by_source.items()):
        print(f"  - {source}: {count}")
    if recent:
        print("Recent:")
        for row in reversed(recent):
            print(f"  - {row.get('event_time')} | {row.get('source')} | {row.get('message')}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Bridge smart-glasses events into Permanence OS intake queues.")
    parser.add_argument("--action", choices=["ingest", "intake", "status"], default="status")
    parser.add_argument("--from-json", action="append", default=[], help="Path to exported JSON event file")
    parser.add_argument("--text", help="Direct event text for intake")
    parser.add_argument("--source", help="Source override (e.g., visionclaw, yj_nearbyglasses)")
    parser.add_argument("--channel", help="Channel override (default: glasses)")
    parser.add_argument("--sender", help="Sender override")
    parser.add_argument("--url", action="append", default=[], help="Attach URL (repeatable)")
    parser.add_argument("--media", action="append", default=[], help="Media path to copy into attachment inbox")
    parser.add_argument("--events-path", help="Events JSONL path")
    parser.add_argument("--attachments-dir", help="Attachment inbox directory")
    parser.add_argument("--reception-queue-dir", help="Ari queue directory")
    parser.add_argument("--research-inbox-path", help="Research inbox JSONL path")
    parser.add_argument("--max-items", type=int, default=20, help="Status: max recent items to print")
    parser.add_argument("--no-reception", action="store_true", help="Skip Ari intake mirroring")
    parser.add_argument("--no-research", action="store_true", help="Skip research inbox mirroring")
    parser.add_argument("--no-attachments", action="store_true", help="Skip media copy/extract")
    args = parser.parse_args(argv)

    events_path = Path(args.events_path).expanduser() if args.events_path else _default_events_path()
    attachments_dir = (
        Path(args.attachments_dir).expanduser()
        if args.attachments_dir
        else _default_attachment_inbox()
    )
    reception_queue_dir = (
        Path(args.reception_queue_dir).expanduser()
        if args.reception_queue_dir
        else _default_reception_queue()
    )
    research_inbox_path = (
        Path(args.research_inbox_path).expanduser()
        if args.research_inbox_path
        else _default_research_inbox_path()
    )

    if args.action == "status":
        return _status(events_path=events_path, max_items=max(1, int(args.max_items)))

    payload_events: list[dict[str, Any]] = []
    warnings: list[str] = []
    if args.action == "ingest":
        if not args.from_json and not (args.text or "").strip():
            print("ingest requires --from-json and/or --text")
            return 2
        for item in args.from_json:
            path = Path(item).expanduser()
            payload = _safe_json_load(path)
            if payload is None:
                warnings.append(f"invalid json: {path}")
                continue
            rows = _iter_payload_events(payload)
            if not rows:
                warnings.append(f"no events found: {path}")
            payload_events.extend(rows)
        if (args.text or "").strip():
            payload_events.append({"message": args.text, "urls": args.url, "media_paths": args.media})
    elif args.action == "intake":
        if not (args.text or "").strip() and not args.from_json:
            print("intake requires --text or --from-json")
            return 2
        if args.from_json:
            for item in args.from_json:
                path = Path(item).expanduser()
                payload = _safe_json_load(path)
                if payload is None:
                    warnings.append(f"invalid json: {path}")
                    continue
                payload_events.extend(_iter_payload_events(payload))
        if (args.text or "").strip():
            payload_events.append({"message": args.text, "urls": args.url, "media_paths": args.media})

    processed: list[dict[str, Any]] = []
    for raw_event in payload_events:
        item, item_warnings = _process_one_event(
            raw_event=raw_event,
            source_override=args.source,
            channel_override=args.channel,
            sender_override=args.sender,
            text_override=args.text if args.action == "intake" and len(payload_events) == 1 else None,
            cli_urls=args.url,
            cli_media=args.media,
            to_reception=not args.no_reception,
            to_research=not args.no_research,
            to_attachments=not args.no_attachments,
            events_path=events_path,
            attachments_dir=attachments_dir,
            reception_queue_dir=reception_queue_dir,
            research_inbox_path=research_inbox_path,
        )
        processed.append(item)
        warnings.extend(item_warnings)

    md_path, json_path = _write_run_report(
        action=args.action,
        events_path=events_path,
        processed=processed,
        warnings=warnings,
    )
    print(f"Glasses bridge written: {md_path}")
    print(f"Glasses bridge latest: {_output_dir() / 'glasses_bridge_latest.md'}")
    print(f"Tool payload written: {json_path}")
    print(f"Events processed: {len(processed)}")
    if warnings:
        print(f"Warnings: {len(warnings)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
