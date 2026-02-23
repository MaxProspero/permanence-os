#!/usr/bin/env python3
"""Tests for research inbox add/process/status flow."""

import json
import os
import sys
import tempfile
from datetime import datetime, timezone

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from scripts.research_inbox import add_entry, process_entries, status


def test_research_inbox_add_and_process():
    with tempfile.TemporaryDirectory() as tmp:
        inbox_path = os.path.join(tmp, "inbox.jsonl")
        state_path = os.path.join(tmp, "state.json")
        sources_path = os.path.join(tmp, "sources.json")
        output_dir = os.path.join(tmp, "outputs")
        tool_dir = os.path.join(tmp, "tool")

        add = add_entry(
            text="Check these: https://example.com/a and https://example.com/b",
            source="telegram",
            channel="dm",
            inbox_path=inbox_path,
        )
        assert add["id"].startswith("rx_")
        assert len(add["urls"]) == 2

        s0 = status(inbox_path=inbox_path, state_path=state_path)
        assert s0["entries_total"] == 1
        assert s0["entries_unprocessed"] == 1
        assert s0["urls_unprocessed"] == 2

        def fake_fetcher(**kwargs):
            urls = kwargs["urls"]
            out = []
            for idx, url in enumerate(urls):
                out.append(
                    {
                        "source": url,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "confidence": 0.7,
                        "notes": f"source {idx}",
                        "hash": f"h{idx}",
                        "origin": "url_fetch",
                    }
                )
            return out

        r1 = process_entries(
            inbox_path=inbox_path,
            state_path=state_path,
            sources_path=sources_path,
            output_dir=output_dir,
            tool_dir=tool_dir,
            fetcher=fake_fetcher,
        )
        assert r1["pending_entries"] == 1
        assert r1["urls_found"] == 2
        assert r1["sources_fetched"] == 2
        assert os.path.exists(r1["report_path"])

        with open(sources_path, "r") as handle:
            sources = json.load(handle)
        assert len(sources) == 2

        s1 = status(inbox_path=inbox_path, state_path=state_path)
        assert s1["entries_unprocessed"] == 0

        r2 = process_entries(
            inbox_path=inbox_path,
            state_path=state_path,
            sources_path=sources_path,
            output_dir=output_dir,
            tool_dir=tool_dir,
            fetcher=fake_fetcher,
        )
        assert r2["pending_entries"] == 0
        assert r2["sources_fetched"] == 0
        assert r2["sources_total"] == 2


if __name__ == "__main__":
    test_research_inbox_add_and_process()
    print("ok")
