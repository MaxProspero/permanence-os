"""
Permanence OS — Zero Point Shared Memory (v0.3)
The "6" in the 3-6-9 architecture.

Central vector store that all agents read from and write to.
Every write MUST have provenance. Ungoverned writes are rejected.
Reads are logged. Stale data is flagged.

This is NOT a database. This is a governed consciousness substrate.
"""

import json
import os
import hashlib
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, field, asdict
from enum import Enum


class MemoryType(Enum):
    PATTERN = "PATTERN"           # Reusable learned pattern
    SKILL = "SKILL"               # Transferable capability
    FACT = "FACT"                  # Verified information
    FAILURE = "FAILURE"           # Documented failure mode
    INSIGHT = "INSIGHT"           # Cross-domain connection
    PROPOSAL = "PROPOSAL"         # Idea Agent output (pending)


class ConfidenceLevel(Enum):
    HIGH = "HIGH"         # Multiple diverse sources, tested
    MEDIUM = "MEDIUM"     # Multiple sources or single high-quality
    LOW = "LOW"           # Single source, untested
    UNVERIFIED = "UNVERIFIED"  # No source validation


@dataclass
class ZeroPointEntry:
    """Single entry in the Zero Point shared memory."""
    entry_id: str
    memory_type: str
    content: str
    tags: List[str]

    # Provenance (MANDATORY — no entry without these)
    source: str
    author_agent: str
    confidence: str
    evidence_count: int
    limitations: Optional[str]

    # Metadata
    created_at: str
    updated_at: str
    version: int = 1
    read_count: int = 0
    last_read_by: Optional[str] = None
    last_read_at: Optional[str] = None

    # Governance
    reviewed: bool = False
    reviewer_agent: Optional[str] = None
    promoted_to_canon: bool = False
    flagged_stale: bool = False


