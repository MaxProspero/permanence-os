#!/usr/bin/env python3
"""Tests for core.model_router."""

import json
import os
import sys
import tempfile

os.environ.setdefault("PERMANENCE_LOG_DIR", "/tmp/permanence-os-test-logs")

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.model_router import ModelRouter


def test_route_defaults_to_sonnet_for_unknown_task():
    with tempfile.TemporaryDirectory() as tmp:
        log_path = os.path.join(tmp, "routing.jsonl")
        router = ModelRouter(log_path=log_path)
        model = router.route("unknown-task")
        assert "sonnet" in model


def test_route_uses_haiku_for_classification():
    with tempfile.TemporaryDirectory() as tmp:
        log_path = os.path.join(tmp, "routing.jsonl")
        router = ModelRouter(log_path=log_path)
        model = router.route("classification")
        assert "haiku" in model


def test_env_override_for_opus_model():
    with tempfile.TemporaryDirectory() as tmp:
        log_path = os.path.join(tmp, "routing.jsonl")
        os.environ["PERMANENCE_MODEL_OPUS"] = "claude-opus-custom"
        try:
            router = ModelRouter(log_path=log_path)
            model = router.route("strategy")
            assert model == "claude-opus-custom"
        finally:
            os.environ.pop("PERMANENCE_MODEL_OPUS", None)


def test_routing_log_is_append_only():
    with tempfile.TemporaryDirectory() as tmp:
        log_path = os.path.join(tmp, "routing.jsonl")
        router = ModelRouter(log_path=log_path)
        router.route("planning")
        router.route("execution")

        with open(log_path, "r") as f:
            lines = [line.strip() for line in f if line.strip()]

        assert len(lines) == 2
        first = json.loads(lines[0])
        second = json.loads(lines[1])
        assert first["task_type"] == "planning"
        assert second["task_type"] == "execution"


if __name__ == "__main__":
    test_route_defaults_to_sonnet_for_unknown_task()
    test_route_uses_haiku_for_classification()
    test_env_override_for_opus_model()
    test_routing_log_is_append_only()
    print("✓ Model router tests passed")

