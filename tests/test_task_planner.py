"""Tests for the Task Planner — agent work scheduling and budget allocation."""

import json
import os
import pytest
from core.task_planner import (
    TaskPlanner,
    STATUS_PLANNED,
    STATUS_READY,
    STATUS_RUNNING,
    STATUS_COMPLETED,
    STATUS_FAILED,
    STATUS_CANCELLED,
    STATUS_BLOCKED,
    PRIORITY_CRITICAL,
    PRIORITY_HIGH,
    PRIORITY_NORMAL,
    PRIORITY_LOW,
)


@pytest.fixture
def planner(tmp_path):
    """Create a TaskPlanner with temp paths."""
    return TaskPlanner(
        state_path=str(tmp_path / "planner_state.json"),
        log_path=str(tmp_path / "planner.jsonl"),
    )


# ── Task Creation ────────────────────────────────────────────────────────

class TestCreateTask:
    def test_create_basic_task(self, planner):
        task = planner.create_task(title="Research AI safety")
        assert task["title"] == "Research AI safety"
        assert task["status"] == STATUS_PLANNED
        assert task["task_id"].startswith("task_")
        assert task["priority"] == PRIORITY_NORMAL

    def test_create_task_with_all_fields(self, planner):
        task = planner.create_task(
            title="Build feature X",
            task_type="execution",
            agent_id="developer",
            priority=PRIORITY_HIGH,
            budget_usd=10.00,
            provider="anthropic",
            scheduled_for="2026-03-10T09:00:00",
            description="Build the new feature X with full test coverage",
            parameters={"branch": "feature-x"},
        )
        assert task["task_type"] == "execution"
        assert task["agent_id"] == "developer"
        assert task["priority"] == PRIORITY_HIGH
        assert task["budget_usd"] == 10.00
        assert task["provider"] == "anthropic"
        assert task["scheduled_for"] == "2026-03-10T09:00:00"
        assert task["parameters"]["branch"] == "feature-x"

    def test_create_task_invalid_priority_defaults(self, planner):
        task = planner.create_task(title="Test", priority="yolo")
        assert task["priority"] == PRIORITY_NORMAL

    def test_create_task_logged(self, planner):
        planner.create_task(title="Test task")
        with open(planner.log_path) as f:
            lines = [json.loads(l) for l in f if l.strip()]
        assert any(e["event"] == "task_created" for e in lines)

    def test_create_task_persists(self, planner):
        task = planner.create_task(title="Persist test")
        planner2 = TaskPlanner(
            state_path=str(planner.state_path),
            log_path=str(planner.log_path),
        )
        assert task["task_id"] in planner2._tasks


# ── Task Lifecycle ────────────────────────────────────────────────────────

class TestTaskLifecycle:
    def test_start_task(self, planner):
        task = planner.create_task(title="Start me")
        result = planner.start_task(task["task_id"])
        assert result["ok"] is True
        assert result["status"] == STATUS_RUNNING
        assert planner.get_task(task["task_id"])["started_at"] is not None

    def test_complete_task(self, planner):
        task = planner.create_task(title="Complete me")
        planner.start_task(task["task_id"])
        result = planner.complete_task(task["task_id"], result="Done!", spent_usd=2.50)
        assert result["ok"] is True
        assert result["status"] == STATUS_COMPLETED

        loaded = planner.get_task(task["task_id"])
        assert loaded["result"] == "Done!"
        assert loaded["spent_usd"] == 2.50

    def test_fail_task(self, planner):
        task = planner.create_task(title="Fail me")
        planner.start_task(task["task_id"])
        result = planner.fail_task(task["task_id"], error="API timeout")
        assert result["ok"] is True
        assert result["status"] == STATUS_FAILED

    def test_cancel_task(self, planner):
        task = planner.create_task(title="Cancel me")
        result = planner.cancel_task(task["task_id"])
        assert result["ok"] is True
        assert result["status"] == STATUS_CANCELLED

    def test_cannot_cancel_completed_task(self, planner):
        task = planner.create_task(title="Done task")
        planner.start_task(task["task_id"])
        planner.complete_task(task["task_id"])
        result = planner.cancel_task(task["task_id"])
        assert result["ok"] is False

    def test_start_nonexistent_task(self, planner):
        result = planner.start_task("fake_id")
        assert result["ok"] is False

    def test_complete_nonexistent_task(self, planner):
        result = planner.complete_task("fake_id")
        assert result["ok"] is False

    def test_cannot_start_completed_task(self, planner):
        task = planner.create_task(title="Done")
        planner.start_task(task["task_id"])
        planner.complete_task(task["task_id"])
        result = planner.start_task(task["task_id"])
        assert result["ok"] is False


