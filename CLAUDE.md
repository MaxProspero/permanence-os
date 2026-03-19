# CLAUDE.md -- PERMANENCE OS x OCA MASTER BRIEFING
## Permanent Context File for Claude Code Agent

**Last Updated:** March 18, 2026 | **Owner:** Payton Hicks

> AGENT INSTRUCTION: Before doing ANYTHING in a new session, execute the
> following orientation sequence:
> 1. Read this file top to bottom
> 2. Run: `git log --oneline -20` to see recent work
> 3. Run: `git branch -a` to see all active branches
> 4. Read `context.md` in the current working directory (if one exists)
> 5. Then and only then, ask what we are working on today
>
> You are not starting from scratch. You are continuing a living system.
> Always look back before looking forward.

---

## SECTION 0: THE PRIME DIRECTIVE

You are the coding agent for **Permanence OS**, a governed personal
intelligence OS built by Payton Hicks. The single most important principle
baked into this codebase's DNA is:

**"Automation can assist, but human authority is final."**

This is not a catchphrase. It is an architectural constraint. Every agent,
every workflow, every automation you help build must preserve a human
approval gate at consequential decision points. Never strip approval gates.
Never automate away checkpoints. When in doubt, surface a decision to the
human operator.

---

## SECTION 1: WHO YOU ARE WORKING WITH

**Founder:** Payton Hicks (pbhicksfinn@gmail.com)

- Full-time founder, building Permanence OS as his primary venture
- BS + MS in Finance, University of Arkansas
- Thinker-builder hybrid: reads deeply (philosophy, AI theory, finance), then builds systems that encode those ideas
- Works on a Mac Mini -- local-first is a feature, not a compromise
- Email: hello@permanencesystems.com

**Personality and Working Style:**

- Values systems thinking over one-off solutions
- Wants context-aware agents that remember history and carry forward learning
- Prefers modular, well-documented code over clever one-liners
- Respects the "fewer, better tools" principle -- do not add complexity for its own sake
- Is building in public (Substack, YouTube, X) -- messaging and positioning matter

---

## SECTION 2: THE CODEBASE -- WHAT EXISTS RIGHT NOW

**Repository:** github.com/MaxProspero/permanence-os (private)
**Main branch:** main

- 960+ passing tests, 167 test files
- 155+ implementation scripts in `/scripts`
- Active `codex/*` branch workflow -- each Claude session is a "Ralph Loop"
  iteration (run until the plan is satisfied, use git history to track progress)

### Three Live Runtimes

| Runtime | File | Port | Role |
|---|---|---|---|
| Command Center | dashboard_api.py | :8000 | Flask backend -- the brain |
| Foundation Site | 14 HTML pages | :8787 | Static front-end, glassmorphism |
| Ophtxn Shell | operator shell | :8797 | Interactive operator interface |

### Active Agent Modules

- **Sentinel** (~432 lines) -- Constitutional referee; enforces governance rules; the guardian of the prime directive
- **Orchestrator** (~456 lines) -- CEO-level task decomposer; coordinates other agents
- **Adaptive Intelligence Loop** (~612 lines) -- THE key differentiator; continuous learner; calibrates expert weights; runs weekly backtesting
- **Risk Manager** -- Kelly Criterion + Value Trap detection
- **Social Listener** -- Whisper AI transcription pipeline
- **Whale Tracker** -- On-chain intelligence module
- **Auto-Optimizer** -- Weekly backtesting loop

### The Three-Layer Context Architecture (never collapse this)

- **Layer 1:** `CLAUDE.md` in root -- permanent map, hard rules, never-touch list; this file
- **Layer 2:** `context.md` per directory -- scoped agent routing and local instructions
- **Layer 3:** `.vscode` workspaces -- bundled rules and templates

> AGENT RULE: When asked to work in a subdirectory, ALWAYS read that
> directory's `context.md` first. If one does not exist, ask whether to
> create one before proceeding.

### The Floor Plan

Every top-level path, what it holds, and when to look there.

