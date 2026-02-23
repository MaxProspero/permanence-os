# PERMANENCE OS

> A governed personal intelligence system that compounds judgment without losing agency, authenticity, or coherence over time.

## ✅ Current State (2026-02-03)
- OpenClaw connected; status/health captured into `outputs/` + `memory/tool/`
- Governed pipeline wired (Polemarch → Planner → Researcher → Executor → Reviewer → Compliance Gate)
- HR Agent active with system health reporting + tool degradation awareness
- Episodic memory logging in both per-task JSON and daily JSONL
- Automations scheduled for daily briefing/dashboard and weekly HR/cleanup

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
Layer 0: Human Authority (Dax / Payton) ─────────── Final Authority
         │
Layer 1: Base Canon ─────────────── Constitutional Law
         │
Layer 2: Polemarch ──────────────── Governor & Router
         │
Layer 2.5: System Services ─────── Compliance Gate, HR Agent, Briefing Agent
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

## 🪪 Identity Protocol

The system supports dual identities:
- **Kael Dax** (internal / system use)
- **Payton Hicks** (public / legal use)

Routing rules are defined in `identity_config.yaml`. Agents use internal identity for logs and
escalations, and public identity for outward-facing or binding actions.

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
│   ├── conciliator.py
│   ├── compliance_gate.py
│   └── departments/
│       ├── email_agent.py
│       ├── device_agent.py
│       ├── social_agent.py
│       ├── health_agent.py
│       ├── briefing_agent.py
│       ├── trainer_agent.py
│       └── therapist_agent.py
├── identity_config.yaml
├── run_task.py
├── scripts/
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
python run_task.py "Your task goal" --allow-single-source
```

When OpenClaw is installed locally, the runner captures OpenClaw status + health
before execution (stored in `outputs/` and `memory/tool/`).

This runner expects a provenance list at `memory/working/sources.json` with:
- At least two distinct sources by default (override with `--allow-single-source`)

- `source`
- `timestamp`
- `confidence`

Example format: `docs/sources_example.json`

Helper to build sources:
```bash
python scripts/new_sources.py "source-name" 0.7 "optional notes"
```

Ingest tool outputs into sources.json:
```bash
python scripts/ingest_tool_outputs.py --tool-dir memory/tool --output memory/working/sources.json
```

Ingest local documents into sources.json:
```bash
python scripts/ingest_documents.py --doc-dir memory/working/documents --output memory/working/sources.json
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

### Unified CLI
```bash
python cli.py run "Your task goal"
python cli.py run "Your task goal" --allow-single-source
python cli.py add-source "source-name" 0.7 "optional notes"
python cli.py ingest --tool-dir memory/tool --output memory/working/sources.json
python cli.py ingest-docs --doc-dir memory/working/documents --output memory/working/sources.json
python cli.py ingest-sources --adapter tool_memory --output memory/working/sources.json
python cli.py ingest-sources --adapter url_fetch --urls https://example.com --output memory/working/sources.json
python cli.py ingest-sources --adapter web_search --query "AI governance frameworks" --output memory/working/sources.json
python cli.py server --host 127.0.0.1 --port 8000
python cli.py scrimmage --last-hours 24 --replays 10
python cli.py looking-glass "Test scenario"
python cli.py hyper-sim --iterations 1000 --warp-speed
python cli.py arcana scan --last 50
python cli.py status
python cli.py openclaw-status
python cli.py openclaw-status --health
python cli.py openclaw-sync --once
python cli.py clean --all
python cli.py test
python cli.py queue list
python cli.py hr-report
python cli.py briefing
python cli.py automation-report --days 1
python cli.py reliability-watch --arm --days 7 --check-interval-minutes 30
python cli.py reliability-watch --status
python cli.py reliability-watch --disarm
python cli.py reliability-gate --days 7
python cli.py reliability-streak
python cli.py phase-gate --days 7
python cli.py status-glance
python cli.py dell-cutover-verify
python cli.py ari-reception --action summary
python cli.py sandra-reception --action summary
python cli.py ari-reception --action intake --sender "Payton" --message "Need review of weekly phase gate" --channel discord
python cli.py email-triage
python cli.py gmail-ingest
python cli.py health-summary
python cli.py social-summary
python cli.py logos-gate
python cli.py dashboard
python cli.py command-center
python cli.py command-center --run-horizon --demo-horizon
python cli.py snapshot
python cli.py v04-snapshot
python cli.py cleanup-weekly
python cli.py git-autocommit
```

Automation writes a one-line quick status file to storage logs:
- `status_today.txt`
- `status_today.json`

Ari receptionist can run in automation mode:
- set `PERMANENCE_ARI_ENABLED=1`
- set `PERMANENCE_ARI_SLOT=19` (or `all`)

