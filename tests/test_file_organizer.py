#!/usr/bin/env python3
"""Tests for safe file organizer scan/apply flows."""

import json
import os
import sys
import tempfile
import time
from pathlib import Path

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from scripts.file_organizer import apply_plan, build_plan, write_scan_artifacts


def test_build_plan_and_apply_moves_to_quarantine():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "Downloads"
        output_dir = Path(tmp) / "outputs"
        quarantine_root = Path(tmp) / "quarantine"
        root.mkdir(parents=True, exist_ok=True)

        dup_a = root / "dup_a.txt"
        dup_b = root / "dup_b.txt"
        stale = root / "stale.txt"
        large = root / "large.bin"

        dup_payload = "same-content-" * 120  # >1KB for duplicate hashing threshold
        dup_a.write_text(dup_payload)
        dup_b.write_text(dup_payload)
        stale.write_text("old")
        large.write_bytes(b"x" * 2 * 1024 * 1024)  # 2 MB

        old = time.time() - (40 * 24 * 60 * 60)
        os.utime(stale, (old, old))

        plan = build_plan(
            roots=[str(root)],
            stale_days=30,
            min_large_mb=1,
            top_large=10,
            duplicate_min_kb=1,
            quarantine_root=str(quarantine_root),
        )
        assert plan["scan_summary"]["files_scanned"] >= 4
        assert plan["scan_summary"]["large_files_count"] >= 1
        assert plan["scan_summary"]["duplicate_groups"] >= 1
        assert plan["scan_summary"]["actions_count"] >= 2

        plan_path, report_path = write_scan_artifacts(plan, output_dir=str(output_dir))
        assert os.path.exists(plan_path)
        assert os.path.exists(report_path)

        result = apply_plan(plan_path=plan_path, dry_run=False)
        assert result["failed"] == 0
        assert result["moved"] >= 2
        assert os.path.isdir(result["run_dir"])
        assert os.path.exists(result["manifest_path"])

        with open(plan_path, "r") as handle:
            loaded = json.load(handle)
        moved_targets = [a["path"] for a in loaded["actions"]]
        assert any(str(stale) == p for p in moved_targets)
        assert any(str(dup_b) == p or str(dup_a) == p for p in moved_targets)


if __name__ == "__main__":
    test_build_plan_and_apply_moves_to_quarantine()
    print("ok")
