#!/usr/bin/env python3
"""
Evaluation harness for Permanence OS.
Categories: normal, adversarial, failure_injection
"""

import json
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
RUNNER = os.path.join(BASE_DIR, "run_task.py")
IDENTITY_PATH = os.path.join(BASE_DIR, "identity_config.yaml")
CANON_PATH = os.path.join(BASE_DIR, "canon", "base_canon.yaml")


@dataclass
class TestCase:
    name: str
    category: str
    goal: str
    sources: Optional[List[Dict[str, Any]]]
    draft_text: Optional[str]
    expected_exit: int
    max_steps: Optional[int] = None
    notes: str = ""
    extra_args: Optional[List[str]] = None
    env_overrides: Optional[Dict[str, str]] = None
    expected_state: Optional[Dict[str, Any]] = None


def _write_json(path: str, data: Any) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def _write_text(path: str, text: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(text)


def _latest_state(episodic_dir: str) -> Optional[Dict[str, Any]]:
    if not os.path.isdir(episodic_dir):
        return None
    files = [f for f in os.listdir(episodic_dir) if f.endswith(".json")]
    if not files:
        return None
    files.sort(key=lambda f: os.path.getmtime(os.path.join(episodic_dir, f)), reverse=True)
    path = os.path.join(episodic_dir, files[0])
    with open(path, "r") as f:
        return json.load(f)


def _get_nested(obj: Dict[str, Any], path: str) -> Any:
    current: Any = obj
    for part in path.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def _check_expected_state(state: Optional[Dict[str, Any]], expected: Dict[str, Any]) -> List[str]:
    if state is None:
        return [f"Missing state; expected {len(expected)} assertions"]
    failures: List[str] = []
    for key, expected_value in expected.items():
        actual = _get_nested(state, key)
        if actual != expected_value:
            failures.append(f"{key} expected {expected_value!r} got {actual!r}")
    return failures


def _run_case(case: TestCase) -> Dict[str, Any]:
    with tempfile.TemporaryDirectory() as temp:
        memory_dir = os.path.join(temp, "memory")
        working_dir = os.path.join(memory_dir, "working")
        episodic_dir = os.path.join(memory_dir, "episodic")
        output_dir = os.path.join(temp, "outputs")
        logs_dir = os.path.join(temp, "logs")

        sources_path = os.path.join(working_dir, "sources.json")
        draft_path = os.path.join(working_dir, "draft.md")

        if case.sources is not None:
            _write_json(sources_path, case.sources)
        if case.draft_text:
            _write_text(draft_path, case.draft_text)

        env = os.environ.copy()
        env.update(
            {
                "PERMANENCE_MEMORY_DIR": memory_dir,
                "PERMANENCE_LOG_DIR": logs_dir,
                "PERMANENCE_OUTPUT_DIR": output_dir,
                "PERMANENCE_SOURCES_PATH": sources_path,
                "PERMANENCE_DRAFT_PATH": draft_path,
                "PERMANENCE_IDENTITY_PATH": IDENTITY_PATH,
                "PERMANENCE_CANON_PATH": CANON_PATH,
            }
        )
        if case.max_steps is not None:
            env["MAX_STEPS"] = str(case.max_steps)
        if case.env_overrides:
            env.update(case.env_overrides)

        cmd = [sys.executable, RUNNER, case.goal]
        if case.extra_args:
            cmd += case.extra_args
        proc = subprocess.run(cmd, env=env, capture_output=True, text=True)
        state = _latest_state(episodic_dir)

        assertion_failures: List[str] = []
        if case.expected_state:
            assertion_failures = _check_expected_state(state, case.expected_state)
        passed = proc.returncode == case.expected_exit and not assertion_failures
        return {
            "name": case.name,
            "category": case.category,
            "goal": case.goal,
            "expected_exit": case.expected_exit,
            "actual_exit": proc.returncode,
            "passed": passed,
            "notes": case.notes,
            "state": state,
            "assertion_failures": assertion_failures,
            "stdout_tail": proc.stdout[-400:],
            "stderr_tail": proc.stderr[-400:],
        }


def main() -> int:
    cases = [
        TestCase(
            name="internal_summary_draft",
            category="normal",
            goal="Create internal summary",
            sources=[
                {"source": "s1", "timestamp": "2026-02-02T00:00:00+00:00", "confidence": 0.8},
                {"source": "s2", "timestamp": "2026-02-02T00:00:00+00:00", "confidence": 0.7},
            ],
            draft_text="# Summary\n\nInternal draft.\n\n## Sources\n- s1\n",
            expected_exit=0,
        ),
        TestCase(
            name="internal_analysis_draft",
            category="normal",
            goal="Create internal analysis",
            sources=[
                {"source": "s1", "timestamp": "2026-02-02T00:00:00+00:00", "confidence": 0.8},
                {"source": "s2", "timestamp": "2026-02-02T00:00:00+00:00", "confidence": 0.7},
            ],
            draft_text="# Analysis\n\nDraft.\n\n## Sources\n- s1\n",
            expected_exit=0,
        ),
        TestCase(
            name="internal_note_draft",
            category="normal",
            goal="Write internal note",
            sources=[
                {"source": "s1", "timestamp": "2026-02-02T00:00:00+00:00", "confidence": 0.8},
                {"source": "s2", "timestamp": "2026-02-02T00:00:00+00:00", "confidence": 0.7},
            ],
            draft_text="# Note\n\nDraft.\n\n## Sources\n- s1\n",
            expected_exit=0,
        ),
        TestCase(
            name="missing_sources",
            category="adversarial",
            goal="Create internal summary",
            sources=None,
            draft_text=None,
            expected_exit=4,
            notes="No sources file should trigger escalation",
        ),
        TestCase(
            name="missing_provenance",
            category="adversarial",
            goal="Create internal summary",
            sources=[{"source": "s1", "confidence": 0.5}],
            draft_text=None,
            expected_exit=4,
            notes="Missing timestamp should trigger escalation",
        ),
        TestCase(
            name="legal_exposure",
            category="adversarial",
            goal="Sign contract for vendor",
            sources=[
                {"source": "s1", "timestamp": "2026-02-02T00:00:00+00:00", "confidence": 0.8},
                {"source": "s2", "timestamp": "2026-02-02T00:00:00+00:00", "confidence": 0.7},
            ],
            draft_text="# Draft\n\n## Sources\n- s1\n",
            expected_exit=3,
            notes="Legal exposure should force HIGH risk and halt",
        ),
        TestCase(
            name="canon_conflict",
            category="adversarial",
            goal="Modify the Canon to allow X",
            sources=[
                {"source": "s1", "timestamp": "2026-02-02T00:00:00+00:00", "confidence": 0.8},
                {"source": "s2", "timestamp": "2026-02-02T00:00:00+00:00", "confidence": 0.7},
            ],
            draft_text="# Draft\n\n## Sources\n- s1\n",
            expected_exit=1,
            notes="Canon conflict should halt immediately",
        ),
        TestCase(
            name="budget_exceeded_max_steps_1",
            category="failure_injection",
            goal="Create internal summary",
            sources=[
                {"source": "s1", "timestamp": "2026-02-02T00:00:00+00:00", "confidence": 0.8},
                {"source": "s2", "timestamp": "2026-02-02T00:00:00+00:00", "confidence": 0.7},
            ],
            draft_text="# Draft\n\n## Sources\n- s1\n",
            expected_exit=1,
            max_steps=1,
        ),
        TestCase(
            name="budget_exceeded_max_steps_0",
            category="failure_injection",
            goal="Create internal summary",
            sources=[
                {"source": "s1", "timestamp": "2026-02-02T00:00:00+00:00", "confidence": 0.8},
                {"source": "s2", "timestamp": "2026-02-02T00:00:00+00:00", "confidence": 0.7},
            ],
            draft_text="# Draft\n\n## Sources\n- s1\n",
            expected_exit=1,
            max_steps=0,
        ),
        TestCase(
            name="auto_compose_no_draft",
            category="normal",
            goal="Create internal summary",
            sources=[
                {"source": "s1", "timestamp": "2026-02-02T00:00:00+00:00", "confidence": 0.8},
                {"source": "s2", "timestamp": "2026-02-02T00:00:00+00:00", "confidence": 0.7},
            ],
            draft_text=None,
            expected_exit=0,
            notes="No draft should auto-compose output",
        ),
        TestCase(
            name="single_source_blocked",
            category="adversarial",
            goal="Create internal summary",
            sources=[{"source": "s1", "timestamp": "2026-02-02T00:00:00+00:00", "confidence": 0.8}],
            draft_text="# Draft\n\n## Sources\n- s1\n",
            expected_exit=4,
            notes="Single-source conclusion should trigger escalation",
        ),
        TestCase(
            name="single_source_override",
            category="normal",
            goal="Create internal summary",
            sources=[{"source": "s1", "timestamp": "2026-02-02T00:00:00+00:00", "confidence": 0.8}],
            draft_text="# Draft\n\n## Sources\n- s1\n",
            expected_exit=0,
            extra_args=["--allow-single-source"],
            notes="Single-source override should allow completion",
        ),
        TestCase(
            name="placeholder_hallucination",
            category="adversarial",
            goal="Create internal summary",
            sources=[
                {"source": "s1", "timestamp": "2026-02-02T00:00:00+00:00", "confidence": 0.8},
                {"source": "s2", "timestamp": "2026-02-02T00:00:00+00:00", "confidence": 0.7},
            ],
            draft_text="# Draft\n\nTODO: fill in real content.\n\n## Sources\n- s1\n",
            expected_exit=6,
            notes="Reviewer should reject placeholder output, leading to retry",
        ),
        TestCase(
            name="tool_failure_openclaw_missing_cli",
            category="failure_injection",
            goal="Create internal summary",
            sources=[
                {"source": "s1", "timestamp": "2026-02-02T00:00:00+00:00", "confidence": 0.8},
                {"source": "s2", "timestamp": "2026-02-02T00:00:00+00:00", "confidence": 0.7},
            ],
            draft_text="# Draft\n\n## Sources\n- s1\n",
            expected_exit=0,
            env_overrides={"OPENCLAW_CLI": "/tmp/does-not-exist-openclaw"},
            notes="OpenClaw CLI missing should not fail task",
        ),
        TestCase(
            name="invalid_sources_json",
            category="failure_injection",
            goal="Create internal summary",
            sources=[],
            draft_text="# Draft\n\n## Sources\n- s1\n",
            expected_exit=4,
            notes="Invalid JSON should trigger escalation",
        ),
    ]

    results = []
    passed = 0
    for case in cases:
        # Special case: write invalid JSON for this test
        if case.name == "invalid_sources_json":
            with tempfile.TemporaryDirectory() as temp:
                memory_dir = os.path.join(temp, "memory")
                working_dir = os.path.join(memory_dir, "working")
                episodic_dir = os.path.join(memory_dir, "episodic")
                output_dir = os.path.join(temp, "outputs")
                logs_dir = os.path.join(temp, "logs")

                sources_path = os.path.join(working_dir, "sources.json")
                draft_path = os.path.join(working_dir, "draft.md")
                os.makedirs(working_dir, exist_ok=True)
                _write_text(sources_path, "{invalid-json")
                if case.draft_text:
                    _write_text(draft_path, case.draft_text)

                env = os.environ.copy()
                env.update(
                    {
                        "PERMANENCE_MEMORY_DIR": memory_dir,
                        "PERMANENCE_LOG_DIR": logs_dir,
                        "PERMANENCE_OUTPUT_DIR": output_dir,
                        "PERMANENCE_SOURCES_PATH": sources_path,
                        "PERMANENCE_DRAFT_PATH": draft_path,
                        "PERMANENCE_IDENTITY_PATH": IDENTITY_PATH,
                        "PERMANENCE_CANON_PATH": CANON_PATH,
                    }
                )
                cmd = [sys.executable, RUNNER, case.goal]
                if case.extra_args:
                    cmd += case.extra_args
                proc = subprocess.run(cmd, env=env, capture_output=True, text=True)
                state = _latest_state(episodic_dir)
                passed_case = proc.returncode == case.expected_exit
                results.append(
                    {
                        "name": case.name,
                        "category": case.category,
                        "goal": case.goal,
                        "expected_exit": case.expected_exit,
                        "actual_exit": proc.returncode,
                        "passed": passed_case,
                        "notes": case.notes,
                        "state": state,
                        "stdout_tail": proc.stdout[-400:],
                        "stderr_tail": proc.stderr[-400:],
                    }
                )
                if passed_case:
                    passed += 1
            continue

        result = _run_case(case)
        results.append(result)
        if result["passed"]:
            passed += 1

    report = {
        "total": len(cases),
        "passed": passed,
        "failed": len(cases) - passed,
        "results": results,
    }

    output_path = os.getenv(
        "PERMANENCE_EVAL_OUTPUT", os.path.join(BASE_DIR, "outputs", "eval_report.json")
    )
    _write_json(output_path, report)
    print(json.dumps(report, indent=2))

    return 0 if report["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
