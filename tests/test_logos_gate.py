#!/usr/bin/env python3
"""Tests for Logos gate evaluator."""

import os
import sys
import json
import tempfile
from pathlib import Path

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from scripts import logos_gate


def test_logos_gate_writes_report():
    with tempfile.TemporaryDirectory() as temp:
        log_dir = Path(temp) / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        history_path = log_dir / "hr_agent_history.json"
        history_path.write_text(json.dumps({"scores": [["2026-02-01T00:00:00+00:00", 80]]}))

        os.environ["PERMANENCE_LOG_DIR"] = str(log_dir)
        output_dir = Path(temp) / "outputs"
        os.environ["PERMANENCE_OUTPUT_DIR"] = str(output_dir)

        out_path = output_dir / "logos_gate.md"
        sys.argv = ["logos_gate.py", "--output", str(out_path)]
        logos_gate.main()
        assert out_path.exists()


if __name__ == "__main__":
    test_logos_gate_writes_report()
    print("✓ Logos gate tests passed")
