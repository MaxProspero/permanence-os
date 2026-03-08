#!/usr/bin/env python3
"""Tests for the Synthesis Database (core/synthesis_db.py).

Covers:
  - Schema creation
  - Ledger write governance gates (provenance, evidence, confidence cap)
  - FTS5 full-text search
  - Contradiction resolution
  - Review/approval workflow
  - Zero Point mirror operations
  - Episodic log
  - Cost logging and summaries
  - Knowledge graph nodes/edges
  - Stats dashboard
  - Compatibility layer (SQLiteZeroPoint, SQLiteEpisodicMemory)
"""

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.synthesis_db import (  # noqa: E402
    SynthesisDB,
    STATUS_ACTIVE,
    STATUS_PENDING_REVIEW,
    STATUS_SUPERSEDED,
    STATUS_REJECTED,
    CONFIDENCE_ORDER,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_db(tmp_dir: str) -> SynthesisDB:
    """Create a SynthesisDB in a temp directory."""
    db_path = os.path.join(tmp_dir, "test_permanence.db")
    return SynthesisDB(db_path=db_path)


def _write_fact(db: SynthesisDB, title: str = "Test fact", **kwargs) -> dict:
    """Convenience writer for FACT entries."""
    defaults = dict(
        entry_type="FACT",
        title=title,
        summary="A test fact for unit testing.",
        source="unit_test",
        author_agent="test_agent",
        confidence="LOW",
        evidence_count=1,
    )
    defaults.update(kwargs)
    return db.write_ledger_entry(**defaults)


# ---------------------------------------------------------------------------
# Schema and initialization
# ---------------------------------------------------------------------------

def test_db_creates_schema():
    with tempfile.TemporaryDirectory() as tmp:
        db = _make_db(tmp)
        conn = db._get_conn()
        tables = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()]
        assert "ledger_entries" in tables
        assert "zero_point_entries" in tables
        assert "episodic_log" in tables
        assert "model_cost_log" in tables
        assert "knowledge_nodes" in tables
        assert "knowledge_edges" in tables
        db.close()


def test_fts_tables_created():
    with tempfile.TemporaryDirectory() as tmp:
        db = _make_db(tmp)
        conn = db._get_conn()
        tables = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()]
        assert "ledger_fts" in tables
        assert "zero_point_fts" in tables
        db.close()


def test_wal_mode_enabled():
    with tempfile.TemporaryDirectory() as tmp:
        db = _make_db(tmp)
        mode = db._get_conn().execute("PRAGMA journal_mode").fetchone()[0]
        assert mode == "wal"
        db.close()


# ---------------------------------------------------------------------------
# Ledger governance gates
# ---------------------------------------------------------------------------

def test_gate_rejects_no_provenance():
    with tempfile.TemporaryDirectory() as tmp:
        db = _make_db(tmp)
        result = db.write_ledger_entry(
            entry_type="FACT",
            title="No source",
            summary="test",
            source="",
            author_agent="",
        )
        assert result["status"] == "REJECTED"
        assert "provenance" in result["reason"].lower()
        db.close()


def test_gate_rejects_no_evidence():
    with tempfile.TemporaryDirectory() as tmp:
        db = _make_db(tmp)
        result = db.write_ledger_entry(
            entry_type="FACT",
            title="No evidence",
            summary="test",
            source="test",
            author_agent="test",
            evidence_count=0,
        )
        assert result["status"] == "REJECTED"
        assert "evidence" in result["reason"].lower()
        db.close()


def test_gate_caps_single_source_confidence():
    with tempfile.TemporaryDirectory() as tmp:
        db = _make_db(tmp)
        result = db.write_ledger_entry(
            entry_type="FACT",
            title="High claim",
            summary="claims HIGH but has 1 source",
            source="test",
            author_agent="test",
            confidence="HIGH",
            evidence_count=1,
        )
        assert result["status"] == "ACCEPTED"
        assert result["confidence"] == "LOW"
        db.close()


def test_gate_allows_multi_source_high_confidence():
    with tempfile.TemporaryDirectory() as tmp:
        db = _make_db(tmp)
        result = db.write_ledger_entry(
            entry_type="FACT",
            title="Multi-source high",
            summary="Multiple sources",
            source="test",
            author_agent="test",
            confidence="HIGH",
            evidence_count=3,
        )
        assert result["status"] == "ACCEPTED"
        assert result["confidence"] == "HIGH"
        db.close()


