#!/usr/bin/env python3
"""Safety tests for PlannerAgent model-assist fallback behavior."""

import os
import sys

os.environ.setdefault("PERMANENCE_LOG_DIR", "/tmp/permanence-os-test-logs")
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from agents.planner import PlannerAgent


class _NoModelRouter:
    def get_model(self, _task_type: str):
        return None


def test_planner_baseline_plan_creation():
    original = os.environ.pop("PERMANENCE_ENABLE_MODEL_ASSIST", None)
    try:
        planner = PlannerAgent(canon={})
        spec = planner.create_plan("Research recent AI governance frameworks")
        assert spec.goal
        assert len(spec.deliverables) > 0
        assert spec.estimated_steps >= 1
    finally:
        if original is not None:
            os.environ["PERMANENCE_ENABLE_MODEL_ASSIST"] = original


def test_planner_model_assist_falls_back_when_no_model():
    original = os.environ.get("PERMANENCE_ENABLE_MODEL_ASSIST")
    os.environ["PERMANENCE_ENABLE_MODEL_ASSIST"] = "true"
    try:
        planner = PlannerAgent(canon={}, model_router=_NoModelRouter())
        spec = planner.create_plan("Generate a concise implementation plan")
        assert spec.goal
        assert len(spec.success_criteria) > 0
        assert spec.estimated_tool_calls >= 0
    finally:
        if original is None:
            os.environ.pop("PERMANENCE_ENABLE_MODEL_ASSIST", None)
        else:
            os.environ["PERMANENCE_ENABLE_MODEL_ASSIST"] = original


if __name__ == "__main__":
    test_planner_baseline_plan_creation()
    test_planner_model_assist_falls_back_when_no_model()
    print("✓ Planner model-assist fallback tests passed")

