#!/usr/bin/env python3
"""
Governed task runner: Polemarch -> Planner -> Researcher -> Executor -> Reviewer -> Conciliator.
"""

import argparse
import json
import os
import sys
from dataclasses import asdict
from typing import Any, Dict, List, Optional

from agents.king_bot import Polemarch, RiskTier, Stage, Status
from agents.planner import PlannerAgent
from agents.researcher import ResearcherAgent
from agents.executor import ExecutorAgent
from agents.reviewer import ReviewerAgent
from agents.conciliator import ConciliatorAgent
from agents.compliance_gate import ComplianceGate
from agents.identity import select_identity_for_goal
from agents.utils import log, BASE_DIR

MEMORY_DIR = os.getenv("PERMANENCE_MEMORY_DIR", os.path.join(BASE_DIR, "memory"))
WORKING_DIR = os.path.join(MEMORY_DIR, "working")
SOURCES_PATH = os.getenv(
    "PERMANENCE_SOURCES_PATH", os.path.join(WORKING_DIR, "sources.json")
)
DRAFT_PATH = os.getenv(
    "PERMANENCE_DRAFT_PATH", os.path.join(WORKING_DIR, "draft.md")
)


def _is_irreversible(goal: str) -> bool:
    goal_lower = goal.lower()
    markers = ["publish", "post", "send", "delete", "commit", "sign", "wire", "pay"]
    return any(m in goal_lower for m in markers)


def _is_external_action(goal: str) -> bool:
    goal_lower = goal.lower()
    markers = ["publish", "post", "send", "email", "announce", "press", "public"]
    return any(m in goal_lower for m in markers)


def _load_sources(path: str) -> Optional[List[Dict[str, Any]]]:
    if not os.path.exists(path):
        return None
    with open(path, "r") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError("Sources file must contain a list of source records")
    return data


def _save_json(obj: Any, path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(obj, f, indent=2)


def run_task(goal: str, sources_path: Optional[str] = None, draft_path: Optional[str] = None) -> int:
    sources_path = sources_path or SOURCES_PATH
    draft_path = draft_path or DRAFT_PATH

    if not goal:
        print("Error: task goal is empty")
        return 2

    polemarch = Polemarch()
    state = polemarch.initialize_task(goal)
    if state:
        state.status = Status.RUNNING
    polemarch.transition_stage(Stage.VALIDATION)

    validation = polemarch.validate_against_canon(goal)
    if not validation["valid"]:
        polemarch.halt(f"Canon violation: {validation['reason']}")
        return 1

    risk = polemarch.assign_risk_tier(goal)
    state.risk_tier = risk

    if risk == RiskTier.HIGH:
        polemarch.escalate("High-risk task requires human approval")
        polemarch.save_state()
        return 3

    budget_check = polemarch.check_budgets()
    if not budget_check["within_budget"]:
        polemarch.halt("Budget exceeded before execution")
        return 1

    polemarch.transition_stage(Stage.PLANNING)
    polemarch.route_to_agent("planner")
    budget_check = polemarch.check_budgets()
    if not budget_check["within_budget"]:
        polemarch.halt("Budget exceeded during planning")
        return 1
    planner = PlannerAgent(polemarch.canon)
    spec = planner.create_plan(goal)
    spec_dict = asdict(spec)

    spec_path = os.path.join(WORKING_DIR, f"{state.task_id}_spec.json")
    _save_json(spec_dict, spec_path)
    if state:
        state.artifacts["spec"] = spec_path

    polemarch.transition_stage(Stage.RESEARCH)
    polemarch.route_to_agent("researcher")
    budget_check = polemarch.check_budgets()
    if not budget_check["within_budget"]:
        polemarch.halt("Budget exceeded during research")
        return 1
    researcher = ResearcherAgent()
    try:
        sources = _load_sources(sources_path)
    except (ValueError, json.JSONDecodeError) as exc:
        polemarch.escalate(f"Sources file invalid: {exc}")
        polemarch.save_state()
        return 4
    if sources is None:
        polemarch.escalate(
            f"Sources missing. Provide a provenance list at {sources_path} (or run cli.py ingest)."
        )
        polemarch.save_state()
        return 4

    validation = researcher.validate_sources(sources)
    if not validation["ok"]:
        polemarch.escalate("Sources missing provenance fields")
        polemarch.save_state()
        return 4

    if state:
        state.sources = sources

    polemarch.transition_stage(Stage.EXECUTION)
    polemarch.route_to_agent("executor")
    budget_check = polemarch.check_budgets()
    if not budget_check["within_budget"]:
        polemarch.halt("Budget exceeded during execution")
        return 1
    executor = ExecutorAgent()
    inputs: Dict[str, Any] = {"sources": sources}
    if os.path.exists(draft_path):
        inputs["draft_path"] = draft_path
    exec_result = executor.execute(spec_dict, inputs=inputs)
    if state:
        state.artifacts["output"] = exec_result.artifact

    polemarch.transition_stage(Stage.OUTPUT_REVIEW)
    polemarch.route_to_agent("reviewer")
    budget_check = polemarch.check_budgets()
    if not budget_check["within_budget"]:
        polemarch.halt("Budget exceeded during review")
        return 1
    reviewer = ReviewerAgent()
    review_result = reviewer.review(exec_result.artifact, spec_dict)

    if review_result.approved:
        gate = ComplianceGate()
        identity_used = select_identity_for_goal(goal)
        action = {
            "goal": goal,
            "identity_used": identity_used,
            "risk_tier": risk.value if hasattr(risk, "value") else str(risk),
            "external_action": _is_external_action(goal),
            "irreversible": _is_irreversible(goal),
            "output_path": exec_result.artifact,
        }
        compliance = gate.review(action)
        if state:
            state.artifacts["compliance"] = {
                "verdict": compliance.verdict,
                "reasons": compliance.reasons,
            }

        if compliance.verdict == "HOLD":
            polemarch.escalate("Compliance Gate HOLD: " + "; ".join(compliance.reasons))
            polemarch.save_state()
            return 5
        if compliance.verdict == "REJECT":
            polemarch.halt("Compliance Gate REJECT: " + "; ".join(compliance.reasons))
            return 5

    polemarch.transition_stage(Stage.CONCILIATION)
    polemarch.route_to_agent("conciliator")
    budget_check = polemarch.check_budgets()
    if not budget_check["within_budget"]:
        polemarch.halt("Budget exceeded during conciliation")
        return 1
    conciliator = ConciliatorAgent()
    decision = conciliator.decide(review_result, retry_count=0, max_retries=2)

    if decision.decision == "ACCEPT" and review_result.approved:
        if state:
            state.status = Status.DONE
            state.stage = Stage.DONE
        log("Task completed successfully", level="INFO")
        polemarch.save_state()
        return 0

    if decision.decision == "ESCALATE":
        polemarch.escalate(decision.reason)
        polemarch.save_state()
        return 5

    log("Retry recommended; update inputs and re-run", level="WARNING")
    polemarch.save_state()
    return 6


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a governed task workflow.")
    parser.add_argument("goal", nargs="+", help="Task goal")
    parser.add_argument("--sources", dest="sources_path", help="Override sources.json path")
    parser.add_argument("--draft", dest="draft_path", help="Override draft.md path")

    args = parser.parse_args()
    goal = " ".join(args.goal).strip()
    return run_task(goal, sources_path=args.sources_path, draft_path=args.draft_path)


if __name__ == "__main__":
    raise SystemExit(main())
