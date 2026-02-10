"""
Permanence OS — Chimera Builder v0.3
Special Agent: Persona Composition Engine

Constructs task-specific agent personalities by splicing trait vectors
from a curated knowledge base of historical figures.

Canon Reference: CA-006 (Chimera Integrity Check)
All persona overlays MUST be reversible. No permanent personality modification.
"""

import json
import os
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict


@dataclass
class TraitVector:
    """A single isolated trait from a historical figure."""
    trait_id: str
    source_figure: str
    trait_name: str
    trait_domain: str           # "intellect" | "strategy" | "creativity" | "leadership" | "resilience" | "precision"
    description: str
    extracted_patterns: List[str]  # Concrete behavioral patterns
    limitations: str            # What this trait does NOT cover
    confidence: str             # HIGH | MEDIUM | LOW


@dataclass
class ChimeraProfile:
    """A composed persona from multiple trait vectors."""
    chimera_id: str
    name: str
    purpose: str                # What task this chimera is optimized for
    trait_vectors: List[TraitVector]
    combined_prompt: str        # The system prompt that activates this persona
    created_at: str
    task_scope: str             # What this chimera is allowed to do
    expiry: Optional[str]       # When this chimera should be decomposed
    is_active: bool = True
    reversible: bool = True     # CA-006: MUST be True


# Curated Ancestral Knowledge Base
# These are the "DNA sources" for chimera construction.
# Each entry isolates SPECIFIC traits, not entire personalities.
ANCESTRAL_REGISTRY = [
    {
        "figure": "Nikola Tesla",
        "domain": "intellect",
        "traits": {
            "pattern_recognition": "Ability to visualize complete systems before building. Tesla would simulate inventions mentally, running them for weeks to identify wear patterns.",
            "first_principles": "Ignored conventional wisdom to derive solutions from fundamental physics. AC power was 'obvious' to him because he reasoned from electromagnetic theory.",
            "obsessive_iteration": "Would not release work until it met internal quality standards. Spent years on single problems."
        },
        "limitations": "Social isolation, financial mismanagement, obsessive behaviors",
        "extract_only": ["pattern_recognition", "first_principles"]
    },
    {
        "figure": "Sun Tzu",
        "domain": "strategy",
        "traits": {
            "asymmetric_advantage": "Win before fighting. Position so that victory is the only logical outcome for the opponent to accept.",
            "terrain_awareness": "Every decision must account for the environment it operates in. Abstract strategy without context fails.",
            "deception_as_efficiency": "Appear weak when strong, appear strong when weak. Minimize actual conflict."
        },
        "limitations": "Military context may not translate directly to business/personal",
        "extract_only": ["asymmetric_advantage", "terrain_awareness"]
    },
    {
        "figure": "Ada Lovelace",
        "domain": "creativity",
        "traits": {
            "bridging_domains": "Saw the connection between mathematics and music, poetry and computation. The first to imagine general-purpose computing.",
            "poetical_science": "Combined analytical rigor with creative imagination. Neither pure logic nor pure art — a synthesis.",
            "future_vision": "Wrote about AI concepts 100+ years before they existed by reasoning from first principles about what machines could do."
        },
        "limitations": "Limited implementation experience due to era constraints",
        "extract_only": ["bridging_domains", "poetical_science"]
    },
    {
        "figure": "Marcus Aurelius",
        "domain": "resilience",
        "traits": {
            "stoic_governance": "Rule yourself before ruling others. Internal discipline as prerequisite for external authority.",
            "memento_mori": "Awareness of mortality as clarity engine. Urgency without panic.",
            "journaling_as_compression": "Daily written reflection to convert experience into principles. The original compression protocol."
        },
        "limitations": "Stoicism can suppress necessary emotional processing",
        "extract_only": ["stoic_governance", "journaling_as_compression"]
    },
    {
        "figure": "Katherine Johnson",
        "domain": "precision",
        "traits": {
            "computational_integrity": "Double and triple-check every calculation. Astronauts trusted her math over the computer's.",
            "quiet_authority": "Let the work speak. Precision earns trust without self-promotion.",
            "pressure_performance": "Maintained accuracy under life-or-death stakes (space missions)."
        },
        "limitations": "Extreme precision can slow iterative processes",
        "extract_only": ["computational_integrity", "pressure_performance"]
    },
    {
        "figure": "Claude Shannon",
        "domain": "intellect",
        "traits": {
            "information_compression": "Founded information theory. Could reduce any signal to its essential bits.",
            "playful_rigor": "Built chess machines and juggling robots — serious science through playful exploration.",
            "binary_clarity": "Proved that any information can be reduced to yes/no decisions. The ultimate compression."
        },
        "limitations": "Theoretical focus; implementation was secondary",
        "extract_only": ["information_compression", "binary_clarity"]
    },
]

