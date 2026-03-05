#!/usr/bin/env python3
"""Tests for clipping transcript ingestion."""

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import scripts.clipping_transcript_ingest as ingest_mod  # noqa: E402


def test_transcript_ingest_creates_and_updates_jobs():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        outputs = root / "outputs"
        tool = root / "tool"
        working = root / "working"
        transcripts = working / "clipping_transcripts"
        outputs.mkdir(parents=True, exist_ok=True)
        tool.mkdir(parents=True, exist_ok=True)
        transcripts.mkdir(parents=True, exist_ok=True)

        transcript_file = transcripts / "market_podcast.txt"
        transcript_file.write_text(
            "\n".join(
                [
                    "00:00:10 --> 00:00:35 Here is the key framework for risk management.",
                    "00:01:00 --> 00:01:28 First define downside, second define trigger.",
                ]
            )
            + "\n",
            encoding="utf-8",
        )

        queue_path = working / "clipping_jobs.json"
        queue_path.write_text("[]\n", encoding="utf-8")

        original = {
            "OUTPUT_DIR": ingest_mod.OUTPUT_DIR,
            "TOOL_DIR": ingest_mod.TOOL_DIR,
            "TRANSCRIPT_DIR": ingest_mod.TRANSCRIPT_DIR,
            "QUEUE_PATH": ingest_mod.QUEUE_PATH,
            "MAX_SEGMENTS_PER_JOB": ingest_mod.MAX_SEGMENTS_PER_JOB,
        }
        try:
            ingest_mod.OUTPUT_DIR = outputs
            ingest_mod.TOOL_DIR = tool
            ingest_mod.TRANSCRIPT_DIR = transcripts
            ingest_mod.QUEUE_PATH = queue_path
            ingest_mod.MAX_SEGMENTS_PER_JOB = 20

            rc_first = ingest_mod.main([])
            assert rc_first == 0

            jobs_after_first = json.loads(queue_path.read_text(encoding="utf-8"))
            assert len(jobs_after_first) == 1
            assert jobs_after_first[0]["job_id"].startswith("CLIP-AUTO-")
            assert len(jobs_after_first[0]["transcript_segments"]) == 2

            # Modify transcript and re-run to verify update path.
            transcript_file.write_text(
                "\n".join(
                    [
                        "00:00:10 --> 00:00:35 Here is the key framework for risk management.",
                        "00:02:00 --> 00:02:20 Third step is review every assumption manually.",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            rc_second = ingest_mod.main([])
            assert rc_second == 0
        finally:
            ingest_mod.OUTPUT_DIR = original["OUTPUT_DIR"]
            ingest_mod.TOOL_DIR = original["TOOL_DIR"]
            ingest_mod.TRANSCRIPT_DIR = original["TRANSCRIPT_DIR"]
            ingest_mod.QUEUE_PATH = original["QUEUE_PATH"]
            ingest_mod.MAX_SEGMENTS_PER_JOB = original["MAX_SEGMENTS_PER_JOB"]

        latest = outputs / "clipping_transcript_ingest_latest.md"
        assert latest.exists()
        content = latest.read_text(encoding="utf-8")
        assert "Clipping Transcript Ingest" in content

        jobs_after_second = json.loads(queue_path.read_text(encoding="utf-8"))
        assert len(jobs_after_second) == 1
        assert len(jobs_after_second[0]["transcript_segments"]) == 2
        assert "review every assumption manually" in jobs_after_second[0]["transcript_segments"][1]["text"].lower()

        tool_files = sorted(tool.glob("clipping_transcript_ingest_*.json"))
        assert tool_files
        payload = json.loads(tool_files[-1].read_text(encoding="utf-8"))
        assert payload.get("job_count") == 1
        assert payload.get("jobs_updated", 0) >= 1


if __name__ == "__main__":
    test_transcript_ingest_creates_and_updates_jobs()
    print("✓ Clipping transcript ingest tests passed")
