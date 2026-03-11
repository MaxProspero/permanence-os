"""
Permanence OS — Synthesis Database (v0.1)

Governed SQLite database backing the Synthesis Ledger, Zero Point mirror,
episodic log, cost tracking, and knowledge graph.

Design:
  - WAL journal for concurrent dashboard reads + single writer
  - All writes enforce provenance (source, author, confidence, evidence)
  - FTS5 full-text search on ledger and zero-point content
  - Single-source writes auto-capped to LOW confidence
  - Append-only — entries are superseded, never deleted

Invariants:
  - No memory without provenance  (Canon CA-004)
  - No agent modifies the Canon   (Canon CA-001)
  - Logs are append-only           (Canon CA-006)
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from memory.zero_point import ConfidenceLevel, MemoryType


# ---------------------------------------------------------------------------
# Schema version — bump when tables change
# ---------------------------------------------------------------------------
SCHEMA_VERSION = 1

# Confidence ordering for filter/sort operations
CONFIDENCE_ORDER: Dict[str, int] = {
    "HIGH": 3,
    "MEDIUM": 2,
    "LOW": 1,
    "UNVERIFIED": 0,
}

# Ledger entry statuses
STATUS_ACTIVE = "ACTIVE"
STATUS_PENDING_REVIEW = "PENDING_REVIEW"
STATUS_SUPERSEDED = "SUPERSEDED"
STATUS_COMPACTED = "COMPACTED"
STATUS_REJECTED = "REJECTED"

# Stale threshold (days since last update)
STALE_THRESHOLD_DAYS = 7


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _generate_id(prefix: str, content: str, author: str) -> str:
    raw = f"{content}:{author}:{_now_iso()}"
    return f"{prefix}-{hashlib.sha256(raw.encode()).hexdigest()[:12]}"


class SynthesisDB:
    """Governed SQLite database for the Permanence OS Synthesis Layer."""

    def __init__(self, db_path: str | Path | None = None):
        if db_path is None:
            # Lazy import to avoid circular dependency with storage singleton
            db_path = os.getenv(
                "PERMANENCE_SYNTHESIS_DB",
                os.path.join("permanence_storage", "permanence.db"),
            )
        self.db_path = str(db_path)
        self._ensure_parent()
        self._conn: Optional[sqlite3.Connection] = None
        self._init_db()

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------

    def _ensure_parent(self) -> None:
        parent = os.path.dirname(self.db_path)
        if parent:
            os.makedirs(parent, exist_ok=True)

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path, timeout=10)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
            self._conn.execute("PRAGMA busy_timeout=5000")
        return self._conn

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    # ------------------------------------------------------------------
    # Schema initialization
    # ------------------------------------------------------------------

    def _init_db(self) -> None:
        conn = self._get_conn()
        conn.executescript(_SCHEMA_SQL)
        conn.commit()

    # ------------------------------------------------------------------
    # Ledger operations (the Synthesis Ledger)
    # ------------------------------------------------------------------

    def write_ledger_entry(
        self,
        *,
        entry_type: str,
        title: str,
        summary: str,
        source: str,
        author_agent: str,
        confidence: str = "LOW",
        evidence_count: int = 1,
        evidence: Optional[List[Dict[str, Any]]] = None,
        tags: Optional[List[str]] = None,
        canon_risk: str = "LOW",
        supersedes: Optional[str] = None,
        actionability: Optional[Dict[str, Any]] = None,
        limitations: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Write a governed entry to the Synthesis Ledger.

        Governance gates (mirrors ZeroPoint.write):
        1. Must have provenance (source + author_agent)
        2. Must have at least 1 evidence source
        3. Single-source writes capped to LOW confidence
        """
        # Gate 1: Provenance
        if not source or not author_agent:
            return {
                "status": "REJECTED",
                "reason": "No provenance. Memory without provenance is fiction.",
                "canon_ref": "CA-004",
            }

        # Gate 2: Evidence
        if evidence_count < 1:
            return {
                "status": "REJECTED",
                "reason": "No evidence. Cannot write unsubstantiated claims.",
                "canon_ref": "invariants/no_memory_without_provenance",
            }

        # Gate 3: Single-source confidence cap
        actual_confidence = confidence
        if evidence_count == 1 and confidence in ("HIGH", "MEDIUM"):
            actual_confidence = "LOW"
            limitations = (limitations or "") + " [AUTO-CAPPED: single source]"

        entry_id = _generate_id("SYN", title, author_agent)
        now = _now_iso()

        conn = self._get_conn()
        conn.execute(
            """INSERT INTO ledger_entries
               (entry_id, entry_type, title, summary, status, confidence,
                source, author_agent, evidence_count, evidence_json,
                tags_json, canon_risk, supersedes, actionability_json,
                limitations, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                entry_id,
                entry_type,
                title,
                summary,
                STATUS_ACTIVE,
                actual_confidence,
                source,
                author_agent,
                evidence_count,
                json.dumps(evidence or []),
                json.dumps(tags or []),
                canon_risk,
                supersedes,
                json.dumps(actionability or {}),
                limitations,
                now,
                now,
            ),
        )
        conn.commit()

        # Mark superseded entry
        if supersedes:
            conn.execute(
                "UPDATE ledger_entries SET status = ?, updated_at = ? WHERE entry_id = ?",
                (STATUS_SUPERSEDED, now, supersedes),
            )
            conn.commit()

        return {
            "status": "ACCEPTED",
            "entry_id": entry_id,
            "confidence": actual_confidence,
            "needs_review": True,
        }

    def read_ledger_entry(self, entry_id: str) -> Optional[Dict[str, Any]]:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM ledger_entries WHERE entry_id = ?", (entry_id,)
        ).fetchone()
        return dict(row) if row else None

    def search_ledger(
        self,
        *,
        query: Optional[str] = None,
        entry_type: Optional[str] = None,
        status: Optional[str] = None,
        min_confidence: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Search the Synthesis Ledger with optional FTS5 full-text query."""
        conn = self._get_conn()

        if query:
            # FTS5 search with rank ordering
            sql = """
                SELECT le.*, ledger_fts.rank
                FROM ledger_fts
                JOIN ledger_entries le ON le.rowid = ledger_fts.rowid
                WHERE ledger_fts MATCH ?
            """
            params: list[Any] = [query]

            if entry_type:
                sql += " AND le.entry_type = ?"
                params.append(entry_type)
            if status:
                sql += " AND le.status = ?"
                params.append(status)
            if min_confidence:
                min_val = CONFIDENCE_ORDER.get(min_confidence, 0)
                valid = [k for k, v in CONFIDENCE_ORDER.items() if v >= min_val]
                placeholders = ",".join("?" for _ in valid)
                sql += f" AND le.confidence IN ({placeholders})"
                params.extend(valid)

            sql += " ORDER BY ledger_fts.rank LIMIT ?"
            params.append(limit)
        else:
            sql = "SELECT * FROM ledger_entries WHERE 1=1"
            params = []

            if entry_type:
                sql += " AND entry_type = ?"
                params.append(entry_type)
            if status:
                sql += " AND status = ?"
                params.append(status)
            if min_confidence:
                min_val = CONFIDENCE_ORDER.get(min_confidence, 0)
                valid = [k for k, v in CONFIDENCE_ORDER.items() if v >= min_val]
                placeholders = ",".join("?" for _ in valid)
                sql += f" AND confidence IN ({placeholders})"
                params.extend(valid)

            sql += " ORDER BY updated_at DESC LIMIT ?"
            params.append(limit)

        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    def resolve_contradiction(
        self, entry_id: str, resolution: str, resolved_by: str
    ) -> bool:
        """Resolve a CONTRADICTION entry."""
        conn = self._get_conn()
        now = _now_iso()
        result = conn.execute(
            """UPDATE ledger_entries
               SET status = ?, reviewed_by = ?, limitations = COALESCE(limitations, '') || ?,
                   updated_at = ?
               WHERE entry_id = ? AND entry_type = 'CONTRADICTION'""",
            (
                STATUS_SUPERSEDED,
                resolved_by,
                f" [RESOLVED: {resolution}]",
                now,
                entry_id,
            ),
        )
        conn.commit()
        return (result.rowcount or 0) > 0

    def mark_reviewed(
        self, entry_id: str, reviewer: str, approved: bool = True
    ) -> bool:
        conn = self._get_conn()
        now = _now_iso()
        new_status = STATUS_ACTIVE if approved else STATUS_REJECTED
        result = conn.execute(
            """UPDATE ledger_entries
               SET reviewed_by = ?, approved_by = ?, status = ?, updated_at = ?
               WHERE entry_id = ?""",
            (reviewer, reviewer if approved else None, new_status, now, entry_id),
        )
        conn.commit()
        return (result.rowcount or 0) > 0

    # ------------------------------------------------------------------
    # Zero Point mirror operations
    # ------------------------------------------------------------------

    def write_zero_point(
        self,
        *,
        entry_id: str,
        memory_type: str,
        content: str,
        tags: List[str],
        source: str,
        author_agent: str,
        confidence: str,
        evidence_count: int = 1,
        limitations: Optional[str] = None,
        version: int = 1,
    ) -> None:
        """Insert or replace a Zero Point entry in SQLite."""
        now = _now_iso()
        conn = self._get_conn()
        conn.execute(
            """INSERT OR REPLACE INTO zero_point_entries
               (entry_id, memory_type, content, tags_json, source, author_agent,
                confidence, evidence_count, limitations, version,
                created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                entry_id,
                memory_type,
                content,
                json.dumps(tags),
                source,
                author_agent,
                confidence,
                evidence_count,
                limitations,
                version,
                now,
                now,
            ),
        )
        conn.commit()

    def search_zero_point(
        self,
        *,
        query: Optional[str] = None,
        tags: Optional[List[str]] = None,
        memory_type: Optional[str] = None,
        min_confidence: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        conn = self._get_conn()

        if query:
            sql = """
                SELECT zp.*
                FROM zero_point_fts
                JOIN zero_point_entries zp ON zp.rowid = zero_point_fts.rowid
                WHERE zero_point_fts MATCH ?
            """
            params: list[Any] = [query]
        else:
            sql = "SELECT * FROM zero_point_entries WHERE 1=1"
            params = []

        if memory_type:
            sql += " AND memory_type = ?"
            params.append(memory_type)
        if min_confidence:
            min_val = CONFIDENCE_ORDER.get(min_confidence, 0)
            valid = [k for k, v in CONFIDENCE_ORDER.items() if v >= min_val]
            placeholders = ",".join("?" for _ in valid)
            sql += f" AND confidence IN ({placeholders})"
            params.extend(valid)

        sql += " ORDER BY updated_at DESC LIMIT ?"
        params.append(limit)

        rows = conn.execute(sql, params).fetchall()
        results = [dict(r) for r in rows]

        # Post-filter by tags if needed (JSON field, not easily indexed)
        if tags:
            filtered = []
            for r in results:
                try:
                    entry_tags = json.loads(r.get("tags_json", "[]"))
                except (json.JSONDecodeError, TypeError):
                    entry_tags = []
                if any(t in entry_tags for t in tags):
                    filtered.append(r)
            results = filtered

        return results

    # ------------------------------------------------------------------
    # Episodic log operations
    # ------------------------------------------------------------------

    def write_episodic(
        self,
        *,
        task_id: str,
        task_goal: str,
        stage: str,
        status: str,
        risk_tier: str = "LOW",
        agents_involved: Optional[List[str]] = None,
        inputs_json: Optional[str] = None,
        outputs_json: Optional[str] = None,
        duration_seconds: Optional[float] = None,
    ) -> None:
        now = _now_iso()
        conn = self._get_conn()
        conn.execute(
            """INSERT INTO episodic_log
               (task_id, task_goal, stage, status, risk_tier,
                agents_json, inputs_json, outputs_json,
                duration_seconds, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                task_id,
                task_goal,
                stage,
                status,
                risk_tier,
                json.dumps(agents_involved or []),
                inputs_json,
                outputs_json,
                duration_seconds,
                now,
            ),
        )
        conn.commit()

    # ------------------------------------------------------------------
    # Cost log operations
    # ------------------------------------------------------------------

    def log_cost(
        self,
        *,
        model_id: str,
        tier: str,
        provider: str,
        input_tokens: int,
        output_tokens: int,
        cost_usd: float,
        session_id: str = "",
        task_id: str = "",
    ) -> None:
        now = _now_iso()
        conn = self._get_conn()
        conn.execute(
            """INSERT INTO model_cost_log
               (model_id, tier, provider, input_tokens, output_tokens,
                cost_usd, session_id, task_id, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                model_id,
                tier,
                provider,
                input_tokens,
                output_tokens,
                cost_usd,
                session_id,
                task_id,
                now,
            ),
        )
        conn.commit()

    def get_cost_summary(
        self, *, session_id: Optional[str] = None, since_iso: Optional[str] = None
    ) -> Dict[str, Any]:
        conn = self._get_conn()
        where = "WHERE 1=1"
        params: list[Any] = []
        if session_id:
            where += " AND session_id = ?"
            params.append(session_id)
        if since_iso:
            where += " AND created_at >= ?"
            params.append(since_iso)

        row = conn.execute(
            f"""SELECT
                    COALESCE(SUM(cost_usd), 0.0) AS total_usd,
                    COALESCE(SUM(input_tokens), 0) AS total_input_tokens,
                    COALESCE(SUM(output_tokens), 0) AS total_output_tokens,
                    COUNT(*) AS total_calls
                FROM model_cost_log {where}""",
            params,
        ).fetchone()
        return dict(row) if row else {}

    def get_cost_by_provider(
        self, *, since_iso: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        conn = self._get_conn()
        where = ""
        params: list[Any] = []
        if since_iso:
            where = "WHERE created_at >= ?"
            params.append(since_iso)

        rows = conn.execute(
            f"""SELECT provider,
                    SUM(cost_usd) AS total_usd,
                    SUM(input_tokens) AS total_input_tokens,
                    SUM(output_tokens) AS total_output_tokens,
                    COUNT(*) AS calls
                FROM model_cost_log {where}
                GROUP BY provider
                ORDER BY total_usd DESC""",
            params,
        ).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Knowledge graph operations
    # ------------------------------------------------------------------

    def write_knowledge_node(
        self, *, node_id: str, label: str, node_type: str, metadata_json: str = "{}"
    ) -> None:
        now = _now_iso()
        conn = self._get_conn()
        conn.execute(
            """INSERT OR REPLACE INTO knowledge_nodes
               (node_id, label, node_type, metadata_json, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (node_id, label, node_type, metadata_json, now),
        )
        conn.commit()

    def write_knowledge_edge(
        self,
        *,
        source_id: str,
        target_id: str,
        relation: str,
        weight: float = 1.0,
        metadata_json: str = "{}",
    ) -> None:
        now = _now_iso()
        conn = self._get_conn()
        conn.execute(
            """INSERT OR REPLACE INTO knowledge_edges
               (source_id, target_id, relation, weight, metadata_json, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (source_id, target_id, relation, weight, metadata_json, now),
        )
        conn.commit()

    # ------------------------------------------------------------------
    # Stats / dashboard
    # ------------------------------------------------------------------

    def get_ledger_stats(self) -> Dict[str, Any]:
        conn = self._get_conn()
        total = conn.execute("SELECT COUNT(*) FROM ledger_entries").fetchone()[0]
        by_type = {}
        for row in conn.execute(
            "SELECT entry_type, COUNT(*) AS cnt FROM ledger_entries GROUP BY entry_type"
        ).fetchall():
            by_type[row["entry_type"]] = row["cnt"]
        by_status = {}
        for row in conn.execute(
            "SELECT status, COUNT(*) AS cnt FROM ledger_entries GROUP BY status"
        ).fetchall():
            by_status[row["status"]] = row["cnt"]
        pending = conn.execute(
            "SELECT COUNT(*) FROM ledger_entries WHERE status = ?",
            (STATUS_PENDING_REVIEW,),
        ).fetchone()[0]

        return {
            "total_entries": total,
            "by_type": by_type,
            "by_status": by_status,
            "pending_review": pending,
        }


# ---------------------------------------------------------------------------
# SQL schema (created on first init)
# ---------------------------------------------------------------------------
_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY
);
INSERT OR IGNORE INTO schema_version (version) VALUES (1);

-- ================================================================
-- Synthesis Ledger
-- ================================================================
CREATE TABLE IF NOT EXISTS ledger_entries (
    rowid         INTEGER PRIMARY KEY AUTOINCREMENT,
    entry_id      TEXT UNIQUE NOT NULL,
    entry_type    TEXT NOT NULL,      -- FACT, DECISION, CONTRADICTION, POLICY, TASK, etc.
    title         TEXT NOT NULL,
    summary       TEXT NOT NULL DEFAULT '',
    status        TEXT NOT NULL DEFAULT 'ACTIVE',
    confidence    TEXT NOT NULL DEFAULT 'LOW',

    -- Provenance (mandatory)
    source        TEXT NOT NULL,
    author_agent  TEXT NOT NULL,
    evidence_count INTEGER NOT NULL DEFAULT 1,
    evidence_json TEXT NOT NULL DEFAULT '[]',

    -- Metadata
    tags_json     TEXT NOT NULL DEFAULT '[]',
    canon_risk    TEXT NOT NULL DEFAULT 'LOW',
    supersedes    TEXT,               -- entry_id of superseded entry
    limitations   TEXT,

    -- Governance
    reviewed_by   TEXT,
    approved_by   TEXT,
    actionability_json TEXT NOT NULL DEFAULT '{}',

    -- Timestamps
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_ledger_type ON ledger_entries(entry_type);
CREATE INDEX IF NOT EXISTS idx_ledger_status ON ledger_entries(status);
CREATE INDEX IF NOT EXISTS idx_ledger_confidence ON ledger_entries(confidence);
CREATE INDEX IF NOT EXISTS idx_ledger_updated ON ledger_entries(updated_at);

-- FTS5 virtual table for full-text search on ledger
CREATE VIRTUAL TABLE IF NOT EXISTS ledger_fts USING fts5(
    title, summary, evidence_json,
    content=ledger_entries,
    content_rowid=rowid
);

-- Triggers to keep FTS in sync
CREATE TRIGGER IF NOT EXISTS ledger_fts_ai AFTER INSERT ON ledger_entries BEGIN
    INSERT INTO ledger_fts(rowid, title, summary, evidence_json)
    VALUES (new.rowid, new.title, new.summary, new.evidence_json);
END;

CREATE TRIGGER IF NOT EXISTS ledger_fts_au AFTER UPDATE ON ledger_entries BEGIN
    INSERT INTO ledger_fts(ledger_fts, rowid, title, summary, evidence_json)
    VALUES ('delete', old.rowid, old.title, old.summary, old.evidence_json);
    INSERT INTO ledger_fts(rowid, title, summary, evidence_json)
    VALUES (new.rowid, new.title, new.summary, new.evidence_json);
END;

-- ================================================================
-- Zero Point mirror
-- ================================================================
CREATE TABLE IF NOT EXISTS zero_point_entries (
    rowid         INTEGER PRIMARY KEY AUTOINCREMENT,
    entry_id      TEXT UNIQUE NOT NULL,
    memory_type   TEXT NOT NULL,
    content       TEXT NOT NULL,
    tags_json     TEXT NOT NULL DEFAULT '[]',

    -- Provenance
    source        TEXT NOT NULL,
    author_agent  TEXT NOT NULL,
    confidence    TEXT NOT NULL DEFAULT 'LOW',
    evidence_count INTEGER NOT NULL DEFAULT 1,
    limitations   TEXT,
    version       INTEGER NOT NULL DEFAULT 1,

    -- Timestamps
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_zp_type ON zero_point_entries(memory_type);
CREATE INDEX IF NOT EXISTS idx_zp_confidence ON zero_point_entries(confidence);

-- FTS5 for zero point
CREATE VIRTUAL TABLE IF NOT EXISTS zero_point_fts USING fts5(
    content, tags_json,
    content=zero_point_entries,
    content_rowid=rowid
);

CREATE TRIGGER IF NOT EXISTS zp_fts_ai AFTER INSERT ON zero_point_entries BEGIN
    INSERT INTO zero_point_fts(rowid, content, tags_json)
    VALUES (new.rowid, new.content, new.tags_json);
END;

CREATE TRIGGER IF NOT EXISTS zp_fts_au AFTER UPDATE ON zero_point_entries BEGIN
    INSERT INTO zero_point_fts(zero_point_fts, rowid, content, tags_json)
    VALUES ('delete', old.rowid, old.content, old.tags_json);
    INSERT INTO zero_point_fts(rowid, content, tags_json)
    VALUES (new.rowid, new.content, new.tags_json);
END;

-- ================================================================
-- Episodic log
-- ================================================================
CREATE TABLE IF NOT EXISTS episodic_log (
    rowid            INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id          TEXT NOT NULL,
    task_goal        TEXT NOT NULL DEFAULT '',
    stage            TEXT NOT NULL DEFAULT '',
    status           TEXT NOT NULL DEFAULT '',
    risk_tier        TEXT NOT NULL DEFAULT 'LOW',
    agents_json      TEXT NOT NULL DEFAULT '[]',
    inputs_json      TEXT,
    outputs_json     TEXT,
    duration_seconds REAL,
    created_at       TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_ep_task ON episodic_log(task_id);
CREATE INDEX IF NOT EXISTS idx_ep_created ON episodic_log(created_at);

-- ================================================================
-- Model cost log
-- ================================================================
CREATE TABLE IF NOT EXISTS model_cost_log (
    rowid          INTEGER PRIMARY KEY AUTOINCREMENT,
    model_id       TEXT NOT NULL,
    tier           TEXT NOT NULL DEFAULT '',
    provider       TEXT NOT NULL DEFAULT '',
    input_tokens   INTEGER NOT NULL DEFAULT 0,
    output_tokens  INTEGER NOT NULL DEFAULT 0,
    cost_usd       REAL NOT NULL DEFAULT 0.0,
    session_id     TEXT NOT NULL DEFAULT '',
    task_id        TEXT NOT NULL DEFAULT '',
    created_at     TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_cost_session ON model_cost_log(session_id);
CREATE INDEX IF NOT EXISTS idx_cost_created ON model_cost_log(created_at);
CREATE INDEX IF NOT EXISTS idx_cost_provider ON model_cost_log(provider);

-- ================================================================
-- Knowledge graph
-- ================================================================
CREATE TABLE IF NOT EXISTS knowledge_nodes (
    rowid         INTEGER PRIMARY KEY AUTOINCREMENT,
    node_id       TEXT UNIQUE NOT NULL,
    label         TEXT NOT NULL,
    node_type     TEXT NOT NULL DEFAULT '',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS knowledge_edges (
    rowid         INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id     TEXT NOT NULL,
    target_id     TEXT NOT NULL,
    relation      TEXT NOT NULL,
    weight        REAL NOT NULL DEFAULT 1.0,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at    TEXT NOT NULL,
    UNIQUE(source_id, target_id, relation)
);

CREATE INDEX IF NOT EXISTS idx_ke_source ON knowledge_edges(source_id);
CREATE INDEX IF NOT EXISTS idx_ke_target ON knowledge_edges(target_id);
"""
