#!/usr/bin/env python3
"""Tests for GitHub research ingest."""

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import scripts.github_research_ingest as gh_mod  # noqa: E402


def test_github_research_ingest_generates_actions():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        outputs = root / "outputs"
        tool = root / "tool"
        working = root / "working"
        outputs.mkdir(parents=True, exist_ok=True)
        tool.mkdir(parents=True, exist_ok=True)
        working.mkdir(parents=True, exist_ok=True)

        targets_path = working / "github_research_targets.json"
        targets_path.write_text(
            json.dumps(
                [
                    {
                        "repo": "owner/repo",
                        "enabled": True,
                        "max_items": 10,
                    }
                ]
            )
            + "\n",
            encoding="utf-8",
        )

        def fake_fetch(path: str, params=None):
            if path == "/repos/owner/repo":
                return {"default_branch": "main", "stargazers_count": 42}
            if path == "/repos/owner/repo/issues":
                return [
                    {
                        "number": 101,
                        "title": "Old bug",
                        "html_url": "https://github.com/owner/repo/issues/101",
                        "updated_at": "2025-01-01T00:00:00Z",
                        "labels": [{"name": "bug"}],
                    },
                    {
                        "number": 102,
                        "title": "Fresh issue",
                        "html_url": "https://github.com/owner/repo/issues/102",
                        "updated_at": "2026-03-01T00:00:00Z",
                        "labels": [],
                    },
                ]
            if path == "/repos/owner/repo/pulls":
                return [
                    {
                        "number": 12,
                        "title": "Old PR",
                        "html_url": "https://github.com/owner/repo/pull/12",
                        "updated_at": "2025-01-15T00:00:00Z",
                    }
                ]
            return {}

        original = {
            "OUTPUT_DIR": gh_mod.OUTPUT_DIR,
            "TOOL_DIR": gh_mod.TOOL_DIR,
            "WORKING_DIR": gh_mod.WORKING_DIR,
            "TARGETS_PATH": gh_mod.TARGETS_PATH,
            "_fetch_json": gh_mod._fetch_json,
        }
        try:
            gh_mod.OUTPUT_DIR = outputs
            gh_mod.TOOL_DIR = tool
            gh_mod.WORKING_DIR = working
            gh_mod.TARGETS_PATH = targets_path
            gh_mod._fetch_json = fake_fetch
            rc = gh_mod.main([])
        finally:
            gh_mod.OUTPUT_DIR = original["OUTPUT_DIR"]
            gh_mod.TOOL_DIR = original["TOOL_DIR"]
            gh_mod.WORKING_DIR = original["WORKING_DIR"]
            gh_mod.TARGETS_PATH = original["TARGETS_PATH"]
            gh_mod._fetch_json = original["_fetch_json"]

        assert rc == 0
        latest = outputs / "github_research_ingest_latest.md"
        assert latest.exists()
        content = latest.read_text(encoding="utf-8")
        assert "GitHub Research Ingest" in content
        assert "owner/repo" in content

        tool_files = sorted(tool.glob("github_research_ingest_*.json"))
        assert tool_files
        payload = json.loads(tool_files[-1].read_text(encoding="utf-8"))
        assert payload.get("repo_count") == 1
        repo = payload["repos"][0]
        assert repo.get("stale_issues", 0) >= 1
        assert repo.get("stale_prs", 0) >= 1
        assert repo.get("top_actions")


if __name__ == "__main__":
    test_github_research_ingest_generates_actions()
    print("✓ GitHub research ingest tests passed")
