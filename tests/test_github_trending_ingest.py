#!/usr/bin/env python3
"""Tests for GitHub trending ingest."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import scripts.github_trending_ingest as trending_mod  # noqa: E402


FAKE_HTML = """
<html>
  <body>
    <article class="Box-row">
      <h2 class="h3 lh-condensed">
        <a href="/ruvnet/RuView"> ruvnet / RuView </a>
      </h2>
      <p class="col-9 color-fg-muted my-1 pr-4">WiFi DensePose from commodity WiFi signals.</p>
      <span itemprop="programmingLanguage">Rust</span>
      <a href="/ruvnet/RuView/stargazers">23,536</a>
      <span>5,096 stars today</span>
    </article>
    <article class="Box-row">
      <h2 class="h3 lh-condensed">
        <a href="/microsoft/markitdown"> microsoft / markitdown </a>
      </h2>
      <p>Tool for converting files to Markdown.</p>
      <span itemprop="programmingLanguage">Python</span>
      <a href="/microsoft/markitdown/stargazers">89,834</a>
      <span>648 stars today</span>
    </article>
  </body>
</html>
"""


class _FakeResponse:
    status_code = 200

    def __init__(self, text: str):
        self.text = text

    def raise_for_status(self):
        return None


def test_github_trending_ingest_collects_and_scores() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        working = root / "working"
        output = root / "outputs"
        tool = root / "tool"
        working.mkdir(parents=True, exist_ok=True)
        output.mkdir(parents=True, exist_ok=True)
        tool.mkdir(parents=True, exist_ok=True)

        focus_path = working / "github_trending_focus.json"
        focus_path.write_text(
            json.dumps(
                {
                    "since": "daily",
                    "languages": ["python"],
                    "top_limit": 10,
                    "watchlist_repos": ["ruvnet/RuView", "microsoft/markitdown"],
                    "keywords": ["agent", "markdown"],
                }
            )
            + "\n",
            encoding="utf-8",
        )

        original = {
            "WORKING_DIR": trending_mod.WORKING_DIR,
            "OUTPUT_DIR": trending_mod.OUTPUT_DIR,
            "TOOL_DIR": trending_mod.TOOL_DIR,
            "FOCUS_PATH": trending_mod.FOCUS_PATH,
        }
        try:
            trending_mod.WORKING_DIR = working
            trending_mod.OUTPUT_DIR = output
            trending_mod.TOOL_DIR = tool
            trending_mod.FOCUS_PATH = focus_path
            with patch.object(trending_mod.requests, "get", return_value=_FakeResponse(FAKE_HTML)):
                rc = trending_mod.main([])
        finally:
            trending_mod.WORKING_DIR = original["WORKING_DIR"]
            trending_mod.OUTPUT_DIR = original["OUTPUT_DIR"]
            trending_mod.TOOL_DIR = original["TOOL_DIR"]
            trending_mod.FOCUS_PATH = original["FOCUS_PATH"]

        assert rc == 0
        assert (output / "github_trending_ingest_latest.md").exists()
        payload_files = sorted(tool.glob("github_trending_ingest_*.json"))
        assert payload_files
        payload = json.loads(payload_files[-1].read_text(encoding="utf-8"))
        assert int(payload.get("repo_count", 0)) == 2
        assert int(payload.get("watchlist_hit_count", 0)) == 2
        top = payload.get("top_items") or []
        assert top
        assert top[0].get("repo") == "ruvnet/RuView"


if __name__ == "__main__":
    test_github_trending_ingest_collects_and_scores()
    print("✓ GitHub trending ingest tests passed")
