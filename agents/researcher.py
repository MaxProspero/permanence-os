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

from agents.utils import log, BASE_DIR

TOOL_DIR = os.getenv("PERMANENCE_TOOL_DIR", os.path.join(BASE_DIR, "memory", "tool"))


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

    def _hash_bytes(self, content: bytes) -> str:
        return hashlib.sha256(content).hexdigest()


if __name__ == "__main__":
    ra = ResearcherAgent()
    sample = [
        {"source": "example", "timestamp": datetime.now(timezone.utc).isoformat(), "confidence": 0.7}
    ]
    print(ra.validate_sources(sample))
