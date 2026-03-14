"""
Permanence OS — Synthesis DB Compatibility Layer (v0.1)

SQLite-backed implementations of ZeroPoint and EpisodicMemory.
Activated via env: PERMANENCE_USE_SQLITE=1

Default remains flat-file (JSON/JSONL) until fully validated.
This layer subclasses the originals and overrides storage methods
to use the Synthesis DB, preserving the governance gates.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from memory.zero_point import (
    ConfidenceLevel,
    MemoryType,
    ZeroPoint,
    ZeroPointEntry,
)
from core.memory import EpisodicMemory


def _use_sqlite() -> bool:
    """Check if SQLite backend is enabled."""
    return os.getenv("PERMANENCE_USE_SQLITE", "").strip() in ("1", "true", "yes")


def _default_db_path(candidate_path: str | None = None) -> str:
    if candidate_path:
        base = os.path.dirname(os.path.abspath(candidate_path))
        if base:
            return os.path.join(base, "permanence.db")
    return os.path.join("permanence_storage", "permanence.db")


class SQLiteZeroPoint(ZeroPoint):
    """ZeroPoint that reads/writes via SynthesisDB instead of JSON files.

    Governance gates remain identical — only storage is replaced.
    """

    def __init__(self, storage_path: str | None = None, db_path: str | None = None):
        # Set _db BEFORE super().__init__() because _load() is called there
        from core.synthesis_db import SynthesisDB

        effective_path = storage_path or "memory/zero_point_store.json"
        self._db = SynthesisDB(db_path=db_path or _default_db_path(effective_path))
        # Provide a default storage_path so parent __init__ doesn't crash
        super().__init__(storage_path=effective_path)

    def _load(self) -> None:
        """Load entries from SQLite instead of JSON file."""
        if not hasattr(self, "_db"):
            # Guard: parent __init__ may call _load before _db is set
            self.entries = {}
            return
        rows = self._db.search_zero_point(limit=10000)
        self.entries = {}
        for row in rows:
            try:
                tags = json.loads(row.get("tags_json", "[]"))
            except (json.JSONDecodeError, TypeError):
                tags = []
            self.entries[row["entry_id"]] = ZeroPointEntry(
                entry_id=row["entry_id"],
                memory_type=row.get("memory_type", "FACT"),
                content=row.get("content", ""),
                tags=tags if isinstance(tags, list) else [],
                source=row.get("source", "unknown"),
                author_agent=row.get("author_agent", "unknown"),
                confidence=row.get("confidence", "LOW"),
                evidence_count=row.get("evidence_count", 1),
                limitations=row.get("limitations"),
                created_at=row.get("created_at", ""),
                updated_at=row.get("updated_at", ""),
                version=row.get("version", 1),
            )

    def _save(self) -> None:
        """Persist all entries to SQLite."""
        for entry_id, entry in self.entries.items():
            self._db.write_zero_point(
                entry_id=entry.entry_id,
                memory_type=entry.memory_type,
                content=entry.content,
                tags=entry.tags if isinstance(entry.tags, list) else [],
                source=entry.source,
                author_agent=entry.author_agent,
                confidence=entry.confidence,
                evidence_count=entry.evidence_count,
                limitations=entry.limitations,
                version=entry.version,
            )

    def search(
        self,
        tags: Optional[List[str]] = None,
        memory_type: Optional[MemoryType] = None,
        min_confidence: Optional[ConfidenceLevel] = None,
        requesting_agent: str = "UNKNOWN",
    ) -> List[Dict]:
        """Search using SQLite FTS5 when no tags filter, else use parent logic."""
        # If only using memory_type or min_confidence, we can use the DB directly
        if not tags:
            rows = self._db.search_zero_point(
                memory_type=memory_type.value if memory_type else None,
                min_confidence=min_confidence.value if min_confidence else None,
            )
            self._log_access(
                "SEARCH",
                "MULTI",
                requesting_agent,
                f"tags={tags}, type={memory_type}, results={len(rows)}",
            )
            return rows

        # Tag-based search: use parent's in-memory filtering
        return super().search(
            tags=tags,
            memory_type=memory_type,
            min_confidence=min_confidence,
            requesting_agent=requesting_agent,
        )


class SQLiteEpisodicMemory(EpisodicMemory):
    """EpisodicMemory that writes to SQLite instead of JSONL files.

    Reads still work from JSONL (backward compatible).
    New writes go to both JSONL (for backward compat) and SQLite.
    """

    def __init__(
        self, memory_dir: Optional[str] = None, db_path: str | None = None
    ):
        super().__init__(memory_dir=memory_dir)
        from core.synthesis_db import SynthesisDB

        effective_memory_dir = memory_dir or "memory/episodic"
        self._db = SynthesisDB(db_path=db_path or _default_db_path(effective_memory_dir))

    def write_entry(self, entry: Dict[str, Any]) -> str:
        """Write to both JSONL (backward compat) and SQLite."""
        # Write to JSONL via parent
        log_path = super().write_entry(entry)

        # Also write to SQLite
        try:
            self._db.write_episodic(
                task_id=entry.get("task_id", ""),
                task_goal=entry.get("inputs", {}).get("goal", "")
                if isinstance(entry.get("inputs"), dict)
                else "",
                stage=entry.get("governance", {}).get("stage", "")
                if isinstance(entry.get("governance"), dict)
                else "",
                status="COMPLETED",
                risk_tier=entry.get("risk_tier", "LOW"),
                agents_involved=entry.get("agents_involved"),
                inputs_json=json.dumps(entry.get("inputs", {})),
                outputs_json=json.dumps(entry.get("outputs", {})),
                duration_seconds=entry.get("duration_seconds"),
            )
        except Exception:
            # SQLite write failure should never break the primary JSONL path
            pass

        return log_path


_DEFAULT_ZP_PATH = "memory/zero_point_store.json"


def get_zero_point(storage_path: str | None = None) -> ZeroPoint:
    """Factory: returns SQLite-backed ZeroPoint if enabled, else standard."""
    effective_path = storage_path or _DEFAULT_ZP_PATH
    if _use_sqlite():
        return SQLiteZeroPoint(storage_path=effective_path)
    return ZeroPoint(storage_path=effective_path)


def get_episodic_memory(memory_dir: str | None = None) -> EpisodicMemory:
    """Factory: returns SQLite-backed EpisodicMemory if enabled, else standard."""
    if _use_sqlite():
        return SQLiteEpisodicMemory(memory_dir=memory_dir)
    return EpisodicMemory(memory_dir=memory_dir)
