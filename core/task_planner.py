#!/usr/bin/env python3
"""
Permanence OS — Task Planner

Plan and schedule agent tasks with budget allocation.
The planner acts as the "think before you spend" layer —
it evaluates all options and allocates resources optimally
before any agent starts executing (and spending money).

Key features:
  - Plan tasks for specific dates/times
  - Set budget per task
  - Priority-based scheduling
  - Pre-execution cost estimation
  - Agent assignment
  - Spending gate integration

Usage:
    from core.task_planner import task_planner

    # Plan a task
    task = task_planner.create_task(
        title="Research competitor analysis",
        task_type="research_synthesis",
        agent_id="research",
        priority="high",
        budget_usd=5.00,
        scheduled_for="2026-03-10T09:00:00",
    )

    # Get today's agenda
    agenda = task_planner.get_agenda()

    # Start a task (integrates with spending gate)
    task_planner.start_task(task["task_id"])

    # Complete a task
    task_planner.complete_task(task["task_id"])
"""

from __future__ import annotations

import json
import os
import uuid
import threading
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DEFAULT_PLANNER_PATH = os.path.join(BASE_DIR, "memory", "working", "task_planner.json")
DEFAULT_PLANNER_LOG = os.path.join(BASE_DIR, "logs", "task_planner.jsonl")

# Task statuses
STATUS_PLANNED = "planned"        # Scheduled but not started
STATUS_READY = "ready"            # Ready to execute (budget approved)
STATUS_RUNNING = "running"        # Currently executing
STATUS_COMPLETED = "completed"    # Finished successfully
STATUS_FAILED = "failed"          # Finished with errors
STATUS_CANCELLED = "cancelled"    # Cancelled by user
STATUS_BLOCKED = "blocked"        # Blocked by spending gate or dependency

VALID_STATUSES = (STATUS_PLANNED, STATUS_READY, STATUS_RUNNING, STATUS_COMPLETED,
                  STATUS_FAILED, STATUS_CANCELLED, STATUS_BLOCKED)

# Priority levels (match spending_gate)
PRIORITY_CRITICAL = "critical"
PRIORITY_HIGH = "high"
PRIORITY_NORMAL = "normal"
PRIORITY_LOW = "low"

VALID_PRIORITIES = (PRIORITY_CRITICAL, PRIORITY_HIGH, PRIORITY_NORMAL, PRIORITY_LOW)