Custom receptionist name/command can run in automation mode:
- set `PERMANENCE_RECEPTIONIST_NAME=Sandra`
- set `PERMANENCE_RECEPTIONIST_ENABLED=1`
- set `PERMANENCE_RECEPTIONIST_SLOT=19` (or `all`)
- optional command override: `PERMANENCE_RECEPTIONIST_COMMAND=sandra-reception` (defaults to `ari-reception`)

Reliability watch can run in background for a fixed 7-day window:
- `python cli.py reliability-watch --arm --days 7`
- `python cli.py reliability-watch --status`
- `python cli.py reliability-watch --disarm`
- helper scripts: `bash automation/setup_reliability_watch.sh` and `bash automation/disable_reliability_watch.sh`

### OpenClaw Integration (Local)
Set the OpenClaw CLI path (if not default):
```bash
export OPENCLAW_CLI="$HOME/.openclaw/bin/openclaw"
```

Capture OpenClaw gateway status for audit logs:
```bash
python scripts/openclaw_status.py
python scripts/openclaw_status.py --health
```
OpenClaw health sync (degradation detection):
```bash
python scripts/openclaw_health_sync.py --once
python cli.py openclaw-sync --once
```

Briefing Agent includes the most recent OpenClaw status file in its notes when present.

### Evaluation Harness
```bash
python scripts/eval_harness.py
# Optional: override report path
PERMANENCE_EVAL_OUTPUT=/tmp/eval_report.json python scripts/eval_harness.py
```

### HR Report
```bash
python scripts/hr_report.py
python cli.py hr-report
```
HR reports include the latest OpenClaw status file when present.

### Briefing Agent
```bash
python scripts/briefing_run.py
python cli.py briefing
```
Briefing outputs include the most recent OpenClaw status excerpt when present.

### Email Triage
Store email JSON/JSONL in `memory/working/email/` and run:
```bash
python scripts/email_triage.py
python cli.py email-triage
```

### Gmail Ingest (Read-only)
1) Create OAuth credentials in Google Cloud (Gmail API enabled).
2) Save credentials to `memory/working/google/credentials.json`.
3) Run:
```bash
python cli.py gmail-ingest --max 50
```

### Health Summary
Store health JSON/JSONL in `memory/working/health/` and run:
```bash
python scripts/health_summary.py
python cli.py health-summary
```

### Social Drafts
Store social drafts in `memory/working/social/` and run:
```bash
python scripts/social_summary.py
python cli.py social-summary
```

### CLI Reference
See `docs/cli_reference.md` for a full command list.

### Roadmap
Phase 2 build priorities are in `docs/roadmap_phase2.md`.

### Governance
Code ownership is defined in `CODEOWNERS`.

### Dashboard Report
```bash
python scripts/dashboard_report.py
python cli.py dashboard
```

### System Snapshot
```bash
python scripts/system_snapshot.py
python cli.py snapshot
python scripts/v04_snapshot.py
python cli.py v04-snapshot
```

### Weekly Cleanup + Auto-Commit
```bash
python scripts/cleanup_weekly.py
python scripts/git_autocommit.py
python cli.py cleanup-weekly
python cli.py git-autocommit
```

### Canon Change Draft (Memory Promotion)
```bash
python scripts/promote_memory.py --count 5
python cli.py promote --count 5
```

Promotion drafts include `docs/promotion_rubric.md` by default (override with `PERMANENCE_PROMOTION_RUBRIC`).

### Promotion Queue (Optional)
```bash
python cli.py queue list
python cli.py queue add --latest --reason "pattern repeat"
python cli.py queue clear
python cli.py promotion-review --output outputs/promotion_review.md
```

### 5. Tests
```bash
python tests/test_polemarch.py
python tests/test_agents.py
python tests/test_compliance_gate.py
python tests/test_researcher_ingest.py
python tests/test_researcher_documents.py
python tests/test_memory_promotion.py
python tests/test_promotion_queue.py
python tests/test_promotion_review.py
python tests/test_hr_agent.py
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


### HR Agent (The Shepherd)
- Monitors system health and agent relations
- Generates weekly System Health reports
- Surfaces patterns and recommendations
- **CANNOT** override or block execution

### Compliance Gate
- Reviews outbound actions for legal/ethical/identity compliance
- Verdicts: APPROVE | HOLD | REJECT
- Sits after Reviewer for external actions

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
- `/docs/dell_cutover.md` - Linux (Dell) automation migration runbook
- `/docs/dell_cutover_powershell.md` - PowerShell + WSL Dell cutover workflow
- `/CHANGELOG.md` - Project change history
- `/docs/sources_example.json` - Sources provenance example
- `/identity_config.yaml` - Identity routing configuration

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