def test_gate_allows_single_source_low_confidence():
    with tempfile.TemporaryDirectory() as tmp:
        db = _make_db(tmp)
        result = db.write_ledger_entry(
            entry_type="FACT",
            title="Single low",
            summary="Single source LOW is fine",
            source="test",
            author_agent="test",
            confidence="LOW",
            evidence_count=1,
        )
        assert result["status"] == "ACCEPTED"
        assert result["confidence"] == "LOW"
        db.close()


# ---------------------------------------------------------------------------
# CRUD operations
# ---------------------------------------------------------------------------

def test_write_and_read_entry():
    with tempfile.TemporaryDirectory() as tmp:
        db = _make_db(tmp)
        result = _write_fact(db, title="Readable fact")
        assert result["status"] == "ACCEPTED"

        entry = db.read_ledger_entry(result["entry_id"])
        assert entry is not None
        assert entry["title"] == "Readable fact"
        assert entry["status"] == STATUS_ACTIVE
        db.close()


def test_read_nonexistent_returns_none():
    with tempfile.TemporaryDirectory() as tmp:
        db = _make_db(tmp)
        assert db.read_ledger_entry("SYN-nonexistent") is None
        db.close()


def test_supersedes_marks_old_entry():
    with tempfile.TemporaryDirectory() as tmp:
        db = _make_db(tmp)
        old = _write_fact(db, title="Old fact")
        new = _write_fact(db, title="New fact", supersedes=old["entry_id"])

        old_entry = db.read_ledger_entry(old["entry_id"])
        assert old_entry["status"] == STATUS_SUPERSEDED
        new_entry = db.read_ledger_entry(new["entry_id"])
        assert new_entry["status"] == STATUS_ACTIVE
        db.close()


# ---------------------------------------------------------------------------
# Full-text search (FTS5)
# ---------------------------------------------------------------------------

def test_fts_search_finds_matching():
    with tempfile.TemporaryDirectory() as tmp:
        db = _make_db(tmp)
        _write_fact(db, title="SQLite performance tuning", summary="WAL mode improves concurrency")
        _write_fact(db, title="Python async patterns", summary="asyncio event loop basics")

        results = db.search_ledger(query="SQLite")
        assert len(results) >= 1
        assert any("SQLite" in r["title"] for r in results)
        db.close()


def test_fts_search_empty_query():
    with tempfile.TemporaryDirectory() as tmp:
        db = _make_db(tmp)
        _write_fact(db, title="Fact one")
        _write_fact(db, title="Fact two")

        results = db.search_ledger()
        assert len(results) == 2
        db.close()


def test_search_filters_by_type():
    with tempfile.TemporaryDirectory() as tmp:
        db = _make_db(tmp)
        _write_fact(db, title="A fact", entry_type="FACT")
        _write_fact(db, title="A decision", entry_type="DECISION")

        results = db.search_ledger(entry_type="DECISION")
        assert len(results) == 1
        assert results[0]["entry_type"] == "DECISION"
        db.close()


def test_search_filters_by_status():
    with tempfile.TemporaryDirectory() as tmp:
        db = _make_db(tmp)
        old = _write_fact(db, title="Old")
        _write_fact(db, title="New", supersedes=old["entry_id"])

        active = db.search_ledger(status=STATUS_ACTIVE)
        assert all(r["status"] == STATUS_ACTIVE for r in active)
        db.close()


def test_search_filters_by_min_confidence():
    with tempfile.TemporaryDirectory() as tmp:
        db = _make_db(tmp)
        _write_fact(db, title="High conf", confidence="HIGH", evidence_count=3)
        _write_fact(db, title="Low conf", confidence="LOW", evidence_count=1)

        results = db.search_ledger(min_confidence="HIGH")
        assert len(results) == 1
        assert results[0]["confidence"] == "HIGH"
        db.close()


# ---------------------------------------------------------------------------
# Contradiction resolution
# ---------------------------------------------------------------------------

def test_resolve_contradiction():
    with tempfile.TemporaryDirectory() as tmp:
        db = _make_db(tmp)
        result = db.write_ledger_entry(
            entry_type="CONTRADICTION",
            title="Conflicting data",
            summary="Source A says X, Source B says Y",
            source="detector",
            author_agent="contradiction_detector",
            evidence_count=2,
            confidence="MEDIUM",
        )
        entry_id = result["entry_id"]

        resolved = db.resolve_contradiction(entry_id, "Source A was correct", "human_reviewer")
        assert resolved is True

        entry = db.read_ledger_entry(entry_id)
        assert entry["status"] == STATUS_SUPERSEDED
        assert "RESOLVED" in (entry.get("limitations") or "")
        db.close()