class TaskPlanner:
    """
    Plans and schedules agent work with budget allocation.

    The planner evaluates all pending tasks, estimates costs,
    and creates an optimal execution plan before any money is spent.
    """

    def __init__(
        self,
        state_path: Optional[str] = None,
        log_path: Optional[str] = None,
    ):
        self.state_path = Path(state_path or DEFAULT_PLANNER_PATH)
        self.log_path = Path(log_path or DEFAULT_PLANNER_LOG)
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

        # Load tasks
        self._tasks: Dict[str, Dict[str, Any]] = self._load_state()

    def _load_state(self) -> Dict[str, Dict[str, Any]]:
        """Load persisted task state."""
        if self.state_path.exists():
            try:
                data = json.loads(self.state_path.read_text(encoding="utf-8"))
                if isinstance(data, dict) and "tasks" in data:
                    return data["tasks"]
            except (json.JSONDecodeError, OSError, TypeError, ValueError):
                pass
        return {}

    def _save_state(self) -> None:
        """Persist task state to disk."""
        try:
            data = {
                "tasks": self._tasks,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            self.state_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except OSError:
            pass

    def _log_event(self, event_type: str, details: Dict[str, Any]) -> None:
        """Append event to planner log."""
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event": event_type,
            **details,
        }
        try:
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
        except OSError:
            pass

    def create_task(
        self,
        title: str,
        task_type: str = "general",
        agent_id: str = "",
        priority: str = PRIORITY_NORMAL,
        budget_usd: float = 0.0,
        provider: str = "anthropic",
        scheduled_for: Optional[str] = None,
        description: str = "",
        depends_on: Optional[List[str]] = None,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Create a planned task.

        Args:
            title: Short task title
            task_type: Type (research_synthesis, planning, execution, classification, etc.)
            agent_id: Which agent should run this
            priority: critical/high/normal/low
            budget_usd: Maximum budget for this task
            provider: Preferred LLM provider
            scheduled_for: ISO datetime for when to run (None = ASAP)
            description: Detailed description
            depends_on: List of task_ids this depends on
            parameters: Extra parameters for the agent
        """
        if priority not in VALID_PRIORITIES:
            priority = PRIORITY_NORMAL

        task_id = f"task_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).isoformat()

        task = {
            "task_id": task_id,
            "title": title,
            "description": description,
            "task_type": task_type,
            "agent_id": agent_id,
            "priority": priority,
            "budget_usd": round(budget_usd, 6),
            "spent_usd": 0.0,
            "provider": provider,
            "status": STATUS_PLANNED,
            "scheduled_for": scheduled_for,
            "depends_on": depends_on or [],
            "parameters": parameters or {},
            "created_at": now,
            "started_at": None,
            "completed_at": None,
            "result": None,
        }

        with self._lock:
            self._tasks[task_id] = task
            self._save_state()

        self._log_event("task_created", {
            "task_id": task_id,
            "title": title,
            "task_type": task_type,
            "priority": priority,
            "budget_usd": budget_usd,
        })

        return task

    def start_task(self, task_id: str) -> Dict[str, Any]:
        """
        Mark a task as running.
        Should be called after spending gate approval is obtained.
        """
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return {"ok": False, "error": f"Task not found: {task_id}"}
            if task["status"] not in (STATUS_PLANNED, STATUS_READY, STATUS_BLOCKED):
                return {"ok": False, "error": f"Cannot start task in status: {task['status']}"}

            # Check dependencies
            for dep_id in task.get("depends_on", []):
                dep = self._tasks.get(dep_id)
                if dep and dep["status"] != STATUS_COMPLETED:
                    task["status"] = STATUS_BLOCKED
                    self._save_state()
                    return {"ok": False, "error": f"Blocked by dependency: {dep_id} (status: {dep['status']})"}

            task["status"] = STATUS_RUNNING
            task["started_at"] = datetime.now(timezone.utc).isoformat()
            self._save_state()

        self._log_event("task_started", {"task_id": task_id, "title": task["title"]})
        return {"ok": True, "task_id": task_id, "status": STATUS_RUNNING}

    def complete_task(
        self,
        task_id: str,
        result: Optional[str] = None,
        spent_usd: float = 0.0,
    ) -> Dict[str, Any]:
        """Mark a task as completed."""
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return {"ok": False, "error": f"Task not found: {task_id}"}

            task["status"] = STATUS_COMPLETED
            task["completed_at"] = datetime.now(timezone.utc).isoformat()
            task["result"] = result
            task["spent_usd"] = round(spent_usd, 6)
            self._save_state()

        self._log_event("task_completed", {
            "task_id": task_id,
            "title": task["title"],
            "spent_usd": round(spent_usd, 6),
            "budget_usd": task["budget_usd"],
        })
        return {"ok": True, "task_id": task_id, "status": STATUS_COMPLETED}

    def fail_task(self, task_id: str, error: str = "") -> Dict[str, Any]:
        """Mark a task as failed."""
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return {"ok": False, "error": f"Task not found: {task_id}"}

            task["status"] = STATUS_FAILED
            task["completed_at"] = datetime.now(timezone.utc).isoformat()
            task["result"] = error
            self._save_state()

        self._log_event("task_failed", {"task_id": task_id, "error": error})
        return {"ok": True, "task_id": task_id, "status": STATUS_FAILED}

    def cancel_task(self, task_id: str) -> Dict[str, Any]:
        """Cancel a planned or running task."""
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return {"ok": False, "error": f"Task not found: {task_id}"}
            if task["status"] == STATUS_COMPLETED:
                return {"ok": False, "error": "Cannot cancel completed task"}

            task["status"] = STATUS_CANCELLED
            task["completed_at"] = datetime.now(timezone.utc).isoformat()
            self._save_state()

        self._log_event("task_cancelled", {"task_id": task_id})
        return {"ok": True, "task_id": task_id, "status": STATUS_CANCELLED}

    def record_task_spend(self, task_id: str, amount_usd: float) -> Dict[str, Any]:
        """Record spending against a task's budget."""
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return {"ok": False, "error": f"Task not found: {task_id}"}

            task["spent_usd"] = round(task.get("spent_usd", 0.0) + amount_usd, 6)
            over_budget = task["spent_usd"] > task["budget_usd"] if task["budget_usd"] > 0 else False
            self._save_state()

        return {
            "ok": True,
            "task_id": task_id,
            "spent_usd": task["spent_usd"],
            "budget_usd": task["budget_usd"],
            "over_budget": over_budget,
            "remaining": round(max(0, task["budget_usd"] - task["spent_usd"]), 6),
        }

    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get a single task by ID."""
        return self._tasks.get(task_id)

    def get_agenda(
        self,
        date: Optional[str] = None,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        agent_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get the task agenda, optionally filtered.

        Args:
            date: Filter by scheduled date (YYYY-MM-DD). None = all dates.
            status: Filter by status. None = all statuses.
            priority: Filter by priority. None = all priorities.
            agent_id: Filter by agent. None = all agents.
        """
        tasks = list(self._tasks.values())

        if date:
            tasks = [t for t in tasks if t.get("scheduled_for", "").startswith(date)]

        if status:
            tasks = [t for t in tasks if t["status"] == status]

        if priority:
            tasks = [t for t in tasks if t["priority"] == priority]

        if agent_id:
            tasks = [t for t in tasks if t["agent_id"] == agent_id]

        # Sort by priority (critical first), then scheduled_for
        priority_order = {PRIORITY_CRITICAL: 0, PRIORITY_HIGH: 1, PRIORITY_NORMAL: 2, PRIORITY_LOW: 3}
        tasks.sort(key=lambda t: (
            priority_order.get(t["priority"], 99),
            t.get("scheduled_for") or "9999",
        ))

        return tasks

    def get_execution_plan(self, daily_budget_usd: float = 0.0) -> Dict[str, Any]:
        """
        Pre-planning analysis: generate an optimal execution plan.

        Evaluates all pending tasks, checks budgets, identifies
        the cheapest execution path, and suggests resource allocation.
        This is the "look before you leap" function.
        """
        pending = [
            t for t in self._tasks.values()
            if t["status"] in (STATUS_PLANNED, STATUS_READY, STATUS_BLOCKED)
        ]

        if not pending:
            return {
                "ok": True,
                "message": "No pending tasks",
                "tasks": [],
                "total_budget_needed": 0.0,
                "fits_daily_budget": True,
            }

        # Sort by priority
        priority_order = {PRIORITY_CRITICAL: 0, PRIORITY_HIGH: 1, PRIORITY_NORMAL: 2, PRIORITY_LOW: 3}
        pending.sort(key=lambda t: priority_order.get(t["priority"], 99))

        total_budget = sum(t["budget_usd"] for t in pending)
        fits_budget = total_budget <= daily_budget_usd if daily_budget_usd > 0 else True

        # Build execution plan
        plan_tasks = []
        running_total = 0.0
        for task in pending:
            budget = task["budget_usd"]
            would_fit = (running_total + budget) <= daily_budget_usd if daily_budget_usd > 0 else True

            # Check if dependencies are satisfied
            deps_met = all(
                self._tasks.get(dep, {}).get("status") == STATUS_COMPLETED
                for dep in task.get("depends_on", [])
            )

            plan_tasks.append({
                "task_id": task["task_id"],
                "title": task["title"],
                "priority": task["priority"],
                "budget_usd": budget,
                "agent_id": task["agent_id"],
                "provider": task["provider"],
                "dependencies_met": deps_met,
                "fits_remaining_budget": would_fit,
                "recommendation": "execute" if (deps_met and would_fit) else
                                  "defer_budget" if not would_fit else
                                  "blocked_dependency",
            })

            if would_fit:
                running_total += budget

        # Smart allocation suggestion
        alternatives = []
        if not fits_budget and daily_budget_usd > 0:
            # Suggest using cheaper providers for low-priority tasks
            for pt in plan_tasks:
                if pt["priority"] in (PRIORITY_LOW, PRIORITY_NORMAL) and pt["provider"] != "ollama":
                    alternatives.append({
                        "task_id": pt["task_id"],
                        "suggestion": f"Use Ollama (free) instead of {pt['provider']} — saves ${pt['budget_usd']:.2f}",
                        "savings_usd": pt["budget_usd"],
                    })

        return {
            "ok": True,
            "total_budget_needed": round(total_budget, 6),
            "daily_budget_usd": round(daily_budget_usd, 6),
            "fits_daily_budget": fits_budget,
            "tasks": plan_tasks,
            "alternatives": alternatives,
            "summary": {
                "critical": len([t for t in plan_tasks if t["priority"] == PRIORITY_CRITICAL]),
                "high": len([t for t in plan_tasks if t["priority"] == PRIORITY_HIGH]),
                "normal": len([t for t in plan_tasks if t["priority"] == PRIORITY_NORMAL]),
                "low": len([t for t in plan_tasks if t["priority"] == PRIORITY_LOW]),
                "executable_now": len([t for t in plan_tasks if t["recommendation"] == "execute"]),
                "deferred": len([t for t in plan_tasks if t["recommendation"] == "defer_budget"]),
                "blocked": len([t for t in plan_tasks if t["recommendation"] == "blocked_dependency"]),
            },
        }

    def get_stats(self) -> Dict[str, Any]:
        """Get task statistics summary."""
        all_tasks = list(self._tasks.values())
        if not all_tasks:
            return {
                "total": 0,
                "by_status": {},
                "by_priority": {},
                "total_budget": 0.0,
                "total_spent": 0.0,
            }

        by_status = {}
        by_priority = {}
        total_budget = 0.0
        total_spent = 0.0

        for task in all_tasks:
            status = task["status"]
            priority = task["priority"]
            by_status[status] = by_status.get(status, 0) + 1
            by_priority[priority] = by_priority.get(priority, 0) + 1
            total_budget += task.get("budget_usd", 0.0)
            total_spent += task.get("spent_usd", 0.0)

        return {
            "total": len(all_tasks),
            "by_status": by_status,
            "by_priority": by_priority,
            "total_budget": round(total_budget, 6),
            "total_spent": round(total_spent, 6),
        }

    def cleanup_old_tasks(self, days_old: int = 30) -> Dict[str, Any]:
        """Remove completed/cancelled/failed tasks older than N days."""
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days_old)).isoformat()
        removed = 0

        with self._lock:
            to_remove = []
            for task_id, task in self._tasks.items():
                if task["status"] in (STATUS_COMPLETED, STATUS_FAILED, STATUS_CANCELLED):
                    completed_at = task.get("completed_at", "")
                    if completed_at and completed_at < cutoff:
                        to_remove.append(task_id)

            for task_id in to_remove:
                del self._tasks[task_id]
                removed += 1

            if removed:
                self._save_state()

        return {"ok": True, "removed": removed}


# ── Module singleton ──────────────────────────────────────────────────

_planner: Optional[TaskPlanner] = None


def get_task_planner() -> TaskPlanner:
    """Get the global TaskPlanner singleton."""
    global _planner
    if _planner is None:
        _planner = TaskPlanner()
    return _planner
