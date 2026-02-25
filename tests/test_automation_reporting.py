#!/usr/bin/env python3
"""Tests for automation reporting scripts."""

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import scripts.automation_daily_report as report_mod  # noqa: E402


class _DummyPaths:
    def __init__(self, root: Path):
        self.outputs_briefings = root / "briefings"
        self.outputs_digests = root / "digests"
        self.logs = root / "logs"
        self.outputs_briefings.mkdir(parents=True, exist_ok=True)
        self.outputs_digests.mkdir(parents=True, exist_ok=True)
        self.logs.mkdir(parents=True, exist_ok=True)


class _DummyStorage:
    def __init__(self, root: Path):
        self.paths = _DummyPaths(root)


def test_collect_runs_and_write_report():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        log_dir = tmp_path / "automation"
        log_dir.mkdir(parents=True, exist_ok=True)
        run_log = log_dir / "run_20260207-023756.log"
        run_log.write_text(
            "=== Briefing Run Started: Fri Feb  6 20:37:45 2026 ===\n"
            "Briefing Status: 0 | Digest Status: 0 | NotebookLM Status: 0\n"
        )

        dummy = _DummyStorage(tmp_path)
        (dummy.paths.outputs_briefings / "briefing_20260207-023756.md").write_text("ok")
        (dummy.paths.outputs_digests / "sources_digest_20260207-023756.md").write_text("ok")

        original_storage = report_mod.storage
        try:
            report_mod.storage = dummy
            with patch.object(report_mod, "_check_launchd", return_value=True):
                runs = report_mod._collect_runs(log_dir)
                assert len(runs) == 1
                assert runs[0].success is True

                report = report_mod._build_report(runs, days=1, label="com.permanence.briefing")
                assert "Launchd loaded: yes" in report
                assert "Successful runs: 1" in report
                assert "briefing_20260207-023756.md" in report
                assert "Promotion daily status: n/a" in report
        finally:
            report_mod.storage = original_storage


def test_collect_runs_marks_fail_on_promotion_daily_error():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        log_dir = tmp_path / "automation"
        log_dir.mkdir(parents=True, exist_ok=True)
        run_log = log_dir / "run_20260207-190000.log"
        run_log.write_text(
            "=== Briefing Run Started: Fri Feb  6 20:37:45 2026 ===\n"
            "Briefing Status: 0 | Digest Status: 0 | NotebookLM Status: 0\n"
            "Ari Status: 0\n"
            "Health Status: 0 | Report Status: 0\n"
            "Chronicle Capture: 0 | Chronicle Report: 0 | Chronicle Publish: 0\n"
            "Promotion Daily Status: 3\n"
            "Glance Status: 0\n"
            "V04 Snapshot Status: 0\n"
        )

        dummy = _DummyStorage(tmp_path)
        original_storage = report_mod.storage
        try:
            report_mod.storage = dummy
            with patch.object(report_mod, "_check_launchd", return_value=True):
                runs = report_mod._collect_runs(log_dir)
                assert len(runs) == 1
                assert runs[0].promotion_daily_status == 3
                assert runs[0].success is False

                report = report_mod._build_report(runs, days=1, label="com.permanence.briefing")
                assert "Failed/incomplete runs: 1" in report
                assert "promotion_daily=3" in report
        finally:
            report_mod.storage = original_storage