# ── Dependencies ──────────────────────────────────────────────────────────

class TestDependencies:
    def test_blocked_by_dependency(self, planner):
        task_a = planner.create_task(title="Task A")
        task_b = planner.create_task(title="Task B", depends_on=[task_a["task_id"]])

        # Try to start B before A completes
        result = planner.start_task(task_b["task_id"])
        assert result["ok"] is False
        assert "Blocked by dependency" in result["error"]

    def test_unblocked_after_dependency_completes(self, planner):
        task_a = planner.create_task(title="Task A")
        task_b = planner.create_task(title="Task B", depends_on=[task_a["task_id"]])

        # Complete A
        planner.start_task(task_a["task_id"])
        planner.complete_task(task_a["task_id"])

        # Now B can start
        result = planner.start_task(task_b["task_id"])
        assert result["ok"] is True

    def test_no_dependencies_starts_fine(self, planner):
        task = planner.create_task(title="Independent")
        result = planner.start_task(task["task_id"])
        assert result["ok"] is True


# ── Budget Tracking ───────────────────────────────────────────────────────

class TestBudgetTracking:
    def test_record_task_spend(self, planner):
        task = planner.create_task(title="Budget task", budget_usd=10.00)
        planner.start_task(task["task_id"])

        result = planner.record_task_spend(task["task_id"], 3.50)
        assert result["ok"] is True
        assert result["spent_usd"] == 3.50
        assert result["remaining"] == 6.50
        assert result["over_budget"] is False

    def test_over_budget_detected(self, planner):
        task = planner.create_task(title="Cheap task", budget_usd=2.00)
        planner.start_task(task["task_id"])

        planner.record_task_spend(task["task_id"], 1.50)
        result = planner.record_task_spend(task["task_id"], 1.00)
        assert result["over_budget"] is True

    def test_record_spend_nonexistent_task(self, planner):
        result = planner.record_task_spend("fake_id", 1.00)
        assert result["ok"] is False

    def test_zero_budget_never_over(self, planner):
        task = planner.create_task(title="Free task", budget_usd=0.0)
        planner.start_task(task["task_id"])
        result = planner.record_task_spend(task["task_id"], 5.00)
        assert result["over_budget"] is False


# ── Agenda & Filtering ────────────────────────────────────────────────────

class TestAgenda:
    def test_get_empty_agenda(self, planner):
        agenda = planner.get_agenda()
        assert agenda == []

    def test_get_agenda_all_tasks(self, planner):
        planner.create_task(title="Task 1")
        planner.create_task(title="Task 2")
        planner.create_task(title="Task 3")
        agenda = planner.get_agenda()
        assert len(agenda) == 3

    def test_filter_by_status(self, planner):
        t1 = planner.create_task(title="Planned")
        t2 = planner.create_task(title="Running")
        planner.start_task(t2["task_id"])

        planned = planner.get_agenda(status=STATUS_PLANNED)
        assert len(planned) == 1
        assert planned[0]["title"] == "Planned"

        running = planner.get_agenda(status=STATUS_RUNNING)
        assert len(running) == 1
        assert running[0]["title"] == "Running"

    def test_filter_by_priority(self, planner):
        planner.create_task(title="Critical", priority=PRIORITY_CRITICAL)
        planner.create_task(title="Low", priority=PRIORITY_LOW)

        critical = planner.get_agenda(priority=PRIORITY_CRITICAL)
        assert len(critical) == 1
        assert critical[0]["title"] == "Critical"

    def test_filter_by_date(self, planner):
        planner.create_task(title="Today", scheduled_for="2026-03-10T09:00:00")
        planner.create_task(title="Tomorrow", scheduled_for="2026-03-11T09:00:00")

        today = planner.get_agenda(date="2026-03-10")
        assert len(today) == 1
        assert today[0]["title"] == "Today"

    def test_filter_by_agent(self, planner):
        planner.create_task(title="Research", agent_id="research")
        planner.create_task(title="Dev", agent_id="developer")

        research = planner.get_agenda(agent_id="research")
        assert len(research) == 1
        assert research[0]["title"] == "Research"

    def test_agenda_sorted_by_priority(self, planner):
        planner.create_task(title="Low", priority=PRIORITY_LOW)
        planner.create_task(title="Critical", priority=PRIORITY_CRITICAL)
        planner.create_task(title="Normal", priority=PRIORITY_NORMAL)

        agenda = planner.get_agenda()
        assert agenda[0]["title"] == "Critical"
        assert agenda[1]["title"] == "Normal"
        assert agenda[2]["title"] == "Low"