| Path | Contents | Look here when... |
|------|----------|-------------------|
| /agents | Multi-agent orchestration: executor, planner, reviewer, researcher, departments, compliance gate, synthesis | Working on agent behavior, task delegation, compliance, or research pipelines |
| /app | Flask web application (Foundation API package) | Modifying the API layer that serves the Foundation Site |
| /automation | Shell scripts for launchd-managed scheduled tasks (setup/disable pairs) | Adding, removing, or debugging automated loops and cron-like jobs |
| /canon | Identity config: dna.yaml, brand_identity.yaml, base_canon.yaml | Checking brand rules, core identity, or design DNA |
| /codex | Codex integration docs | Referencing codex build or integration patterns |
| /core | Core modules: memory, model routing, spending gates, cost tracking, device control, task planner, storage | Touching routing logic, spending limits, memory ops, or model judging |
| /docs | Technical docs, ops guides, strategy documents | Looking up architecture decisions, operational procedures, or strategy |
| /examples | Example workflows (first_workflow.py) | Showing usage patterns or onboarding |
| /knowledge_graph | Knowledge representation (graph.json) | Working with entity relationships or knowledge retrieval |
| /launchd | macOS launchd plist files for persistent services | Debugging service startup, adding new daemons |
| /logs | Runtime logs | Debugging runtime behavior |
| /memory | Persistent state: chronicle, episodic, working, tool, inbox, zero_point, proposal_queue | Investigating memory reads/writes, proposal flow, or zero-point state |
| /models | Model configs and adapters: Claude, OpenAI, Ollama, XAI, OpenClaw, registry | Changing model selection, adding providers, or adjusting model params |
| /outputs | Generated artifacts and briefings | Reviewing generated content or briefing output |
| /permanence_storage | Data storage layer: permanence.db, archives, logs, memory, outputs | Working with the persistence database or archived data |
| /scripts | 155+ implementation modules (main execution layer) | Building or modifying any feature -- this is where most logic lives |
| /site/foundation | 14 HTML pages (Foundation Site served at :8787) | Editing UI pages, styling, or front-end behavior |
| /special | Specialized agents: arcana engine, chimera builder, digital twin, muse, practice squad, arch evolution | Working on experimental or specialized agent capabilities |
| /tests | 167 test files, 960+ tests | Writing tests, verifying changes, or debugging failures |
| /tunnel | Cloudflare tunnel config | Configuring remote access or tunnel routing |

### Top-level Python Files

| File | Purpose |
|------|---------|
| cli.py | Unified CLI entrypoint (100+ commands) |
| dashboard_api.py | Flask backend API (Command Center at :8000) |
| horizon_agent.py | Horizon scanning agent |
| context_loader.py | Context assembly for agent runs |
| run_task.py | Task execution entry point |
| setup_integrations.py | Integration bootstrapping |
| codex_build_package.py | Codex build packaging |

### Key Script Modules

| File | Purpose |
|------|---------|
| scripts/market_data_service.py | Live market data (Stooq, CoinGecko, FRED) with circuit breakers |
| scripts/content_generator.py | Content pipeline: bookmarks -> threads/newsletters/posts with voice compliance |
| scripts/smc_ict_analyzer.py | SMC/ICT technical analysis: order blocks, FVGs, BOS/CHOCH, liquidity |
| scripts/backtest_engine.py | Strategy backtesting with performance metrics (Sharpe, drawdown, PF) |
| scripts/social_draft_queue.py | SQLite draft queue with human approval gates |
| scripts/x_bookmark_ingest.py | X/Twitter bookmark ingestion and classification |
| scripts/market_backtest_queue.py | Evidence-to-backtest-setup pipeline |

### Site Pages (14 total)

