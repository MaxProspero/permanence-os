#!/usr/bin/env python3
"""Tests for briefing_run script."""

import os
import sys
import tempfile
from unittest.mock import patch

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import scripts.briefing_run as briefing_run  # noqa: E402


def test_briefing_run_writes_file_with_openclaw_excerpt():
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["PERMANENCE_OUTPUT_DIR"] = tmp
        status_path = os.path.join(tmp, "openclaw_status_20260203-000000.txt")
        with open(status_path, "w") as f:
            f.write("OpenClaw status\nGateway reachable\n")

        with patch("scripts.briefing_run.capture_openclaw_status") as mock_capture:
            mock_capture.return_value = {"status": "ok", "reachable": True}
            output = os.path.join(tmp, "briefing_test.md")
            with patch("sys.argv", ["briefing_run.py", "--output", output]):
                briefing_run.main()

        assert os.path.exists(output)
        with open(output, "r") as f:
            content = f.read()
        assert "OpenClaw status" in content


if __name__ == "__main__":
    test_briefing_run_writes_file_with_openclaw_excerpt()
    print("✓ Briefing run tests passed")
