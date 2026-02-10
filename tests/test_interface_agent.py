#!/usr/bin/env python3
"""Tests for Interface Agent intake behavior."""

from __future__ import annotations

import json
import os
import tempfile

from core.interface_agent import InterfaceAgent
from memory.zero_point import MemoryType, ZeroPoint


class _PolemarchStub:
    def __init__(self):
        self.calls = []

    def assess_risk(self, intake_record):
        self.calls.append(intake_record)
        return {"risk_tier": "LOW", "route_to": "planner"}


def _make_agent(tmp_path: str):
    zp = ZeroPoint(storage_path=os.path.join(tmp_path, "zp.json"))
    stub = _PolemarchStub()
    return InterfaceAgent(zero_point=zp, polemarch=stub), zp, stub


def test_valid_intake_is_written_with_provenance():
    with tempfile.TemporaryDirectory() as tmp:
        agent, zp, _stub = _make_agent(tmp)
        response = agent.process_intake(
            {"source": "mobile", "content": "Fix the roof", "timestamp": "2026-02-07T00:00:00Z"},
            source_type="mobile",
        )
        assert set(response.keys()) == {"ticket_id"}

        entries = zp.search(memory_type=MemoryType.INTAKE, requesting_agent="TEST")
        assert len(entries) == 1
        payload = json.loads(entries[0]["content"])
        assert payload["provenance"] == "external_interface"
        assert payload["source_type"] == "mobile"


def test_sanitization_strips_script_payload():
    with tempfile.TemporaryDirectory() as tmp:
        agent, zp, _stub = _make_agent(tmp)
        agent.process_intake({"source": "web", "content": "<script>alert(1)</script>normal"}, source_type="web")
        entries = zp.search(memory_type=MemoryType.INTAKE, requesting_agent="TEST")
        payload = json.loads(entries[0]["content"])
        assert "<script>" not in payload["content"].lower()
        assert "script_tag_removed" in payload["flags"]


def test_malformed_payload_is_logged_but_not_rejected():
    with tempfile.TemporaryDirectory() as tmp:
        agent, zp, _stub = _make_agent(tmp)
        response = agent.process_intake("not a json payload", source_type="webhook")
        assert "ticket_id" in response
        entries = zp.search(memory_type=MemoryType.INTAKE, requesting_agent="TEST")
        payload = json.loads(entries[0]["content"])
        assert payload["malformed"] is True
        assert "non_json_payload" in payload["flags"]


def test_assess_risk_triggered_after_intake():
    with tempfile.TemporaryDirectory() as tmp:
        agent, _zp, stub = _make_agent(tmp)
        agent.process_intake({"source": "mobile", "content": "Schedule training"})
        assert len(stub.calls) == 1


def test_interface_response_is_ticket_only():
    with tempfile.TemporaryDirectory() as tmp:
        agent, _zp, _stub = _make_agent(tmp)
        response = agent.process_intake({"source": "mobile", "content": "Test"})
        assert list(response.keys()) == ["ticket_id"]
