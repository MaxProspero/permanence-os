#!/usr/bin/env python3
"""Tests for Drive PDF adapter registration."""

from agents.researcher_adapters import list_adapters


def test_drive_pdfs_adapter_registered():
    names = [adapter.name for adapter in list_adapters()]
    assert "drive_pdfs" in names

