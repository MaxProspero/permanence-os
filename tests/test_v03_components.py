"""
Permanence OS — Test Suite v0.3
Tests for: DNA, Zero Point, Muse, Digital Twin, Chimera, Arch Evolution

Run: pytest tests/test_v03_components.py -v
"""

import os
import sys
import json
import pytest
import tempfile
import shutil
from datetime import datetime, timezone

# Add parent to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from memory.zero_point import ZeroPoint, MemoryType, ConfidenceLevel
from special.muse_agent import MuseAgent, MuseExplorationMode, CORE_IP_TARGETS
from special.digital_twin import DigitalTwinSimulator, SimulationResult
from special.chimera_builder import ChimeraBuilder, ANCESTRAL_REGISTRY
from special.arch_evolution_agent import ArchitectureEvolutionAgent, COMPONENT_BENCHMARKS


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test storage."""
    d = tempfile.mkdtemp()
    yield d
    shutil.rmtree(d)


# ==================== ZERO POINT TESTS ====================

class TestZeroPoint:

    def test_write_with_provenance(self, temp_dir):
        """Governed writes with full provenance should succeed."""
        zp = ZeroPoint(storage_path=os.path.join(temp_dir, "zp.json"))
        result = zp.write(
            content="Test pattern: governance before intelligence",
            memory_type=MemoryType.PATTERN,
            tags=["governance", "principle"],
            source="Canon v0.3",
            author_agent="TEST-AGENT",
            confidence=ConfidenceLevel.HIGH,
            evidence_count=3
        )
        assert result["status"] == "ACCEPTED"
        assert result["entry_id"].startswith("ZP-")

    def test_write_without_provenance_rejected(self, temp_dir):
        """Writes without provenance MUST be rejected. CA-004."""
        zp = ZeroPoint(storage_path=os.path.join(temp_dir, "zp.json"))
        result = zp.write(
            content="Ungoverned thought",
            memory_type=MemoryType.FACT,
            tags=["test"],
            source="",  # No source
            author_agent="TEST-AGENT",
            confidence=ConfidenceLevel.HIGH,
            evidence_count=1
        )
        assert result["status"] == "REJECTED"
        assert "provenance" in result["reason"].lower()

    def test_single_source_confidence_cap(self, temp_dir):
        """Single-source writes get capped to LOW confidence."""
        zp = ZeroPoint(storage_path=os.path.join(temp_dir, "zp.json"))
        result = zp.write(
            content="Single source claim",
            memory_type=MemoryType.FACT,
            tags=["test"],
            source="one-paper.pdf",
            author_agent="TEST-AGENT",
            confidence=ConfidenceLevel.HIGH,  # Will be capped
            evidence_count=1  # Only one source
        )
        assert result["status"] == "ACCEPTED"
        assert result["confidence"] == "LOW"  # Capped

    def test_read_logs_access(self, temp_dir):
        """Every read must be logged."""
        zp = ZeroPoint(storage_path=os.path.join(temp_dir, "zp.json"))
        write_result = zp.write(
            content="Readable entry",
            memory_type=MemoryType.PATTERN,
            tags=["test"],
            source="test_source",
            author_agent="WRITER",
            confidence=ConfidenceLevel.MEDIUM,
            evidence_count=2
        )
        entry_id = write_result["entry_id"]
        entry = zp.read(entry_id, "READER-AGENT")
        assert entry is not None
        assert entry["read_count"] == 1
        assert entry["last_read_by"] == "READER-AGENT"

    def test_search_by_tags(self, temp_dir):
        """Search should filter by tags."""
        zp = ZeroPoint(storage_path=os.path.join(temp_dir, "zp.json"))
        zp.write("Gov pattern", MemoryType.PATTERN, ["governance"],
                 "src1", "AGENT", ConfidenceLevel.HIGH, 3)
        zp.write("Health data", MemoryType.FACT, ["health"],
                 "src2", "AGENT", ConfidenceLevel.MEDIUM, 2)
        results = zp.search(tags=["governance"], requesting_agent="TEST")
        assert len(results) == 1
        assert "governance" in results[0]["tags"]

    def test_stats(self, temp_dir):
        """Stats should report accurate counts."""
        zp = ZeroPoint(storage_path=os.path.join(temp_dir, "zp.json"))
        zp.write("Entry 1", MemoryType.PATTERN, ["a"], "s", "A",
                 ConfidenceLevel.HIGH, 3)
        zp.write("Entry 2", MemoryType.SKILL, ["b"], "s", "A",
                 ConfidenceLevel.MEDIUM, 2)
        stats = zp.get_stats()
        assert stats["total_entries"] == 2
        assert stats["unreviewed"] == 2


# ==================== MUSE AGENT TESTS ====================

class TestMuseAgent:

    def test_generate_proposal(self, temp_dir):
        """Muse should generate proposals that land in queue."""
        muse = MuseAgent(proposal_queue_path=os.path.join(temp_dir, "queue.json"))
        result = muse.generate_proposal(
            target_component="Governance State Machine",
            improvement_type="optimization",
            description="Add dynamic risk recalculation at each state transition",
            inspiration_source="trading_systems",
            implementation_sketch="At each stage transition, re-evaluate risk tier based on accumulated context"
        )
        assert result["status"] == "QUEUED"
        assert result["proposal_id"].startswith("MUSE-")
        assert result["score"] > 0

    def test_muse_never_executes(self, temp_dir):
        """Muse must have 'execute' in forbidden actions."""
        muse = MuseAgent(proposal_queue_path=os.path.join(temp_dir, "queue.json"))
        assert "execute_code" in muse.FORBIDDEN_ACTIONS
        assert "direct_implementation" in muse.FORBIDDEN_ACTIONS

    def test_core_ip_priority_scoring(self, temp_dir):
        """Proposals targeting core IP should score higher."""
        muse = MuseAgent(proposal_queue_path=os.path.join(temp_dir, "queue.json"))

        core_result = muse.generate_proposal(
            target_component="Compression Layer",
            improvement_type="optimization",
            description="Auto-pattern extraction",
            inspiration_source="information_theory",
            implementation_sketch="Extract patterns automatically"
        )

        non_core_result = muse.generate_proposal(
            target_component="UI Dashboard",
            improvement_type="optimization",
            description="Make it prettier",
            inspiration_source="design",
            implementation_sketch="Add colors"
        )

        assert core_result["score"] > non_core_result["score"]

    def test_queue_status(self, temp_dir):
        """Queue should track pending/approved/rejected counts."""
        muse = MuseAgent(proposal_queue_path=os.path.join(temp_dir, "queue.json"))
        muse.generate_proposal("A", "optimization", "Test 1", "src", "sketch")
        muse.generate_proposal("B", "expansion", "Test 2", "src", "sketch")

        status = muse.get_queue_status()
        assert status["total"] == 2
        assert status["pending"] == 2

    def test_exploration_cycle(self, temp_dir):
        """Exploration cycle should produce context for each target."""
        muse = MuseAgent(proposal_queue_path=os.path.join(temp_dir, "queue.json"))
        results = muse.run_exploration_cycle(
            mode=MuseExplorationMode.DIVERGENT,
            focus_targets=["Governance State Machine", "Compression Layer"]
        )
        assert len(results) == 2
        assert results[0]["status"] == "CONTEXT_READY"


# ==================== DIGITAL TWIN TESTS ====================

class TestDigitalTwin:

    def test_simulate_safe_action(self):
        """Safe actions should get PROCEED recommendation."""
        twin = DigitalTwinSimulator()
        report = twin.simulate(
            task_id="T-001",
            action="read_data",
            context={"modifies_data": False},
            risk_tier="LOW",
            agent_id="TEST-AGENT",
            episodic_history=[
                {"action": "read_data", "outcome": "success"},
                {"action": "read_data", "outcome": "success"},
                {"action": "read_data", "outcome": "success"},
            ]
        )
        assert report.recommendation in ("PROCEED", "PROCEED_WITH_MONITORING")

    def test_simulate_irreversible_action(self):
        """Irreversible HIGH-risk actions should escalate."""
        twin = DigitalTwinSimulator()
        report = twin.simulate(
            task_id="T-002",
            action="send_email",
            context={"sends_external": True, "financial_impact": True},
            risk_tier="HIGH",
            agent_id="TEST-AGENT"
        )
        assert report.reversibility == "irreversible"
        assert report.recommendation in ("BLOCK", "ESCALATE")

    def test_stress_tests_run(self):
        """All 5 standard stress scenarios should be tested."""
        twin = DigitalTwinSimulator()
        report = twin.simulate(
            task_id="T-003",
            action="process_data",
            context={},
            risk_tier="MEDIUM",
            agent_id="TEST"
        )
        assert len(report.stress_scenarios) == 5

    def test_simulation_never_executes(self):
        """Twin must never execute real actions."""
        twin = DigitalTwinSimulator()
        assert "execute_real_action" in twin.FORBIDDEN_ACTIONS


# ==================== CHIMERA BUILDER TESTS ====================

class TestChimeraBuilder:

    def test_list_available_traits(self):
        """Should list extractable traits from registry."""
        builder = ChimeraBuilder(storage_path="/tmp/test_chimera.json")
        traits = builder.list_available_traits()
        assert len(traits) > 0
        assert all("figure" in t and "trait" in t for t in traits)

    def test_extract_approved_trait(self):
        """Should extract traits that are in extract_only list."""
        builder = ChimeraBuilder(storage_path="/tmp/test_chimera.json")
        tv = builder.extract_trait("Nikola Tesla", "pattern_recognition")
        assert tv is not None
        assert tv.source_figure == "Nikola Tesla"
        assert tv.trait_domain == "intellect"

    def test_reject_unapproved_trait(self):
        """Should reject traits NOT in extract_only list."""
        builder = ChimeraBuilder(storage_path="/tmp/test_chimera.json")
        tv = builder.extract_trait("Nikola Tesla", "obsessive_iteration")
        assert tv is None  # Not in extract_only

    def test_compose_chimera(self, temp_dir):
        """Should compose a chimera from 2+ trait vectors."""
        builder = ChimeraBuilder(storage_path=os.path.join(temp_dir, "chimera.json"))
        result = builder.compose_chimera(
            purpose="Strategic system design with precision",
            trait_requests=[
                {"figure": "Sun Tzu", "trait": "asymmetric_advantage"},
                {"figure": "Katherine Johnson", "trait": "computational_integrity"},
            ],
            task_scope="Architecture review and improvement proposals",
            expiry_hours=2
        )
        assert result["status"] == "COMPOSED"
        assert result["traits_loaded"] == 2
        assert result["reversible"] is True

    def test_chimera_requires_two_traits(self, temp_dir):
        """Chimera needs at least 2 traits."""
        builder = ChimeraBuilder(storage_path=os.path.join(temp_dir, "chimera.json"))
        result = builder.compose_chimera(
            purpose="Test",
            trait_requests=[{"figure": "Sun Tzu", "trait": "asymmetric_advantage"}],
            task_scope="Test",
        )
        assert result["status"] == "FAILED"

    def test_decompose_chimera(self, temp_dir):
        """Chimeras must be decomposable (CA-006 reversibility)."""
        builder = ChimeraBuilder(storage_path=os.path.join(temp_dir, "chimera.json"))
        compose = builder.compose_chimera(
            purpose="Temp",
            trait_requests=[
                {"figure": "Sun Tzu", "trait": "terrain_awareness"},
                {"figure": "Ada Lovelace", "trait": "bridging_domains"},
            ],
            task_scope="Test",
        )
        result = builder.decompose_chimera(compose["chimera_id"])
        assert result["status"] == "DECOMPOSED"


# ==================== ARCHITECTURE EVOLUTION TESTS ====================

class TestArchEvolution:

    def test_audit_component_with_metrics(self):
        """Should audit a component and return health score."""
        agent = ArchitectureEvolutionAgent()
        audit = agent.audit_component(
            "Governance State Machine",
            current_metrics={
                "routing_accuracy": 0.92,
                "risk_tier_accuracy": 0.88,
                "escalation_appropriateness": 0.80,
                "stage_transition_clean": 0.99,
                "mean_routing_steps": 2.5,
            }
        )
        assert 0.0 <= audit.health_score <= 1.0
        assert audit.recommendation in ("HEALTHY", "NEEDS_ATTENTION", "CRITICAL")

    def test_audit_without_metrics(self):
        """Should handle missing metrics gracefully."""
        agent = ArchitectureEvolutionAgent()
        audit = agent.audit_component("Compression Layer", current_metrics={})
        assert audit.health_score == 0.0  # No data

    def test_full_system_audit(self):
        """Should audit all 5 components."""
        agent = ArchitectureEvolutionAgent()
        result = agent.run_full_system_audit()
        assert len(result["components"]) == 5
        assert "system_health" in result

    def test_propose_evolution(self):
        """Should create proposals that require ceremony."""
        agent = ArchitectureEvolutionAgent()
        result = agent.propose_evolution(
            component="Risk-Tier Algorithms",
            title="Add compound risk detection",
            current_state="Static per-task risk classification",
            proposed_state="Dynamic risk that considers task sequence",
            expected_improvement="Catch cascading risk patterns",
            implementation_steps=["Add task history to risk context", "Implement compound rules"],
            rollback_plan="Revert to static classification",
            risk_of_change="MEDIUM"
        )
        assert result["status"] == "PROPOSED"
        assert result["note"].lower().count("canon ceremony") > 0

    def test_all_five_components_defined(self):
        """All 5 core IP components must have benchmark definitions."""
        expected = [
            "Governance State Machine",
            "Provenance Memory",
            "Canon Amendment Ceremony",
            "Risk-Tier Algorithms",
            "Compression Layer",
        ]
        for comp in expected:
            assert comp in COMPONENT_BENCHMARKS, f"Missing benchmarks for: {comp}"


# ==================== INTEGRATION TESTS ====================

class TestIntegration:

    def test_muse_to_zero_point_flow(self, temp_dir):
        """Muse generates idea → written to Zero Point with provenance."""
        zp = ZeroPoint(storage_path=os.path.join(temp_dir, "zp.json"))
        muse = MuseAgent(proposal_queue_path=os.path.join(temp_dir, "queue.json"))

        # Muse generates proposal
        proposal = muse.generate_proposal(
            target_component="Compression Layer",
            improvement_type="synthesis",
            description="Cross-reference failure archive with compression patterns",
            inspiration_source="immune_systems",
            implementation_sketch="Build cross-reference index"
        )

        # Write proposal summary to Zero Point
        result = zp.write(
            content=f"Muse proposal {proposal['proposal_id']}: Cross-reference failures with compression",
            memory_type=MemoryType.PROPOSAL,
            tags=["muse", "compression", "improvement"],
            source=f"Muse Agent cycle",
            author_agent="MUSE",
            confidence=ConfidenceLevel.MEDIUM,
            evidence_count=1
        )
        assert result["status"] == "ACCEPTED"

    def test_twin_blocks_dangerous_then_chimera_advises(self, temp_dir):
        """Twin blocks dangerous action, then chimera provides alternative approach."""
        twin = DigitalTwinSimulator()
        builder = ChimeraBuilder(storage_path=os.path.join(temp_dir, "chimera.json"))

        # Twin evaluates dangerous action
        report = twin.simulate(
            task_id="T-INT-001",
            action="execute_trade",
            context={"financial_impact": True, "sends_external": True},
            risk_tier="HIGH",
            agent_id="FINANCE-AGENT"
        )

        # If blocked, compose chimera for strategic advice
        if report.recommendation in ("BLOCK", "ESCALATE"):
            chimera = builder.compose_chimera(
                purpose="Provide strategic alternative to blocked trade",
                trait_requests=[
                    {"figure": "Sun Tzu", "trait": "asymmetric_advantage"},
                    {"figure": "Claude Shannon", "trait": "information_compression"},
                ],
                task_scope="Advisory only — no execution",
                expiry_hours=1
            )
            assert chimera["status"] == "COMPOSED"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