# ── Execution Plan ────────────────────────────────────────────────────────

class TestExecutionPlan:
    def test_empty_plan(self, planner):
        plan = planner.get_execution_plan()
        assert plan["ok"] is True
        assert len(plan["tasks"]) == 0

    def test_plan_within_budget(self, planner):
        planner.create_task(title="T1", priority=PRIORITY_HIGH, budget_usd=5.00)
        planner.create_task(title="T2", priority=PRIORITY_NORMAL, budget_usd=3.00)

        plan = planner.get_execution_plan(daily_budget_usd=20.00)
        assert plan["fits_daily_budget"] is True
        assert plan["total_budget_needed"] == 8.00
        assert all(t["recommendation"] == "execute" for t in plan["tasks"])

    def test_plan_exceeds_budget(self, planner):
        planner.create_task(title="Expensive", priority=PRIORITY_HIGH, budget_usd=15.00)
        planner.create_task(title="Cheap", priority=PRIORITY_NORMAL, budget_usd=5.00)

        plan = planner.get_execution_plan(daily_budget_usd=10.00)
        assert plan["fits_daily_budget"] is False
        assert plan["total_budget_needed"] == 20.00

    def test_plan_suggests_alternatives(self, planner):
        planner.create_task(title="Critical research", priority=PRIORITY_CRITICAL, budget_usd=8.00)
        planner.create_task(title="Nice to have", priority=PRIORITY_LOW, budget_usd=5.00, provider="anthropic")

        plan = planner.get_execution_plan(daily_budget_usd=10.00)
        assert len(plan["alternatives"]) > 0
        assert "Ollama" in plan["alternatives"][0]["suggestion"]

    def test_plan_respects_dependencies(self, planner):
        t1 = planner.create_task(title="First", budget_usd=3.00)
        planner.create_task(title="Second", budget_usd=3.00, depends_on=[t1["task_id"]])

        plan = planner.get_execution_plan(daily_budget_usd=20.00)
        # First task should be executable, second should be blocked
        tasks = {t["title"]: t for t in plan["tasks"]}
        assert tasks["First"]["recommendation"] == "execute"
        assert tasks["Second"]["recommendation"] == "blocked_dependency"

    def test_plan_summary(self, planner):
        planner.create_task(title="C1", priority=PRIORITY_CRITICAL, budget_usd=1.00)
        planner.create_task(title="H1", priority=PRIORITY_HIGH, budget_usd=1.00)
        planner.create_task(title="N1", priority=PRIORITY_NORMAL, budget_usd=1.00)

        plan = planner.get_execution_plan(daily_budget_usd=10.00)
        assert plan["summary"]["critical"] == 1
        assert plan["summary"]["high"] == 1
        assert plan["summary"]["normal"] == 1


# ── Stats ─────────────────────────────────────────────────────────────────

class TestStats:
    def test_empty_stats(self, planner):
        stats = planner.get_stats()
        assert stats["total"] == 0

    def test_stats_with_tasks(self, planner):
        t1 = planner.create_task(title="T1", priority=PRIORITY_HIGH, budget_usd=5.00)
        t2 = planner.create_task(title="T2", priority=PRIORITY_LOW, budget_usd=3.00)
        planner.start_task(t1["task_id"])
        planner.complete_task(t1["task_id"], spent_usd=2.00)

        stats = planner.get_stats()
        assert stats["total"] == 2
        assert stats["by_status"].get(STATUS_COMPLETED, 0) == 1
        assert stats["by_status"].get(STATUS_PLANNED, 0) == 1
        assert stats["total_budget"] == 8.00
        assert stats["total_spent"] == 2.00


# ── Cleanup ───────────────────────────────────────────────────────────────

class TestCleanup:
    def test_cleanup_removes_old_completed(self, planner):
        task = planner.create_task(title="Old task")
        planner.start_task(task["task_id"])
        planner.complete_task(task["task_id"])

        # Backdate the completed_at
        planner._tasks[task["task_id"]]["completed_at"] = "2020-01-01T00:00:00"
        planner._save_state()

        result = planner.cleanup_old_tasks(days_old=1)
        assert result["removed"] == 1
        assert task["task_id"] not in planner._tasks

    def test_cleanup_keeps_recent(self, planner):
        task = planner.create_task(title="Recent task")
        planner.start_task(task["task_id"])
        planner.complete_task(task["task_id"])

        result = planner.cleanup_old_tasks(days_old=1)
        assert result["removed"] == 0

    def test_cleanup_keeps_active_tasks(self, planner):
        planner.create_task(title="Active")
        result = planner.cleanup_old_tasks(days_old=0)
        assert result["removed"] == 0
