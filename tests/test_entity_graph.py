#!/usr/bin/env python3
"""Tests for the Entity Graph engine (core/entity_graph.py)."""

import json
import os
import sys

import pytest

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, BASE_DIR)

from core.entity_graph import (
    EntityGraph,
    ENTITY_TYPES,
    RELATIONSHIP_TYPES,
    _validate_entity_type,
    _validate_relationship,
    _validate_properties,
)


# -- Fixtures ---------------------------------------------------------------

@pytest.fixture
def graph(tmp_path):
    """Fresh EntityGraph backed by a temporary database."""
    db_path = str(tmp_path / "test_entity_graph.db")
    return EntityGraph(db_path=db_path)


@pytest.fixture
def populated_graph(graph):
    """Graph with a few pre-created entities."""
    graph.create_entity("TASK", "Build dashboard", {"priority": "high"})
    graph.create_entity("AGENT", "Sentinel", {"role": "guardian"})
    graph.create_entity("DOCUMENT", "Design spec", {"format": "md"})
    graph.create_entity("USER", "Payton")
    return graph


# -- TestEntityCRUD ---------------------------------------------------------

class TestEntityCRUD:
    def test_create_entity(self, graph):
        entity = graph.create_entity("TASK", "Test task")
        assert entity["entity_type"] == "TASK"
        assert entity["title"] == "Test task"
        assert entity["status"] == "active"
        assert len(entity["id"]) == 12
        assert entity["created_by"] == "user"

    def test_create_entity_with_properties(self, graph):
        props = {"priority": "high", "tags": ["urgent"]}
        entity = graph.create_entity("NOTE", "Meeting notes", properties=props)
        assert entity["properties"]["priority"] == "high"
        assert "urgent" in entity["properties"]["tags"]

    def test_create_entity_with_creator(self, graph):
        entity = graph.create_entity("TASK", "Agent task", created_by="orchestrator")
        assert entity["created_by"] == "orchestrator"

    def test_create_entity_strips_whitespace(self, graph):
        entity = graph.create_entity("TASK", "  padded title  ")
        assert entity["title"] == "padded title"

    def test_get_entity(self, graph):
        created = graph.create_entity("AGENT", "Sentinel")
        fetched = graph.get_entity(created["id"])
        assert fetched is not None
        assert fetched["id"] == created["id"]
        assert fetched["title"] == "Sentinel"

    def test_get_nonexistent_entity(self, graph):
        result = graph.get_entity("doesnotexist")
        assert result is None

    def test_update_entity_title(self, graph):
        entity = graph.create_entity("TASK", "Old title")
        updated = graph.update_entity(entity["id"], {"title": "New title"})
        assert updated["title"] == "New title"
        assert updated["updated_at"] >= entity["created_at"]

    def test_update_entity_status(self, graph):
        entity = graph.create_entity("TASK", "Some task")
        updated = graph.update_entity(entity["id"], {"status": "archived"})
        assert updated["status"] == "archived"

    def test_update_entity_properties(self, graph):
        entity = graph.create_entity("NOTE", "Note", {"key": "old"})
        updated = graph.update_entity(entity["id"], {"properties": {"key": "new"}})
        assert updated["properties"]["key"] == "new"

    def test_update_nonexistent_entity(self, graph):
        result = graph.update_entity("nonexistent", {"title": "Nope"})
        assert result is None

    def test_delete_entity(self, graph):
        entity = graph.create_entity("TASK", "To delete")
        assert graph.delete_entity(entity["id"]) is True
        assert graph.get_entity(entity["id"]) is None

    def test_delete_nonexistent_entity(self, graph):
        assert graph.delete_entity("nonexistent") is False

    def test_create_entity_invalid_type(self, graph):
        with pytest.raises(ValueError, match="Invalid entity type"):
            graph.create_entity("INVALID_TYPE", "Bad entity")

    def test_create_entity_empty_title(self, graph):
        with pytest.raises(ValueError, match="title cannot be empty"):
            graph.create_entity("TASK", "")

    def test_create_entity_whitespace_title(self, graph):
        with pytest.raises(ValueError, match="title cannot be empty"):
            graph.create_entity("TASK", "   ")


