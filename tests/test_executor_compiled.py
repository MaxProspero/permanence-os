#!/usr/bin/env python3
"""Tests for Executor compiled output formatting."""

import os
import sys

os.environ.setdefault("PERMANENCE_LOG_DIR", "/tmp/permanence-os-test-logs")
os.environ.setdefault("PERMANENCE_OUTPUT_DIR", "/tmp/permanence-os-test-outputs")

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from agents.executor import ExecutorAgent


def test_compiled_output_has_sections():
    ea = ExecutorAgent()
    spec = {"goal": "Test goal", "deliverables": ["Deliverable A"], "constraints": ["c1"]}
    sources = [{"source": "s1", "timestamp": "2026-02-02T00:00:00+00:00", "confidence": 0.7}]
    res = ea.execute(spec=spec, inputs={"sources": sources})
    assert res.status == "AUTO_COMPOSED"
    assert res.artifact is not None
    with open(res.artifact, "r") as f:
        content = f.read()
    assert "## Output (Spec-Bound)" in content
    assert "### Deliverable A" in content
    assert "## Sources (Provenance)" in content
    assert "- [s1]" in content or "- [s2]" in content
    assert "TODO:" not in content


if __name__ == "__main__":
    test_compiled_output_has_sections()
    print("✓ Executor compiled output tests passed")
