"""
Tests for core.agent_bus -- the central nervous system for Permanence OS agents.

Covers: registration, graph access, search, inbox push, event system,
approval workflow, audit logging, autonomy levels, cross-surface queries,
memory read/write, status management, singleton behavior.
"""

import json
import os
import shutil
import tempfile
import threading
import pytest

from core.agent_bus import (
    AgentBus,
    AgentRecord,
    ApprovalItem,
    AutonomyLevel,
    ALWAYS_APPROVE_ACTIONS,
    SURFACE_NAMES,
    get_bus,
    reset_bus,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_dir():
    """Create a temporary directory that mimics the project layout."""
    d = tempfile.mkdtemp(prefix="agent_bus_test_")
    os.makedirs(os.path.join(d, "permanence_storage"), exist_ok=True)
    os.makedirs(os.path.join(d, "memory", "inbox"), exist_ok=True)
    # Create a minimal canon/dna.yaml so EntityGraph can init
    yield d
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def bus(tmp_dir):
    """Fresh AgentBus wired to a temp directory."""
    return AgentBus(base_dir=tmp_dir)


@pytest.fixture(autouse=True)
def reset_singleton():
    """Reset the global singleton between tests."""
    reset_bus()
    yield
    reset_bus()


# ---------------------------------------------------------------------------
# 1. Registration
# ---------------------------------------------------------------------------

class TestRegistration:

    def test_register_agent(self, bus):
        result = bus.register("sentinel", ["governance"], "EXPLICIT_APPROVAL")
        assert result["name"] == "sentinel"
        assert result["autonomy_level"] == "EXPLICIT_APPROVAL"
        assert result["capabilities"] == ["governance"]
        assert result["status"] == "idle"

    def test_register_multiple_agents(self, bus):
        bus.register("sentinel", ["governance"], "EXPLICIT_APPROVAL")
        bus.register("orchestrator", ["coordination"], "SOFT_APPROVAL")
        agents = bus.list_agents()
        assert len(agents) == 2
        names = {a["name"] for a in agents}
        assert names == {"sentinel", "orchestrator"}

    def test_register_invalid_autonomy_level(self, bus):
        with pytest.raises(ValueError, match="Invalid autonomy level"):
            bus.register("bad_agent", [], "INVALID_LEVEL")

    def test_get_agent_not_found(self, bus):
        assert bus.get_agent("nonexistent") is None

    def test_get_registered_agent(self, bus):
        bus.register("risk_manager", ["risk"], "FULL_AUTO")
        agent = bus.get_agent("risk_manager")
        assert agent is not None
        assert agent["name"] == "risk_manager"

    def test_register_overwrites_existing(self, bus):
        bus.register("sentinel", ["gov"], "EXPLICIT_APPROVAL")
        bus.register("sentinel", ["gov", "audit"], "SOFT_APPROVAL")
        agent = bus.get_agent("sentinel")
        assert agent["autonomy_level"] == "SOFT_APPROVAL"
        assert agent["capabilities"] == ["gov", "audit"]


# ---------------------------------------------------------------------------
# 2. Graph Access
# ---------------------------------------------------------------------------

class TestGraphAccess:

    def test_graph_property_returns_entity_graph(self, bus):
        graph = bus.graph
        assert graph is not None
        assert hasattr(graph, "create_entity")
        assert hasattr(graph, "search")

    def test_graph_singleton_same_instance(self, bus):
        g1 = bus.graph
        g2 = bus.graph
        assert g1 is g2

    def test_create_entity_via_graph(self, bus):
        entity = bus.graph.create_entity("TASK", "Test task", created_by="test")
        assert entity["title"] == "Test task"
        assert entity["entity_type"] == "TASK"

    def test_link_entities_via_graph(self, bus):
        e1 = bus.graph.create_entity("AGENT", "Sentinel", created_by="test")
        e2 = bus.graph.create_entity("TASK", "Review", created_by="test")
        rel = bus.graph.link(e1["id"], e2["id"], "ASSIGNED_TO")
        assert rel["relationship"] == "ASSIGNED_TO"


# ---------------------------------------------------------------------------
# 3. Search
# ---------------------------------------------------------------------------

class TestSearch:

    def test_search_returns_results(self, bus):
        bus.graph.create_entity("NOTE", "Alpha research notes", created_by="test")
        bus.graph.create_entity("NOTE", "Beta analysis", created_by="test")
        results = bus.search("Alpha")
        assert len(results) >= 1
        assert any("Alpha" in r["title"] for r in results)

    def test_search_empty_query(self, bus):
        results = bus.search("")
        assert results == []

    def test_search_with_type_filter(self, bus):
        bus.graph.create_entity("NOTE", "Research on AI", created_by="test")
        bus.graph.create_entity("TASK", "Research todo", created_by="test")
        results = bus.search("Research", entity_type="NOTE")
        assert all(r["entity_type"] == "NOTE" for r in results)


# ---------------------------------------------------------------------------
# 4. Inbox Push
# ---------------------------------------------------------------------------

class TestInboxPush:

    def test_inbox_push_returns_enriched_item(self, bus):
        item = bus.inbox_push({"title": "New alert", "source": "sentinel"})
        assert "id" in item
        assert "timestamp" in item
        assert item["read"] is False
        assert item["title"] == "New alert"

    def test_inbox_push_appears_in_list(self, bus):
        bus.inbox_push({"title": "Item 1", "source": "test"})
        bus.inbox_push({"title": "Item 2", "source": "test"})
        items = bus.inbox_list()
        assert len(items) == 2

    def test_inbox_unread_filter(self, bus):
        bus.inbox_push({"title": "Unread", "source": "test"})
        # Manually mark one as read
        inbox = bus._load_inbox()
        inbox[0]["read"] = True
        bus._save_inbox(inbox)
        bus.inbox_push({"title": "Also unread", "source": "test"})
        unread = bus.inbox_list(unread_only=True)
        assert len(unread) == 1
        assert unread[0]["title"] == "Also unread"


# ---------------------------------------------------------------------------
# 5. Event System
# ---------------------------------------------------------------------------

class TestEventSystem:

    def test_on_and_emit(self, bus):
        received = []
        bus.on("test_event", lambda data: received.append(data))
        bus.emit("test_event", {"key": "value"})
        assert len(received) == 1
        assert received[0]["key"] == "value"

    def test_multiple_handlers(self, bus):
        count = {"a": 0, "b": 0}
        bus.on("multi", lambda d: count.__setitem__("a", count["a"] + 1))
        bus.on("multi", lambda d: count.__setitem__("b", count["b"] + 1))
        called = bus.emit("multi", {})
        assert called == 2
        assert count["a"] == 1
        assert count["b"] == 1

    def test_off_unsubscribe(self, bus):
        received = []
        handler = lambda d: received.append(d)
        bus.on("unsub_test", handler)
        assert bus.off("unsub_test", handler) is True
        bus.emit("unsub_test", {})
        assert len(received) == 0

    def test_off_nonexistent_handler(self, bus):
        assert bus.off("no_event", lambda d: None) is False

    def test_handler_error_does_not_break_bus(self, bus):
        def bad_handler(data):
            raise RuntimeError("boom")

        received = []
        bus.on("error_test", bad_handler)
        bus.on("error_test", lambda d: received.append(d))
        called = bus.emit("error_test", {"ok": True})
        # Second handler still runs even though first exploded
        assert len(received) == 1

    def test_inbox_push_fires_event(self, bus):
        received = []
        bus.on("inbox_push", lambda data: received.append(data))
        bus.inbox_push({"title": "Event test", "source": "test"})
        assert len(received) == 1
        assert received[0]["title"] == "Event test"


# ---------------------------------------------------------------------------
# 6. Approval Workflow
# ---------------------------------------------------------------------------

class TestApprovalWorkflow:

    def test_request_approval(self, bus):
        bus.register("sentinel", ["gov"], "EXPLICIT_APPROVAL")
        approval = bus.request_approval(
            "sentinel", "data_delete", {"target": "old_records"}
        )
        assert approval.status == "pending"
        assert approval.agent_name == "sentinel"

    def test_approve_item(self, bus):
        bus.register("sentinel", ["gov"], "EXPLICIT_APPROVAL")
        approval = bus.request_approval("sentinel", "action", {})
        result = bus.approve(approval.item_id, approved_by="payton")
        assert result["status"] == "approved"
        assert result["resolved_by"] == "payton"

    def test_reject_item(self, bus):
        bus.register("sentinel", ["gov"], "EXPLICIT_APPROVAL")
        approval = bus.request_approval("sentinel", "risky_action", {})
        result = bus.reject(approval.item_id, rejected_by="payton")
        assert result["status"] == "rejected"

    def test_approve_nonexistent_item(self, bus):
        assert bus.approve("fake_id") is None

    def test_reject_nonexistent_item(self, bus):
        assert bus.reject("fake_id") is None

    def test_check_approval_status(self, bus):
        bus.register("orchestrator", ["coord"], "SOFT_APPROVAL")
        approval = bus.request_approval("orchestrator", "deploy", {})
        status = bus.check_approval(approval.item_id)
        assert status["status"] == "pending"
        bus.approve(approval.item_id)
        status = bus.check_approval(approval.item_id)
        assert status["status"] == "approved"


# ---------------------------------------------------------------------------
# 7. Audit Logging
# ---------------------------------------------------------------------------

class TestAuditLogging:

    def test_log_creates_entry(self, bus):
        entry = bus.log("sentinel", "compliance_check", {"result": "pass"})
        assert entry["agent"] == "sentinel"
        assert entry["action"] == "compliance_check"
        assert "timestamp" in entry

    def test_audit_trail_returns_entries(self, bus):
        bus.log("sentinel", "action_1")
        bus.log("orchestrator", "action_2")
        bus.log("sentinel", "action_3")
        trail = bus.audit_trail()
        assert len(trail) >= 3

    def test_audit_trail_filter_by_agent(self, bus):
        bus.log("sentinel", "check_1")
        bus.log("orchestrator", "route_1")
        bus.log("sentinel", "check_2")
        trail = bus.audit_trail(agent_name="sentinel")
        assert all(e["agent"] == "sentinel" for e in trail)
        assert len(trail) == 2

    def test_audit_trail_respects_limit(self, bus):
        for i in range(10):
            bus.log("test", f"action_{i}")
        trail = bus.audit_trail(limit=3)
        assert len(trail) == 3

    def test_audit_persisted_to_file(self, bus):
        bus.log("test", "persisted_action")
        assert os.path.exists(bus._audit_path)
        with open(bus._audit_path) as f:
            lines = f.readlines()
        assert any("persisted_action" in line for line in lines)


# ---------------------------------------------------------------------------
# 8. Autonomy Levels / can_act
# ---------------------------------------------------------------------------

class TestAutonomyLevels:

    def test_full_auto_can_act(self, bus):
        bus.register("whale_tracker", ["tracking"], "FULL_AUTO")
        result = bus.can_act("whale_tracker", "scan_chain")
        assert result["allowed"] is True
        assert result["requires_approval"] is False

    def test_explicit_approval_cannot_act(self, bus):
        bus.register("sentinel", ["governance"], "EXPLICIT_APPROVAL")
        result = bus.can_act("sentinel", "modify_config")
        assert result["allowed"] is False
        assert result["requires_approval"] is True

    def test_soft_approval_can_act_flagged(self, bus):
        bus.register("orchestrator", ["coord"], "SOFT_APPROVAL")
        result = bus.can_act("orchestrator", "schedule_task")
        assert result["allowed"] is True
        assert result["requires_approval"] is True

    def test_never_cannot_act(self, bus):
        bus.register("readonly", ["observe"], "NEVER")
        result = bus.can_act("readonly", "any_action")
        assert result["allowed"] is False
        assert result["requires_approval"] is False

    def test_always_approve_overrides_full_auto(self, bus):
        bus.register("auto_agent", ["all"], "FULL_AUTO")
        result = bus.can_act("auto_agent", "financial_transaction")
        assert result["allowed"] is False
        assert result["requires_approval"] is True

    def test_unregistered_agent_cannot_act(self, bus):
        result = bus.can_act("ghost", "anything")
        assert result["allowed"] is False


# ---------------------------------------------------------------------------
# 9. Cross-Surface Queries
# ---------------------------------------------------------------------------

class TestCrossSurfaceQueries:

    def test_surface_data_command(self, bus):
        bus.graph.create_entity("APPROVAL", "Approve deploy", created_by="test")
        data = bus.surface_data("command")
        assert data["surface"] == "command"
        assert "data" in data
        assert "approval" in data["data"]

    def test_surface_data_flow(self, bus):
        bus.graph.create_entity("TASK", "Write newsletter", created_by="test")
        data = bus.surface_data("flow")
        assert "task" in data["data"]
        assert len(data["data"]["task"]) >= 1

    def test_surface_data_markets(self, bus):
        bus.graph.create_entity("TICKER", "AAPL", created_by="test")
        data = bus.surface_data("markets")
        assert "ticker" in data["data"]

    def test_surface_data_intelligence(self, bus):
        bus.graph.create_entity("NOTE", "Research memo", created_by="test")
        data = bus.surface_data("intelligence")
        assert "note" in data["data"]

    def test_surface_data_network(self, bus):
        bus.graph.create_entity("CONTACT", "John Doe", created_by="test")
        data = bus.surface_data("network")
        assert "contact" in data["data"]

    def test_surface_data_invalid_name(self, bus):
        with pytest.raises(ValueError, match="Unknown surface"):
            bus.surface_data("nonexistent")


# ---------------------------------------------------------------------------
# 10. Memory Read/Write
# ---------------------------------------------------------------------------

class TestMemory:

    def test_memory_write_and_read(self, bus):
        assert bus.memory_write("test_key", {"value": 42})
        result = bus.memory_read("test_key")
        assert result == {"value": 42}

    def test_memory_read_nonexistent(self, bus):
        assert bus.memory_read("missing_key") is None

    def test_memory_overwrite(self, bus):
        bus.memory_write("counter", 1)
        bus.memory_write("counter", 2)
        assert bus.memory_read("counter") == 2


# ---------------------------------------------------------------------------
# 11. Agent Status
# ---------------------------------------------------------------------------

class TestAgentStatus:

    def test_set_and_get_status(self, bus):
        bus.register("sentinel", ["gov"], "EXPLICIT_APPROVAL")
        bus.status("sentinel", "active")
        assert bus.status("sentinel") == "active"

    def test_status_invalid(self, bus):
        bus.register("sentinel", ["gov"], "EXPLICIT_APPROVAL")
        with pytest.raises(ValueError, match="Invalid status"):
            bus.status("sentinel", "flying")

    def test_status_unregistered_agent(self, bus):
        assert bus.status("ghost") is None


# ---------------------------------------------------------------------------
# 12. Singleton
# ---------------------------------------------------------------------------

class TestSingleton:

    def test_get_bus_returns_same_instance(self, tmp_dir):
        b1 = get_bus(base_dir=tmp_dir)
        b2 = get_bus()
        assert b1 is b2

    def test_reset_bus_clears_instance(self, tmp_dir):
        b1 = get_bus(base_dir=tmp_dir)
        reset_bus()
        b2 = get_bus(base_dir=tmp_dir)
        assert b1 is not b2


# ---------------------------------------------------------------------------
# 13. Thread Safety
# ---------------------------------------------------------------------------

class TestThreadSafety:

    def test_concurrent_registrations(self, bus):
        errors = []

        def register_agent(name):
            try:
                bus.register(name, ["test"], "FULL_AUTO")
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=register_agent, args=(f"agent_{i}",))
            for i in range(10)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(bus.list_agents()) == 10
