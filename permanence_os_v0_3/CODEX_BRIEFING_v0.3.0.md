# PERMANENCE OS — CODEX BRIEFING v0.3.0
## February 6, 2026
## Prepared by Claude (Anthropic) for Payton Hicks

---

## WHAT THIS IS

This briefing contains everything Codex needs to upgrade Permanence OS from v0.2 to v0.3.
It includes new agent implementations, architectural upgrades, and the complete file tree.

**DO NOT cherry-pick. Execute in order. Each section depends on the previous.**

---

## SUMMARY OF CHANGES (v0.2 → v0.3)

### New Agents
1. **Idea Agent (Muse)** — Creative exploration engine that continuously generates abstract/grand improvement proposals for all system components. Operates on a scheduled loop. Outputs go to a proposal queue for Polemarch review.
2. **Digital Twin Simulator** — Shadow-execution engine. Before any HIGH-risk action executes in reality, the Twin runs it in simulation and reports predicted outcomes.
3. **Chimera Builder** — RAG-based persona composition engine. Constructs task-specific agent personalities by splicing trait vectors from a curated knowledge base of historical figures.
4. **Architecture Evolution Agent** — Continuous improvement engine for the 5 core IP components. Benchmarks governance state machine, provenance memory, Canon ceremony, risk-tier algorithms, and compression layer against failure modes and proposes upgrades.

### Architectural Upgrades
1. **Shared Memory Layer (Zero Point)** — Central vector store that all agents read from and write to, with governance gates. Implements the "6" in the 3-6-9 architecture.
2. **3-6-9 DNA System** — Every agent now inherits a constitutional DNA triad: Safety, Abundance, Service. This is checked at boot time alongside Canon.
3. **Twin Protocol** — Every department agent can optionally spawn a simulation twin for pre-execution validation.
4. **Proposal Queue** — New governance structure for the Idea Agent's outputs. Ideas don't execute — they enter a queue, get risk-tiered, and require human approval before any implementation.

### Updated Systems
1. **Canon v0.3** — New invariant: "No agent writes to shared memory without provenance and confidence score." New heuristic: "Chimera Integrity Check" — persona overlays must be reversible.
2. **Polemarch v0.3** — Now routes to new agents. Handles Twin Protocol activation for HIGH-risk tasks.
3. **Memory Architecture v0.3** — Added Zero Point (shared memory) as 5th memory type. Promotion path: Working → Episodic → Zero Point → Canon.

---

## ARCHITECTURE (v0.3)

```
Layer 0: Human (Payton) — Final Authority
Layer 1: Base Canon + 3-6-9 DNA — Constitutional Law + Genetic Code
Layer 2: Polemarch + Governor's Council — Governor & Router
Layer 3: Executive Agents — Planner, Researcher, Executor, Reviewer, Conciliator
Layer 4: Department Agents — Email, Health, Social, Device, Briefing, Trainer, Therapist
Layer 5: Special Agents — Muse (Idea), Digital Twin, Chimera Builder, Architecture Evolution
Layer 6: Zero Point — Shared Memory Substrate
Layer 7: Audit Loop — Evolution & Learning
```

### File Tree (Target State)

```
permanence_os/
├── canon/
│   ├── values.yaml
│   ├── invariants.yaml
│   ├── tradeoffs.yaml
│   ├── decision_heuristics.yaml
│   ├── failure_archive.yaml
│   ├── long_arc.yaml
│   └── dna.yaml                    # NEW: 3-6-9 DNA triad
├── core/
│   ├── state.py                    # UPDATED: new stages for twin/chimera
│   ├── canon.py                    # UPDATED: DNA validation
│   ├── polemarch.py                # RENAMED from king_bot.py, UPDATED
│   ├── graph.py                    # UPDATED: new routes
│   ├── runner.py                   # UPDATED: twin protocol
│   ├── orchestration.py
│   └── conciliator.py
├── agents/
│   ├── base.py                     # UPDATED: DNA inheritance
│   ├── planner.py
│   ├── researcher.py
│   ├── executor.py
│   └── reviewer.py
├── departments/
│   ├── email_agent.py
│   ├── device_agent.py
│   ├── social_agent.py
│   ├── health_agent.py
│   ├── briefing_agent.py
│   ├── trainer_agent.py
│   └── therapist_agent.py
├── special/                         # NEW directory
│   ├── muse_agent.py               # Idea Agent
│   ├── digital_twin.py             # Digital Twin Simulator
│   ├── chimera_builder.py          # Persona Composition
│   └── arch_evolution_agent.py     # Architecture Evolution
├── memory/                          # NEW directory
│   ├── zero_point.py               # Shared memory substrate
│   ├── episodic.py                  # Episodic memory (refactored)
│   ├── working.py                   # Working memory (refactored)
│   ├── tool_memory.py               # Tool memory (refactored)
│   └── proposal_queue.py           # Idea Agent proposal queue
├── tests/
│   ├── test_canon.py
│   ├── test_polemarch.py
│   ├── test_agents.py
│   ├── test_memory.py
│   ├── test_zero_point.py          # NEW
│   ├── test_muse.py                # NEW
│   ├── test_twin.py                # NEW
│   ├── test_chimera.py             # NEW
│   ├── test_arch_evolution.py      # NEW
│   └── test_adversarial.py
├── docs/
│   ├── ARCHITECTURE_v0.3.md
│   ├── CANON_CHANGELOG.md
│   └── AGENT_REGISTRY.md           # NEW: all agents documented
├── scripts/
│   └── run_muse_cycle.py           # Scheduled idea generation
├── cli.py                           # UPDATED: new commands
└── README.md
```

