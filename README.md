# PERMANENCE OS

> A governed personal intelligence system that compounds judgment without losing agency, authenticity, or coherence over time.

## 🎯 What Is This?

This is **not** a typical AI agent system.

This is a structured intelligence governance framework designed to:
- Convert complexity into actionable principles
- Maintain human authority at all times
- Compound learning without losing coherence
- Survive variance (work at 2 AM, not just peak states)
- Fail cleanly and learn from failures

## 🏗️ Architecture

```
Layer 0: Human (Payton) ─────────── Final Authority
         │
Layer 1: Base Canon ─────────────── Constitutional Law
         │
Layer 2: Polemarch ──────────────── Governor & Router
         │
Layer 3: Executive Bots ─────────── Strategy Translation
         │
Layer 4: Department Bots ────────── Specialized Work
         │
Layer 5: Audit Loop ─────────────── Evolution & Learning
```

## ⚔️ The Polemarch

**King Bot** is formally known as **The Polemarch** (Greek: πολέμαρχος - "war leader").

This isn't metaphorical. The Polemarch operates like a military commander:

- **Receives orders** (task goals)
- **Consults doctrine** (Canon)
- **Assesses terrain** (complexity, risk)
- **Assigns forces** (routes to agents)
- **Enforces discipline** (budgets, constraints)
- **Calls for reinforcements** (escalates to human)
- **Records engagements** (logs every decision)

Core principle: *"Discipline under fire, clarity under fog, structure under chaos."*

Implementation note: the Polemarch code lives in `agents/king_bot.py` for backward compatibility.

## 📁 Directory Structure

```
permanence-os/
├── canon/              # Constitutional law (YAML)
│   └── base_canon.yaml
├── agents/             # Agent implementations
│   ├── king_bot.py
│   ├── planner.py
│   ├── researcher.py
│   ├── executor.py
│   └── reviewer.py
├── memory/             # Persistent storage
│   ├── episodic/       # Task logs
│   ├── working/        # Temporary scratchpad
│   └── tool/           # Raw tool outputs
├── logs/               # Append-only system logs
├── tests/              # Test suites
└── outputs/            # Final deliverables
```

## 🚀 Quick Start

### 1. Initialize
```bash
git clone <your-repo>
cd permanence-os
pip install -r requirements.txt
```

### 2. Configure
```bash
cp .env.example .env
# Add your API keys to .env
```

Optional: set path overrides in `.env` if you need custom locations.

### 3. Run
```bash
python agents/king_bot.py
```

### 4. Governed Task Runner
```bash
python run_task.py "Your task goal"
python run_task.py "Your task goal" --sources /path/to/sources.json --draft /path/to/draft.md
```

This runner expects a provenance list at `memory/working/sources.json` with:
- `source`
- `timestamp`
- `confidence`

Example format: `docs/sources_example.json`

Helper to build sources:
```bash
python scripts/new_sources.py "source-name" 0.7 "optional notes"
```

Optional draft input:
- Place a markdown draft at `memory/working/draft.md` to have the Executor package it.

Cleanup helper:
```bash
python scripts/clean_artifacts.py --all
```

Status helper:
```bash
python scripts/status.py
```

### 5. Tests
```bash
python tests/test_polemarch.py
python tests/test_agents.py
```

## 🎛️ Core Principles

### The Constitution
1. **Bots are roles, not beings** - Replaceable workers with bounded authority
2. **No autonomy without audit** - Every action is loggable and reviewable
3. **No memory without provenance** - Source, timestamp, confidence required
4. **Governance lives in structure** - Authority in state machines, not prompts
5. **Human authority is final** - System escalates, never overrides

### The Three Compression Layers

**Layer 1: Signal Compression** - Filter inputs before they compete for attention
**Layer 2: Decision Compression** - Convert repeated choices into automated rules
**Layer 3: Identity Compression** - Establish consistent behavior independent of mood

### The 2 AM Test

**The ultimate filter:** Will this work when willpower is depleted?

Systems must function at worst state, not peak state.

## 📊 Risk Tiers

| Tier | Characteristics | Handling |
|------|----------------|----------|
| **LOW** | Reversible, informational, no side effects | Auto-execute with review |
| **MEDIUM** | Strategic, resource-consuming, ambiguous | Reviewer approval required |
| **HIGH** | Irreversible, financial/legal/reputational impact | Human approval required |

## 🔧 Agent Roles

### Polemarch (Governor)
- Validates against Canon
- Assigns risk tiers
- Enforces budgets
- Routes execution
- Escalates when needed
- **NEVER** creates content or reasons about truth

### Planner Agent
- Converts goals to structured specs
- Defines success criteria
- Estimates resource needs
- **CANNOT** execute plans or gather data

### Researcher Agent
- Gathers verified information
- Cites all sources
- Assigns confidence levels
- **CANNOT** speculate beyond sources

### Executor Agent
- Produces outputs per spec
- Tracks resource consumption
- **CANNOT** improvise scope changes

### Reviewer Agent
- Evaluates against rubrics
- Provides specific feedback
- **CANNOT** generate content or modify outputs

## 📈 Success Metrics

- Canon fidelity (value alignment)
- Factual accuracy (source-backed claims)
- Tool discipline (budget adherence)
- Hallucination rate (unsupported assertions)
- Escalation correctness (appropriate human involvement)

## 🔄 Version Control

**Current Version:** 0.1.0
**Status:** Foundation Phase

All Canon changes require:
1. Written rationale
2. Impact analysis
3. Rollback plan
4. Version bump
5. Human approval
6. Changelog entry

**No silent updates. Ever.**

## 🚨 Failure Modes

The system is designed to fail cleanly:
- Budget violations → immediate halt
- Canon conflicts → escalation
- Source failures → refusal with explanation
- Quality degradation → reviewer blocks output

**Failures are logged, analyzed, and integrated into Canon.**

## 📚 Documentation

- `/canon/base_canon.yaml` - System constitution
- `/docs/architecture.md` - Detailed system design
- `/docs/agent_specs.md` - Individual agent specifications
- `/docs/memory_system.md` - Memory architecture
- `/docs/compression_framework.md` - Theoretical foundation
- `/docs/canon_change_template.md` - Canon update ceremony template
- `/CHANGELOG.md` - Project change history
- `/docs/sources_example.json` - Sources provenance example

## 🤝 Contributing

This is a personal system, but the architecture is designed to be:
- **Observable** - All decisions logged
- **Auditable** - State machine driven
- **Forkable** - Adapt the Canon for your needs
- **Learnable** - Failure archive is public

## 📄 License

MIT License - See LICENSE file

## ⚠️ Critical Reminders

1. Intelligence is cheap. **Governance is rare.**
2. You don't rise to aspirations. **You fall to defaults.**
3. Agents are tools, not identities.
4. If it's not in the graph, **it cannot happen.**
5. Memory must never outrank law: **Canon > Episodic > Working**
6. Refusal is a valid output.
7. **Logs are not optional.**
8. Coherence > Intensity
9. The map is not the terrain.
10. **Compression over accumulation.**

---

*"This is how legendary systems are built. Not through cleverness, but through structure. Not through autonomy, but through constraint. Not through speed, but through compounding."*

**Permanence OS v0.1.0**
February 2026
