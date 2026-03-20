"""
Permanence OS -- Entity Graph Engine (v0.1)

SQLite-backed entity graph that connects everything across all surfaces.
This is the hidden data layer: entities (people, tasks, documents, agents)
and the relationships between them.

Design:
  - 60/30/10 rule: 60% deterministic SQLite ops, 30% rule-based filtering,
    10% reserved for future AI-powered inference
  - All writes include provenance (created_by)
  - JSON properties for flexible schema extension
  - Full-text search across titles and properties
  - Graph traversal up to configurable depth

Invariants:
  - No entity without a type and title
  - No relationship without valid source and target
  - All dates are ISO 8601 UTC
  - Properties are always valid JSON
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ENTITY_TYPES = frozenset({
    "USER", "AGENT", "CONTACT", "COMPANY", "NOTE", "DOCUMENT",
    "TASK", "REMINDER", "APPROVAL", "DECISION", "MISSION",
    "TICKER", "STRATEGY", "POSITION", "PORTFOLIO", "MEMORY", "CANON",
})

RELATIONSHIP_TYPES = frozenset({
    "LINKED_TO", "CREATED_FROM", "ASSIGNED_TO", "ABOUT",
    "REQUIRES_APPROVAL", "GENERATED_BY", "DERIVED_INTO",
    "BELONGS_TO", "INFORMS",
})

VALID_STATUSES = frozenset({"active", "archived", "deleted", "pending"})

SCHEMA_VERSION = 1


def _now_iso() -> str:
    """Current UTC time as ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


def _gen_id() -> str:
    """Generate a 12-character hex ID."""
    return uuid.uuid4().hex[:12]


def _validate_entity_type(entity_type: str) -> str:
    """Validate and normalize entity type."""
    normalized = entity_type.upper()
    if normalized not in ENTITY_TYPES:
        raise ValueError(
            f"Invalid entity type '{entity_type}'. "
            f"Must be one of: {sorted(ENTITY_TYPES)}"
        )
    return normalized


def _validate_relationship(relationship: str) -> str:
    """Validate and normalize relationship type."""
    normalized = relationship.upper()
    if normalized not in RELATIONSHIP_TYPES:
        raise ValueError(
            f"Invalid relationship '{relationship}'. "
            f"Must be one of: {sorted(RELATIONSHIP_TYPES)}"
        )
    return normalized


def _validate_properties(properties: Any) -> str:
    """Validate properties and return JSON string."""
    if properties is None:
        return "{}"
    if not isinstance(properties, dict):
        raise ValueError("Properties must be a dict")
    return json.dumps(properties)


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS entities (
    id TEXT PRIMARY KEY,
    entity_type TEXT NOT NULL,
    title TEXT NOT NULL,
    status TEXT DEFAULT 'active',
    properties TEXT DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    created_by TEXT DEFAULT 'user'
);

CREATE TABLE IF NOT EXISTS relationships (
    id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL,
    target_id TEXT NOT NULL,
    relationship TEXT NOT NULL,
    properties TEXT DEFAULT '{}',
    created_at TEXT NOT NULL,
    FOREIGN KEY (source_id) REFERENCES entities(id),
    FOREIGN KEY (target_id) REFERENCES entities(id)
);

