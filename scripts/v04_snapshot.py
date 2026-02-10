#!/usr/bin/env python3
"""
Generate a compact v0.4 operations snapshot.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

from core.storage import storage  # noqa: E402


STATUS_RE = re.compile(
    r"Briefing Status:\s*(\d+)\s*\|\s*Digest Status:\s*(\d+)\s*\|\s*NotebookLM Status:\s*(\d+)"
)


def _load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text())
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _latest_name(path: Path, pattern: str) -> str:
    candidates = sorted(path.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0].name if candidates else "none"


def _latest_run_status() -> Dict[str, Any]:
    log_dir = Path(BASE_DIR) / "logs" / "automation"
    candidates = sorted(log_dir.glob("run_*.log"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not candidates:
        return {"run": "none", "briefing": None, "digest": None, "notebooklm": None}
    latest = candidates[0]
    text = latest.read_text(errors="ignore")
    match = STATUS_RE.search(text)
    if not match:
        return {"run": latest.name, "briefing": None, "digest": None, "notebooklm": None}
    return {
        "run": latest.name,
        "briefing": int(match.group(1)),
        "digest": int(match.group(2)),
        "notebooklm": int(match.group(3)),
    }


def _parse_iso(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None


def _zero_point_telemetry() -> Dict[str, Any]:
    zp_path = Path(os.getenv("PERMANENCE_ZERO_POINT_PATH", os.path.join(BASE_DIR, "memory", "zero_point_store.json")))
    payload = _load_json(zp_path)
    entries = payload.get("entries", {})
    if not isinstance(entries, dict):
        entries = {}

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=24)
    intake_24h = 0
    malformed_24h = 0
    training_total = 0
    forecast_total = 0

    for entry in entries.values():
        if not isinstance(entry, dict):
            continue
        memory_type = str(entry.get("memory_type", "")).upper()
        created = _parse_iso(entry.get("created_at") or entry.get("updated_at"))
        content = {}
        try:
            content = json.loads(str(entry.get("content", "{}")))
        except json.JSONDecodeError:
            content = {}

        if memory_type == "INTAKE":
            if created and created >= cutoff:
                intake_24h += 1
                if bool(content.get("malformed")) or bool(content.get("flags")):
                    malformed_24h += 1
        elif memory_type == "TRAINING":
            training_total += 1
        elif memory_type == "FORECAST":
            forecast_total += 1

    return {
        "entry_count": len(entries),
        "intake_24h": intake_24h,
        "malformed_24h": malformed_24h,
        "training_total": training_total,
        "forecast_total": forecast_total,
    }


def build_snapshot() -> List[str]:
    now = datetime.now(timezone.utc)
    run_status = _latest_run_status()
    status_today = _load_json(storage.paths.logs / "status_today.json")
    watch_state = _load_json(storage.paths.logs / "reliability_watch_state.json")
    telemetry = _zero_point_telemetry()

    lines = [
        "# V0.4 Snapshot",
        "",
        f"- Generated (UTC): {now.isoformat()}",
        f"- Storage root: {storage.paths.root}",
        "",
        "## Latest Run",
        f"- Log: {run_status['run']}",
        f"- Briefing status: {run_status['briefing']}",
        f"- Digest status: {run_status['digest']}",
        f"- NotebookLM status: {run_status['notebooklm']}",
        "",
        "## Glance",
        f"- Today state: {status_today.get('today_state', 'UNKNOWN')}",
        f"- Slot progress: {status_today.get('slot_progress', '0/0')}",
        f"- Streak: {(status_today.get('streak') or {}).get('current', 0)}/{(status_today.get('streak') or {}).get('target', 7)}",
        f"- Phase gate: {status_today.get('phase_gate', 'PENDING')}",
        "",
        "## Reliability Watch",
        f"- Active: {'yes' if watch_state and not watch_state.get('completed') and not watch_state.get('stopped') else 'no'}",
        f"- Ends at: {watch_state.get('ends_at_local', 'n/a')}",
        f"- Last check: {watch_state.get('last_check_local', 'n/a')}",
        f"- Last summary: {watch_state.get('last_summary', {})}",
        "",
        "## V0.4 Telemetry",
        f"- Zero Point entries: {telemetry['entry_count']}",
        f"- Intake (24h): {telemetry['intake_24h']} (malformed: {telemetry['malformed_24h']})",
        f"- Training entries: {telemetry['training_total']}",
        f"- Forecast entries: {telemetry['forecast_total']}",
        "",
        "## Outputs",
        f"- Latest briefing: {_latest_name(storage.paths.outputs_briefings, 'briefing_*.md')}",
        f"- Latest digest: {_latest_name(storage.paths.outputs_digests, 'sources_digest_*.md')}",
        f"- Latest synthesis draft: {_latest_name(storage.paths.outputs_synthesis_drafts, 'synthesis_*.md')}",
        f"- Latest synthesis final: {_latest_name(storage.paths.outputs_synthesis_final, 'synthesis_*.md')}",
        "",
    ]
    return lines


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate v0.4 operational snapshot")
    parser.add_argument("--output", help="Optional output path")
    args = parser.parse_args()

    if args.output:
        output_path = Path(os.path.expanduser(args.output))
        output_path.parent.mkdir(parents=True, exist_ok=True)
    else:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        output_path = storage.paths.outputs_snapshots / f"v04_snapshot_{stamp}.md"

    output_path.write_text("\n".join(build_snapshot()))
    print(f"V0.4 snapshot written to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
