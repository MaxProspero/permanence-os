#!/usr/bin/env python3
"""Tests for ecosystem research ingest."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import scripts.ecosystem_research_ingest as eco_mod  # noqa: E402


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict | None = None):
        self.status_code = status_code
        self._payload = payload or {}

    def json(self) -> dict:
        return self._payload


def test_ecosystem_research_ingest_collects_sources() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        working = root / "working"
        output = root / "outputs"
        tool = root / "tool"
        working.mkdir(parents=True, exist_ok=True)
        output.mkdir(parents=True, exist_ok=True)
        tool.mkdir(parents=True, exist_ok=True)

        watchlist_path = working / "ecosystem_watchlist.json"
        watchlist_path.write_text(
            json.dumps(
                {
                    "docs_urls": ["https://docs.github.com/en/codespaces/overview"],
                    "repos": ["ruvnet/ruflo", "microsoft/markitdown"],
                    "developers": ["ruvnet", "mitchellh"],
                    "communities": ["https://discord.gg/tradesbysci"],
                    "keywords": ["agent", "workflow", "markdown"],
                }
            )
            + "\n",
            encoding="utf-8",
        )

        def fake_get(url, headers=None, timeout=None, allow_redirects=True):  # type: ignore[no-untyped-def]
            if url.endswith("/repos/ruvnet/ruflo"):
                return _FakeResponse(
                    200,
                    {
                        "stargazers_count": 18300,
                        "forks_count": 2020,
                        "open_issues_count": 31,
                        "language": "TypeScript",
                        "updated_at": "2026-03-03T00:00:00Z",
                        "description": "Agent orchestration workflow platform.",
                        "html_url": "https://github.com/ruvnet/ruflo",
                    },
                )
            if url.endswith("/repos/microsoft/markitdown"):
                return _FakeResponse(
                    200,
                    {
                        "stargazers_count": 89800,
                        "forks_count": 5200,
                        "open_issues_count": 120,
                        "language": "Python",
                        "updated_at": "2026-03-03T00:00:00Z",
                        "description": "Convert office files and docs to markdown.",
                        "html_url": "https://github.com/microsoft/markitdown",
                    },
                )
            if url.endswith("/users/ruvnet"):
                return _FakeResponse(
                    200,
                    {
                        "name": "ruv",
                        "followers": 5100,
                        "public_repos": 70,
                        "html_url": "https://github.com/ruvnet",
                        "bio": "builders build",
                    },
                )
            if url.endswith("/users/mitchellh"):
                return _FakeResponse(
                    200,
                    {
                        "name": "Mitchell Hashimoto",
                        "followers": 21000,
                        "public_repos": 95,
                        "html_url": "https://github.com/mitchellh",
                        "bio": "developer",
                    },
                )
            if "docs.github.com" in url:
                return _FakeResponse(200)
            if "discord.gg" in url:
                return _FakeResponse(302)
            return _FakeResponse(404)

        original = {
            "WORKING_DIR": eco_mod.WORKING_DIR,
            "OUTPUT_DIR": eco_mod.OUTPUT_DIR,
            "TOOL_DIR": eco_mod.TOOL_DIR,
            "WATCHLIST_PATH": eco_mod.WATCHLIST_PATH,
        }
        try:
            eco_mod.WORKING_DIR = working
            eco_mod.OUTPUT_DIR = output
            eco_mod.TOOL_DIR = tool
            eco_mod.WATCHLIST_PATH = watchlist_path
            with patch.object(eco_mod.requests, "get", side_effect=fake_get):
                rc = eco_mod.main([])
        finally:
            eco_mod.WORKING_DIR = original["WORKING_DIR"]
            eco_mod.OUTPUT_DIR = original["OUTPUT_DIR"]
            eco_mod.TOOL_DIR = original["TOOL_DIR"]
            eco_mod.WATCHLIST_PATH = original["WATCHLIST_PATH"]

        assert rc == 0
        assert (output / "ecosystem_research_ingest_latest.md").exists()
        payload_files = sorted(tool.glob("ecosystem_research_ingest_*.json"))
        assert payload_files
        payload = json.loads(payload_files[-1].read_text(encoding="utf-8"))
        assert int(payload.get("repo_count", 0)) == 2
        assert int(payload.get("developer_count", 0)) == 2
        assert int(payload.get("docs_count", 0)) == 1
        assert int(payload.get("communities_count", 0)) == 1
        assert payload.get("warnings") == []
        repos = payload.get("repos") or []
        assert repos and repos[0].get("repo") == "ruvnet/ruflo"


if __name__ == "__main__":
    test_ecosystem_research_ingest_collects_sources()
    print("✓ Ecosystem research ingest tests passed")
