#!/usr/bin/env python3
"""
Shared helpers for project chronicle ingestion/reporting.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parents[1]
CHRONICLE_DIR = BASE_DIR / "memory" / "chronicle"
CHRONICLE_EVENTS = CHRONICLE_DIR / "events.jsonl"
CHRONICLE_INDEX = CHRONICLE_DIR / "backfill_index.json"
CHRONICLE_OUTPUT_DIR = BASE_DIR / "outputs" / "chronicle"

TEXT_EXTENSIONS = {
    ".md",
    ".txt",
    ".py",
    ".json",
    ".yaml",
    ".yml",
    ".csv",
    ".tsv",
    ".log",
    ".rst",
    ".toml",
    ".ini",
}

FRUSTRATION_PATTERNS = [
    "frustrat",
    "stuck",
    "not working",
    "failed",
    "disconnect",
    "blocked",
    "issue",
    "error",
    "quota",
    "greyed out",
]

DIRECTION_PATTERNS = [
    "build order",
    "next step",
    "priority",
    "roadmap",
    "new direction",
    "thesis",
    "should",
    "focus",
    "strategy",
    "market validated",
]

TECH_ISSUE_PATTERNS = [
    "error",
    "failed",
    "disconnect",
    "quota",
    "not found",
    "denied",
    "blocked",
    "timeout",
    "permission",
]


def utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def ensure_chronicle_dirs() -> None:
    CHRONICLE_DIR.mkdir(parents=True, exist_ok=True)
    CHRONICLE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    entries: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(item, dict):
                entries.append(item)
    return entries


def append_jsonl(path: Path, entry: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=True) + "\n")


def load_backfill_index() -> set[str]:
    if not CHRONICLE_INDEX.exists():
        return set()
    try:
        data = json.loads(CHRONICLE_INDEX.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return set()
    if isinstance(data, list):
        return {str(x) for x in data}
    return set()


def save_backfill_index(items: set[str]) -> None:
    CHRONICLE_INDEX.write_text(json.dumps(sorted(items), indent=2), encoding="utf-8")


def normalize_path(path: Path) -> str:
    return str(path.resolve())


def fingerprint_file(path: Path, size: int, mtime: float) -> str:
    raw = f"{normalize_path(path)}|{size}|{int(mtime)}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def categorize_path(path: Path) -> str:
    lower = normalize_path(path).lower()
    if "executive" in lower and "summary" in lower:
        return "executive_summary"
    if "notebooklm" in lower:
        return "notebooklm"
    if "quantum" in lower:
        return "quantum"
    if "permanence" in lower:
        return "permanence"
    if "chat" in lower or "conversation" in lower:
        return "chat_artifact"
    if lower.endswith(".py"):
        return "code"
    if lower.endswith(".md"):
        return "markdown"
    if lower.endswith(".docx"):
        return "docx"
    if lower.endswith(".pdf"):
        return "pdf"
    return "general"


def _extract_docx_text(path: Path) -> str:
    try:
        with zipfile.ZipFile(path) as zf:
            with zf.open("word/document.xml") as handle:
                xml = handle.read().decode("utf-8", errors="ignore")
    except Exception:
        return ""
    text = re.sub(r"<[^>]+>", " ", xml)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _extract_pdf_text(path: Path, max_chars: int) -> str:
    try:
        from pypdf import PdfReader  # type: ignore
    except Exception:
        return ""
    try:
        reader = PdfReader(str(path))
    except Exception:
        return ""
    chunks: list[str] = []
    for page in reader.pages[:3]:
        try:
            chunks.append(page.extract_text() or "")
        except Exception:
            continue
        if sum(len(x) for x in chunks) >= max_chars:
            break
    text = " ".join(chunks)
    return text[:max_chars]


def safe_read_excerpt(path: Path, max_chars: int = 1400) -> str:
    ext = path.suffix.lower()
    try:
        if ext in TEXT_EXTENSIONS:
            return path.read_text(encoding="utf-8", errors="ignore")[:max_chars]
        if ext == ".docx":
            return _extract_docx_text(path)[:max_chars]
        if ext == ".pdf":
            return _extract_pdf_text(path, max_chars=max_chars)[:max_chars]
    except Exception:
        return ""
    return ""


def _count_patterns(text: str, patterns: list[str]) -> int:
    lower = text.lower()
    return sum(1 for p in patterns if p in lower)


def detect_signals(text: str) -> dict[str, int]:
    if not text:
        return {"frustration_hits": 0, "direction_hits": 0, "issue_hits": 0}
    return {
        "frustration_hits": _count_patterns(text, FRUSTRATION_PATTERNS),
        "direction_hits": _count_patterns(text, DIRECTION_PATTERNS),
        "issue_hits": _count_patterns(text, TECH_ISSUE_PATTERNS),
    }


def to_utc_iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).isoformat().replace("+00:00", "Z")
