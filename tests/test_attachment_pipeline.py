#!/usr/bin/env python3
"""Tests for attachment pipeline module."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import scripts.attachment_pipeline as attachment_mod  # noqa: E402


def test_attachment_pipeline_indexes_files_and_builds_queue() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        inbox = root / "inbox"
        working = root / "working"
        output = root / "outputs"
        tool = root / "tool"
        queue_path = working / "transcription_queue.json"
        inbox.mkdir(parents=True, exist_ok=True)
        working.mkdir(parents=True, exist_ok=True)
        output.mkdir(parents=True, exist_ok=True)
        tool.mkdir(parents=True, exist_ok=True)

        (inbox / "notes.md").write_text("# Notes\n\nAttachment one.\n", encoding="utf-8")
        (inbox / "voice.m4a").write_bytes(b"fake-audio")
        (inbox / "clip.mp4").write_bytes(b"fake-video")
        (inbox / "image.png").write_bytes(b"fake-image")

        original = {
            "WORKING_DIR": attachment_mod.WORKING_DIR,
            "OUTPUT_DIR": attachment_mod.OUTPUT_DIR,
            "TOOL_DIR": attachment_mod.TOOL_DIR,
        }
        try:
            attachment_mod.WORKING_DIR = working
            attachment_mod.OUTPUT_DIR = output
            attachment_mod.TOOL_DIR = tool
            rc = attachment_mod.main(
                [
                    "--inbox-dir",
                    str(inbox),
                    "--queue-path",
                    str(queue_path),
                    "--max-files",
                    "100",
                ]
            )
        finally:
            attachment_mod.WORKING_DIR = original["WORKING_DIR"]
            attachment_mod.OUTPUT_DIR = original["OUTPUT_DIR"]
            attachment_mod.TOOL_DIR = original["TOOL_DIR"]

        assert rc == 0
        assert (output / "attachment_pipeline_latest.md").exists()
        payload_files = sorted(tool.glob("attachment_pipeline_*.json"))
        assert payload_files
        payload = json.loads(payload_files[-1].read_text(encoding="utf-8"))
        counts = payload.get("counts") or {}
        assert int(counts.get("total", 0)) == 4
        assert int(counts.get("document", 0)) == 1
        assert int(counts.get("audio", 0)) == 1
        assert int(counts.get("video", 0)) == 1
        assert int(counts.get("image", 0)) == 1
        assert queue_path.exists()
        queue = json.loads(queue_path.read_text(encoding="utf-8"))
        assert isinstance(queue, list)
        assert len(queue) == 2


if __name__ == "__main__":
    test_attachment_pipeline_indexes_files_and_builds_queue()
    print("✓ Attachment pipeline tests passed")