class ZeroPoint:
    """
    The Zero Point shared memory substrate.

    Rules:
    - All writes require provenance (source, timestamp, confidence, author_agent)
    - Reads are logged
    - Stale data (>7 days without refresh) is flagged
    - No overwrites — updates create new versions
    - Emergency broadcasts bypass review but are flagged for audit
    """

    STALE_THRESHOLD_DAYS = 7

    def __init__(self, storage_path: str = "memory/zero_point_store.json"):
        self.storage_path = storage_path
        self.entries: Dict[str, ZeroPointEntry] = {}
        self.access_log: List[Dict] = []
        self._load()

    def _load(self):
        """Load persisted Zero Point state."""
        if os.path.exists(self.storage_path):
            try:
                with open(self.storage_path, 'r') as f:
                    data = json.load(f)
                for eid, edata in data.get("entries", {}).items():
                    self.entries[eid] = ZeroPointEntry(**edata)
            except (json.JSONDecodeError, TypeError):
                self.entries = {}

    def _save(self):
        """Persist Zero Point state."""
        os.makedirs(os.path.dirname(self.storage_path) or '.', exist_ok=True)
        data = {
            "entries": {eid: asdict(entry) for eid, entry in self.entries.items()},
            "last_saved": datetime.now(timezone.utc).isoformat(),
            "total_entries": len(self.entries)
        }
        with open(self.storage_path, 'w') as f:
            json.dump(data, f, indent=2)

    def _generate_id(self, content: str, author: str) -> str:
        """Generate deterministic entry ID from content hash."""
        raw = f"{content}:{author}:{datetime.now(timezone.utc).isoformat()}"
        return f"ZP-{hashlib.sha256(raw.encode()).hexdigest()[:12]}"

    def _log_access(self, action: str, entry_id: str, agent_id: str, detail: str = ""):
        """Log every access to Zero Point."""
        self.access_log.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": action,
            "entry_id": entry_id,
            "agent_id": agent_id,
            "detail": detail
        })

    def write(self, content: str, memory_type: MemoryType, tags: List[str],
              source: str, author_agent: str, confidence: ConfidenceLevel,
              evidence_count: int = 1, limitations: Optional[str] = None,
              emergency: bool = False) -> Dict:
        """
        Write to Zero Point.

        GOVERNANCE GATES:
        1. Must have provenance (source, confidence, author)
        2. Must have at least 1 evidence source
        3. Single-source writes get LOW confidence cap
        4. Emergency writes bypass review but are flagged
        """
        now = datetime.now(timezone.utc).isoformat()

        # Gate 1: Provenance check
        if not source or not author_agent:
            return {
                "status": "REJECTED",
                "reason": "No provenance. Memory without provenance is fiction.",
                "canon_ref": "CA-004"
            }

        # Gate 2: Evidence check
        if evidence_count < 1:
            return {
                "status": "REJECTED",
                "reason": "No evidence. Cannot write unsubstantiated claims.",
                "canon_ref": "invariants/no_memory_without_provenance"
            }

        # Gate 3: Single-source confidence cap
        actual_confidence = confidence
        if evidence_count == 1 and confidence in (ConfidenceLevel.HIGH, ConfidenceLevel.MEDIUM):
            actual_confidence = ConfidenceLevel.LOW
            limitations = (limitations or "") + " [AUTO-CAPPED: single source]"

        entry_id = self._generate_id(content, author_agent)
        entry = ZeroPointEntry(
            entry_id=entry_id,
            memory_type=memory_type.value,
            content=content,
            tags=tags,
            source=source,
            author_agent=author_agent,
            confidence=actual_confidence.value,
            evidence_count=evidence_count,
            limitations=limitations,
            created_at=now,
            updated_at=now,
            reviewed=False if not emergency else False,  # Emergency still needs post-hoc review
        )

        self.entries[entry_id] = entry
        self._log_access("WRITE", entry_id, author_agent,
                         f"type={memory_type.value}, confidence={actual_confidence.value}"
                         + (", EMERGENCY=True" if emergency else ""))
        self._save()

        return {
            "status": "ACCEPTED",
            "entry_id": entry_id,
            "confidence": actual_confidence.value,
            "emergency": emergency,
            "needs_review": True
        }

    def read(self, entry_id: str, requesting_agent: str) -> Optional[Dict]:
        """
        Read from Zero Point. Access is logged.
        Stale entries are flagged automatically.
        """
        entry = self.entries.get(entry_id)
        if not entry:
            self._log_access("READ_MISS", entry_id, requesting_agent)
            return None

        # Update read metadata
        entry.read_count += 1
        entry.last_read_by = requesting_agent
        entry.last_read_at = datetime.now(timezone.utc).isoformat()

        # Stale check
        updated = datetime.fromisoformat(entry.updated_at)
        if datetime.now(timezone.utc) - updated > timedelta(days=self.STALE_THRESHOLD_DAYS):
            entry.flagged_stale = True

        self._log_access("READ", entry_id, requesting_agent)
        self._save()

        return asdict(entry)

    def search(self, tags: Optional[List[str]] = None,
               memory_type: Optional[MemoryType] = None,
               min_confidence: Optional[ConfidenceLevel] = None,
               requesting_agent: str = "UNKNOWN") -> List[Dict]:
        """
        Search Zero Point by tags, type, or confidence.
        Returns matching entries sorted by confidence then recency.
        """
        results = []
        confidence_order = {"HIGH": 3, "MEDIUM": 2, "LOW": 1, "UNVERIFIED": 0}

        for entry in self.entries.values():
            # Filter by tags
            if tags and not any(t in entry.tags for t in tags):
                continue
            # Filter by type
            if memory_type and entry.memory_type != memory_type.value:
                continue
            # Filter by confidence
            if min_confidence and confidence_order.get(entry.confidence, 0) < \
                    confidence_order.get(min_confidence.value, 0):
                continue

            results.append(asdict(entry))

        # Sort: highest confidence first, then most recent
        results.sort(key=lambda x: (
            confidence_order.get(x["confidence"], 0),
            x["updated_at"]
        ), reverse=True)

        self._log_access("SEARCH", "MULTI", requesting_agent,
                         f"tags={tags}, type={memory_type}, results={len(results)}")
        return results

    def mark_reviewed(self, entry_id: str, reviewer_agent: str) -> bool:
        """Mark an entry as reviewed by a Reviewer agent."""
        entry = self.entries.get(entry_id)
        if not entry:
            return False
        entry.reviewed = True
        entry.reviewer_agent = reviewer_agent
        entry.updated_at = datetime.now(timezone.utc).isoformat()
        self._log_access("REVIEW", entry_id, reviewer_agent)
        self._save()
        return True

    def get_stats(self) -> Dict:
        """System health stats for Zero Point."""
        total = len(self.entries)
        reviewed = sum(1 for e in self.entries.values() if e.reviewed)
        stale = sum(1 for e in self.entries.values() if e.flagged_stale)
        by_type = {}
        for e in self.entries.values():
            by_type[e.memory_type] = by_type.get(e.memory_type, 0) + 1

        return {
            "total_entries": total,
            "reviewed": reviewed,
            "unreviewed": total - reviewed,
            "stale": stale,
            "by_type": by_type,
            "access_log_size": len(self.access_log)
        }
