#!/usr/bin/env python3
"""
RESEARCHER AGENT
Gathers verified information with provenance. No speculation beyond sources.
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
import hashlib
import json
import os
import re

from agents.utils import log, BASE_DIR

TOOL_DIR = os.getenv("PERMANENCE_TOOL_DIR", os.path.join(BASE_DIR, "memory", "tool"))
DOC_DIR = os.getenv(
    "PERMANENCE_DOCUMENTS_DIR", os.path.join(BASE_DIR, "memory", "working", "documents")
)


@dataclass
class SourceRecord:
    """Provenanced source entry."""
    source: str
    timestamp: str
    confidence: float
    notes: Optional[str] = None
    hash: Optional[str] = None
    origin: Optional[str] = None


class ResearcherAgent:
    """
    ROLE: Gather verified information with provenance.

    CONSTRAINTS:
    - Must cite sources with source + timestamp + confidence
    - Cannot speculate beyond sources
    - Cannot generate final content
    """

    def validate_sources(self, sources: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Validate that all sources include provenance fields."""
        if not sources:
            return {
                "ok": False,
                "errors": [{"index": None, "missing": ["source", "timestamp", "confidence"]}],
            }
        required = {"source", "timestamp", "confidence"}
        errors = []

        for idx, src in enumerate(sources):
            missing = required.difference(src.keys())
            if missing:
                errors.append({"index": idx, "missing": sorted(missing)})

        ok = len(errors) == 0
        log("Researcher validation complete", level="INFO")
        return {"ok": ok, "errors": errors}

    def compile_sources(self, _query: str) -> None:
        """
        Placeholder for external research.
        Explicitly unimplemented to avoid unsourced claims.
        """
        log("Researcher compile_sources called without tools", level="WARNING")
        raise NotImplementedError(
            "ResearcherAgent.compile_sources requires external tools and is not implemented."
        )

    def compile_sources_from_tool_memory(
        self,
        tool_dir: str = TOOL_DIR,
        output_path: Optional[str] = None,
        default_confidence: float = 0.5,
        max_entries: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Convert raw tool outputs into a sources list with provenance.
        """
        if not os.path.isdir(tool_dir):
            raise FileNotFoundError(f"Tool memory directory not found: {tool_dir}")

        sources: List[Dict[str, Any]] = []
        files = [f for f in os.listdir(tool_dir) if os.path.isfile(os.path.join(tool_dir, f))]
        files.sort(key=lambda f: os.path.getmtime(os.path.join(tool_dir, f)), reverse=True)

        for name in files:
            path = os.path.join(tool_dir, name)
            if len(sources) >= max_entries:
                break
            sources.extend(self._sources_from_file(path, default_confidence))
            if len(sources) >= max_entries:
                sources = sources[:max_entries]
                break

        if output_path:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, "w") as f:
                json.dump(sources, f, indent=2)

        log(f"Compiled {len(sources)} sources from tool memory", level="INFO")
        return sources

    def compile_sources_from_documents(
        self,
        doc_dir: str = DOC_DIR,
        output_path: Optional[str] = None,
        default_confidence: float = 0.6,
        max_entries: int = 100,
        excerpt_chars: int = 280,
    ) -> List[Dict[str, Any]]:
        """
        Convert local documents into a sources list with provenance.
        Supports .txt, .md, .markdown, and .json files.
        """
        if not os.path.isdir(doc_dir):
            raise FileNotFoundError(f"Document directory not found: {doc_dir}")

        sources: List[Dict[str, Any]] = []
        files = [f for f in os.listdir(doc_dir) if os.path.isfile(os.path.join(doc_dir, f))]
        files.sort(key=lambda f: os.path.getmtime(os.path.join(doc_dir, f)), reverse=True)

        for name in files:
            if len(sources) >= max_entries:
                break
            path = os.path.join(doc_dir, name)
            sources.extend(self._sources_from_document(path, default_confidence, excerpt_chars))
            if len(sources) >= max_entries:
                sources = sources[:max_entries]
                break

        if output_path:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, "w") as f:
                json.dump(sources, f, indent=2)

        log(f"Compiled {len(sources)} sources from documents", level="INFO")
        return sources

    def _sources_from_file(self, path: str, default_confidence: float) -> List[Dict[str, Any]]:
        try:
            if path.endswith(".json"):
                with open(path, "r") as f:
                    data = json.load(f)
                return self._sources_from_json(data, path, default_confidence)
        except (json.JSONDecodeError, OSError):
            pass

        # Fallback: treat as raw text output
        try:
            with open(path, "rb") as f:
                content = f.read()
            mtime = datetime.fromtimestamp(os.path.getmtime(path), timezone.utc).isoformat()
            return [
                {
                    "source": os.path.basename(path),
                    "timestamp": mtime,
                    "confidence": default_confidence,
                    "notes": "Raw tool output",
                    "hash": self._hash_bytes(content),
                    "origin": path,
                }
            ]
        except OSError:
            return []

    def _sources_from_json(
        self, data: Any, path: str, default_confidence: float
    ) -> List[Dict[str, Any]]:
        items = data if isinstance(data, list) else [data]
        results: List[Dict[str, Any]] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            source = item.get("source") or item.get("url") or item.get("title") or os.path.basename(path)
            timestamp = (
                item.get("timestamp")
                or item.get("retrieved_at")
                or item.get("date")
                or datetime.fromtimestamp(os.path.getmtime(path), timezone.utc).isoformat()
            )
            confidence = item.get("confidence", default_confidence)
            notes = item.get("notes") or item.get("summary")
            raw = json.dumps(item, sort_keys=True).encode("utf-8")
            results.append(
                {
                    "source": source,
                    "timestamp": timestamp,
                    "confidence": confidence,
                    "notes": notes,
                    "hash": self._hash_bytes(raw),
                    "origin": path,
                }
            )
        return results

    def _sources_from_document(
        self, path: str, default_confidence: float, excerpt_chars: int
    ) -> List[Dict[str, Any]]:
        ext = os.path.splitext(path)[1].lower()
        if ext in {".txt", ".md", ".markdown"}:
            try:
                with open(path, "rb") as f:
                    content = f.read()
            except OSError:
                return []
            text = content.decode("utf-8", errors="ignore")
            excerpt = self._excerpt(text, excerpt_chars)
            mtime = datetime.fromtimestamp(os.path.getmtime(path), timezone.utc).isoformat()
            return [
                {
                    "source": os.path.basename(path),
                    "timestamp": mtime,
                    "confidence": default_confidence,
                    "notes": excerpt or "Document ingested (no excerpt)",
                    "hash": self._hash_bytes(content),
                    "origin": path,
                }
            ]

        if ext == ".json":
            try:
                with open(path, "r") as f:
                    data = json.load(f)
            except (OSError, json.JSONDecodeError):
                return []
            return self._sources_from_json(data, path, default_confidence)

        return []

    def _excerpt(self, text: str, limit: int) -> str:
        normalized = re.sub(r"\s+", " ", text).strip()
        if len(normalized) <= limit:
            return normalized
        return normalized[: limit - 3].rstrip() + "..."

    def _hash_bytes(self, content: bytes) -> str:
        return hashlib.sha256(content).hexdigest()


if __name__ == "__main__":
    ra = ResearcherAgent()
    sample = [
        {"source": "example", "timestamp": datetime.now(timezone.utc).isoformat(), "confidence": 0.7}
    ]
    print(ra.validate_sources(sample))
