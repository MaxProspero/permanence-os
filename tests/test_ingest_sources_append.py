#!/usr/bin/env python3
"""Tests for ingest-sources append merge."""

import json
import os
import tempfile

from scripts.ingest_sources import _merge_sources


def test_merge_sources_dedupes_by_source_origin_hash():
    existing = [
        {"source": "a", "origin": "x", "hash": "1"},
        {"source": "b", "origin": "x", "hash": "2"},
    ]
    new = [
        {"source": "a", "origin": "x", "hash": "1"},
        {"source": "c", "origin": "y", "hash": "3"},
    ]
    merged = _merge_sources(existing, new)
    assert len(merged) == 3

