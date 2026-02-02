#!/usr/bin/env python3
"""
Example: Complete workflow execution
"""

import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from agents.king_bot import Polemarch, RiskTier
from agents.planner import PlannerAgent
import yaml

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CANON_PATH = os.getenv(
    "PERMANENCE_CANON_PATH", os.path.join(BASE_DIR, "canon", "base_canon.yaml")
)


def run_example_workflow():
    """
    Demonstrate full workflow:
    1. Initialize task
    2. Validate against Canon
    3. Assign risk tier
    4. Create plan
    5. Route to execution
    """

    print("\n" + "=" * 60)
    print("PERMANENCE OS - EXAMPLE WORKFLOW")
    print("=" * 60 + "\n")

    # Initialize Polemarch
    polemarch = Polemarch()
    print("✓ Polemarch initialized\n")

    # Load Canon for Planner
    with open(CANON_PATH, "r") as f:
        canon = yaml.safe_load(f)
    planner = PlannerAgent(canon)
    print("✓ Planner Agent initialized\n")

    # Define task
    task_goal = "Research recent developments in AI governance and create a summary"
    print(f"📋 Task: {task_goal}\n")

    # Step 1: Initialize
    state = polemarch.initialize_task(task_goal)
    print(f"✓ Task initialized: {state.task_id}\n")

    # Step 2: Validate against Canon
    validation = polemarch.validate_against_canon(task_goal)
    print(f"✓ Canon validation: {validation['valid']}")
    print(f"  Reason: {validation['reason']}\n")

    if not validation["valid"]:
        polemarch.halt(f"Canon violation: {validation['reason']}")
        return

    # Step 3: Assign risk tier
    risk = polemarch.assign_risk_tier(task_goal)
    state.risk_tier = risk
    print(f"✓ Risk tier assigned: {risk.value}\n")

    # Step 4: Check budgets
    budget_check = polemarch.check_budgets()
    print(f"✓ Budget check: {budget_check['within_budget']}")
    print(f"  Steps: {budget_check['details']['steps']}")
    print(f"  Tools: {budget_check['details']['tools']}\n")

    if not budget_check["within_budget"]:
        polemarch.halt("Budget exceeded before execution")
        return

    # Step 5: Create plan
    print("📝 Creating task specification...\n")
    spec = planner.create_plan(task_goal)

    print(f"✓ Plan created: {spec.task_id}")
    print("\nDeliverables:")
    for d in spec.deliverables:
        print(f"  - {d}")
    print("\nSuccess Criteria:")
    for c in spec.success_criteria:
        print(f"  - {c}")
    print("\nEstimates:")
    print(f"  Steps: {spec.estimated_steps}")
    print(f"  Tool Calls: {spec.estimated_tool_calls}")
    print(f"  Falsifiable: {spec.falsifiable}\n")

    # Step 6: Route based on risk
    if risk == RiskTier.HIGH:
        escalation = polemarch.escalate("High-risk task requires human approval")
        print(f"⚠️  ESCALATED: {escalation['reason']}\n")
    else:
        routing = polemarch.route_to_agent("researcher")
        print(f"✓ Routed to agent: {routing['agent']}")
        print(f"  Instructions: {routing['instructions']}\n")

    # Step 7: Save state
    polemarch.save_state()
    print("✓ State saved\n")

    # Summary
    print("=" * 60)
    print("WORKFLOW COMPLETE")
    print(f"Final Stage: {state.stage.value}")
    print(f"Final Status: {state.status.value}")
    print(f"Steps Used: {state.step_count}/{state.max_steps}")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    run_example_workflow()
