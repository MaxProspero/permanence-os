#!/usr/bin/env python3
"""Tests for the /api/arena/state endpoint and its helper functions."""

import json
import os
import sys

import pytest

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, BASE_DIR)


# ── Import arena helpers from dashboard_api ──────────────────────────────

from dashboard_api import (
    _build_arena_agents,
    _get_arena_hub,
    _get_arena_connections,
    _get_arena_events,
    ARENA_DEPT_COLORS,
    ARENA_DEPT_LABELS,
    app,
)


# ── Fixtures ─────────────────────────────────────────────────────────────

@pytest.fixture
def client():
    """Flask test client."""
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


# ── Department Map Tests ─────────────────────────────────────────────────

def test_dept_colors_has_all_departments():
    """All three departments have colors defined (v0.4 streamlined)."""
    for dept in ["CORE", "OPERATIONS", "INFRASTRUCTURE"]:
        assert dept in ARENA_DEPT_COLORS, f"Missing color for {dept}"
        assert ARENA_DEPT_COLORS[dept].startswith("#"), f"Color for {dept} should be hex"


def test_dept_labels_has_all_departments():
    """All three departments have labels defined (v0.4 streamlined)."""
    for dept in ["CORE", "OPERATIONS", "INFRASTRUCTURE"]:
        assert dept in ARENA_DEPT_LABELS, f"Missing label for {dept}"
        assert len(ARENA_DEPT_LABELS[dept]) > 0


# ── Agent Builder Tests ──────────────────────────────────────────────────

def test_build_arena_agents_returns_list():
    """Agent builder returns a list."""
    agents = _build_arena_agents()
    assert isinstance(agents, list)


def test_build_arena_agents_has_entries():
    """Agent builder returns agents from the registry."""
    agents = _build_arena_agents()
    assert len(agents) > 0, "Should have agents from AGENT_REGISTRY"


def test_arena_agent_has_required_fields():
    """Each arena agent has all required fields."""
    agents = _build_arena_agents()
    required = {"id", "name", "department", "department_label", "color", "risk", "status"}
    for a in agents:
        for field in required:
            assert field in a, f"Agent {a.get('id', '?')} missing field: {field}"


def test_arena_agent_departments_are_valid():
    """All agents/workflows have valid department assignments (v0.4)."""
    valid_depts = {"CORE", "OPERATIONS", "INFRASTRUCTURE", "WORKFLOW"}
    agents = _build_arena_agents()
    for a in agents:
        assert a["department"] in valid_depts, \
            f"Agent {a['id']} has invalid department: {a['department']}"


def test_arena_agent_colors_match_department():
    """Agent colors match their department's color (workflows use own color)."""
    agents = _build_arena_agents()
    for a in agents:
        if a.get("kind") == "workflow":
            assert a["color"] == "#6ecfff", \
                f"Workflow {a['id']} should have workflow color #6ecfff"
        else:
            expected_color = ARENA_DEPT_COLORS.get(a["department"])
            assert a["color"] == expected_color, \
                f"Agent {a['id']} color {a['color']} != dept color {expected_color}"


def test_arena_agent_names_are_readable():
    """Agent names are title-cased readable names."""
    agents = _build_arena_agents()
    for a in agents:
        assert a["name"][0].isupper(), f"Agent name should be title case: {a['name']}"
        assert "_" not in a["name"], f"Agent name should not contain underscores: {a['name']}"


# ── Hub Builder Tests ────────────────────────────────────────────────────

def test_arena_hub_has_status():
    """Hub builder returns status field."""
    hub = _get_arena_hub()
    assert "status" in hub
    assert hub["status"] in ("online", "offline", "degraded")


def test_arena_hub_has_spending():
    """Hub builder includes spending info."""
    hub = _get_arena_hub()
    assert "spending" in hub
    assert "mode" in hub["spending"]


# ── Connection Builder Tests ─────────────────────────────────────────────

def test_arena_connections_returns_list():
    """Connection builder returns a list."""
    agents = _build_arena_agents()
    conns = _get_arena_connections(agents)
    assert isinstance(conns, list)


def test_arena_connections_have_required_fields():
    """Each connection has from, to, and type."""
    agents = _build_arena_agents()
    conns = _get_arena_connections(agents)
    for c in conns:
        assert "from" in c, f"Connection missing 'from': {c}"
        assert "to" in c, f"Connection missing 'to': {c}"
        assert "type" in c, f"Connection missing 'type': {c}"


def test_arena_connections_types_are_valid():
    """Connection types are valid."""
    valid_types = {"pipeline", "control", "dispatch"}
    agents = _build_arena_agents()
    conns = _get_arena_connections(agents)
    for c in conns:
        assert c["type"] in valid_types, f"Invalid connection type: {c['type']}"


def test_arena_core_agents_form_pipeline():
    """Core agents should have pipeline connections between them."""
    agents = _build_arena_agents()
    conns = _get_arena_connections(agents)
    pipeline_conns = [c for c in conns if c["type"] == "pipeline"]
    core_agents = [a for a in agents if a["department"] == "CORE"]
    if len(core_agents) > 1:
        assert len(pipeline_conns) > 0, "Core agents should form a pipeline"


def test_arena_infra_agents_connect_to_hub():
    """Infrastructure agents should connect to the hub."""
    agents = _build_arena_agents()
    conns = _get_arena_connections(agents)
    control_conns = [c for c in conns if c["type"] == "control"]
    infra_agents = [a for a in agents if a["department"] == "INFRASTRUCTURE"]
    if infra_agents:
        assert len(control_conns) > 0, "Infra agents should have hub connections"


# ── Event Builder Tests ──────────────────────────────────────────────────

def test_arena_events_returns_list():
    """Event builder returns a list."""
    events = _get_arena_events()
    assert isinstance(events, list)


def test_arena_events_max_ten():
    """Event builder returns at most 10 events."""
    events = _get_arena_events()
    assert len(events) <= 10


# ── API Endpoint Tests ───────────────────────────────────────────────────

def test_arena_state_endpoint_returns_200(client):
    """GET /api/arena/state returns 200."""
    resp = client.get("/api/arena/state")
    assert resp.status_code == 200


def test_arena_state_endpoint_returns_json(client):
    """GET /api/arena/state returns valid JSON."""
    resp = client.get("/api/arena/state")
    data = resp.get_json()
    assert data is not None
    assert data["ok"] is True


def test_arena_state_has_all_sections(client):
    """Arena state response contains all required sections."""
    resp = client.get("/api/arena/state")
    data = resp.get_json()
    assert "agents" in data
    assert "hub" in data
    assert "connections" in data
    assert "events" in data
    assert "departments" in data
    assert "ts" in data


def test_arena_state_agents_match_registry(client):
    """Arena state agents+workflows match both registries."""
    from core.polemarch import AGENT_REGISTRY, WORKFLOW_REGISTRY
    resp = client.get("/api/arena/state")
    data = resp.get_json()
    expected_total = len(AGENT_REGISTRY) + len(WORKFLOW_REGISTRY)
    assert len(data["agents"]) == expected_total, \
        f"Expected {expected_total} (agents+workflows), got {len(data['agents'])}"


def test_arena_state_departments_have_colors(client):
    """Department section includes colors."""
    resp = client.get("/api/arena/state")
    data = resp.get_json()
    depts = data["departments"]
    for key, info in depts.items():
        assert "label" in info
        assert "color" in info
        assert info["color"].startswith("#")
