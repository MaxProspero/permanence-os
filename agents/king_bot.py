#!/usr/bin/env python3
"""
POLEMARCH - The Governor (formerly King Bot)
Routes, enforces, escalates. Never creates content or reasons about truth.
"""

import yaml
import json
from datetime import datetime, timezone
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from enum import Enum
import os

# Configuration
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CANON_PATH = os.getenv(
    "PERMANENCE_CANON_PATH", os.path.join(BASE_DIR, "canon", "base_canon.yaml")
)
LOG_DIR = os.getenv("PERMANENCE_LOG_DIR", os.path.join(BASE_DIR, "logs"))
MEMORY_DIR = os.getenv("PERMANENCE_MEMORY_DIR", os.path.join(BASE_DIR, "memory"))
MAX_STEPS = int(os.getenv("MAX_STEPS", "12"))
MAX_TOOL_CALLS = int(os.getenv("MAX_TOOL_CALLS", "5"))


class Stage(Enum):
    INIT = "INIT"
    VALIDATION = "VALIDATION"
    PLANNING = "PLANNING"
    SCOPING = "SCOPING"
    RESEARCH = "RESEARCH"
    SOURCE_REVIEW = "SOURCE_REVIEW"
    EXECUTION = "EXECUTION"
    OUTPUT_REVIEW = "OUTPUT_REVIEW"
    CONCILIATION = "CONCILIATION"
    DONE = "DONE"
    FAILED = "FAILED"
    ESCALATED = "ESCALATED"


class Status(Enum):
    INIT = "INIT"
    RUNNING = "RUNNING"
    BLOCKED = "BLOCKED"
    DONE = "DONE"
    FAILED = "FAILED"


