#!/usr/bin/env python3
"""
RESEARCHER AGENT
Gathers verified information with provenance. No speculation beyond sources.
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

from agents.utils import log


@dataclass
class SourceRecord:
    """Provenanced source entry."""
    source: str
    timestamp: str
    confidence: float
    notes: Optional[str] = None


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


if __name__ == "__main__":
    ra = ResearcherAgent()
    sample = [
        {"source": "example", "timestamp": datetime.now(timezone.utc).isoformat(), "confidence": 0.7}
    ]
    print(ra.validate_sources(sample))
