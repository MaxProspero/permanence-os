"""
Permanence OS — Architecture Evolution Agent v0.3
Special Agent: Core IP Continuous Improvement Engine

Responsible for benchmarking, auditing, and proposing improvements to
the 5 core IP components:
1. Hierarchical Governance State Machine
2. Memory Architecture with Provenance
3. Canon Amendment Ceremony
4. Risk-Tier Assignment Algorithms
5. Compression Layer Implementation

This agent ensures these components are "in tip top shape and constantly improving."
"""

import json
import os
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict


@dataclass
class ComponentAudit:
    """Audit result for a single core IP component."""
    audit_id: str
    component_name: str
    audited_at: str
    health_score: float          # 0.0 - 1.0
    strengths: List[str]
    weaknesses: List[str]
    improvement_opportunities: List[str]
    failure_modes_detected: List[str]
    benchmark_results: Dict      # Component-specific metrics
    recommendation: str          # "HEALTHY" | "NEEDS_ATTENTION" | "CRITICAL"


@dataclass
class EvolutionProposal:
    """Specific improvement proposal for a core IP component."""
    proposal_id: str
    component: str
    title: str
    current_state: str
    proposed_state: str
    expected_improvement: str
    risk_of_change: str          # LOW | MEDIUM | HIGH
    implementation_steps: List[str]
    rollback_plan: str
    created_at: str
    status: str = "PROPOSED"     # PROPOSED | APPROVED | IMPLEMENTED | ROLLED_BACK


# Benchmark definitions for each core IP component
COMPONENT_BENCHMARKS = {
    "Governance State Machine": {
        "metrics": [
            {"name": "routing_accuracy", "target": 0.95, "weight": 0.3,
             "description": "% of tasks routed to correct agent"},
            {"name": "risk_tier_accuracy", "target": 0.90, "weight": 0.25,
             "description": "% of tasks correctly risk-classified"},
            {"name": "escalation_appropriateness", "target": 0.85, "weight": 0.2,
             "description": "% of escalations that were actually needed"},
            {"name": "stage_transition_clean", "target": 0.98, "weight": 0.15,
             "description": "% of state transitions without errors"},
            {"name": "mean_routing_steps", "target": 3.0, "weight": 0.1,
             "description": "Average steps from input to correct agent (lower = better)"},
        ],
        "failure_patterns": [
            "Authority creep — agent exceeding role boundaries",
            "Routing loops — task bouncing between agents",
            "Silent failures — errors not propagating to logs",
            "Over-escalation — too many tasks reaching human",
            "Under-escalation — HIGH-risk tasks not flagged",
        ]
    },
    "Provenance Memory": {
        "metrics": [
            {"name": "provenance_completeness", "target": 1.0, "weight": 0.3,
             "description": "% of memories with full provenance"},
            {"name": "source_diversity", "target": 0.7, "weight": 0.2,
             "description": "% of entries with 2+ independent sources"},
            {"name": "staleness_rate", "target": 0.1, "weight": 0.2,
             "description": "% of entries flagged stale (lower = better)"},
            {"name": "confidence_calibration", "target": 0.85, "weight": 0.2,
             "description": "How well confidence scores match actual accuracy"},
            {"name": "retrieval_relevance", "target": 0.80, "weight": 0.1,
             "description": "% of retrieved memories relevant to query"},
        ],
        "failure_patterns": [
            "Memory corruption — contradictory entries",
            "Provenance forgery — fabricated sources",
            "Stale accumulation — old data never refreshed",
            "Confidence inflation — LOW evidence rated HIGH",
            "Memory bloat — too many entries, slow retrieval",
        ]
    },
    "Canon Amendment Ceremony": {
        "metrics": [
            {"name": "ceremony_compliance", "target": 1.0, "weight": 0.35,
             "description": "% of changes following full ceremony"},
            {"name": "impact_analysis_done", "target": 1.0, "weight": 0.25,
             "description": "% of amendments with impact analysis"},
            {"name": "rollback_available", "target": 1.0, "weight": 0.2,
             "description": "% of amendments with rollback plans"},
            {"name": "drift_detection_rate", "target": 0.9, "weight": 0.2,
             "description": "% of informal changes caught by detection"},
        ],
        "failure_patterns": [
            "Silent amendments — changes without ceremony",
            "Canon drift — informal rule evolution",
            "Ceremony fatigue — skipping steps under pressure",
            "Amendment conflicts — new rules contradicting existing",
            "Version confusion — agents reading different Canon versions",
        ]
    },
    "Risk-Tier Algorithms": {
        "metrics": [
            {"name": "classification_accuracy", "target": 0.90, "weight": 0.3,
             "description": "% of tasks correctly risk-classified"},
            {"name": "false_high_rate", "target": 0.15, "weight": 0.2,
             "description": "% of LOW tasks classified HIGH (lower = better)"},
            {"name": "missed_high_rate", "target": 0.05, "weight": 0.3,
             "description": "% of HIGH tasks classified LOW (lower = better, CRITICAL)"},
            {"name": "context_sensitivity", "target": 0.80, "weight": 0.1,
             "description": "Does same task get different risk at 2 AM vs 2 PM?"},
            {"name": "compound_detection", "target": 0.70, "weight": 0.1,
             "description": "Detects multiple LOWs compounding to MEDIUM"},
        ],
        "failure_patterns": [
            "Static classification — ignoring context",
            "Risk inflation — everything becomes HIGH",
            "Risk deflation — dangerous normalization of risk",
            "Compound blindness — missing cascading risks",
            "Temporal blindness — same risk regardless of timing",
        ]
    },
    "Compression Layer": {
        "metrics": [
            {"name": "pattern_extraction_rate", "target": 0.7, "weight": 0.25,
             "description": "% of repeated experiences converted to patterns"},
            {"name": "principle_accuracy", "target": 0.85, "weight": 0.25,
             "description": "% of extracted principles that hold under testing"},
            {"name": "compression_ratio", "target": 10.0, "weight": 0.2,
             "description": "Ratio of raw data to compressed principles (higher = better)"},
            {"name": "actionability", "target": 0.80, "weight": 0.2,
             "description": "% of compressed outputs that lead to concrete actions"},
            {"name": "variance_survival", "target": 0.75, "weight": 0.1,
             "description": "% of compressed rules that work under stress/variance"},
        ],
        "failure_patterns": [
            "Over-compression — losing essential nuance",
            "Under-compression — accumulating without extracting",
            "Premature compression — compressing before enough data",
            "Brittle rules — principles that break under variance",
            "Abstraction addiction — frameworks without implementation",
        ]
    },
}


