"""
Permanence OS — Digital Twin Simulator v0.3
Special Agent: Shadow Execution Engine

Before any HIGH-risk action executes in reality, the Twin runs it
in simulation and reports predicted outcomes.

The Twin is the "what if" engine. The real agent is the "do it" engine.
The Twin catches what confidence might miss.
"""

import json
import copy
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum


class SimulationResult(Enum):
    SAFE = "SAFE"                   # Proceed with execution
    CAUTION = "CAUTION"             # Proceed with monitoring
    DANGEROUS = "DANGEROUS"         # Block execution, escalate
    UNKNOWN = "UNKNOWN"             # Insufficient data to simulate


@dataclass
class SimulationReport:
    """Output of a Digital Twin simulation run."""
    simulation_id: str
    original_task_id: str
    agent_id: str
    simulated_at: str

    # Inputs
    action: str
    context: Dict
    risk_tier: str

    # Simulation outputs
    result: str                     # SAFE | CAUTION | DANGEROUS | UNKNOWN
    predicted_outcomes: List[Dict]  # [{outcome, probability, impact}]
    side_effects: List[str]        # Predicted unintended consequences
    reversibility: str              # "fully_reversible" | "partially_reversible" | "irreversible"
    confidence_in_simulation: str   # HIGH | MEDIUM | LOW

    # Stress test results
    stress_scenarios: List[Dict]    # [{scenario, outcome}]

    # Recommendation
    recommendation: str             # "PROCEED" | "PROCEED_WITH_MONITORING" | "BLOCK" | "ESCALATE"
    escalation_reason: Optional[str] = None


