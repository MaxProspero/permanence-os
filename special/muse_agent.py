"""
Permanence OS — Muse Agent (The Idea Agent) v0.3
Special Agent: Creative Exploration & System Improvement

The Muse generates. The Muse never executes.
All proposals enter the queue. Execution requires Polemarch routing + human approval.

This agent explores creativity, memory, and cross-domain patterns to propose
abstract and grand improvements to all parts of the system.

Canon Reference: CA-007 (Muse Containment)
"""

import json
import os
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict

# Import would be: from agents.base import BaseAgent, RiskTier
# For Codex: ensure this inherits from BaseAgent once integrated
try:
    from agents.base import BaseAgent, RiskTier
except ImportError:
    # Standalone mode for testing
    BaseAgent = object
    class RiskTier:
        LOW = "LOW"
        MEDIUM = "MEDIUM"
        HIGH = "HIGH"


@dataclass
class Proposal:
    """A single improvement proposal from the Muse."""
    proposal_id: str
    title: str
    description: str
    target_component: str          # Which system component this improves
    improvement_type: str          # "optimization" | "expansion" | "abstraction" | "synthesis" | "compression"
    inspiration_source: str        # Where the idea came from
    estimated_impact: str          # "incremental" | "significant" | "transformative"
    risk_tier: str                 # LOW | MEDIUM | HIGH
    implementation_sketch: str     # High-level how-to (not a plan — that's Planner's job)
    dependencies: List[str]        # What needs to exist first
    failure_modes: List[str]       # How this could go wrong
    created_at: str
    status: str = "PENDING"        # PENDING | APPROVED | REJECTED | DEFERRED
    human_notes: Optional[str] = None
    score: float = 0.0             # Computed priority score


class MuseExplorationMode:
    """Modes of creative exploration the Muse can operate in."""

    DIVERGENT = "DIVERGENT"        # Generate many varied ideas
    CONVERGENT = "CONVERGENT"      # Refine and combine existing ideas
    CROSS_DOMAIN = "CROSS_DOMAIN"  # Apply patterns from one domain to another
    FAILURE_MINING = "FAILURE_MINING"    # Extract improvement ideas from failure archive
    COMPRESSION = "COMPRESSION"    # Find ways to simplify existing complexity
    ABSTRACTION = "ABSTRACTION"    # Elevate concrete patterns to general principles


# The 5 core IP components the Muse should always be improving
CORE_IP_TARGETS = [
    {
        "name": "Governance State Machine",
        "description": "Hierarchical state machine with risk tiers and stage transitions",
        "improvement_vectors": [
            "Reduce routing latency",
            "Add new valid state transitions",
            "Improve risk-tier assignment accuracy",
            "Better failure detection in transitions",
        ]
    },
    {
        "name": "Provenance Memory",
        "description": "Memory architecture where all data has source, timestamp, confidence",
        "improvement_vectors": [
            "Cross-reference validation between memories",
            "Automatic confidence decay over time",
            "Source credibility scoring",
            "Memory deduplication and compression",
        ]
    },
    {
        "name": "Canon Amendment Ceremony",
        "description": "Formal process for modifying constitutional law",
        "improvement_vectors": [
            "Impact simulation before amendment",
            "Automated regression testing against existing invariants",
            "Amendment rollback mechanism",
            "Multi-stakeholder review process",
        ]
    },
    {
        "name": "Risk-Tier Algorithms",
        "description": "Classification of actions into LOW/MEDIUM/HIGH risk",
        "improvement_vectors": [
            "Context-aware dynamic risk assessment",
            "Historical outcome-based calibration",
            "Compound risk detection (multiple LOW = MEDIUM)",
            "Time-of-day risk adjustment (2 AM test integration)",
        ]
    },
    {
        "name": "Compression Layer",
        "description": "Converting complexity into actionable principles",
        "improvement_vectors": [
            "Automatic pattern extraction from episodic memory",
            "Principle-to-heuristic compilation",
            "Cross-agent compression (shared learnings)",
            "Lossy vs lossless compression modes",
        ]
    },
]

# Cross-domain inspiration sources
INSPIRATION_DOMAINS = [
    "neuroscience",
    "trading_systems",
    "military_strategy",
    "biological_evolution",
    "information_theory",
    "network_architecture",
    "game_theory",
    "thermodynamics",
    "music_theory",
    "urban_planning",
    "immune_systems",
    "mycorrhizal_networks",
    "constitutional_law",
    "sports_team_dynamics",
]