class ArchitectureEvolutionAgent:
    """
    Architecture Evolution Agent.

    Continuously audits and improves the 5 core IP components.
    Generates benchmarks, detects degradation, and proposes improvements.
    """

    ROLE = "ARCH_EVOLUTION"
    ROLE_DESCRIPTION = "Core IP continuous improvement engine"
    ALLOWED_TOOLS = ["read_canon", "read_zero_point", "read_episodic_memory",
                     "read_system_metrics", "write_proposal"]
    FORBIDDEN_ACTIONS = [
        "modify_canon_directly",
        "modify_agents",
        "execute_changes",
        "bypass_ceremony",
    ]
    DEPARTMENT = "SPECIAL"

    def __init__(self, storage_path: str = "memory/arch_evolution.json"):
        self.storage_path = storage_path
        self.audit_history: List[ComponentAudit] = []
        self.evolution_proposals: List[EvolutionProposal] = []
        self._audit_count = 0
        self._proposal_count = 0

    def _gen_audit_id(self) -> str:
        self._audit_count += 1
        return f"AUDIT-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{self._audit_count:04d}"

    def _gen_proposal_id(self) -> str:
        self._proposal_count += 1
        return f"EVO-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{self._proposal_count:04d}"

    def audit_component(self, component_name: str,
                         current_metrics: Optional[Dict] = None,
                         recent_failures: Optional[List[Dict]] = None) -> ComponentAudit:
        """
        Run a full audit of a core IP component.

        Args:
            component_name: One of the 5 core IP components
            current_metrics: Actual metric values (from system monitoring)
            recent_failures: Recent failure events for this component
        """
        benchmarks = COMPONENT_BENCHMARKS.get(component_name)
        if not benchmarks:
            raise ValueError(f"Unknown component: {component_name}")

        now = datetime.now(timezone.utc).isoformat()
        audit_id = self._gen_audit_id()
        metrics = current_metrics or {}
        failures = recent_failures or []

        # Score each metric
        benchmark_results = {}
        total_score = 0.0
        total_weight = 0.0

        for metric in benchmarks["metrics"]:
            name = metric["name"]
            target = metric["target"]
            weight = metric["weight"]
            actual = metrics.get(name)

            if actual is not None:
                # Score: how close to target (1.0 = perfect)
                if target > 0:
                    score = min(1.0, actual / target)
                else:
                    score = 1.0 if actual <= target else max(0, 1 - actual)

                benchmark_results[name] = {
                    "target": target,
                    "actual": actual,
                    "score": round(score, 3),
                    "status": "PASS" if score >= 0.8 else "WARN" if score >= 0.5 else "FAIL"
                }
                total_score += score * weight
                total_weight += weight
            else:
                benchmark_results[name] = {
                    "target": target,
                    "actual": None,
                    "score": None,
                    "status": "NO_DATA"
                }

        health_score = round(total_score / total_weight, 3) if total_weight > 0 else 0.0

        # Identify strengths and weaknesses
        strengths = [
            f"{name}: {r['actual']} (target: {r['target']})"
            for name, r in benchmark_results.items()
            if r["status"] == "PASS"
        ]

        weaknesses = [
            f"{name}: {r['actual']} vs target {r['target']}"
            for name, r in benchmark_results.items()
            if r["status"] in ("WARN", "FAIL")
        ]

        # Detect failure patterns
        detected_patterns = []
        for pattern in benchmarks.get("failure_patterns", []):
            # In production: match against actual failure data
            for failure in failures:
                if any(keyword in str(failure).lower()
                       for keyword in pattern.lower().split()[:3]):
                    detected_patterns.append(pattern)
                    break

        # Generate improvement opportunities
        opportunities = []
        for name, r in benchmark_results.items():
            if r["status"] in ("WARN", "FAIL"):
                opportunities.append(
                    f"Improve {name} from {r['actual']} to target {r['target']}"
                )

        # Determine recommendation
        if health_score >= 0.85:
            recommendation = "HEALTHY"
        elif health_score >= 0.60:
            recommendation = "NEEDS_ATTENTION"
        else:
            recommendation = "CRITICAL"

        audit = ComponentAudit(
            audit_id=audit_id,
            component_name=component_name,
            audited_at=now,
            health_score=health_score,
            strengths=strengths,
            weaknesses=weaknesses,
            improvement_opportunities=opportunities,
            failure_modes_detected=detected_patterns,
            benchmark_results=benchmark_results,
            recommendation=recommendation
        )

        self.audit_history.append(audit)
        return audit

    def run_full_system_audit(self, all_metrics: Optional[Dict] = None,
                               all_failures: Optional[Dict] = None) -> Dict:
        """
        Audit ALL 5 core IP components at once.
        Returns system-wide health assessment.
        """
        all_metrics = all_metrics or {}
        all_failures = all_failures or {}
        results = {}

        for component_name in COMPONENT_BENCHMARKS:
            metrics = all_metrics.get(component_name, {})
            failures = all_failures.get(component_name, [])
            audit = self.audit_component(component_name, metrics, failures)
            results[component_name] = {
                "health_score": audit.health_score,
                "recommendation": audit.recommendation,
                "weaknesses": len(audit.weaknesses),
                "failure_modes": len(audit.failure_modes_detected),
                "opportunities": len(audit.improvement_opportunities),
            }

        # System-wide health
        scores = [r["health_score"] for r in results.values()]
        avg_health = round(sum(scores) / len(scores), 3) if scores else 0.0

        critical_count = sum(
            1 for r in results.values() if r["recommendation"] == "CRITICAL"
        )

        return {
            "system_health": avg_health,
            "system_status": "CRITICAL" if critical_count > 0 else
                            "NEEDS_ATTENTION" if avg_health < 0.85 else "HEALTHY",
            "components": results,
            "critical_components": critical_count,
            "total_weaknesses": sum(r["weaknesses"] for r in results.values()),
            "total_opportunities": sum(r["opportunities"] for r in results.values()),
            "audited_at": datetime.now(timezone.utc).isoformat()
        }

    def propose_evolution(self, component: str, title: str,
                           current_state: str, proposed_state: str,
                           expected_improvement: str,
                           implementation_steps: List[str],
                           rollback_plan: str,
                           risk_of_change: str = "MEDIUM") -> Dict:
        """
        Propose a specific evolution to a core IP component.
        Proposals require Canon ceremony for implementation.
        """
        proposal = EvolutionProposal(
            proposal_id=self._gen_proposal_id(),
            component=component,
            title=title,
            current_state=current_state,
            proposed_state=proposed_state,
            expected_improvement=expected_improvement,
            risk_of_change=risk_of_change,
            implementation_steps=implementation_steps,
            rollback_plan=rollback_plan,
            created_at=datetime.now(timezone.utc).isoformat()
        )

        self.evolution_proposals.append(proposal)

        return {
            "status": "PROPOSED",
            "proposal_id": proposal.proposal_id,
            "component": component,
            "risk": risk_of_change,
            "note": "Requires Canon ceremony and human approval for implementation."
        }

    def get_evolution_dashboard(self) -> Dict:
        """Dashboard view of all architecture evolution activity."""
        return {
            "total_audits": len(self.audit_history),
            "total_proposals": len(self.evolution_proposals),
            "proposals_by_status": {
                status: sum(1 for p in self.evolution_proposals if p.status == status)
                for status in ["PROPOSED", "APPROVED", "IMPLEMENTED", "ROLLED_BACK"]
            },
            "recent_audits": [
                {
                    "component": a.component_name,
                    "health": a.health_score,
                    "recommendation": a.recommendation,
                    "date": a.audited_at
                }
                for a in self.audit_history[-5:]
            ],
            "top_proposals": [
                {
                    "id": p.proposal_id,
                    "component": p.component,
                    "title": p.title,
                    "risk": p.risk_of_change,
                    "status": p.status
                }
                for p in self.evolution_proposals
                if p.status == "PROPOSED"
            ][:5]
        }
