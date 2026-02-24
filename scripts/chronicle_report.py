#!/usr/bin/env python3
"""
Build a timeline report from chronicle events + git history.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from scripts.chronicle_common import (
    BASE_DIR,
    CHRONICLE_EVENTS,
    CHRONICLE_OUTPUT_DIR,
    read_jsonl,
    utc_iso,
)


def _parse_ts(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None


def _git_commits(days: int, max_commits: int) -> list[dict[str, str]]:
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    cmd = [
        "git",
        "log",
        f"--since={since}",
        f"-n{max_commits}",
        "--date=iso-strict",
        "--pretty=format:%H%x09%ad%x09%s",
    ]
    try:
        raw = subprocess.check_output(cmd, cwd=BASE_DIR).decode("utf-8", errors="ignore")
    except Exception:
        return []

    out: list[dict[str, str]] = []
    for line in raw.splitlines():
        parts = line.split("\t", 2)
        if len(parts) != 3:
            continue
        out.append({"hash": parts[0], "timestamp": parts[1], "subject": parts[2]})
    return out


def _build_md(report: dict[str, Any]) -> str:
    lines: list[str] = [
        "# Chronicle Timeline Report",
        "",
        f"- Generated: {report['generated_at']}",
        f"- Window: last {report['days']} days",
        f"- Chronicle events: {report['events_count']}",
        f"- Git commits in window: {report['commit_count']}",
        "",
        "## Event Types",
    ]
    for event_type, count in sorted(report["event_type_counts"].items(), key=lambda x: (-x[1], x[0])):
        lines.append(f"- {event_type}: {count}")

    lines.extend(
        [
            "",
            "## Signal Summary",
            f"- Direction hits: {report['signal_totals']['direction_hits']}",
            f"- Frustration hits: {report['signal_totals']['frustration_hits']}",
            f"- Issue hits: {report['signal_totals']['issue_hits']}",
            f"- Log error hits: {report['signal_totals']['log_error_hits']}",
            f"- Log warning hits: {report['signal_totals']['log_warning_hits']}",
            f"- Backfill records analyzed: {report['signal_totals']['backfill_records_analyzed']}",
            "",
            "## Timeline",
        ]
    )

    if report["timeline"]:
        for item in report["timeline"]:
            lines.append(f"- {item['timestamp']} | {item['type']} | {item['summary']}")
    else:
        lines.append("- none")

    lines.extend(["", "## Direction Shifts (Detected)"])
    if report["direction_events"]:
        for item in report["direction_events"]:
            lines.append(f"- {item['timestamp']} | {item['summary']}")
    else:
        lines.append("- none")

    lines.extend(["", "## Friction / Issues (Detected)"])
    if report["issue_events"]:
        for item in report["issue_events"]:
            lines.append(f"- {item['timestamp']} | {item['summary']}")
    else:
        lines.append("- none")

    lines.extend(["", "## Recent Commits"])
    if report["commits"]:
        for c in report["commits"]:
            lines.append(f"- {c['timestamp']} | `{c['hash'][:8]}` | {c['subject']}")
    else:
        lines.append("- none")

    lines.extend(["", "## Source Artifacts"])
    if report["source_artifacts"]:
        for p in report["source_artifacts"]:
            lines.append(f"- {p}")
    else:
        lines.append("- none")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate chronicle timeline report.")
    parser.add_argument("--days", type=int, default=180, help="Lookback window in days")
    parser.add_argument("--max-events", type=int, default=400, help="Max timeline events")
    parser.add_argument("--max-commits", type=int, default=120, help="Max commits to include")
    parser.add_argument("--output", help="Output markdown path")
    args = parser.parse_args()

    all_events = read_jsonl(CHRONICLE_EVENTS)
    cutoff = datetime.now(timezone.utc) - timedelta(days=args.days)
    filtered: list[dict[str, Any]] = []
    for item in all_events:
        ts = _parse_ts(str(item.get("timestamp", "")))
        if ts is None:
            continue
        if ts >= cutoff:
            filtered.append(item)

    filtered.sort(key=lambda x: str(x.get("timestamp", "")))
    if len(filtered) > args.max_events:
        filtered = filtered[-args.max_events :]

    event_type_counts: Counter[str] = Counter(str(x.get("type", "unknown")) for x in filtered)
    commits = _git_commits(days=args.days, max_commits=args.max_commits)

    direction_hits = 0
    frustration_hits = 0
    issue_hits = 0
    log_error_hits = 0
    log_warning_hits = 0
    backfill_direction_hits = 0
    backfill_frustration_hits = 0
    backfill_issue_hits = 0
    backfill_records_analyzed = 0
    timeline: list[dict[str, str]] = []
    direction_events: list[dict[str, str]] = []
    issue_events: list[dict[str, str]] = []
    source_artifacts: list[str] = []

    for ev in filtered:
        ts = str(ev.get("timestamp", ""))
        et = str(ev.get("type", "unknown"))
        note = str(ev.get("note", "")).strip()
        files_processed = ev.get("files_processed")
        roots = ev.get("roots")

        note_sig = ev.get("note_signals") or {}
        chat_sig = ev.get("chat_signals") or {}
        direction = int(note_sig.get("direction_hits", 0)) + int(chat_sig.get("direction_hits", 0))
        frustration = int(note_sig.get("frustration_hits", 0)) + int(chat_sig.get("frustration_hits", 0))
        issues = int(note_sig.get("issue_hits", 0)) + int(chat_sig.get("issue_hits", 0))
        direction_hits += direction
        frustration_hits += frustration
        issue_hits += issues

        log_counts = ev.get("log_issue_counts") or {}
        log_error_hits += int(log_counts.get("error_hits", 0))
        log_warning_hits += int(log_counts.get("warning_hits", 0))

        summary = note if note else f"type={et}"
        if isinstance(files_processed, int):
            summary = f"{summary} | files_processed={files_processed}"
        if isinstance(roots, list) and roots:
            summary = f"{summary} | roots={len(roots)}"

        timeline.append({"timestamp": ts, "type": et, "summary": summary[:220]})

        if direction > 0:
            direction_events.append({"timestamp": ts, "summary": summary[:220]})
        if issues > 0 or int(log_counts.get("error_hits", 0)) > 0:
            issue_events.append({"timestamp": ts, "summary": summary[:220]})

        for key in ("snapshot_json", "report_md", "chat_file"):
            value = ev.get(key)
            if isinstance(value, str) and value:
                source_artifacts.append(value)

        if et == "backfill_scan":
            snapshot_json = ev.get("snapshot_json")
            if isinstance(snapshot_json, str) and snapshot_json:
                snapshot_path = Path(snapshot_json)
                if snapshot_path.exists():
                    try:
                        data = json.loads(snapshot_path.read_text(encoding="utf-8"))
                    except Exception:
                        data = {}
                    records = data.get("records")
                    if isinstance(records, list):
                        for rec in records:
                            if not isinstance(rec, dict):
                                continue
                            sig = rec.get("signals") or {}
                            backfill_direction_hits += int(sig.get("direction_hits", 0))
                            backfill_frustration_hits += int(sig.get("frustration_hits", 0))
                            backfill_issue_hits += int(sig.get("issue_hits", 0))
                            backfill_records_analyzed += 1

    source_artifacts = sorted(set(source_artifacts))

    report = {
        "generated_at": utc_iso(),
        "days": args.days,
        "events_count": len(filtered),
        "commit_count": len(commits),
        "event_type_counts": dict(event_type_counts),
        "signal_totals": {
            "direction_hits": direction_hits + backfill_direction_hits,
            "frustration_hits": frustration_hits + backfill_frustration_hits,
            "issue_hits": issue_hits + backfill_issue_hits,
            "log_error_hits": log_error_hits,
            "log_warning_hits": log_warning_hits,
            "backfill_records_analyzed": backfill_records_analyzed,
        },
        "timeline": timeline,
        "direction_events": direction_events[-80:],
        "issue_events": issue_events[-80:],
        "commits": commits,
        "source_artifacts": source_artifacts,
    }

    CHRONICLE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    md_path = Path(args.output).expanduser() if args.output else CHRONICLE_OUTPUT_DIR / f"chronicle_report_{stamp}.md"
    json_path = md_path.with_suffix(".json")

    md_path.write_text(_build_md(report), encoding="utf-8")
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"Chronicle report: {md_path}")
    print(f"Chronicle JSON: {json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
