#!/usr/bin/env python3
"""Tests for chronicle publish workflow."""

import json
import os
import sys
import tempfile
from unittest.mock import patch

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import scripts.chronicle_publish as chronicle_publish  # noqa: E402


def _write(path: str, content: str) -> None:
    with open(path, "w") as f:
        f.write(content)


def test_chronicle_publish_exports_shared_and_drive_files():
    with tempfile.TemporaryDirectory() as tmp:
        report_json = os.path.join(tmp, "chronicle_report_test.json")
        report_md = os.path.join(tmp, "chronicle_report_test.md")
        output_dir = os.path.join(tmp, "shared")
        drive_dir = os.path.join(tmp, "drive")

        payload = {
            "generated_at": "2026-02-24T00:00:00Z",
            "days": 30,
            "events_count": 4,
            "commit_count": 12,
            "signal_totals": {
                "direction_hits": 9,
                "frustration_hits": 3,
                "issue_hits": 2,
                "log_error_hits": 1,
                "log_warning_hits": 0,
            },
            "direction_events": [{"timestamp": "2026-02-23T12:00:00Z", "summary": "shift"}],
            "issue_events": [{"timestamp": "2026-02-23T13:00:00Z", "summary": "issue"}],
        }
        _write(report_json, json.dumps(payload, indent=2))
        _write(report_md, "# Chronicle Timeline Report\n\n- sample\n")

        with patch(
            "sys.argv",
            [
                "chronicle_publish.py",
                "--report-json",
                report_json,
                "--report-md",
                report_md,
                "--output-dir",
                output_dir,
                "--drive-dir",
                drive_dir,
            ],
        ):
            rc = chronicle_publish.main()

        assert rc == 0
        assert os.path.exists(os.path.join(output_dir, "chronicle_latest.json"))
        assert os.path.exists(os.path.join(output_dir, "chronicle_latest.md"))
        assert os.path.exists(os.path.join(output_dir, "chronicle_latest_summary.md"))
        assert os.path.exists(os.path.join(output_dir, "chronicle_latest_manifest.json"))
        assert os.path.exists(os.path.join(drive_dir, "chronicle_latest_summary.md"))

        manifest_path = os.path.join(output_dir, "chronicle_latest_manifest.json")
        with open(manifest_path, "r") as f:
            manifest = json.load(f)
        assert manifest["events_count"] == 4
        assert manifest["commit_count"] == 12


if __name__ == "__main__":
    test_chronicle_publish_exports_shared_and_drive_files()
    print("PASS: chronicle publish")
