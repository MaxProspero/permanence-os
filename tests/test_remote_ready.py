#!/usr/bin/env python3
"""Tests for remote readiness evaluator."""

import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from scripts.remote_ready import evaluate_readiness


def _details(tailscale_state: str, online: bool, ssh_open: bool, awake: bool, automation: bool):
    return {
        "checked_at": "2026-02-24T00:00:00Z",
        "tailscale": {
            "installed": True,
            "backend_state": tailscale_state,
            "online": online,
            "ip4": "100.1.2.3",
            "dns_name": "host.ts.net",
        },
        "ssh_port_open": ssh_open,
        "caffeinate_running": awake,
        "automation_scheduled": automation,
    }


def test_remote_ready_pass_when_all_requirements_met():
    result = evaluate_readiness(
        _details("Running", True, True, True, True),
        require_awake=True,
    )
    assert result.ready is True


def test_remote_ready_fails_when_ssh_missing():
    result = evaluate_readiness(
        _details("Running", True, False, True, True),
        require_awake=True,
    )
    assert result.ready is False
    assert result.ssh_ok is False


def test_remote_ready_skip_awake_check():
    result = evaluate_readiness(
        _details("Running", True, True, False, True),
        require_awake=False,
    )
    assert result.ready is True

