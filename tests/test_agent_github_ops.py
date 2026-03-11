"""Tests for scripts/agent_github_ops.py — Agent GitHub Operations."""

import json
import os
import tempfile

import pytest

# Allow running from repo root
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scripts.agent_github_ops import (
    PROTECTED_BRANCHES,
    MAX_DAILY_WRITES_DEFAULT,
    _is_protected,
    _validate_branch_name,
    _check_daily_limit,
    _load_daily_writes,
    _log_write,
    list_branches,
    get_daily_write_count,
    cleanup_stale_branches,
    WRITE_LOG_PATH,
)


class TestProtectedBranches:
    """Protected branch safety checks."""

    def test_main_is_protected(self):
        assert _is_protected("main") is True

    def test_master_is_protected(self):
        assert _is_protected("master") is True

    def test_vibrant_merkle_is_protected(self):
        assert _is_protected("claude/vibrant-merkle") is True

    def test_origin_main_is_protected(self):
        assert _is_protected("origin/main") is True

    def test_agent_branch_is_not_protected(self):
        assert _is_protected("agent/researcher/test-feature") is False

    def test_random_branch_not_protected(self):
        assert _is_protected("feature/something") is False


class TestBranchNaming:
    """Branch naming convention enforcement."""

    def test_valid_agent_branch(self):
        result = _validate_branch_name("agent/researcher/add-search", "researcher")
        assert result is None

    def test_wrong_agent_prefix(self):
        result = _validate_branch_name("agent/executor/add-search", "researcher")
        assert result is not None
        assert "must start with" in result

    def test_missing_agent_prefix(self):
        result = _validate_branch_name("feature/add-search", "researcher")
        assert result is not None

    def test_protected_branch_blocked(self):
        result = _validate_branch_name("main", "researcher")
        assert result is not None
        assert "protected" in result.lower()

    def test_forbidden_pattern_release(self):
        result = _validate_branch_name("release/v1.0", "researcher")
        assert result is not None


class TestDailyWriteLimit:
    """Daily write limit enforcement."""

    def test_no_writes_returns_zero(self, tmp_path, monkeypatch):
        fake_log = str(tmp_path / "writes.jsonl")
        monkeypatch.setattr("scripts.agent_github_ops.WRITE_LOG_PATH", fake_log)
        assert _load_daily_writes("researcher") == 0

    def test_check_limit_under(self, tmp_path, monkeypatch):
        fake_log = str(tmp_path / "writes.jsonl")
        monkeypatch.setattr("scripts.agent_github_ops.WRITE_LOG_PATH", fake_log)
        assert _check_daily_limit("researcher", 10) is True

    def test_check_limit_exceeded(self, tmp_path, monkeypatch):
        from datetime import datetime, timezone
        fake_log = str(tmp_path / "writes.jsonl")
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        with open(fake_log, "w") as f:
            for i in range(10):
                entry = {"agent_id": "researcher", "timestamp": f"{today}T{i:02d}:00:00+00:00", "action": "push"}
                f.write(json.dumps(entry) + "\n")
        monkeypatch.setattr("scripts.agent_github_ops.WRITE_LOG_PATH", fake_log)
        assert _check_daily_limit("researcher", 10) is False

    def test_different_agent_not_counted(self, tmp_path, monkeypatch):
        from datetime import datetime, timezone
        fake_log = str(tmp_path / "writes.jsonl")
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        with open(fake_log, "w") as f:
            for i in range(10):
                entry = {"agent_id": "executor", "timestamp": f"{today}T{i:02d}:00:00+00:00", "action": "push"}
                f.write(json.dumps(entry) + "\n")
        monkeypatch.setattr("scripts.agent_github_ops.WRITE_LOG_PATH", fake_log)
        assert _check_daily_limit("researcher", 10) is True


class TestWriteCount:
    """Write count reporting."""

    def test_write_count_structure(self, tmp_path, monkeypatch):
        fake_log = str(tmp_path / "writes.jsonl")
        monkeypatch.setattr("scripts.agent_github_ops.WRITE_LOG_PATH", fake_log)
        result = get_daily_write_count("researcher")
        assert result["agent_id"] == "researcher"
        assert result["writes_today"] == 0
        assert result["limit"] == MAX_DAILY_WRITES_DEFAULT
        assert result["remaining"] == MAX_DAILY_WRITES_DEFAULT


class TestLogWrite:
    """Audit logging."""

    def test_log_creates_file(self, tmp_path, monkeypatch):
        fake_log = str(tmp_path / "sub" / "writes.jsonl")
        monkeypatch.setattr("scripts.agent_github_ops.WRITE_LOG_PATH", fake_log)
        _log_write("researcher", "push", {"branch": "agent/researcher/test"})
        assert os.path.exists(fake_log)
        with open(fake_log) as f:
            entry = json.loads(f.readline())
        assert entry["agent_id"] == "researcher"
        assert entry["action"] == "push"
        assert "timestamp" in entry


class TestCleanupDryRun:
    """Branch cleanup dry-run safety."""

    def test_cleanup_returns_list(self):
        # This tests the function signature, actual git operations need a real repo
        result = cleanup_stale_branches(days_old=30, dry_run=True)
        assert isinstance(result, list)

    def test_protected_branches_constant(self):
        """Verify protected branches list hasn't been accidentally modified."""
        assert "main" in PROTECTED_BRANCHES
        assert "claude/vibrant-merkle" in PROTECTED_BRANCHES