# v0.4 Sibling Dynamics extension.
ARCHETYPE_FEMININE = [
    {
        "figure": "The Oracle",
        "domain": "intuition",
        "traits": {
            "intuitive_foresight": "Early warning pattern sensing under uncertainty.",
            "signal_discernment": "Separates weak but meaningful signals from noise."
        },
        "limitations": "Heuristic intuition must be validated by evidence.",
        "extract_only": ["intuitive_foresight", "signal_discernment"],
    },
    {
        "figure": "The Weaver",
        "domain": "systems",
        "traits": {
            "interconnected_thinking": "Links distant domains into one coherent map.",
            "holistic_synthesis": "Balances local optimization with whole-system stability."
        },
        "limitations": "Can over-link unrelated concepts if unguided.",
        "extract_only": ["interconnected_thinking", "holistic_synthesis"],
    },
    {
        "figure": "Sophia",
        "domain": "wisdom",
        "traits": {
            "feminine_balance": "Balances action drive with reflective wisdom.",
            "governance_temperance": "Prevents overreaction in high-pressure decisions."
        },
        "limitations": "Requires explicit task scope to avoid vague outputs.",
        "extract_only": ["feminine_balance", "governance_temperance"],
    },
]

ANCESTRAL_REGISTRY.extend(ARCHETYPE_FEMININE)


