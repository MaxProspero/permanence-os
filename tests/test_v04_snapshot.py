#!/usr/bin/env python3
"""Tests for v0.4 snapshot report generation."""

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import scripts.v04_snapshot as snap_mod  # noqa: E402


class _DummyPaths:
    def __init__(self, root: Path):
        self.root = root
        self.logs = root / "logs"
        self.outputs_briefings = root / "outputs" / "briefings"
        self.outputs_digests = root / "outputs" / "digests"
        self.outputs_synthesis_drafts = root / "outputs" / "synthesis" / "drafts"
        self.outputs_synthesis_final = root / "outputs" / "synthesis" / "final"
        self.outputs_snapshots = root / "outputs" / "snapshots"
        for path in (
            self.logs,
            self.outputs_briefings,
            self.outputs_digests,
            self.outputs_synthesis_drafts,
            self.outputs_synthesis_final,
            self.outputs_snapshots,
        ):
            path.mkdir(parents=True, exist_ok=True)


class _DummyStorage:
    def __init__(self, root: Path):
        self.paths = _DummyPaths(root)


def test_build_snapshot_includes_v04_sections():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        dummy = _DummyStorage(root)
        (dummy.paths.outputs_briefings / "briefing_20260207-120000.md").write_text("ok")
        (dummy.paths.outputs_digests / "sources_digest_20260207-120000.md").write_text("ok")
        (dummy.paths.outputs_synthesis_drafts / "synthesis_20260207-120000.md").write_text("ok")
        (dummy.paths.outputs_synthesis_final / "synthesis_20260207-120500.md").write_text("ok")
        (dummy.paths.logs / "status_today.json").write_text(
            json.dumps({"today_state": "PASS", "slot_progress": "3/3", "streak": {"current": 2, "target": 7}})
        )
        (dummy.paths.logs / "reliability_watch_state.json").write_text(
            json.dumps({"completed": False, "stopped": False, "ends_at_local": "2099-01-01T00:00:00"})
        )

        zp_path = root / "zero_point_store.json"
        zp_path.write_text(
            json.dumps(
                {
                    "entries": {
                        "e1": {"memory_type": "INTAKE", "created_at": "2099-01-01T00:00:00+00:00", "content": "{}"},
                        "e2": {"memory_type": "TRAINING", "created_at": "2099-01-01T00:00:00+00:00", "content": "{}"},
                        "e3": {"memory_type": "FORECAST", "created_at": "2099-01-01T00:00:00+00:00", "content": "{}"},
                    }
                }
            )
        )
        os.environ["PERMANENCE_ZERO_POINT_PATH"] = str(zp_path)

        original_storage = snap_mod.storage
        try:
            snap_mod.storage = dummy
            with patch.object(
                snap_mod,
                "_latest_run_status",
                return_value={"run": "run_20260207-120000.log", "briefing": 0, "digest": 0, "notebooklm": 0},
            ):
                text = "\n".join(snap_mod.build_snapshot())
        finally:
            snap_mod.storage = original_storage

        assert "## V0.4 Telemetry" in text
        assert "Zero Point entries: 3" in text
        assert "Latest briefing: briefing_20260207-120000.md" in text


def test_main_writes_snapshot_file():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        dummy = _DummyStorage(root)
        output_path = root / "snapshot.md"

        original_storage = snap_mod.storage
        try:
            snap_mod.storage = dummy
            with patch.object(sys, "argv", ["v04_snapshot.py", "--output", str(output_path)]):
                rc = snap_mod.main()
        finally:
            snap_mod.storage = original_storage

        assert rc == 0
        assert output_path.exists()
        content = output_path.read_text()
        assert "# V0.4 Snapshot" in content

