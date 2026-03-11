#!/usr/bin/env python3
"""
Scan files for likely secret leaks before push.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
from pathlib import Path
from typing import Iterable

BASE_DIR = Path(__file__).resolve().parents[1]

KEY_NAME_PATTERN = re.compile(
    r"^\s*(ANTHROPIC_API_KEY|OPENAI_API_KEY|GH_TOKEN|GITHUB_TOKEN|TAVILY_API_KEY|"
    r"PERMANENCE_GITHUB_READ_TOKEN|PERMANENCE_SOCIAL_READ_TOKEN|PERMANENCE_GITHUB_WRITE_TOKEN|"
    r"PERMANENCE_SOCIAL_PUBLISH_TOKEN|NOTION_API_KEY|BRAVE_API_KEY)\s*=\s*(?P<value>[^#\n\r]*)"
)

RAW_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("anthropic", re.compile(r"sk-ant-[A-Za-z0-9._-]{20,}")),
    ("openai_sk", re.compile(r"sk-[A-Za-z0-9]{20,}")),
    ("openai_proj", re.compile(r"sk-proj-[A-Za-z0-9._-]{20,}")),
    ("tavily", re.compile(r"tvly-[A-Za-z0-9._-]{12,}")),
    ("github_pat", re.compile(r"github_pat_[A-Za-z0-9_]{20,}")),
    ("github_token", re.compile(r"ghp_[A-Za-z0-9]{20,}")),
    ("slack_token", re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}")),
    ("notion_secret", re.compile(r"(secret_[A-Za-z0-9]{20,}|ntn_[A-Za-z0-9]{20,})")),
    ("brave_key", re.compile(r"BSA[A-Za-z0-9_-]{20,}")),
]

ALLOWLIST_FRAGMENTS = {
    "your_key_here",
    "YOUR_KEY_HERE",
    "sk-ant-test",
    "sk-ant-YOUR_KEY_HERE",
    "example",
    "dummy",
    "placeholder",
    "os.getenv",
}


def _git_list_files(staged: bool) -> list[Path]:
    cmd = [
        "git",
        "-C",
        str(BASE_DIR),
        "diff",
        "--cached",
        "--name-only",
        "--diff-filter=ACMRTUXB",
    ]
    if not staged:
        cmd = ["git", "-C", str(BASE_DIR), "ls-files"]
    proc = subprocess.run(cmd, check=False, capture_output=True, text=True)
    if proc.returncode != 0:
        return []
    rows = [line.strip() for line in (proc.stdout or "").splitlines() if line.strip()]
    return [BASE_DIR / row for row in rows]


def _looks_binary(path: Path) -> bool:
    try:
        chunk = path.read_bytes()[:2048]
    except OSError:
        return True
    return b"\x00" in chunk


def _allowlisted(line: str) -> bool:
    text = line.strip()
    if not text:
        return True
    return any(fragment in text for fragment in ALLOWLIST_FRAGMENTS)


def _scan_lines(path: Path, lines: Iterable[str]) -> list[dict[str, object]]:
    findings: list[dict[str, object]] = []
    for idx, raw in enumerate(lines, start=1):
        line = raw.rstrip("\n")
        if _allowlisted(line):
            continue

        key_match = KEY_NAME_PATTERN.match(line)
        if key_match:
            value = (key_match.group("value") or "").strip().strip('"').strip("'")
            if value and not _allowlisted(value):
                findings.append(
                    {
                        "file": str(path.relative_to(BASE_DIR)),
                        "line": idx,
                        "type": "key_assignment",
                    }
                )

        for tag, pattern in RAW_PATTERNS:
            if pattern.search(line):
                findings.append(
                    {
                        "file": str(path.relative_to(BASE_DIR)),
                        "line": idx,
                        "type": tag,
                    }
                )
                break
    return findings


def scan_paths(paths: list[Path]) -> list[dict[str, object]]:
    findings: list[dict[str, object]] = []
    for path in paths:
        if not path.exists() or not path.is_file():
            continue
        rel = str(path.relative_to(BASE_DIR))
        if rel.startswith(".git/"):
            continue
        if _looks_binary(path):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        findings.extend(_scan_lines(path, text.splitlines()))
    return findings


def _format_findings(findings: list[dict[str, object]]) -> str:
    lines = [
        "Secret scan detected potential sensitive values.",
        "Resolve before push.",
    ]
    for row in findings:
        lines.append(f"- {row['file']}:{row['line']} ({row['type']})")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Scan for likely secret leaks.")
    parser.add_argument("--all-files", action="store_true", help="Scan all tracked files")
    parser.add_argument("--staged", action="store_true", help="Scan staged files")
    args = parser.parse_args(argv)

    staged = True
    if args.all_files:
        staged = False
    if args.staged:
        staged = True

    paths = _git_list_files(staged=staged)
    findings = scan_paths(paths)
    if findings:
        print(_format_findings(findings))
        return 1

    print(f"Secret scan clean ({'staged' if staged else 'all-files'}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