CREATE INDEX IF NOT EXISTS idx_entities_type ON entities(entity_type);
CREATE INDEX IF NOT EXISTS idx_entities_title ON entities(title);
CREATE INDEX IF NOT EXISTS idx_entities_status ON entities(status);
CREATE INDEX IF NOT EXISTS idx_relationships_source ON relationships(source_id);
CREATE INDEX IF NOT EXISTS idx_relationships_target ON relationships(target_id);
CREATE INDEX IF NOT EXISTS idx_relationships_type ON relationships(relationship);
"""


# ---------------------------------------------------------------------------
# EntityGraph
# ---------------------------------------------------------------------------

class EntityGraph:
    """SQLite-backed entity graph engine."""

    def __init__(self, db_path: str = "permanence_storage/entity_graph.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        """Initialize database and create tables if needed."""
        try:
            import os
            os.makedirs(os.path.dirname(self.db_path) or ".", exist_ok=True)
            conn = sqlite3.connect(self.db_path)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
            conn.executescript(_SCHEMA_SQL)
            conn.commit()
            conn.close()
        except sqlite3.Error as e:
            raise RuntimeError(f"Failed to initialize entity graph database: {e}")

    def _connect(self) -> sqlite3.Connection:
        """Get a database connection with row factory."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    # -- Entity CRUD --------------------------------------------------------

    def create_entity(
        self,
        entity_type: str,
        title: str,
        properties: Optional[dict] = None,
        created_by: str = "user",
    ) -> dict:
        """Create a new entity and return it as a dict."""
        entity_type = _validate_entity_type(entity_type)
        props_json = _validate_properties(properties)

        if not title or not title.strip():
            raise ValueError("Entity title cannot be empty")

        entity_id = _gen_id()
        now = _now_iso()

        try:
            conn = self._connect()
            conn.execute(
                """INSERT INTO entities (id, entity_type, title, status, properties, created_at, updated_at, created_by)
                   VALUES (?, ?, ?, 'active', ?, ?, ?, ?)""",
                (entity_id, entity_type, title.strip(), props_json, now, now, created_by),
            )
            conn.commit()
            conn.close()
        except sqlite3.Error as e:
            raise RuntimeError(f"Failed to create entity: {e}")

        return {
            "id": entity_id,
            "entity_type": entity_type,
            "title": title.strip(),
            "status": "active",
            "properties": properties or {},
            "created_at": now,
            "updated_at": now,
            "created_by": created_by,
        }

    def get_entity(self, entity_id: str) -> Optional[dict]:
        """Get an entity by ID. Returns None if not found."""
        try:
            conn = self._connect()
            row = conn.execute(
                "SELECT * FROM entities WHERE id = ?", (entity_id,)
            ).fetchone()
            conn.close()
        except sqlite3.Error as e:
            raise RuntimeError(f"Failed to get entity: {e}")

        if row is None:
            return None
        return self._row_to_entity(row)

    def update_entity(self, entity_id: str, updates: dict) -> Optional[dict]:
        """Update an entity. Returns updated entity or None if not found."""
        entity = self.get_entity(entity_id)
        if entity is None:
            return None

        allowed_fields = {"title", "status", "properties"}
        filtered = {k: v for k, v in updates.items() if k in allowed_fields}

        if not filtered:
            return entity

        if "title" in filtered:
            if not filtered["title"] or not str(filtered["title"]).strip():
                raise ValueError("Entity title cannot be empty")
            filtered["title"] = str(filtered["title"]).strip()

        if "status" in filtered:
            if filtered["status"] not in VALID_STATUSES:
                raise ValueError(
                    f"Invalid status '{filtered['status']}'. "
                    f"Must be one of: {sorted(VALID_STATUSES)}"
                )

        if "properties" in filtered:
            filtered["properties"] = _validate_properties(filtered["properties"])

        filtered["updated_at"] = _now_iso()

        set_clause = ", ".join(f"{k} = ?" for k in filtered)
        values = list(filtered.values()) + [entity_id]

        try:
            conn = self._connect()
            conn.execute(
                f"UPDATE entities SET {set_clause} WHERE id = ?",
                values,
            )
            conn.commit()
            conn.close()
        except sqlite3.Error as e:
            raise RuntimeError(f"Failed to update entity: {e}")

        return self.get_entity(entity_id)

    def delete_entity(self, entity_id: str) -> bool:
        """Delete an entity and all its relationships. Returns True if deleted."""
        try:
            conn = self._connect()
            # Remove relationships first
            conn.execute(
                "DELETE FROM relationships WHERE source_id = ? OR target_id = ?",
                (entity_id, entity_id),
            )
            cursor = conn.execute(
                "DELETE FROM entities WHERE id = ?", (entity_id,)
            )
            deleted = cursor.rowcount > 0
            conn.commit()
            conn.close()
            return deleted
        except sqlite3.Error as e:
            raise RuntimeError(f"Failed to delete entity: {e}")

    # -- Relationships ------------------------------------------------------

    def link(
        self,
        source_id: str,
        target_id: str,
        relationship: str,
        properties: Optional[dict] = None,
    ) -> dict:
        """Create a relationship between two entities."""
        relationship = _validate_relationship(relationship)
        props_json = _validate_properties(properties)

        # Validate both entities exist
        source = self.get_entity(source_id)
        target = self.get_entity(target_id)
        if source is None:
            raise ValueError(f"Source entity '{source_id}' not found")
        if target is None:
            raise ValueError(f"Target entity '{target_id}' not found")

        # Check for duplicate
        try:
            conn = self._connect()
            existing = conn.execute(
                """SELECT id FROM relationships
                   WHERE source_id = ? AND target_id = ? AND relationship = ?""",
                (source_id, target_id, relationship),
            ).fetchone()

            if existing:
                conn.close()
                return {
                    "id": existing["id"],
                    "source_id": source_id,
                    "target_id": target_id,
                    "relationship": relationship,
                    "properties": properties or {},
                    "created_at": None,
                    "duplicate": True,
                }

            rel_id = _gen_id()
            now = _now_iso()
            conn.execute(
                """INSERT INTO relationships (id, source_id, target_id, relationship, properties, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (rel_id, source_id, target_id, relationship, props_json, now),
            )
            conn.commit()
            conn.close()
        except sqlite3.Error as e:
            raise RuntimeError(f"Failed to create relationship: {e}")

        return {
            "id": rel_id,
            "source_id": source_id,
            "target_id": target_id,
            "relationship": relationship,
            "properties": properties or {},
            "created_at": now,
        }

    def unlink(
        self, source_id: str, target_id: str, relationship: Optional[str] = None
    ) -> bool:
        """Remove relationship(s) between two entities. Returns True if any removed."""
        try:
            conn = self._connect()
            if relationship:
                relationship = _validate_relationship(relationship)
                cursor = conn.execute(
                    """DELETE FROM relationships
                       WHERE source_id = ? AND target_id = ? AND relationship = ?""",
                    (source_id, target_id, relationship),
                )
            else:
                cursor = conn.execute(
                    """DELETE FROM relationships
                       WHERE source_id = ? AND target_id = ?""",
                    (source_id, target_id),
                )
            removed = cursor.rowcount > 0
            conn.commit()
            conn.close()
            return removed
        except sqlite3.Error as e:
            raise RuntimeError(f"Failed to unlink entities: {e}")

    def get_linked(
        self,
        entity_id: str,
        relationship: Optional[str] = None,
        entity_type: Optional[str] = None,
    ) -> list:
        """Get all entities linked to this one, optionally filtered."""
        try:
            conn = self._connect()

            # Get entities where this entity is the source
            query = """
                SELECT e.*, r.relationship AS rel_type, r.id AS rel_id,
                       'outgoing' AS direction
                FROM entities e
                JOIN relationships r ON e.id = r.target_id
                WHERE r.source_id = ?
            """
            params: list = [entity_id]

            if relationship:
                relationship = _validate_relationship(relationship)
                query += " AND r.relationship = ?"
                params.append(relationship)
            if entity_type:
                entity_type = _validate_entity_type(entity_type)
                query += " AND e.entity_type = ?"
                params.append(entity_type)

            # Also get entities where this entity is the target
            query2 = """
                SELECT e.*, r.relationship AS rel_type, r.id AS rel_id,
                       'incoming' AS direction
                FROM entities e
                JOIN relationships r ON e.id = r.source_id
                WHERE r.target_id = ?
            """
            params2: list = [entity_id]

            if relationship:
                query2 += " AND r.relationship = ?"
                params2.append(relationship)
            if entity_type:
                query2 += " AND e.entity_type = ?"
                params2.append(entity_type)

            rows = conn.execute(query, params).fetchall()
            rows2 = conn.execute(query2, params2).fetchall()
            conn.close()
        except sqlite3.Error as e:
            raise RuntimeError(f"Failed to get linked entities: {e}")

        results = []
        seen_ids = set()
        for row in list(rows) + list(rows2):
            entity = self._row_to_entity(row)
            entity["relationship"] = row["rel_type"]
            entity["direction"] = row["direction"]
            # Deduplicate by entity id + relationship
            key = (entity["id"], row["rel_type"], row["direction"])
            if key not in seen_ids:
                seen_ids.add(key)
                results.append(entity)

        return results

    # -- Search and Query ---------------------------------------------------

    def search(
        self, query: str, entity_type: Optional[str] = None, limit: int = 20
    ) -> list:
        """Full-text search across entity titles and properties."""
        if not query or not query.strip():
            return []

        search_term = f"%{query.strip()}%"

        try:
            conn = self._connect()
            sql = """
                SELECT * FROM entities
                WHERE (title LIKE ? OR properties LIKE ?)
                AND status != 'deleted'
            """
            params: list = [search_term, search_term]

            if entity_type:
                entity_type = _validate_entity_type(entity_type)
                sql += " AND entity_type = ?"
                params.append(entity_type)

            sql += " ORDER BY updated_at DESC LIMIT ?"
            params.append(limit)

            rows = conn.execute(sql, params).fetchall()
            conn.close()
        except sqlite3.Error as e:
            raise RuntimeError(f"Search failed: {e}")

        return [self._row_to_entity(row) for row in rows]

    def query(self, filters: dict) -> list:
        """Structured query with filters: entity_type, status, created_by."""
        conditions = []
        params: list = []

        if "entity_type" in filters:
            entity_type = _validate_entity_type(filters["entity_type"])
            conditions.append("entity_type = ?")
            params.append(entity_type)

        if "status" in filters:
            conditions.append("status = ?")
            params.append(filters["status"])

        if "created_by" in filters:
            conditions.append("created_by = ?")
            params.append(filters["created_by"])

        where = " AND ".join(conditions) if conditions else "1=1"

        try:
            conn = self._connect()
            rows = conn.execute(
                f"SELECT * FROM entities WHERE {where} ORDER BY updated_at DESC",
                params,
            ).fetchall()
            conn.close()
        except sqlite3.Error as e:
            raise RuntimeError(f"Query failed: {e}")

        return [self._row_to_entity(row) for row in rows]

    # -- Graph Traversal ----------------------------------------------------

    def get_graph_around(self, entity_id: str, depth: int = 1) -> Optional[dict]:
        """Return entity + all linked entities up to N depth."""
        center = self.get_entity(entity_id)
        if center is None:
            return None

        nodes = {entity_id: center}
        edges = []
        frontier = {entity_id}

        for _ in range(depth):
            next_frontier = set()
            for node_id in frontier:
                try:
                    conn = self._connect()
                    # Outgoing
                    out_rows = conn.execute(
                        """SELECT r.id AS rel_id, r.source_id, r.target_id,
                                  r.relationship, r.properties AS rel_props
                           FROM relationships r WHERE r.source_id = ?""",
                        (node_id,),
                    ).fetchall()
                    # Incoming
                    in_rows = conn.execute(
                        """SELECT r.id AS rel_id, r.source_id, r.target_id,
                                  r.relationship, r.properties AS rel_props
                           FROM relationships r WHERE r.target_id = ?""",
                        (node_id,),
                    ).fetchall()
                    conn.close()
                except sqlite3.Error as e:
                    raise RuntimeError(f"Graph traversal failed: {e}")

                for row in list(out_rows) + list(in_rows):
                    edge = {
                        "id": row["rel_id"],
                        "source_id": row["source_id"],
                        "target_id": row["target_id"],
                        "relationship": row["relationship"],
                        "properties": json.loads(row["rel_props"] or "{}"),
                    }
                    # Avoid duplicate edges
                    if not any(e["id"] == edge["id"] for e in edges):
                        edges.append(edge)

                    # Add neighbor to nodes
                    neighbor_id = (
                        row["target_id"]
                        if row["source_id"] == node_id
                        else row["source_id"]
                    )
                    if neighbor_id not in nodes:
                        neighbor = self.get_entity(neighbor_id)
                        if neighbor:
                            nodes[neighbor_id] = neighbor
                            next_frontier.add(neighbor_id)

            frontier = next_frontier

        return {
            "center": center,
            "nodes": list(nodes.values()),
            "edges": edges,
        }

    # -- Stats --------------------------------------------------------------

    def stats(self) -> dict:
        """Return counts by entity type and relationship type."""
        try:
            conn = self._connect()
            entity_rows = conn.execute(
                "SELECT entity_type, COUNT(*) as cnt FROM entities GROUP BY entity_type"
            ).fetchall()
            rel_rows = conn.execute(
                "SELECT relationship, COUNT(*) as cnt FROM relationships GROUP BY relationship"
            ).fetchall()
            total_entities = conn.execute(
                "SELECT COUNT(*) as cnt FROM entities"
            ).fetchone()["cnt"]
            total_rels = conn.execute(
                "SELECT COUNT(*) as cnt FROM relationships"
            ).fetchone()["cnt"]
            conn.close()
        except sqlite3.Error as e:
            raise RuntimeError(f"Failed to get stats: {e}")

        return {
            "total_entities": total_entities,
            "total_relationships": total_rels,
            "entities_by_type": {row["entity_type"]: row["cnt"] for row in entity_rows},
            "relationships_by_type": {row["relationship"]: row["cnt"] for row in rel_rows},
        }

    # -- Helpers ------------------------------------------------------------

    @staticmethod
    def _row_to_entity(row: sqlite3.Row) -> dict:
        """Convert a database row to an entity dict."""
        return {
            "id": row["id"],
            "entity_type": row["entity_type"],
            "title": row["title"],
            "status": row["status"],
            "properties": json.loads(row["properties"] or "{}"),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "created_by": row["created_by"],
        }
