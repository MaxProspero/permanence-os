#!/usr/bin/env python3
"""
Create timestamped backup bundle for revenue working state + outputs.
"""

from __future__ import annotations

import argparse
import json
import os
import tarfile
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
WORKING_DIR = Path(os.getenv("PERMANENCE_WORKING_DIR", str(BASE_DIR / "memory" / "working")))
OUTPUT_DIR = Path(os.getenv("PERMANENCE_OUTPUT_DIR", str(BASE_DIR / "outputs")))
BACKUP_DIR = Path(os.getenv("PERMANENCE_BACKUP_DIR", str(BASE_DIR / "backups" / "revenue")))


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")


def _collect_paths() -> list[Path]:
    candidates = [
        WORKING_DIR / "sales_pipeline.json",
        WORKING_DIR / "revenue_intake.jsonl",
        WORKING_DIR / "revenue_playbook.json",
        WORKING_DIR / "revenue_targets.json",
        WORKING_DIR / "revenue_action_status.jsonl",
        WORKING_DIR / "revenue_outreach_status.jsonl",
        WORKING_DIR / "revenue_deal_events.jsonl",
        WORKING_DIR / "revenue_site_events.jsonl",
        OUTPUT_DIR / "revenue_action_queue_latest.md",
        OUTPUT_DIR / "revenue_execution_board_latest.md",
        OUTPUT_DIR / "revenue_outreach_pack_latest.md",
        OUTPUT_DIR / "revenue_followup_queue_latest.md",
        OUTPUT_DIR / "revenue_weekly_summary_latest.md",
        OUTPUT_DIR / "revenue_eval_latest.md",
        OUTPUT_DIR / "integration_readiness_latest.md",
    ]
    return [path for path in candidates if path.exists()]


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a compressed revenue backup bundle.")
    parser.add_argument("--dest-dir", default=str(BACKUP_DIR), help="Destination directory for backup archives")
    args = parser.parse_args()

    dest_dir = Path(os.path.expanduser(args.dest_dir))
    dest_dir.mkdir(parents=True, exist_ok=True)
    stamp = _utc_stamp()
    archive_path = dest_dir / f"revenue_backup_{stamp}.tar.gz"
    manifest_path = dest_dir / f"revenue_backup_{stamp}.json"
    latest_manifest = dest_dir / "revenue_backup_latest.json"

    files = _collect_paths()
    with tarfile.open(archive_path, "w:gz") as tar:
        for path in files:
            rel = path.relative_to(BASE_DIR) if path.is_relative_to(BASE_DIR) else path.name
            tar.add(path, arcname=str(rel))

    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "archive_path": str(archive_path),
        "file_count": len(files),
        "files": [str(path) for path in files],
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    latest_manifest.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Revenue backup archive: {archive_path}")
    print(f"Revenue backup manifest: {manifest_path}")
    print(f"Files included: {len(files)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