# -- TestRelationships ------------------------------------------------------

class TestRelationships:
    def test_link_entities(self, graph):
        e1 = graph.create_entity("TASK", "Task A")
        e2 = graph.create_entity("AGENT", "Agent B")
        rel = graph.link(e1["id"], e2["id"], "ASSIGNED_TO")
        assert rel["source_id"] == e1["id"]
        assert rel["target_id"] == e2["id"]
        assert rel["relationship"] == "ASSIGNED_TO"

    def test_link_with_properties(self, graph):
        e1 = graph.create_entity("TASK", "Task")
        e2 = graph.create_entity("USER", "User")
        rel = graph.link(e1["id"], e2["id"], "ASSIGNED_TO", {"role": "reviewer"})
        assert rel["properties"]["role"] == "reviewer"

    def test_unlink_entities(self, graph):
        e1 = graph.create_entity("TASK", "Task")
        e2 = graph.create_entity("USER", "User")
        graph.link(e1["id"], e2["id"], "ASSIGNED_TO")
        assert graph.unlink(e1["id"], e2["id"], "ASSIGNED_TO") is True

    def test_unlink_all_relationships(self, graph):
        e1 = graph.create_entity("TASK", "Task")
        e2 = graph.create_entity("USER", "User")
        graph.link(e1["id"], e2["id"], "ASSIGNED_TO")
        graph.link(e1["id"], e2["id"], "ABOUT")
        assert graph.unlink(e1["id"], e2["id"]) is True

    def test_unlink_nonexistent(self, graph):
        assert graph.unlink("a", "b", "LINKED_TO") is False

    def test_get_linked(self, graph):
        e1 = graph.create_entity("TASK", "Task")
        e2 = graph.create_entity("AGENT", "Agent")
        graph.link(e1["id"], e2["id"], "ASSIGNED_TO")
        linked = graph.get_linked(e1["id"])
        assert len(linked) == 1
        assert linked[0]["id"] == e2["id"]

    def test_get_linked_bidirectional(self, graph):
        e1 = graph.create_entity("TASK", "Task")
        e2 = graph.create_entity("AGENT", "Agent")
        graph.link(e1["id"], e2["id"], "ASSIGNED_TO")
        # e2 should see e1 as incoming
        linked_from_e2 = graph.get_linked(e2["id"])
        assert len(linked_from_e2) == 1
        assert linked_from_e2[0]["id"] == e1["id"]

    def test_get_linked_filtered_by_relationship(self, graph):
        e1 = graph.create_entity("TASK", "Task")
        e2 = graph.create_entity("AGENT", "Agent")
        e3 = graph.create_entity("USER", "User")
        graph.link(e1["id"], e2["id"], "ASSIGNED_TO")
        graph.link(e1["id"], e3["id"], "ABOUT")
        linked = graph.get_linked(e1["id"], relationship="ASSIGNED_TO")
        assert len(linked) == 1
        assert linked[0]["id"] == e2["id"]

    def test_get_linked_filtered_by_type(self, graph):
        e1 = graph.create_entity("TASK", "Task")
        e2 = graph.create_entity("AGENT", "Agent")
        e3 = graph.create_entity("USER", "User")
        graph.link(e1["id"], e2["id"], "ASSIGNED_TO")
        graph.link(e1["id"], e3["id"], "ASSIGNED_TO")
        linked = graph.get_linked(e1["id"], entity_type="AGENT")
        assert len(linked) == 1
        assert linked[0]["entity_type"] == "AGENT"

    def test_link_invalid_relationship(self, graph):
        e1 = graph.create_entity("TASK", "Task")
        e2 = graph.create_entity("USER", "User")
        with pytest.raises(ValueError, match="Invalid relationship"):
            graph.link(e1["id"], e2["id"], "FAKE_REL")

    def test_link_nonexistent_source(self, graph):
        e2 = graph.create_entity("USER", "User")
        with pytest.raises(ValueError, match="Source entity"):
            graph.link("nonexistent", e2["id"], "LINKED_TO")

    def test_link_nonexistent_target(self, graph):
        e1 = graph.create_entity("TASK", "Task")
        with pytest.raises(ValueError, match="Target entity"):
            graph.link(e1["id"], "nonexistent", "LINKED_TO")