class ChimeraBuilder:
    """
    The Chimera Builder.

    Constructs task-specific agent personas by compositing traits
    from historical figures via the Ancestral Registry.

    CRITICAL CONSTRAINTS (CA-006):
    - All persona overlays are REVERSIBLE
    - No permanent personality modification without Canon ceremony
    - Chimeras are task-scoped with explicit expiry
    - Trait extraction isolates specific capabilities, not full personalities
    """

    ROLE = "CHIMERA_BUILDER"
    ROLE_DESCRIPTION = "Persona composition engine using ancestral trait vectors"
    ALLOWED_TOOLS = ["read_ancestral_registry", "compose_persona", "read_zero_point"]
    FORBIDDEN_ACTIONS = [
        "permanent_personality_change",
        "modify_base_agent_identity",
        "bypass_expiry",
        "extract_harmful_traits",
        "modify_canon",
    ]
    DEPARTMENT = "SPECIAL"

    def __init__(self, registry: Optional[List[Dict]] = None,
                 storage_path: str = "memory/chimera_profiles.json"):
        self.registry = registry or ANCESTRAL_REGISTRY
        self.storage_path = storage_path
        self.active_chimeras: Dict[str, ChimeraProfile] = {}
        self._chimera_count = 0
        self._load()

    def _load(self):
        if os.path.exists(self.storage_path):
            try:
                with open(self.storage_path, 'r') as f:
                    data = json.load(f)
                for cid, cdata in data.get("chimeras", {}).items():
                    vectors = [TraitVector(**tv) for tv in cdata.pop("trait_vectors", [])]
                    self.active_chimeras[cid] = ChimeraProfile(
                        trait_vectors=vectors, **cdata
                    )
            except (json.JSONDecodeError, TypeError, KeyError):
                self.active_chimeras = {}

    def _save(self):
        os.makedirs(os.path.dirname(self.storage_path) or '.', exist_ok=True)
        data = {
            "chimeras": {
                cid: asdict(profile)
                for cid, profile in self.active_chimeras.items()
            },
            "last_updated": datetime.now(timezone.utc).isoformat()
        }
        with open(self.storage_path, 'w') as f:
            json.dump(data, f, indent=2)

    def _generate_chimera_id(self) -> str:
        self._chimera_count += 1
        return f"CHI-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{self._chimera_count:04d}"

    def list_available_traits(self) -> List[Dict]:
        """List all available traits from the Ancestral Registry."""
        available = []
        for entry in self.registry:
            for trait_name in entry.get("extract_only", []):
                trait_desc = entry["traits"].get(trait_name, "")
                available.append({
                    "figure": entry["figure"],
                    "domain": entry["domain"],
                    "trait": trait_name,
                    "description": trait_desc,
                    "limitations": entry["limitations"]
                })
        return available

    def extract_trait(self, figure_name: str, trait_name: str) -> Optional[TraitVector]:
        """
        Extract a specific trait from a historical figure.
        Only traits in the 'extract_only' list can be extracted.
        """
        entry = next(
            (e for e in self.registry if e["figure"] == figure_name),
            None
        )
        if not entry:
            return None

        if trait_name not in entry.get("extract_only", []):
            return None  # Not approved for extraction

        trait_desc = entry["traits"].get(trait_name, "")
        if not trait_desc:
            return None

        return TraitVector(
            trait_id=f"TV-{figure_name[:3].upper()}-{trait_name[:5].upper()}",
            source_figure=figure_name,
            trait_name=trait_name,
            trait_domain=entry["domain"],
            description=trait_desc,
            extracted_patterns=[trait_desc],  # In production: LLM extracts behavioral patterns
            limitations=entry["limitations"],
            confidence="MEDIUM"  # Requires validation in practice
        )

    def compose_chimera(self, purpose: str, trait_requests: List[Dict],
                         task_scope: str, expiry_hours: int = 24) -> Dict:
        """
        Compose a new Chimera from multiple trait vectors.

        Args:
            purpose: What this chimera is optimized for
            trait_requests: List of {"figure": "...", "trait": "..."}
            task_scope: What actions this chimera is allowed to take
            expiry_hours: How long before auto-decomposition (default 24h)

        Returns:
            Composition result with chimera_id or error

        CA-006 ENFORCEMENT:
        - reversible = True (always)
        - expiry is mandatory
        - task_scope must be declared
        """
        now = datetime.now(timezone.utc)
        chimera_id = self._generate_chimera_id()

        # Extract requested traits
        vectors = []
        for req in trait_requests:
            tv = self.extract_trait(req["figure"], req["trait"])
            if tv:
                vectors.append(tv)
            else:
                return {
                    "status": "FAILED",
                    "reason": f"Cannot extract '{req['trait']}' from '{req['figure']}'. "
                              f"Either figure not in registry or trait not approved for extraction."
                }

        if len(vectors) < 2:
            return {
                "status": "FAILED",
                "reason": "Chimera requires at least 2 trait vectors for composition."
            }

        # Build combined system prompt
        combined_prompt = self._build_chimera_prompt(purpose, vectors, task_scope)

        # Create expiry
        from datetime import timedelta
        expiry = (now + timedelta(hours=expiry_hours)).isoformat()

        profile = ChimeraProfile(
            chimera_id=chimera_id,
            name=f"Chimera-{'-'.join(v.source_figure.split()[0] for v in vectors)}",
            purpose=purpose,
            trait_vectors=vectors,
            combined_prompt=combined_prompt,
            created_at=now.isoformat(),
            task_scope=task_scope,
            expiry=expiry,
            is_active=True,
            reversible=True  # CA-006: Always True
        )

        self.active_chimeras[chimera_id] = profile
        self._save()

        return {
            "status": "COMPOSED",
            "chimera_id": chimera_id,
            "name": profile.name,
            "traits_loaded": len(vectors),
            "expiry": expiry,
            "reversible": True,
            "combined_prompt_preview": combined_prompt[:200] + "..."
        }

    def _build_chimera_prompt(self, purpose: str, vectors: List[TraitVector],
                               task_scope: str) -> str:
        """Build the system prompt that activates a chimera persona."""
        trait_descriptions = []
        for v in vectors:
            trait_descriptions.append(
                f"- {v.source_figure}'s {v.trait_name}: {v.description}"
            )

        prompt = f"""You are a specialized Chimera agent within Permanence OS.

PURPOSE: {purpose}
TASK SCOPE: {task_scope}

You operate with the following trait composition:
{chr(10).join(trait_descriptions)}

CONSTRAINTS:
- You are task-scoped. Do not exceed the declared scope.
- You are reversible. This persona overlay will be decomposed after task completion.
- You follow all Canon invariants and DNA triad requirements.
- You log all actions with provenance.
- If the task exceeds your scope, escalate to Polemarch.

TRAIT INTEGRATION NOTES:
Combine these traits synergistically. Do not simply alternate between them.
Find the synthesis point where multiple traits reinforce each other.
"""
        return prompt

    def decompose_chimera(self, chimera_id: str) -> Dict:
        """
        Decompose a chimera — return to base agent state.
        This is the reversibility mechanism required by CA-006.
        """
        profile = self.active_chimeras.get(chimera_id)
        if not profile:
            return {"status": "NOT_FOUND", "chimera_id": chimera_id}

        profile.is_active = False
        self._save()

        return {
            "status": "DECOMPOSED",
            "chimera_id": chimera_id,
            "name": profile.name,
            "was_active_for": f"Created at {profile.created_at}",
            "traits_released": len(profile.trait_vectors)
        }

    def cleanup_expired(self) -> List[str]:
        """Auto-decompose expired chimeras."""
        now = datetime.now(timezone.utc)
        decomposed = []

        for cid, profile in self.active_chimeras.items():
            if profile.is_active and profile.expiry:
                expiry_time = datetime.fromisoformat(profile.expiry)
                if now > expiry_time:
                    profile.is_active = False
                    decomposed.append(cid)

        if decomposed:
            self._save()

        return decomposed

    def get_active_chimeras(self) -> List[Dict]:
        """List all currently active chimeras."""
        return [
            {
                "chimera_id": cid,
                "name": profile.name,
                "purpose": profile.purpose,
                "traits": len(profile.trait_vectors),
                "expiry": profile.expiry,
                "is_active": profile.is_active
            }
            for cid, profile in self.active_chimeras.items()
            if profile.is_active
        ]
