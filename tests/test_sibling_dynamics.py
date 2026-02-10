#!/usr/bin/env python3
"""Tests for sibling dynamics v0.4 refactor requirements."""

from __future__ import annotations

import os
from pathlib import Path

from special.chimera_builder import ARCHETYPE_FEMININE, ChimeraBuilder


def test_no_brotherhood_references_in_python_code():
    root = Path(__file__).resolve().parents[1]
    offenders = []
    for path in root.rglob("*.py"):
        if ".git" in path.parts or "__pycache__" in path.parts:
            continue
        if path.name == "test_sibling_dynamics.py":
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        lower = text.lower()
        if "brotherhood" in lower or "brothers" in lower:
            offenders.append(str(path))
    assert offenders == []


def test_chimera_includes_feminine_archetypes():
    names = {entry["figure"] for entry in ARCHETYPE_FEMININE}
    assert "The Oracle" in names
    assert "The Weaver" in names
    assert "Sophia" in names


def test_sophia_trait_available_for_composition():
    builder = ChimeraBuilder(storage_path=os.path.join("/tmp", "chimera_sibling_test.json"))
    trait = builder.extract_trait("Sophia", "feminine_balance")
    assert trait is not None