def test_resolve_non_contradiction_fails():
    with tempfile.TemporaryDirectory() as tmp:
        db = _make_db(tmp)
        result = _write_fact(db, title="Not a contradiction")
        resolved = db.resolve_contradiction(result["entry_id"], "test", "reviewer")
        assert resolved is False
        db.close()


# ---------------------------------------------------------------------------
# Review / approval workflow
# ---------------------------------------------------------------------------

def test_mark_reviewed_approved():
    with tempfile.TemporaryDirectory() as tmp:
        db = _make_db(tmp)
        result = _write_fact(db, title="Needs review")
        ok = db.mark_reviewed(result["entry_id"], "reviewer_agent", approved=True)
        assert ok is True
        entry = db.read_ledger_entry(result["entry_id"])
        assert entry["reviewed_by"] == "reviewer_agent"
        assert entry["approved_by"] == "reviewer_agent"
        assert entry["status"] == STATUS_ACTIVE
        db.close()


def test_mark_reviewed_rejected():
    with tempfile.TemporaryDirectory() as tmp:
        db = _make_db(tmp)
        result = _write_fact(db, title="Bad fact")
        ok = db.mark_reviewed(result["entry_id"], "reviewer_agent", approved=False)
        assert ok is True
        entry = db.read_ledger_entry(result["entry_id"])
        assert entry["status"] == STATUS_REJECTED
        assert entry["approved_by"] is None
        db.close()


# ---------------------------------------------------------------------------
# Zero Point mirror
# ---------------------------------------------------------------------------

def test_zero_point_write_and_search():
    with tempfile.TemporaryDirectory() as tmp:
        db = _make_db(tmp)
        db.write_zero_point(
            entry_id="ZP-test001",
            memory_type="FACT",
            content="Python is a programming language",
            tags=["python", "programming"],
            source="unit_test",
            author_agent="test",
            confidence="HIGH",
            evidence_count=3,
        )
        results = db.search_zero_point(query="Python")
        assert len(results) >= 1
        assert "Python" in results[0]["content"]
        db.close()


def test_zero_point_tag_filter():
    with tempfile.TemporaryDirectory() as tmp:
        db = _make_db(tmp)
        db.write_zero_point(
            entry_id="ZP-tag1",
            memory_type="FACT",
            content="Tagged entry",
            tags=["finance", "budget"],
            source="test",
            author_agent="test",
            confidence="LOW",
        )
        db.write_zero_point(
            entry_id="ZP-tag2",
            memory_type="FACT",
            content="Other entry",
            tags=["engineering"],
            source="test",
            author_agent="test",
            confidence="LOW",
        )
        results = db.search_zero_point(tags=["finance"])
        assert len(results) >= 1
        assert all("finance" in json.loads(r.get("tags_json", "[]")) for r in results)
        db.close()


def test_zero_point_type_filter():
    with tempfile.TemporaryDirectory() as tmp:
        db = _make_db(tmp)
        db.write_zero_point(
            entry_id="ZP-skill1",
            memory_type="SKILL",
            content="Writing tests",
            tags=["testing"],
            source="test",
            author_agent="test",
            confidence="LOW",
        )
        db.write_zero_point(
            entry_id="ZP-fact1",
            memory_type="FACT",
            content="Earth orbits Sun",
            tags=["astronomy"],
            source="test",
            author_agent="test",
            confidence="LOW",
        )
        results = db.search_zero_point(memory_type="SKILL")
        assert len(results) == 1
        assert results[0]["memory_type"] == "SKILL"
        db.close()


# ---------------------------------------------------------------------------
# Episodic log
# ---------------------------------------------------------------------------

def test_episodic_write():
    with tempfile.TemporaryDirectory() as tmp:
        db = _make_db(tmp)
        db.write_episodic(
            task_id="task_001",
            task_goal="Test the system",
            stage="EXECUTE",
            status="COMPLETED",
            risk_tier="LOW",
            agents_involved=["researcher", "writer"],
            duration_seconds=12.5,
        )
        conn = db._get_conn()
        rows = conn.execute("SELECT * FROM episodic_log WHERE task_id = ?", ("task_001",)).fetchall()
        assert len(rows) == 1
        assert rows[0]["task_goal"] == "Test the system"
        db.close()