# -- TestSearch --------------------------------------------------------------

class TestSearch:
    def test_search_by_title(self, populated_graph):
        results = populated_graph.search("dashboard")
        assert len(results) == 1
        assert results[0]["title"] == "Build dashboard"

    def test_search_by_property(self, populated_graph):
        results = populated_graph.search("guardian")
        assert len(results) == 1
        assert results[0]["title"] == "Sentinel"

    def test_search_by_type(self, populated_graph):
        results = populated_graph.search("Sentinel", entity_type="AGENT")
        assert len(results) == 1

    def test_search_no_results(self, populated_graph):
        results = populated_graph.search("nonexistent_xyz_123")
        assert len(results) == 0

    def test_search_empty_query(self, populated_graph):
        results = populated_graph.search("")
        assert len(results) == 0

    def test_search_limit(self, graph):
        for i in range(10):
            graph.create_entity("TASK", f"Task {i}")
        results = graph.search("Task", limit=3)
        assert len(results) == 3

    def test_search_excludes_deleted(self, graph):
        entity = graph.create_entity("TASK", "Deleted task")
        graph.update_entity(entity["id"], {"status": "deleted"})
        results = graph.search("Deleted task")
        assert len(results) == 0


# -- TestQuery ---------------------------------------------------------------

class TestQuery:
    def test_query_by_type(self, populated_graph):
        results = populated_graph.query({"entity_type": "TASK"})
        assert len(results) == 1
        assert results[0]["entity_type"] == "TASK"

    def test_query_by_status(self, graph):
        graph.create_entity("TASK", "Active task")
        e2 = graph.create_entity("TASK", "Archived task")
        graph.update_entity(e2["id"], {"status": "archived"})
        results = graph.query({"status": "archived"})
        assert len(results) == 1

    def test_query_combined(self, graph):
        graph.create_entity("TASK", "Task A", created_by="agent")
        graph.create_entity("TASK", "Task B", created_by="user")
        graph.create_entity("NOTE", "Note C", created_by="agent")
        results = graph.query({"entity_type": "TASK", "created_by": "agent"})
        assert len(results) == 1
        assert results[0]["title"] == "Task A"

    def test_query_empty_filters(self, populated_graph):
        results = populated_graph.query({})
        assert len(results) == 4  # All entities in populated_graph

    def test_query_no_results(self, graph):
        results = graph.query({"entity_type": "PORTFOLIO"})
        assert len(results) == 0


# -- TestGraph ---------------------------------------------------------------

class TestGraph:
    def test_get_graph_depth_1(self, graph):
        e1 = graph.create_entity("TASK", "Center task")
        e2 = graph.create_entity("AGENT", "Linked agent")
        graph.link(e1["id"], e2["id"], "ASSIGNED_TO")
        result = graph.get_graph_around(e1["id"], depth=1)
        assert result["center"]["id"] == e1["id"]
        assert len(result["nodes"]) == 2
        assert len(result["edges"]) == 1

    def test_get_graph_depth_2(self, graph):
        e1 = graph.create_entity("TASK", "Center")
        e2 = graph.create_entity("AGENT", "Level 1")
        e3 = graph.create_entity("USER", "Level 2")
        graph.link(e1["id"], e2["id"], "ASSIGNED_TO")
        graph.link(e2["id"], e3["id"], "BELONGS_TO")
        result = graph.get_graph_around(e1["id"], depth=2)
        assert len(result["nodes"]) == 3
        assert len(result["edges"]) == 2

    def test_get_graph_depth_2_stops_at_1(self, graph):
        e1 = graph.create_entity("TASK", "Center")
        e2 = graph.create_entity("AGENT", "Level 1")
        e3 = graph.create_entity("USER", "Level 2")
        graph.link(e1["id"], e2["id"], "ASSIGNED_TO")
        graph.link(e2["id"], e3["id"], "BELONGS_TO")
        result = graph.get_graph_around(e1["id"], depth=1)
        assert len(result["nodes"]) == 2  # Only center + level 1

    def test_get_graph_isolated(self, graph):
        e1 = graph.create_entity("TASK", "Isolated")
        result = graph.get_graph_around(e1["id"])
        assert len(result["nodes"]) == 1
        assert len(result["edges"]) == 0

    def test_get_graph_nonexistent(self, graph):
        result = graph.get_graph_around("nonexistent")
        assert result is None


