#!/usr/bin/env python3
"""Tests for clipping pipeline manager."""

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import scripts.clipping_pipeline_manager as clip_mod  # noqa: E402


def test_clipping_pipeline_generates_candidates():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        outputs = root / "outputs"
        tool = root / "tool"
        working = root / "working"
        outputs.mkdir(parents=True, exist_ok=True)
        tool.mkdir(parents=True, exist_ok=True)
        working.mkdir(parents=True, exist_ok=True)

        queue_path = working / "clipping_jobs.json"
        queue_path.write_text(
            json.dumps(
                [
                    {
                        "job_id": "CLIP-42",
                        "title": "Podcast episode",
                        "source_url": "https://example.com/podcast",
                        "niche": "finance",
                        "status": "processing",
                        "transcript_segments": [
                            {
                                "start": 10,
                                "end": 36,
                                "text": "Here is the key framework. First, protect downside. Second, allocate by edge.",
                            },
                            {
                                "start": 100,
                                "end": 155,
                                "text": "Long rambling segment with low structure and weak pacing.",
                            },
                        ],
                    }
                ]
            ),
            encoding="utf-8",
        )

        original = {
            "OUTPUT_DIR": clip_mod.OUTPUT_DIR,
            "TOOL_DIR": clip_mod.TOOL_DIR,
            "QUEUE_PATH": clip_mod.QUEUE_PATH,
        }
        try:
            clip_mod.OUTPUT_DIR = outputs
            clip_mod.TOOL_DIR = tool
            clip_mod.QUEUE_PATH = queue_path
            rc = clip_mod.main()
        finally:
            clip_mod.OUTPUT_DIR = original["OUTPUT_DIR"]
            clip_mod.TOOL_DIR = original["TOOL_DIR"]
            clip_mod.QUEUE_PATH = original["QUEUE_PATH"]

        assert rc == 0
        latest = outputs / "clipping_pipeline_latest.md"
        assert latest.exists()
        content = latest.read_text(encoding="utf-8")
        assert "Clipping Pipeline Manager" in content
        assert "CLIP-42" in content

        tool_files = sorted(tool.glob("clipping_pipeline_*.json"))
        assert tool_files
        payload = json.loads(tool_files[-1].read_text(encoding="utf-8"))
        assert payload.get("job_count") == 1
        assert payload.get("candidate_count", 0) >= 1
        candidates = payload.get("candidates_by_job", {}).get("CLIP-42", [])
        assert candidates
        assert candidates[0]["score"] >= 0


if __name__ == "__main__":
    test_clipping_pipeline_generates_candidates()
    print("✓ Clipping pipeline tests passed")