# ---------------------------------------------------------------------------
# Cost logging
# ---------------------------------------------------------------------------

def test_cost_log_and_summary():
    with tempfile.TemporaryDirectory() as tmp:
        db = _make_db(tmp)
        db.log_cost(
            model_id="claude-sonnet-4-6",
            tier="sonnet",
            provider="anthropic",
            input_tokens=1000,
            output_tokens=500,
            cost_usd=0.0105,
            session_id="sess_001",
        )
        db.log_cost(
            model_id="gpt-4o-mini",
            tier="haiku",
            provider="openai",
            input_tokens=500,
            output_tokens=200,
            cost_usd=0.000195,
            session_id="sess_001",
        )
        summary = db.get_cost_summary(session_id="sess_001")
        assert summary["total_calls"] == 2
        assert summary["total_usd"] > 0
        assert summary["total_input_tokens"] == 1500
        db.close()


def test_cost_by_provider():
    with tempfile.TemporaryDirectory() as tmp:
        db = _make_db(tmp)
        db.log_cost(
            model_id="claude-sonnet-4-6", tier="sonnet", provider="anthropic",
            input_tokens=100, output_tokens=50, cost_usd=0.001,
        )
        db.log_cost(
            model_id="qwen3:4b", tier="sonnet", provider="ollama",
            input_tokens=100, output_tokens=50, cost_usd=0.0,
        )
        by_provider = db.get_cost_by_provider()
        providers = {r["provider"] for r in by_provider}
        assert "anthropic" in providers
        assert "ollama" in providers
        db.close()


# ---------------------------------------------------------------------------
# Knowledge graph
# ---------------------------------------------------------------------------

def test_knowledge_node_write():
    with tempfile.TemporaryDirectory() as tmp:
        db = _make_db(tmp)
        db.write_knowledge_node(
            node_id="concept:python",
            label="Python",
            node_type="concept",
            metadata_json='{"domain": "programming"}',
        )
        conn = db._get_conn()
        row = conn.execute(
            "SELECT * FROM knowledge_nodes WHERE node_id = ?", ("concept:python",)
        ).fetchone()
        assert row is not None
        assert row["label"] == "Python"
        db.close()


def test_knowledge_edge_write():
    with tempfile.TemporaryDirectory() as tmp:
        db = _make_db(tmp)
        db.write_knowledge_node(node_id="A", label="A", node_type="test")
        db.write_knowledge_node(node_id="B", label="B", node_type="test")
        db.write_knowledge_edge(
            source_id="A",
            target_id="B",
            relation="related_to",
            weight=0.8,
        )
        conn = db._get_conn()
        edges = conn.execute(
            "SELECT * FROM knowledge_edges WHERE source_id = ?", ("A",)
        ).fetchall()
        assert len(edges) == 1
        assert edges[0]["relation"] == "related_to"
        db.close()


# ---------------------------------------------------------------------------
# Stats / dashboard
# ---------------------------------------------------------------------------

def test_ledger_stats():
    with tempfile.TemporaryDirectory() as tmp:
        db = _make_db(tmp)
        _write_fact(db, title="Stat fact 1")
        _write_fact(db, title="Stat fact 2")
        db.write_ledger_entry(
            entry_type="DECISION",
            title="Stat decision",
            summary="A decision",
            source="test",
            author_agent="test",
            evidence_count=2,
            confidence="MEDIUM",
        )
        stats = db.get_ledger_stats()
        assert stats["total_entries"] == 3
        assert stats["by_type"].get("FACT", 0) == 2
        assert stats["by_type"].get("DECISION", 0) == 1
        db.close()


# ---------------------------------------------------------------------------
# Entry types (Synthesis Ledger types)
# ---------------------------------------------------------------------------

def test_all_entry_types_writable():
    with tempfile.TemporaryDirectory() as tmp:
        db = _make_db(tmp)
        for entry_type in ["FACT", "DECISION", "CONTRADICTION", "POLICY", "TASK"]:
            result = db.write_ledger_entry(
                entry_type=entry_type,
                title=f"Test {entry_type}",
                summary=f"A {entry_type.lower()} entry",
                source="test",
                author_agent="test",
                evidence_count=1,
            )
            assert result["status"] == "ACCEPTED", f"Failed for {entry_type}"
        stats = db.get_ledger_stats()
        assert stats["total_entries"] == 5
        db.close()