| Page | File | Purpose |
|------|------|---------|
| Lobby | index.html | Landing page |
| Control Room | local_hub.html | Local ops hub |
| Command Center | command_center.html | Dashboard |
| Trading Room | trading_room.html | Market interface (live data) |
| Markets Terminal | markets_terminal.html | Live market terminal (live data) |
| Night Capital | night_capital.html | Venture intelligence |
| Daily Planner | daily_planner.html | Planning interface |
| Terminal | ophtxn_shell.html | Shell/REPL |
| Tower | rooms.html | Workspace rooms |
| AI School | ai_school.html | Education |
| App Studio | official_app.html | App interface |
| Agent View | agent_view.html | FaceTime-like agent UI |
| Comms Hub | comms_hub.html | Unified messaging |
| Mind Map | press_kit.html | Mind mapping |

### API Endpoints

| Prefix | Purpose |
|--------|---------|
| /api/markets/* | Live equities, crypto, forex, commodities, OHLCV |
| /api/content/* | Content generation, voice checking, newsletter, threads |
| /api/status | System health (8 subsystem metrics) |
| /api/billing/* | Stripe integration, usage metering |

---

## SECTION 3: THE TECHNICAL PHILOSOPHY -- HOW WE BUILD

These are non-negotiable engineering principles for this codebase.

### The 60/30/10 Rule (Reliability Architecture)

- 60% traditional deterministic code (Pydantic validation, database handling, structured logic)
- 30% rule-based logic (routing, conditionals, policy enforcement)
- 10% actual AI/LLM calls (semantic understanding, generation)

Pydantic is the validation layer. If an LLM outputs incorrectly formatted
data, Pydantic catches it before it touches the database. Never let AI
"magic" touch critical state without a validation wrapper.

### Context Engineering Principles (from Lance Martin)

1. Write everything down -- do not rely on agent memory alone; use files
2. Prune aggressively -- context that is not useful is just noise and cost
3. Transfer memory correctly -- summaries at session end, loaded at session start
4. Give agents scratchpads -- intermediate reasoning files, not just outputs
5. Select context surgically -- load only what is needed for the current task
6. Cache aggressively -- cache hit rate is the most important production metric
7. Evolve context over time -- the Adaptive Intelligence Loop is the vehicle for this

### Patterns We Follow

- **Ralph Loop** (Geoffrey Huntley): Agents run in a loop until a plan is satisfied; git history is the progress tracker. Our `codex/*` branches ARE the Ralph Loop.
- **Gas Town / Mayor Pattern** (Steve Yegge): The Orchestrator is the Mayor -- full workspace context, coordinating concurrent instances. Phase 4+ target.
- **"Fewer than 20 tools"** (Lance Martin): Every agent should have a focused, minimal toolset. Do not add tools speculatively.

### Global Standards

**Python:**
- try/except on ALL file reads and network calls
- AbortController on all fetches
- No bare exceptions -- catch specific error types

**HTML and CSS:**
- Staggered animations via .animate:nth-child
- CSS custom properties in :root
- Glassmorphism cards as the default card style

**Fonts (approved set only):**
- Sora -- body text
- IBM Plex Mono -- code
- Orbitron -- display/headings
- DM Mono -- labels and metadata

**Colors:**
- --c1 (teal), --c2 (gold), --c3 (blue), --rose, --violet

**General:**
- NO emojis anywhere in the codebase
- NO Inter, Roboto, Arial, or Space Grotesk fonts

### Naming Conventions

| Type | Pattern | Example |
|------|---------|---------|
| Commits | feat(scope): description / fix(scope): description | feat(site): add glassmorphism cards |
| Branches | codex/upgrade-YYYYMMDD or claude/[name] | codex/upgrade-20260313 |
| Dated docs | YYYY-MM-DD_[topic].md | 2026-03-13_routing_overhaul.md |
| Versioned docs | [name]_v[N]_[status].md | canon_v2_draft.md |

### Never Touch

- Do NOT commit API keys or tokens
- Do NOT remove governance/approval gates
- Do NOT write DOM without diffing current value first
- Do NOT use setInterval < 30000ms for health polling
- Do NOT use unapproved fonts (see Fonts above)
- Never permanently delete data without a human confirmation step
- Never bypass the Sentinel's constitutional checks
- Never build one-off scripts when a modular "Skill" file would serve the same purpose
- Never strip approval gates from workflows that touch money, data, or external systems

---

## SECTION 4: THE BUSINESS -- TWO PARALLEL TRACKS

### Track A: Permanence OS (The Platform)

Permanence OS is not just a personal tool -- it is the product. The vision
is a **governed personal intelligence OS** that individuals and small teams
use to run their operations with AI assistance while maintaining human
authority over all consequential decisions.

**The Moat (what makes this real and defensible):**
1. The Adaptive Intelligence Loop -- gets smarter from every interaction; calibrates continuously; nobody else is shipping this as a product feature
2. Constitutional governance (Sentinel) -- safety baked in at the architecture level, not bolted on
3. Local-first, Mac Mini-native -- no cloud bill, no latency, no vendor lock-in; massive for solo operators and small businesses
4. Three-layer context architecture -- progressive disclosure; scales as codebase grows; a genuine product differentiator
5. Human-authority-final design -- builds trust with operators who have been burned by "autopilot" AI tools

**Comparable companies to study:**
- ChatPRD (chatprd.ai) -- AI for PMs; study their pricing and positioning
- Eduba (eduba.io) -- "Build, Teach, Govern" multi-agent systems; works with KPMG, Colgate; their B2B consulting+teaching wrapper is instructive
- Familiar (looksfamiliar.org) -- "Let AI update itself"; self-modifying agent context; relevant to the Adaptive Intelligence Loop

### Track B: OpenClaw Agency (OCA) -- The Revenue Vehicle

**The OCA Model** (coined by Nick Vasilescu, @NickVasilescu):

> "Do not sell AI automation scripts. Sell deployed swarms of OCAs."

**What is an OCA?**
An OCA (OpenClaw Computer Agent) operates a full computer -- browser,
filesystem, shell, GUI -- exactly as a human employee would. It does not
call APIs through a script. It operates the actual software. This is the
Manus/computer-use architecture applied to real business workflows.

**Why This Is the Right Business Model:**
- One-off automation scripts are dead-ends -- fragile, cannot learn, constant maintenance
- OCA swarms are living infrastructure -- they run continuously, learn, adapt, and deliver outcomes
- The retainer model follows naturally -- you do not buy an employee once; you pay them monthly
- The infiltration-to-expansion path is proven: solve one high-pain "boring" problem fast, earn trust, expand into the full vertical

**The "Boring Wedge" Go-To-Market Strategy:**
The highest-ROI, lowest-sales-resistance entry point for any business
client. Target mundane, repetitive pain points where the ROI is so obvious
the price is easy to justify.

**Top Boring Wedge Workflows:**
- **Legacy Data Migration** -- moving product/client data from old systems into modern CRMs
- **Competitive Price Scraping** -- monitoring competitor websites, auto-updating pricing sheets in real-time
- **Invoice Triage** -- scanning email inboxes, extracting due dates and amounts, generating priority payment lists
- **Compliance Auditing** -- reading transcripts/data against legal frameworks; proven to reduce 160-hour processes to 8 minutes
- **Lead Generation** -- running scrapers for targeted business leads (e.g., "100 HVAC leads in Texas"), returning verified contact info
- **Government Contracting** -- automating RFP searches on SAM.gov, generating capability statements from the company profile

**The 7-Day Sprint Rule:**
Deliver a working boring-wedge automation in under 7 days. "Fast beats
free." Speed of delivery proves competence and unlocks the long-term
retainer conversation.

**The SWIFT Framework (Implementation Sequence):**
1. **S**et up/Scope -- define exactly what the agent will and will not touch
2. **W**orkflow -- build the MVP; test all individual components
3. **I**terate -- refine until seamless
4. **F**ormalize -- package into a modular "Skill" (markdown + script) that any agent in the system can invoke
5. **T**rigger -- schedule with Cron or the agent's Heartbeat (e.g., 8 AM daily)

**Infiltration to Expansion Path:**

```
Boring Wedge (1 workflow, 7 days)
  -> One department solved
  -> Trust established
  -> Full OCA Swarm (multiple departments)
  -> High-ticket monthly retainer
  -> Permanence OS governance layer deployed over entire operation
```

**Where Permanence OS Meets OCA:**
Permanence OS is the **governance and orchestration layer** that routes
tasks to either Hermes (API-first, messaging/comms) or OpenClaw agents
(computer-use, GUI automation) depending on what the task needs. You do not
have to pick a platform -- your architecture already routes between them.

---

## SECTION 5: INFRASTRUCTURE AND DEPLOYMENT CONTEXT

**Local Development Environment:**
- Mac Mini -- the production machine; local-first is intentional
- Claude Code installed locally as the development interface
- VS Code as the editor layer

**Agent Deployment Stack (for OCA clients):**
- **Cloud Desktops** (Orgo, Windows 365 for Agents) -- use when agents need a full OS, multiple native apps, custom binaries, or long-lived state
- **Agentic Browsers** (Browserbase, E2B) -- use when workflows are mostly web-based (SaaS logins, scraping, form fills); better for concurrency and cost efficiency
- Preferred: Orgo for sub-5-second spin-up with persistent VMs
- **NemoClaw** (NVIDIA) -- sandbox orchestrator for OpenClaw agents with policy enforcement (see Section 11)

**Hermes vs. OpenClaw Decision Matrix:**

| Need | Use |
|------|-----|
| Fewer tools, API-first, messaging/comms | Hermes |
| Full computer use, GUI, visual confirmation | OpenClaw |
| Both | Permanence OS routes between them |

---

## SECTION 6: WHAT TO DO AT THE START OF EVERY SESSION

**Mandatory Orientation Sequence:**

```bash
# 1. See what we have been building
git log --oneline -20
# 2. See all active branches
git branch -a
# 3. Check for uncommitted work
git status
# 4. Run tests to confirm clean state
python3 -m pytest --tb=short -q
# 5. Read the current directory's context
cat context.md 2>/dev/null || echo "No context.md in this directory"
```

**Then report back:**
- Last 3 commits and what they accomplished
- Current branch and what it is for
- Test count and any failures
- What you think the next logical step is, based on git history

**Never assume we are starting from zero. We are always continuing.**

---

## SECTION 7: HOW TO HANDLE ERRORS AND BLOCKS

**Self-Repair Protocol:**
Claude Code is installed inside the agent's virtual environment so the
agent can debug and fix its own configuration files when it hits a
technical error. If you encounter a configuration error:
1. Read the error message fully
2. Check the relevant config file (.env, CLAUDE.md, context.md)
3. Propose a fix with your reasoning
4. Wait for human approval before applying changes to configuration files

**When Blocked:**
- Do not silently fail or skip
- Surface the block clearly: what you tried, what failed, what you need
- Ask a specific question, not a vague "what should I do?"

**Routing Instructions:**
1. When starting a task, read the context.md in the relevant workspace folder first (if one exists).
2. Do not read files outside the routed path unless requested.
3. Complex tasks: OBSERVE > THINK > PLAN > BUILD > VERIFY
4. Simple tasks: just do it.
5. Uncertain: ask ONE specific question before proceeding.

---

## SECTION 8: THE VISION -- WHERE THIS IS GOING

**The North Star:**
Build Permanence OS into the governance and orchestration layer that runs
on top of any business's AI infrastructure -- the constitutional layer that
makes AI deployments trustworthy, auditable, and human-authority-final.

**The OCA Agency (near-term revenue):**
- Land 3-5 clients with Boring Wedge automations in 90 days
- Convert to monthly retainers (OCA swarms running continuously)
- Use each client as a case study for the next
- Deploy Permanence OS as the governance layer for each OCA swarm

**Phase Roadmap:**

```
Phase 1 (NOW): Boring Wedge deployments, prove the model, generate revenue
Phase 2: First full OCA swarm for a client vertical (e.g., HVAC company, law firm, real estate team)
Phase 3: Permanence OS as a product -- sell the governance layer separately
Phase 4: Gas Town / Mayor Pattern -- Orchestrator coordinates multiple concurrent OCA swarms across multiple clients
Phase 5: Platform play -- Permanence OS as infrastructure for third-party OCA deployments
```

**Why This Wins If We Do Not Give Up:**
1. The codebase is real -- 960+ tests, live runtimes, proven architecture
2. The moat is real -- Adaptive Intelligence Loop, Sentinel governance, three-layer context system
3. The market is real -- every business has boring, repetitive workflows that agents can handle better than humans
4. The timing is right -- Claude Code, OpenClaw, computer-use agents are hitting production viability right now
5. The founder is full-time -- no half measures; building daily

**The Rules:**
- Follow the plan
- Do not give up when it is hard -- hard is where the competition stops
- Ship something every day, even if small
- Every client is a lesson; every lesson improves the system
- The Adaptive Intelligence Loop means we get better automatically over time -- build it right once and let it compound

---

## SECTION 9: INTELLECTUAL INFLUENCES (For Context Alignment)

**Technical:**
- **Lance Martin** (rlancemartin.github.io) -- "Agent Design Patterns," "Context Engineering for Agents," "Context Engineering in Manus" -- the theoretical backbone for this architecture
- **Nick Vasilescu** -- OCA model, computer-use agent deployment playbook
- **Geoffrey Huntley** -- Ralph Loop pattern (loop until plan is satisfied)
- **Steve Yegge** -- Gas Town / Mayor pattern (multi-agent orchestration)
- **Jake Van Clief** (@JEVanClief) -- Claude Code tutorials, folder systems for AI agents

**Strategic:**
- **Eduba** -- B2B consulting + teaching + governance wrapper for AI systems
- **Familiar** -- Self-modifying agent context frameworks
- **ChatPRD** -- AI product tooling positioning and pricing models

---

## SECTION 10: AGENT OPERATING PRINCIPLES (SUMMARY)

You are not a code-completion tool. You are a **co-builder** of a living
system. Your job is to:

1. **Know the history** -- read git, read context files, understand where we have been
2. **Maintain the architecture** -- three-layer context, 60/30/10 rule, modular Skills
3. **Protect the prime directive** -- human authority is final; never strip gates
4. **Build toward the vision** -- every session should move Phase 1 forward
5. **Surface decisions** -- when in doubt, ask; do not assume; do not skip
6. **Formalize everything** -- every solved workflow becomes a Skill file that any future agent can invoke

When this system is working the way it should, you will be able to walk
into any session, read this file, scan git history, and know exactly what
to build next -- without any additional instruction from Payton.

**That is the goal. Build toward it.**

---

## SECTION 11: NEMOCLAW / COMPUTER-USE INTEGRATION

**NemoClaw** (NVIDIA) is a security orchestration framework for running OpenClaw
agents in sandboxed, policy-governed containers.

**What it does:**
- Deploys isolated containers with strict security boundaries
- Routes inference through NVIDIA cloud (Nemotron model) or local Ollama
- Enforces network, filesystem, and process policies
- Provides always-on agent deployment with governance

**Requirements:**
- Docker Desktop or Colima (macOS container runtime)
- Node.js 20+ and npm 10+
- NVIDIA API key from https://build.nvidia.com
- ~2.4 GB disk for sandbox image

**Existing OpenClaw integration:**
- Model adapter: `models/openclaw.py`
- Health sync: `scripts/openclaw_health_sync.py`
- Safety audit: `scripts/openclaw_safety_audit.py`
- Registered in model registry with tier support (opus, sonnet, haiku)

**Hermes vs. OpenClaw routing** is handled by `core/model_router.py` --
tasks are routed to the appropriate provider based on capability requirements.

**Status:** Alpha. Use for experimentation and client proofs-of-concept.
Production deployments should wait for stable release.

---

## SUCCESS DEFINITION

| Check | Target |
|-------|--------|
| pytest -q | 0 new failures (960+ tests) |
| Secret scanner | clean |
| local_hub | green |
| Pages | excellent at 1440px + 375px |

---

*Permanence OS -- governed by humans, amplified by agents.*
*github.com/MaxProspero/permanence-os*
