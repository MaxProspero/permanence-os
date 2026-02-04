#!/usr/bin/env python3
"""Tests for Gmail ingest helpers (no network)."""

import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from scripts.gmail_ingest import _extract_headers, _parse_message


def test_extract_headers():
    headers = [{"name": "Subject", "value": "Hello"}, {"name": "From", "value": "a@b.com"}]
    parsed = _extract_headers(headers)
    assert parsed["subject"] == "Hello"
    assert parsed["from"] == "a@b.com"


def test_parse_message():
    msg = {
        "id": "1",
        "threadId": "t1",
        "snippet": "hi",
        "labelIds": ["INBOX"],
        "payload": {"headers": [{"name": "Subject", "value": "Test"}]},
    }
    parsed = _parse_message(msg)
    assert parsed["id"] == "1"
    assert parsed["subject"] == "Test"


if __name__ == "__main__":
    test_extract_headers()
    test_parse_message()
    print("✓ Gmail ingest helper tests passed")