class MuseAgent:
    """
    The Muse Agent.

    Creative exploration engine that continuously generates abstract and grand
    ways to improve all parts of the system.

    ROLE: Generate improvement proposals
    FORBIDDEN: Execute anything. Modify any system component. Skip the queue.
    DEPARTMENT: SPECIAL
    """

    ROLE = "MUSE"
    ROLE_DESCRIPTION = "Creative exploration and system improvement proposal engine"
    ALLOWED_TOOLS = ["read_zero_point", "read_episodic_memory", "read_canon",
                     "read_failure_archive", "write_proposal_queue"]
    FORBIDDEN_ACTIONS = [
        "execute_code",
        "modify_canon",
        "modify_agents",
        "send_external",
        "approve_proposals",
        "skip_queue",
        "direct_implementation",
    ]
    DEPARTMENT = "SPECIAL"

    def __init__(self, proposal_queue_path: str = "memory/proposal_queue.json"):
        self.proposal_queue_path = proposal_queue_path
        self.proposals: List[Proposal] = []
        self.exploration_history: List[Dict] = []
        self._load_queue()

    def _load_queue(self):
        """Load existing proposal queue."""
        if os.path.exists(self.proposal_queue_path):
            try:
                with open(self.proposal_queue_path, 'r') as f:
                    data = json.load(f)
                self.proposals = [Proposal(**p) for p in data.get("proposals", [])]
            except (json.JSONDecodeError, TypeError):
                self.proposals = []

    def _save_queue(self):
        """Persist proposal queue."""
        os.makedirs(os.path.dirname(self.proposal_queue_path) or '.', exist_ok=True)
        data = {
            "proposals": [asdict(p) for p in self.proposals],
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "total": len(self.proposals),
            "pending": sum(1 for p in self.proposals if p.status == "PENDING"),
        }
        with open(self.proposal_queue_path, 'w') as f:
            json.dump(data, f, indent=2)

    def _generate_proposal_id(self) -> str:
        """Generate sequential proposal ID."""
        count = len(self.proposals) + 1
        return f"MUSE-{count:04d}"

    def _score_proposal(self, proposal: Proposal) -> float:
        """
        Score a proposal for priority ranking.
        Higher = more valuable.
        """
        score = 0.0

        # Impact scoring
        impact_scores = {"incremental": 1.0, "significant": 3.0, "transformative": 5.0}
        score += impact_scores.get(proposal.estimated_impact, 0)

        # Risk penalty (higher risk = lower priority unless transformative)
        risk_penalty = {"LOW": 0, "MEDIUM": -1.0, "HIGH": -2.0}
        score += risk_penalty.get(proposal.risk_tier, 0)

        # Fewer dependencies = faster to implement = bonus
        dep_bonus = max(0, 3 - len(proposal.dependencies))
        score += dep_bonus

        # Failure mode awareness bonus (more identified = better thought out)
        if len(proposal.failure_modes) >= 2:
            score += 1.0

        # Core IP target bonus
        core_names = [t["name"] for t in CORE_IP_TARGETS]
        if proposal.target_component in core_names:
            score += 2.0  # Priority to improving core IP

        return round(score, 2)

    def generate_proposal(self, target_component: str, improvement_type: str,
                          description: str, inspiration_source: str,
                          implementation_sketch: str,
                          estimated_impact: str = "significant",
                          dependencies: Optional[List[str]] = None,
                          failure_modes: Optional[List[str]] = None) -> Dict:
        """
        Generate a new improvement proposal.
        Does NOT execute. Adds to queue for review.
        """
        now = datetime.now(timezone.utc).isoformat()

        proposal = Proposal(
            proposal_id=self._generate_proposal_id(),
            title=f"[{improvement_type.upper()}] {target_component}: {description[:80]}",
            description=description,
            target_component=target_component,
            improvement_type=improvement_type,
            inspiration_source=inspiration_source,
            estimated_impact=estimated_impact,
            risk_tier=self._assess_risk(improvement_type, target_component),
            implementation_sketch=implementation_sketch,
            dependencies=dependencies or [],
            failure_modes=failure_modes or ["Not yet analyzed"],
            created_at=now,
        )

        proposal.score = self._score_proposal(proposal)
        self.proposals.append(proposal)
        self._save_queue()

        return {
            "status": "QUEUED",
            "proposal_id": proposal.proposal_id,
            "score": proposal.score,
            "risk_tier": proposal.risk_tier,
            "message": "Proposal queued for Polemarch review. Muse does not execute."
        }

    def _assess_risk(self, improvement_type: str, target: str) -> str:
        """Assess risk tier for a proposal."""
        # Anything touching Canon or core governance = HIGH
        high_risk_targets = ["Canon Amendment Ceremony", "Governance State Machine"]
        if target in high_risk_targets:
            return "HIGH"

        # Abstraction and synthesis = MEDIUM (could introduce drift)
        if improvement_type in ("abstraction", "synthesis"):
            return "MEDIUM"

        # Optimization and compression = LOW (improving existing)
        return "LOW"

    def run_exploration_cycle(self, mode: str = MuseExplorationMode.DIVERGENT,
                              focus_targets: Optional[List[str]] = None,
                              zero_point_entries: Optional[List[Dict]] = None,
                              failure_archive: Optional[List[Dict]] = None) -> List[Dict]:
        """
        Run a full exploration cycle.

        This is the scheduled creative session. It examines:
        1. Current system state (via Zero Point entries)
        2. Failure history (via failure archive)
        3. Core IP improvement vectors
        4. Cross-domain inspiration

        Returns a list of generated proposals.

        NOTE: In production, this would use LLM inference to generate
        creative proposals. Current implementation provides the framework
        and seed data for the LLM to work with.
        """
        cycle_id = f"CYCLE-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
        targets = focus_targets or [t["name"] for t in CORE_IP_TARGETS]
        generated = []

        self.exploration_history.append({
            "cycle_id": cycle_id,
            "mode": mode,
            "targets": targets,
            "started_at": datetime.now(timezone.utc).isoformat(),
        })

        # For each target, generate exploration context
        for target_name in targets:
            target_info = next(
                (t for t in CORE_IP_TARGETS if t["name"] == target_name),
                None
            )
            if not target_info:
                continue

            # Build exploration context (this is what the LLM would use)
            context = {
                "target": target_info,
                "mode": mode,
                "available_improvements": target_info.get("improvement_vectors", []),
                "inspiration_domains": INSPIRATION_DOMAINS,
                "zero_point_relevant": self._filter_relevant_entries(
                    zero_point_entries or [], target_name
                ),
                "relevant_failures": self._filter_relevant_failures(
                    failure_archive or [], target_name
                ),
            }

            generated.append({
                "target": target_name,
                "exploration_context": context,
                "cycle_id": cycle_id,
                "status": "CONTEXT_READY",
                "note": "Feed this context to LLM for creative proposal generation"
            })

        return generated

    def _filter_relevant_entries(self, entries: List[Dict], target: str) -> List[Dict]:
        """Filter Zero Point entries relevant to a target."""
        return [e for e in entries if target.lower() in str(e).lower()][:5]

    def _filter_relevant_failures(self, failures: List[Dict], target: str) -> List[Dict]:
        """Filter failure archive entries relevant to a target."""
        return [f for f in failures if target.lower() in str(f).lower()][:5]

    def get_queue_status(self) -> Dict:
        """Get current proposal queue status."""
        return {
            "total": len(self.proposals),
            "pending": sum(1 for p in self.proposals if p.status == "PENDING"),
            "approved": sum(1 for p in self.proposals if p.status == "APPROVED"),
            "rejected": sum(1 for p in self.proposals if p.status == "REJECTED"),
            "deferred": sum(1 for p in self.proposals if p.status == "DEFERRED"),
            "top_scored": sorted(
                [asdict(p) for p in self.proposals if p.status == "PENDING"],
                key=lambda x: x["score"],
                reverse=True
            )[:5]
        }

    def approve_proposal(self, proposal_id: str, human_notes: str = "") -> Dict:
        """
        Approve a proposal. ONLY callable by human authority or Polemarch.
        The Muse itself CANNOT call this.
        """
        for p in self.proposals:
            if p.proposal_id == proposal_id:
                p.status = "APPROVED"
                p.human_notes = human_notes
                self._save_queue()
                return {"status": "APPROVED", "proposal_id": proposal_id}

        return {"status": "NOT_FOUND", "proposal_id": proposal_id}

    def reject_proposal(self, proposal_id: str, reason: str = "") -> Dict:
        """Reject a proposal with reason."""
        for p in self.proposals:
            if p.proposal_id == proposal_id:
                p.status = "REJECTED"
                p.human_notes = reason
                self._save_queue()
                return {"status": "REJECTED", "proposal_id": proposal_id}

        return {"status": "NOT_FOUND", "proposal_id": proposal_id}
