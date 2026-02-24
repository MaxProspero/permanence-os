#!/usr/bin/env python3
"""Tests for CA-013 brand context loader integration."""

import os
import sys

os.environ.setdefault("PERMANENCE_LOG_DIR", "/tmp/permanence-os-test-logs")
os.environ.setdefault("PERMANENCE_OUTPUT_DIR", "/tmp/permanence-os-test-outputs")

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from context_loader import (
    BrandContextLoader,
    ChronicleContextLoader,
    inject_brand_context_if_needed,
    inject_chronicle_context_if_needed,
)


def test_context_loader_task_gating_examples():
    loader = BrandContextLoader()
    assert loader.task_requires_brand_context("write a tweet about the new drop") is True
    assert loader.task_requires_brand_context("fix the bug in polemarch.py") is False


def test_inject_brand_context_if_needed_examples():
    base_prompt = "Executor base prompt"

    writing_prompt = inject_brand_context_if_needed(
        task_goal="write a tweet about the new drop",
        base_system_prompt=base_prompt,
        level="voice",
    )
    assert writing_prompt != base_prompt
    assert "BRAND VOICE" in writing_prompt

    code_prompt = inject_brand_context_if_needed(
        task_goal="fix the bug in polemarch.py",
        base_system_prompt=base_prompt,
        level="voice",
    )
    assert code_prompt == base_prompt


def test_chronicle_context_loader_task_gating_examples():
    loader = ChronicleContextLoader()
    assert loader.task_requires_chronicle_context("improve the agent roadmap") is True
    assert loader.task_requires_chronicle_context("write a short birthday caption") is False


def test_inject_chronicle_context_if_needed_examples():
    base_prompt = "Executor base prompt"

    improving_prompt = inject_chronicle_context_if_needed(
        task_goal="improve next-step priorities for the system",
        base_system_prompt=base_prompt,
    )
    assert improving_prompt != base_prompt
    assert "CHRONICLE CONTEXT" in improving_prompt

    social_prompt = inject_chronicle_context_if_needed(
        task_goal="write a social caption",
        base_system_prompt=base_prompt,
    )
    assert social_prompt == base_prompt


if __name__ == "__main__":
    test_context_loader_task_gating_examples()
    test_inject_brand_context_if_needed_examples()
    test_chronicle_context_loader_task_gating_examples()
    test_inject_chronicle_context_if_needed_examples()
    print("PASS: brand context loader")