# -- TestStats ---------------------------------------------------------------

class TestStats:
    def test_stats_empty(self, graph):
        s = graph.stats()
        assert s["total_entities"] == 0
        assert s["total_relationships"] == 0
        assert s["entities_by_type"] == {}
        assert s["relationships_by_type"] == {}

    def test_stats_with_data(self, graph):
        e1 = graph.create_entity("TASK", "Task 1")
        e2 = graph.create_entity("TASK", "Task 2")
        e3 = graph.create_entity("AGENT", "Agent 1")
        graph.link(e1["id"], e3["id"], "ASSIGNED_TO")
        graph.link(e2["id"], e3["id"], "ASSIGNED_TO")
        s = graph.stats()
        assert s["total_entities"] == 3
        assert s["total_relationships"] == 2
        assert s["entities_by_type"]["TASK"] == 2
        assert s["entities_by_type"]["AGENT"] == 1
        assert s["relationships_by_type"]["ASSIGNED_TO"] == 2


# -- TestEdgeCases -----------------------------------------------------------

class TestEdgeCases:
    def test_duplicate_link(self, graph):
        e1 = graph.create_entity("TASK", "Task")
        e2 = graph.create_entity("USER", "User")
        rel1 = graph.link(e1["id"], e2["id"], "ASSIGNED_TO")
        rel2 = graph.link(e1["id"], e2["id"], "ASSIGNED_TO")
        assert rel2.get("duplicate") is True
        assert rel2["id"] == rel1["id"]

    def test_self_link(self, graph):
        e1 = graph.create_entity("TASK", "Self-referencing")
        rel = graph.link(e1["id"], e1["id"], "LINKED_TO")
        assert rel["source_id"] == rel["target_id"]

    def test_delete_with_relationships(self, graph):
        e1 = graph.create_entity("TASK", "Task")
        e2 = graph.create_entity("AGENT", "Agent")
        graph.link(e1["id"], e2["id"], "ASSIGNED_TO")
        graph.delete_entity(e1["id"])
        # e2 should have no linked entities
        linked = graph.get_linked(e2["id"])
        assert len(linked) == 0

    def test_invalid_type_validation(self):
        with pytest.raises(ValueError):
            _validate_entity_type("BOGUS")

    def test_invalid_relationship_validation(self):
        with pytest.raises(ValueError):
            _validate_relationship("BOGUS")

    def test_invalid_properties(self):
        with pytest.raises(ValueError):
            _validate_properties("not a dict")

    def test_update_invalid_status(self, graph):
        entity = graph.create_entity("TASK", "Task")
        with pytest.raises(ValueError, match="Invalid status"):
            graph.update_entity(entity["id"], {"status": "bogus_status"})

    def test_entity_types_constant(self):
        assert "TASK" in ENTITY_TYPES
        assert "AGENT" in ENTITY_TYPES
        assert "USER" in ENTITY_TYPES
        assert len(ENTITY_TYPES) == 19

    def test_relationship_types_constant(self):
        assert "LINKED_TO" in RELATIONSHIP_TYPES
        assert "ASSIGNED_TO" in RELATIONSHIP_TYPES
        assert len(RELATIONSHIP_TYPES) == 11
