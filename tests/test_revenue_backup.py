#!/usr/bin/env python3
"""Tests for revenue backup bundle generation."""

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import scripts.revenue_backup as backup_mod  # noqa: E402


def test_revenue_backup_creates_archive_and_manifest():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        working = root / "working"
        outputs = root / "outputs"
        backups = root / "backups"
        working.mkdir(parents=True, exist_ok=True)
        outputs.mkdir(parents=True, exist_ok=True)
        backups.mkdir(parents=True, exist_ok=True)

        (working / "sales_pipeline.json").write_text("[]\n", encoding="utf-8")
        (working / "revenue_playbook.json").write_text('{"offer_name":"x","cta_keyword":"y"}\n', encoding="utf-8")
        (outputs / "revenue_action_queue_latest.md").write_text("# queue\n", encoding="utf-8")

        original = {
            "BASE_DIR": backup_mod.BASE_DIR,
            "WORKING_DIR": backup_mod.WORKING_DIR,
            "OUTPUT_DIR": backup_mod.OUTPUT_DIR,
            "BACKUP_DIR": backup_mod.BACKUP_DIR,
            "argv": list(sys.argv),
        }
        try:
            backup_mod.BASE_DIR = root
            backup_mod.WORKING_DIR = working
            backup_mod.OUTPUT_DIR = outputs
            backup_mod.BACKUP_DIR = backups
            sys.argv = ["revenue_backup.py", "--dest-dir", str(backups)]
            rc = backup_mod.main()
        finally:
            backup_mod.BASE_DIR = original["BASE_DIR"]
            backup_mod.WORKING_DIR = original["WORKING_DIR"]
            backup_mod.OUTPUT_DIR = original["OUTPUT_DIR"]
            backup_mod.BACKUP_DIR = original["BACKUP_DIR"]
            sys.argv = original["argv"]

        assert rc == 0
        manifests = sorted(backups.glob("revenue_backup_*.json"))
        archives = sorted(backups.glob("revenue_backup_*.tar.gz"))
        assert manifests
        assert archives
        payload = json.loads(manifests[-1].read_text(encoding="utf-8"))
        assert payload.get("file_count", 0) >= 1
        assert (backups / "revenue_backup_latest.json").exists()


if __name__ == "__main__":
    test_revenue_backup_creates_archive_and_manifest()
    print("✓ Revenue backup tests passed")