# ---------------------------------------------------------------------------
# Compatibility layer
# ---------------------------------------------------------------------------

def test_sqlite_zero_point_compat():
    """Test SQLiteZeroPoint subclass works end-to-end."""
    with tempfile.TemporaryDirectory() as tmp:
        db_path = os.path.join(tmp, "compat_test.db")
        from core.synthesis_db_compat import SQLiteZeroPoint
        from memory.zero_point import MemoryType, ConfidenceLevel

        zp = SQLiteZeroPoint(storage_path=os.path.join(tmp, "zp.json"), db_path=db_path)
        result = zp.write(
            content="Compatibility test entry",
            memory_type=MemoryType.FACT,
            tags=["compat", "test"],
            source="unit_test",
            author_agent="test_agent",
            confidence=ConfidenceLevel.LOW,
            evidence_count=1,
        )
        assert result["status"] == "ACCEPTED"

        # Verify it's in SQLite
        from core.synthesis_db import SynthesisDB
        db = SynthesisDB(db_path=db_path)
        entries = db.search_zero_point()
        assert len(entries) >= 1
        db.close()


def test_sqlite_episodic_compat():
    """Test SQLiteEpisodicMemory dual-write."""
    with tempfile.TemporaryDirectory() as tmp:
        db_path = os.path.join(tmp, "compat_ep.db")
        from core.synthesis_db_compat import SQLiteEpisodicMemory

        mem = SQLiteEpisodicMemory(memory_dir=tmp, db_path=db_path)
        entry = {
            "task_id": "compat_001",
            "timestamp": "2026-03-08T00:00:00Z",
            "risk_tier": "LOW",
            "canon_checks": {"consulted": True},
            "governance": {"stage": "EXECUTE"},
            "inputs": {"goal": "test"},
            "outputs": {"result": "pass"},
            "agents_involved": ["test"],
            "duration_seconds": 1.0,
        }
        log_path = mem.write_entry(entry)
        assert Path(log_path).exists()

        # Verify in SQLite
        from core.synthesis_db import SynthesisDB
        db = SynthesisDB(db_path=db_path)
        conn = db._get_conn()
        rows = conn.execute(
            "SELECT * FROM episodic_log WHERE task_id = ?", ("compat_001",)
        ).fetchall()
        assert len(rows) >= 1
        db.close()


def test_factory_returns_correct_type():
    """Test factory functions respect PERMANENCE_USE_SQLITE env."""
    from core.synthesis_db_compat import get_zero_point, get_episodic_memory, SQLiteZeroPoint, SQLiteEpisodicMemory
    from memory.zero_point import ZeroPoint
    from core.memory import EpisodicMemory

    # Default: flat-file
    old_val = os.environ.pop("PERMANENCE_USE_SQLITE", None)
    try:
        zp = get_zero_point()
        assert isinstance(zp, ZeroPoint)
        assert not isinstance(zp, SQLiteZeroPoint)

        ep = get_episodic_memory()
        assert isinstance(ep, EpisodicMemory)
        assert not isinstance(ep, SQLiteEpisodicMemory)
    finally:
        if old_val is not None:
            os.environ["PERMANENCE_USE_SQLITE"] = old_val


def test_factory_returns_sqlite_when_enabled():
    """Test factory functions return SQLite types when env is set."""
    from core.synthesis_db_compat import get_zero_point, get_episodic_memory, SQLiteZeroPoint, SQLiteEpisodicMemory

    old_val = os.environ.get("PERMANENCE_USE_SQLITE")
    os.environ["PERMANENCE_USE_SQLITE"] = "1"
    try:
        with tempfile.TemporaryDirectory() as tmp:
            zp = get_zero_point(storage_path=os.path.join(tmp, "zp.json"))
            assert isinstance(zp, SQLiteZeroPoint)

            ep = get_episodic_memory(memory_dir=tmp)
            assert isinstance(ep, SQLiteEpisodicMemory)
    finally:
        if old_val is None:
            os.environ.pop("PERMANENCE_USE_SQLITE", None)
        else:
            os.environ["PERMANENCE_USE_SQLITE"] = old_val