class RiskTier(Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


@dataclass
class SystemState:
    """Complete system state for a task"""
    task_id: str
    task_goal: str
    stage: Stage
    status: Status
    risk_tier: Optional[RiskTier]
    step_count: int
    max_steps: int
    tool_calls_used: int
    max_tool_calls: int
    artifacts: Dict
    sources: List
    escalation: Optional[str]
    logs: List[str]
    created_at: str
    updated_at: str

    def to_dict(self):
        return {
            **asdict(self),
            "stage": self.stage.value,
            "status": self.status.value,
            "risk_tier": self.risk_tier.value if self.risk_tier else None,
        }


class Polemarch:
    """
    THE POLEMARCH - Strategic Commander and Governor

    Etymology: Greek πολέμαρχος (polemarchos) - "war leader"

    NATURE:
    The Polemarch is not a creative force. It is a command structure.
    Like a military commander operating under doctrine, it:
    - Assesses terrain (task complexity)
    - Assigns forces (routes to agents)
    - Enforces discipline (budget and Canon adherence)
    - Escalates when outmatched (human authority)
    - Logs every decision (battle records)

    CORE PRINCIPLE:
    Discipline under fire, clarity under fog, structure under chaos.

    ALLOWED ACTIONS:
    - Read orders (task goals)
    - Consult doctrine (Canon)
    - Assign units (route to agents)
    - Enforce limits (budgets)
    - Call retreat (escalation)
    - Record battle (logs)

    FORBIDDEN ACTIONS (NON-NEGOTIABLE):
    - Reason about truth (researcher's domain)
    - Create content (executor's domain)
    - Evaluate quality (reviewer's domain)
    - Solve problems creatively (human work)
    - Improvise outside doctrine
    - Skip validation steps
    - Modify the Canon
    - Act without logging

    The Polemarch does not think. The Polemarch routes.
    The Polemarch does not create. The Polemarch commands.
    The Polemarch does not persuade. The Polemarch enforces.
    """

    def __init__(self):
        self.canon = self._load_canon()
        self.state: Optional[SystemState] = None

    def _load_canon(self) -> Dict:
        """Load the Canon (Constitutional Law)"""
        with open(CANON_PATH, "r") as f:
            return yaml.safe_load(f)

    def _log(self, message: str, level: str = "INFO"):
        """Append-only logging"""
        timestamp = datetime.now(timezone.utc).isoformat()
        log_entry = f"[{timestamp}] [{level}] {message}"

        if self.state:
            self.state.logs.append(log_entry)

        # Also write to file
        log_file = os.path.join(LOG_DIR, f"{datetime.now(timezone.utc).strftime('%Y-%m-%d')}.log")
        os.makedirs(LOG_DIR, exist_ok=True)
        with open(log_file, "a") as f:
            f.write(log_entry + "\n")

        print(log_entry)

    def initialize_task(self, task_goal: str) -> SystemState:
        """Create new task state"""
        task_id = f"T-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"

        self.state = SystemState(
            task_id=task_id,
            task_goal=task_goal,
            stage=Stage.INIT,
            status=Status.INIT,
            risk_tier=None,
            step_count=0,
            max_steps=MAX_STEPS,
            tool_calls_used=0,
            max_tool_calls=MAX_TOOL_CALLS,
            artifacts={},
            sources=[],
            escalation=None,
            logs=[],
            created_at=datetime.now(timezone.utc).isoformat(),
            updated_at=datetime.now(timezone.utc).isoformat(),
        )

        self._log(f"Task initialized: {task_id}")
        self._log(f"Goal: {task_goal}")

        return self.state

    def validate_against_canon(self, task_goal: str) -> Dict:
        """
        Check if task aligns with Canon
        Returns: {valid: bool, reason: str, canon_ref: str}
        """
        self._log("Validating task against Canon...")

        # Check invariants
        for _invariant in self.canon["invariants"]:
            if "modify" in task_goal.lower() and "canon" in task_goal.lower():
                return {
                    "valid": False,
                    "reason": "Task attempts to modify Canon (forbidden)",
                    "canon_ref": "invariants[0]: No agent modifies the Canon",
                }

        # Check against identity constraints
        _constraints = self.canon.get("identity_constraints", [])
        # Add specific constraint checks as needed

        self._log("Task passes Canon validation")
        return {
            "valid": True,
            "reason": "No Canon conflicts detected",
            "canon_ref": "All invariants checked",
        }

    def assign_risk_tier(self, task_goal: str) -> RiskTier:
        """
        Classify task risk level based on Canon criteria
        """
        task_lower = task_goal.lower()

        # HIGH risk indicators
        high_indicators = [
            "publish",
            "post",
            "send",
            "commit",
            "delete",
            "financial",
            "payment",
            "contract",
            "legal",
            "canon",
            "modify",
            "change system",
        ]

        # MEDIUM risk indicators
        medium_indicators = [
            "create",
            "generate",
            "write",
            "code",
            "research",
            "analyze",
            "plan",
        ]

        # Check HIGH first
        if any(indicator in task_lower for indicator in high_indicators):
            tier = RiskTier.HIGH
        elif any(indicator in task_lower for indicator in medium_indicators):
            tier = RiskTier.MEDIUM
        else:
            tier = RiskTier.LOW

        self._log(f"Risk tier assigned: {tier.value}")
        self._log("Reasoning: Pattern match in task description")

        return tier

    def check_budgets(self) -> Dict:
        """
        Verify resource consumption within limits
        Returns: {within_budget: bool, details: Dict}
        """
        if not self.state:
            return {"within_budget": True, "details": {}}

        step_budget_ok = self.state.step_count < self.state.max_steps
        tool_budget_ok = self.state.tool_calls_used < self.state.max_tool_calls

        within_budget = step_budget_ok and tool_budget_ok

        details = {
            "steps": f"{self.state.step_count}/{self.state.max_steps}",
            "tools": f"{self.state.tool_calls_used}/{self.state.max_tool_calls}",
            "step_budget_ok": step_budget_ok,
            "tool_budget_ok": tool_budget_ok,
        }

        if not within_budget:
            self._log("BUDGET EXCEEDED", level="WARNING")
            self._log(f"Details: {details}", level="WARNING")

        return {"within_budget": within_budget, "details": details}

    def route_to_agent(self, agent_type: str) -> Dict:
        """
        Route task to appropriate agent
        Returns: {agent: str, instructions: str}
        """
        valid_agents = ["planner", "researcher", "executor", "reviewer", "conciliator"]

        if agent_type not in valid_agents:
            self._log(f"Invalid agent type: {agent_type}", level="ERROR")
            return {"agent": None, "instructions": "INVALID_AGENT"}

        self._log(f"Routing to agent: {agent_type}")

        # Increment step count
        if self.state:
            self.state.step_count += 1

        return {
            "agent": agent_type,
            "instructions": f"Execute as {agent_type} within Canon constraints",
        }

    def escalate(self, reason: str) -> Dict:
        """
        Escalate to human authority
        """
        self._log(f"ESCALATING TO HUMAN: {reason}", level="CRITICAL")

        if self.state:
            self.state.escalation = reason
            self.state.status = Status.BLOCKED
            self.state.stage = Stage.ESCALATED

        return {"escalated": True, "reason": reason, "human_decision_required": True}

    def halt(self, reason: str):
        """
        Emergency stop
        """
        self._log(f"SYSTEM HALT: {reason}", level="CRITICAL")

        if self.state:
            self.state.status = Status.FAILED
            self.state.stage = Stage.FAILED

        # Save state
        self.save_state()

    def transition_stage(self, next_stage: Stage):
        """
        Move to next execution stage
        """
        if not self.state:
            return

        prev_stage = self.state.stage
        self.state.stage = next_stage
        self.state.updated_at = datetime.now(timezone.utc).isoformat()

        self._log(f"Stage transition: {prev_stage.value} → {next_stage.value}")

    def save_state(self):
        """
        Persist current state to disk
        """
        if not self.state:
            return

        episodic_dir = os.path.join(MEMORY_DIR, "episodic")
        state_file = os.path.join(episodic_dir, f"{self.state.task_id}.json")
        os.makedirs(episodic_dir, exist_ok=True)

        with open(state_file, "w") as f:
            json.dump(self.state.to_dict(), f, indent=2)

        self._log(f"State saved: {state_file}")


# Backward-compatible alias
KingBot = Polemarch

# Example usage
if __name__ == "__main__":
    polemarch = Polemarch()

    # Test task
    task = "Research recent developments in AI governance and create a summary"

    state = polemarch.initialize_task(task)
    validation = polemarch.validate_against_canon(task)

    if validation["valid"]:
        risk = polemarch.assign_risk_tier(task)
        state.risk_tier = risk

        budget_check = polemarch.check_budgets()

        if budget_check["within_budget"]:
            if risk == RiskTier.HIGH:
                polemarch.escalate("High-risk task requires human approval")
            else:
                routing = polemarch.route_to_agent("planner")
                print(f"\n✓ Task routed to: {routing['agent']}")
        else:
            polemarch.halt("Budget exceeded")
    else:
        polemarch.halt(f"Canon violation: {validation['reason']}")

    polemarch.save_state()
    print(f"\n📊 Final State: {state.stage.value} / {state.status.value}")
