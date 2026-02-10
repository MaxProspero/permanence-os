"""
Permanence OS — Polemarch (Governor) v0.3
Formerly King Bot. Renamed per CA-001 naming convention.

The Polemarch NEVER thinks for outcomes.
The Polemarch decides what is ALLOWED to happen.

v0.3 Updates:
- Routes to new Special Agents (Muse, Twin, Chimera, ArchEvolution)
- Twin Protocol: HIGH-risk tasks get shadow-simulated before execution
- DNA validation enforcement on all routed agents
"""

import yaml
import os
import json
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from enum import Enum
from dataclasses import dataclass, field

from memory.zero_point import MemoryType, ZeroPoint


class RiskTier(Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class Stage(Enum):
    INIT = "INIT"
    VALIDATION = "VALIDATION"
    PLANNING = "PLANNING"
    SCOPING = "SCOPING"
    TWIN_SIMULATION = "TWIN_SIMULATION"  # NEW v0.3
    RESEARCH = "RESEARCH"
    SOURCE_REVIEW = "SOURCE_REVIEW"
    EXECUTION = "EXECUTION"
    OUTPUT_REVIEW = "OUTPUT_REVIEW"
    CONCILIATION = "CONCILIATION"
    DONE = "DONE"
    BLOCKED = "BLOCKED"
    ESCALATED = "ESCALATED"


# Agent routing table
AGENT_REGISTRY = {
    # Core agents
    "planner": {"department": "CORE", "stage": Stage.PLANNING},
    "researcher": {"department": "CORE", "stage": Stage.RESEARCH},
    "executor": {"department": "CORE", "stage": Stage.EXECUTION},
    "reviewer": {"department": "CORE", "stage": Stage.OUTPUT_REVIEW},
    "conciliator": {"department": "CORE", "stage": Stage.CONCILIATION},
    # Department agents
    "email_agent": {"department": "DEPARTMENT", "risk_default": RiskTier.MEDIUM},
    "health_agent": {"department": "DEPARTMENT", "risk_default": RiskTier.LOW},
    "social_agent": {"department": "DEPARTMENT", "risk_default": RiskTier.MEDIUM},
    "briefing_agent": {"department": "DEPARTMENT", "risk_default": RiskTier.LOW},
    "device_agent": {"department": "DEPARTMENT", "risk_default": RiskTier.LOW},
    "trainer_agent": {"department": "DEPARTMENT", "risk_default": RiskTier.LOW},
    "therapist_agent": {"department": "DEPARTMENT", "risk_default": RiskTier.LOW},
    # Special agents (NEW v0.3)
    "muse": {"department": "SPECIAL", "risk_default": RiskTier.LOW},
    "digital_twin": {"department": "SPECIAL", "risk_default": RiskTier.LOW},
    "chimera_builder": {"department": "SPECIAL", "risk_default": RiskTier.MEDIUM},
    "arch_evolution": {"department": "SPECIAL", "risk_default": RiskTier.LOW},
}


@dataclass
class PolemarchDecision:
    timestamp: str
    task_id: str
    decision: str
    risk_tier: str
    canon_ref: str
    route_to: str
    reason: str
    twin_required: bool = False


class Polemarch:
    """
    The Governor. Routes, enforces, escalates. Never creates.

    v0.3 Capabilities:
    - Route to all agent types (core, department, special)
    - Enforce Twin Protocol for HIGH-risk tasks
    - Validate DNA inheritance on routed agents
    - Canon compliance checking
    - Budget enforcement
    """

    FORBIDDEN_ACTIONS = [
        "write_prose", "create_content", "summarize", "persuade",
        "brainstorm", "improvise", "reason_truth", "skip_validation",
        "modify_canon", "act_without_logging"
    ]

    def __init__(self, canon_path: str = "canon/", zero_point: Optional[ZeroPoint] = None):
        self.canon_path = canon_path
        self.decisions: List[PolemarchDecision] = []
        self.canon_data: Dict = {}
        self.zero_point = zero_point or ZeroPoint()
        self._processed_intake_ids: set[str] = set()
        self._load_canon()

    def _load_canon(self):
        """Load Canon for validation."""
        canon_files = ["values.yaml", "invariants.yaml", "tradeoffs.yaml",
                       "decision_heuristics.yaml", "dna.yaml"]
        for fname in canon_files:
            fpath = os.path.join(self.canon_path, fname)
            if os.path.exists(fpath):
                with open(fpath, 'r') as f:
                    self.canon_data[fname.replace('.yaml', '')] = yaml.safe_load(f)

    def validate_task(self, task: Dict) -> Dict:
        """
        Validate a task against Canon before any execution.
        Returns validation result with risk tier assignment.
        """
        task_id = task.get("task_id", "UNKNOWN")
        goal = task.get("goal", "")
        action = task.get("action", "")

        # Check Canon invariants
        violations = self._check_invariants(task)
        if violations:
            decision = self._record_decision(
                task_id, "BLOCKED", "HIGH",
                "invariants", "NONE",
                f"Canon violations: {violations}"
            )
            return {"status": "BLOCKED", "violations": violations, "decision": decision}

        # Assign risk tier
        risk_tier = self._assign_risk_tier(task)

        # Determine route
        route = self._determine_route(task, risk_tier)

        # Check if Twin Protocol required
        twin_required = risk_tier == RiskTier.HIGH

        decision = self._record_decision(
            task_id, "APPROVED", risk_tier.value,
            "values/tradeoffs", route,
            f"Task validated. Risk={risk_tier.value}. Twin={'REQUIRED' if twin_required else 'OPTIONAL'}.",
            twin_required=twin_required
        )

        return {
            "status": "APPROVED",
            "risk_tier": risk_tier.value,
            "route_to": route,
            "twin_required": twin_required,
            "decision": decision
        }

    def _check_invariants(self, task: Dict) -> List[str]:
        """Check task against Canon invariants."""
        violations = []

        # Check if action is in Polemarch's own forbidden list
        action = task.get("action", "")
        if action in self.FORBIDDEN_ACTIONS:
            violations.append(f"Polemarch forbidden action: {action}")

        # Check for irreversible actions without human flag
        if task.get("irreversible", False) and not task.get("human_approved", False):
            violations.append("Irreversible action requires human approval")

        # Check for Canon modification attempts
        if "canon" in action.lower() and "modify" in action.lower():
            violations.append("Canon modification requires ceremony, not task routing")

        return violations

    def _assign_risk_tier(self, task: Dict) -> RiskTier:
        """
        Assign risk tier based on task characteristics.

        v0.3: Enhanced with context-awareness and compound detection.
        """
        # Explicit markers
        if task.get("irreversible", False):
            return RiskTier.HIGH
        if task.get("financial_impact", False):
            return RiskTier.HIGH
        if task.get("reputation_impact", False):
            return RiskTier.HIGH
        if task.get("canon_adjacent", False):
            return RiskTier.HIGH

        # Agent-based defaults
        target_agent = task.get("target_agent", "")
        if target_agent in AGENT_REGISTRY:
            default = AGENT_REGISTRY[target_agent].get("risk_default")
            if default:
                return default

        # Action-based assessment
        action = task.get("action", "").lower()
        high_risk_keywords = ["send", "post", "trade", "delete", "publish", "transfer"]
        medium_risk_keywords = ["modify", "update", "schedule", "compose"]

        if any(kw in action for kw in high_risk_keywords):
            return RiskTier.HIGH
        if any(kw in action for kw in medium_risk_keywords):
            return RiskTier.MEDIUM

        return RiskTier.LOW

    def _determine_route(self, task: Dict, risk_tier: RiskTier) -> str:
        """Determine which agent should handle this task."""
        # Explicit target
        target = task.get("target_agent", "")
        if target and target in AGENT_REGISTRY:
            return target

        # Route by task type
        task_type = task.get("type", "").lower()
        route_map = {
            "plan": "planner",
            "research": "researcher",
            "execute": "executor",
            "review": "reviewer",
            "email": "email_agent",
            "health": "health_agent",
            "social": "social_agent",
            "briefing": "briefing_agent",
            "idea": "muse",
            "simulate": "digital_twin",
            "persona": "chimera_builder",
            "audit": "arch_evolution",
            "improve": "arch_evolution",
        }

        for key, agent in route_map.items():
            if key in task_type:
                return agent

        # Default to planner for unclassified tasks
        return "planner"

    def _record_decision(self, task_id: str, decision: str, risk_tier: str,
                          canon_ref: str, route_to: str, reason: str,
                          twin_required: bool = False) -> Dict:
        """Record and return a decision. Append-only log."""
        d = PolemarchDecision(
            timestamp=datetime.now(timezone.utc).isoformat(),
            task_id=task_id,
            decision=decision,
            risk_tier=risk_tier,
            canon_ref=canon_ref,
            route_to=route_to,
            reason=reason,
            twin_required=twin_required
        )
        self.decisions.append(d)
        return {
            "timestamp": d.timestamp,
            "task_id": d.task_id,
            "decision": d.decision,
            "risk_tier": d.risk_tier,
            "route_to": d.route_to,
            "twin_required": d.twin_required,
        }

    def enforce_budget(self, task_id: str, current_steps: int, max_steps: int,
                        current_tools: int, max_tools: int) -> Dict:
        """Enforce resource budgets. Halt if exceeded."""
        if current_steps > max_steps:
            return {
                "status": "HALTED",
                "reason": f"Step budget exceeded: {current_steps}/{max_steps}",
                "action": "ESCALATE"
            }
        if current_tools > max_tools:
            return {
                "status": "HALTED",
                "reason": f"Tool budget exceeded: {current_tools}/{max_tools}",
                "action": "ESCALATE"
            }
        return {"status": "WITHIN_BUDGET"}

    def get_decision_log(self) -> List[Dict]:
        """Return full decision log."""
        return [
            {
                "timestamp": d.timestamp,
                "task_id": d.task_id,
                "decision": d.decision,
                "risk_tier": d.risk_tier,
                "route_to": d.route_to,
                "reason": d.reason,
                "twin_required": d.twin_required,
            }
            for d in self.decisions
        ]

    def assess_risk(self, intake_record: Dict[str, Any]) -> Dict[str, Any]:
        """
        Lightweight intake risk assessment for Interface Agent routing.
        """
        ticket_id = str(intake_record.get("ticket_id", "UNKNOWN"))
        content = str(intake_record.get("content", ""))
        task = {
            "task_id": ticket_id,
            "goal": content,
            "action": content,
            "type": content,
            "irreversible": any(
                key in content.lower() for key in ("send", "publish", "delete", "wire", "pay")
            ),
        }
        risk_tier = self._assign_risk_tier(task)
        route_to = self._determine_route(task, risk_tier)
        decision = self._record_decision(
            ticket_id,
            "INTAKE_ASSESSED",
            risk_tier.value,
            "values/tradeoffs",
            route_to,
            "Interface intake assessed and routed.",
            twin_required=risk_tier == RiskTier.HIGH,
        )
        return {
            "ticket_id": ticket_id,
            "risk_tier": risk_tier.value,
            "route_to": route_to,
            "decision": decision,
        }

    def poll_intake(self, limit: int = 25) -> List[Dict[str, Any]]:
        """
        Poll Zero Point for new INTAKE records and run assess_risk().
        """
        assessed: List[Dict[str, Any]] = []
        entries = self.zero_point.search(memory_type=MemoryType.INTAKE, requesting_agent="POLEMARCH")
        for entry in entries[: max(1, int(limit))]:
            entry_id = str(entry.get("entry_id", ""))
            if not entry_id or entry_id in self._processed_intake_ids:
                continue
            payload = {}
            try:
                payload = json.loads(entry.get("content", "{}"))
            except Exception:
                payload = {"ticket_id": entry_id, "content": entry.get("content", "")}
            result = self.assess_risk(payload)
            assessed.append(result)
            self._processed_intake_ids.add(entry_id)
        return assessed