class DigitalTwinSimulator:
    """
    Digital Twin Simulator.

    For every HIGH-risk task, the Twin:
    1. Creates a sandboxed copy of the task context
    2. Simulates execution against multiple scenarios
    3. Predicts outcomes with probability estimates
    4. Identifies side effects and reversibility
    5. Reports recommendation to Polemarch

    The Twin NEVER executes real actions. It only simulates.
    """

    ROLE = "DIGITAL_TWIN"
    ROLE_DESCRIPTION = "Shadow execution engine for pre-validation"
    ALLOWED_TOOLS = ["read_zero_point", "read_episodic_memory", "simulate"]
    FORBIDDEN_ACTIONS = [
        "execute_real_action",
        "send_external",
        "modify_state",
        "modify_canon",
        "bypass_simulation",
    ]
    DEPARTMENT = "SPECIAL"

    # Standard stress test scenarios
    STRESS_SCENARIOS = [
        {
            "id": "WORST_CASE",
            "name": "Worst Case",
            "description": "Everything that can go wrong does go wrong",
            "probability_modifier": 0.1
        },
        {
            "id": "2AM_TEST",
            "name": "2 AM Test",
            "description": "Execute during lowest energy/willpower state",
            "probability_modifier": 0.6
        },
        {
            "id": "CASCADE_FAILURE",
            "name": "Cascade Failure",
            "description": "This failure triggers downstream failures",
            "probability_modifier": 0.3
        },
        {
            "id": "ADVERSARIAL",
            "name": "Adversarial Input",
            "description": "Malicious or corrupted input data",
            "probability_modifier": 0.2
        },
        {
            "id": "RESOURCE_EXHAUSTION",
            "name": "Resource Exhaustion",
            "description": "Budget/time/API limits hit mid-execution",
            "probability_modifier": 0.4
        },
    ]

    def __init__(self, history_path: str = "memory/twin_history.json"):
        self.history_path = history_path
        self.simulation_history: List[SimulationReport] = []
        self._sim_count = 0

    def _generate_sim_id(self) -> str:
        self._sim_count += 1
        return f"SIM-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{self._sim_count:04d}"

    def simulate(self, task_id: str, action: str, context: Dict,
                 risk_tier: str, agent_id: str,
                 episodic_history: Optional[List[Dict]] = None,
                 zero_point_data: Optional[List[Dict]] = None) -> SimulationReport:
        """
        Run a full simulation of a proposed action.

        This is the core method. It:
        1. Sandboxes the context (deep copy, no mutations)
        2. Analyzes the action against historical outcomes
        3. Runs stress tests
        4. Computes prediction confidence
        5. Returns recommendation
        """
        now = datetime.now(timezone.utc).isoformat()
        sim_id = self._generate_sim_id()

        # Step 1: Sandbox the context
        sandboxed_context = copy.deepcopy(context)

        # Step 2: Analyze against history
        predicted_outcomes = self._predict_outcomes(
            action, sandboxed_context, episodic_history or []
        )

        # Step 3: Identify side effects
        side_effects = self._identify_side_effects(
            action, sandboxed_context, predicted_outcomes
        )

        # Step 4: Assess reversibility
        reversibility = self._assess_reversibility(action, sandboxed_context)

        # Step 5: Run stress tests
        stress_results = self._run_stress_tests(
            action, sandboxed_context, predicted_outcomes
        )

        # Step 6: Compute confidence in simulation
        sim_confidence = self._compute_simulation_confidence(
            episodic_history or [], zero_point_data or [],
            len(predicted_outcomes)
        )

        # Step 7: Generate recommendation
        result, recommendation, escalation_reason = self._generate_recommendation(
            predicted_outcomes, side_effects, reversibility,
            stress_results, risk_tier, sim_confidence
        )

        report = SimulationReport(
            simulation_id=sim_id,
            original_task_id=task_id,
            agent_id=agent_id,
            simulated_at=now,
            action=action,
            context=sandboxed_context,
            risk_tier=risk_tier,
            result=result,
            predicted_outcomes=predicted_outcomes,
            side_effects=side_effects,
            reversibility=reversibility,
            confidence_in_simulation=sim_confidence,
            stress_scenarios=stress_results,
            recommendation=recommendation,
            escalation_reason=escalation_reason,
        )

        self.simulation_history.append(report)
        return report

    def _predict_outcomes(self, action: str, context: Dict,
                          history: List[Dict]) -> List[Dict]:
        """
        Predict outcomes based on historical patterns.

        In production: This uses LLM inference + episodic memory matching.
        Current implementation: Framework with pattern matching scaffolding.
        """
        outcomes = []

        # Check for similar past actions in episodic history
        similar_actions = [
            h for h in history
            if action.lower() in str(h).lower()
        ]

        if similar_actions:
            # We have precedent
            success_count = sum(
                1 for h in similar_actions
                if h.get("outcome", "").lower() in ("success", "pass", "completed")
            )
            total = len(similar_actions)
            success_rate = success_count / total if total > 0 else 0.5

            outcomes.append({
                "outcome": "SUCCESS",
                "probability": round(success_rate, 2),
                "impact": "positive",
                "based_on": f"{total} similar historical actions"
            })
            outcomes.append({
                "outcome": "FAILURE",
                "probability": round(1 - success_rate, 2),
                "impact": "negative",
                "based_on": f"{total} similar historical actions"
            })
        else:
            # No precedent — uncertain
            outcomes.append({
                "outcome": "SUCCESS",
                "probability": 0.5,
                "impact": "positive",
                "based_on": "no historical precedent — default uncertainty"
            })
            outcomes.append({
                "outcome": "FAILURE",
                "probability": 0.5,
                "impact": "negative",
                "based_on": "no historical precedent — default uncertainty"
            })

        return outcomes

    def _identify_side_effects(self, action: str, context: Dict,
                                outcomes: List[Dict]) -> List[str]:
        """Identify potential unintended consequences."""
        effects = []

        # Check for external side effects
        if context.get("sends_external", False):
            effects.append("External communication — cannot be unsent")
        if context.get("modifies_data", False):
            effects.append("Data modification — may affect downstream processes")
        if context.get("financial_impact", False):
            effects.append("Financial transaction — real money at risk")
        if context.get("reputation_impact", False):
            effects.append("Public-facing — reputation consequences")

        if not effects:
            effects.append("No identified side effects (review manually)")

        return effects

    def _assess_reversibility(self, action: str, context: Dict) -> str:
        """Assess whether the action can be undone."""
        irreversible_markers = [
            "send_email", "post_social", "execute_trade",
            "delete_data", "publish", "transfer_funds"
        ]

        if any(marker in action.lower() for marker in irreversible_markers):
            return "irreversible"

        if context.get("modifies_data", False):
            return "partially_reversible"

        return "fully_reversible"

    def _run_stress_tests(self, action: str, context: Dict,
                          base_outcomes: List[Dict]) -> List[Dict]:
        """Run action through standard stress scenarios."""
        results = []

        for scenario in self.STRESS_SCENARIOS:
            # Apply stress modifier to base outcomes
            stressed_outcomes = []
            for outcome in base_outcomes:
                stressed = copy.deepcopy(outcome)
                if stressed["impact"] == "negative":
                    # Stress increases probability of negative outcomes
                    stressed["probability"] = min(
                        1.0,
                        stressed["probability"] + scenario["probability_modifier"]
                    )
                else:
                    stressed["probability"] = max(
                        0.0,
                        stressed["probability"] - scenario["probability_modifier"]
                    )
                stressed_outcomes.append(stressed)

            # Determine if action survives this stress test
            max_negative_prob = max(
                (o["probability"] for o in stressed_outcomes if o["impact"] == "negative"),
                default=0
            )

            results.append({
                "scenario": scenario["name"],
                "description": scenario["description"],
                "survives": max_negative_prob < 0.7,
                "max_failure_probability": round(max_negative_prob, 2),
                "note": "PASSES" if max_negative_prob < 0.7 else "FAILS — review required"
            })

        return results

    def _compute_simulation_confidence(self, history: List[Dict],
                                        zero_point: List[Dict],
                                        outcome_count: int) -> str:
        """How confident are we in the simulation itself?"""
        score = 0

        # More historical data = higher confidence
        if len(history) > 10:
            score += 3
        elif len(history) > 3:
            score += 2
        elif len(history) > 0:
            score += 1

        # Zero Point data adds confidence
        if len(zero_point) > 5:
            score += 2
        elif len(zero_point) > 0:
            score += 1

        # More predicted outcomes = more thorough
        if outcome_count >= 3:
            score += 1

        if score >= 5:
            return "HIGH"
        elif score >= 3:
            return "MEDIUM"
        return "LOW"

    def _generate_recommendation(self, outcomes, side_effects, reversibility,
                                  stress_results, risk_tier, confidence) -> tuple:
        """Generate final recommendation based on all simulation data."""
        # Count stress test failures
        stress_failures = sum(1 for s in stress_results if not s.get("survives", True))

        # Check for irreversibility
        is_irreversible = reversibility == "irreversible"

        # Check for dangerous side effects
        dangerous_effects = [e for e in side_effects if "cannot" in e.lower() or "real money" in e.lower()]

        # Decision logic
        if stress_failures >= 3 or (is_irreversible and confidence == "LOW"):
            return (
                SimulationResult.DANGEROUS.value,
                "BLOCK",
                f"Failed {stress_failures}/5 stress tests. Irreversible={is_irreversible}. Confidence={confidence}."
            )

        if stress_failures >= 2 or (is_irreversible and risk_tier == "HIGH"):
            return (
                SimulationResult.CAUTION.value,
                "ESCALATE",
                f"Failed {stress_failures}/5 stress tests. Risk={risk_tier}. Requires human review."
            )

        if stress_failures >= 1 or dangerous_effects:
            return (
                SimulationResult.CAUTION.value,
                "PROCEED_WITH_MONITORING",
                f"Minor concerns: {stress_failures} stress failures, {len(dangerous_effects)} side effects."
            )

        return (SimulationResult.SAFE.value, "PROCEED", None)

    def get_simulation_summary(self) -> Dict:
        """Summary stats for all simulations."""
        total = len(self.simulation_history)
        if total == 0:
            return {"total_simulations": 0}

        results = {}
        for report in self.simulation_history:
            results[report.result] = results.get(report.result, 0) + 1

        recommendations = {}
        for report in self.simulation_history:
            recommendations[report.recommendation] = \
                recommendations.get(report.recommendation, 0) + 1

        return {
            "total_simulations": total,
            "results": results,
            "recommendations": recommendations,
            "block_rate": round(
                recommendations.get("BLOCK", 0) / total * 100, 1
            )
        }