---

## PRIORITY BUILD ORDER

### Sprint 1: Foundation Upgrades (Do First)

**1.1 — Canon DNA (canon/dna.yaml)**
**1.2 — Base Agent DNA Inheritance (agents/base.py)**
**1.3 — Zero Point Shared Memory (memory/zero_point.py)**
**1.4 — Proposal Queue (memory/proposal_queue.py)**
**1.5 — Polemarch v0.3 Updates (core/polemarch.py)**

### Sprint 2: Special Agents (Do Second)

**2.1 — Muse Agent (special/muse_agent.py)**
**2.2 — Digital Twin Simulator (special/digital_twin.py)**
**2.3 — Chimera Builder (special/chimera_builder.py)**
**2.4 — Architecture Evolution Agent (special/arch_evolution_agent.py)**

### Sprint 3: Integration & Testing (Do Third)

**3.1 — Graph Updates (core/graph.py)**
**3.2 — Runner Twin Protocol (core/runner.py)**
**3.3 — All New Tests**
**3.4 — CLI Updates**

---

## IMPLEMENTATION SPECIFICATIONS

See the individual code files in this package for complete implementations.
Each file is self-contained with inline documentation.

---

## CANON AMENDMENT LOG

### CA-004: Shared Memory Governance (Approved Feb 6, 2026)
- **New Invariant:** "No agent writes to Zero Point without provenance (source, timestamp, confidence)."
- **Rationale:** Shared memory is the most powerful and dangerous component. Ungoverned writes corrupt the entire system.

### CA-005: DNA Inheritance (Approved Feb 6, 2026)
- **New Invariant:** "Every agent must validate 3-6-9 DNA triad at initialization. Agents that fail DNA check cannot execute."
- **Rationale:** Constitutional values must be genetically inherited, not optionally consulted.

### CA-006: Chimera Integrity (Approved Feb 6, 2026)
- **New Heuristic:** "Chimera Integrity Check — All persona overlays must be reversible. No permanent personality modification without Canon ceremony."
- **Rationale:** Persona composition must be task-scoped, not identity-altering.

### CA-007: Idea Governance (Approved Feb 6, 2026)
- **New Heuristic:** "Muse Containment — The Idea Agent generates but never executes. All proposals enter the queue. Execution requires Polemarch routing + human approval for MEDIUM+ risk."
- **Rationale:** Creativity without governance is chaos.

---

## ACCEPTANCE CRITERIA

The system is v0.3 complete when:
- [ ] All agents boot with DNA validation
- [ ] Zero Point accepts governed writes and rejects ungoverned ones
- [ ] Muse Agent generates proposals that land in the queue
- [ ] Digital Twin can shadow-execute a task and return predictions
- [ ] Chimera Builder can compose a persona from 2+ trait sources
- [ ] Architecture Evolution Agent can audit all 5 IP components
- [ ] Polemarch routes to all new agents correctly
- [ ] All existing tests still pass
- [ ] 15+ new tests pass for new components
- [ ] Canon amendments CA-004 through CA-007 are in YAML files

---

*END OF CODEX BRIEFING*
*PERMANENCE OS v0.3.0*
*February 6, 2026*
