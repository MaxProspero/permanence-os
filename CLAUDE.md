# PERMANENCE OS -- Project Map

## 1. Mission and Overview

| Field | Value |
|-------|-------|
| Product | Governed personal intelligence OS |
| Owner | Payton Hicks (pbhicksfinn@gmail.com) |
| Repo | github.com/MaxProspero/permanence-os (private) |
| Status | Full-time founder, done with school (BS+MS Finance, U of Arkansas) |
| Main branch | main |

Three live runtimes compose the system: a Flask dashboard API (Command Center), a static site server (Foundation Site), and an interactive shell (Ophtxn Shell).

## 2. The Floor Plan

Every top-level path, what it holds, and when to look there.

### Directories

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
| /models | Model configs and adapters: Claude, OpenAI, Ollama, XAI, registry | Changing model selection, adding providers, or adjusting model params |
| /outputs | Generated artifacts and briefings | Reviewing generated content or briefing output |
| /permanence_storage | Data storage layer: permanence.db, archives, logs, memory, outputs | Working with the persistence database or archived data |
| /scripts | 151 implementation modules (main execution layer) | Building or modifying any feature -- this is where most logic lives |
| /site/foundation | 13 HTML pages (Foundation Site served at :8787) | Editing UI pages, styling, or front-end behavior |
| /special | Specialized agents: arcana engine, chimera builder, digital twin, muse, practice squad, arch evolution | Working on experimental or specialized agent capabilities |
| /tests | 163 test files, 772+ tests | Writing tests, verifying changes, or debugging failures |
| /tunnel | Cloudflare tunnel config | Configuring remote access or tunnel routing |

### Top-level Python files

| File | Purpose |
|------|---------|
| cli.py | Unified CLI entrypoint (100+ commands) |
| dashboard_api.py | Flask backend API (Command Center at :8000) |
| horizon_agent.py | Horizon scanning agent |
| context_loader.py | Context assembly for agent runs |
| run_task.py | Task execution entry point |
| setup_integrations.py | Integration bootstrapping |
| codex_build_package.py | Codex build packaging |

## 3. Live Services

| Service | URL | Backend |
|---------|-----|---------|
| Command Center | http://127.0.0.1:8000 | dashboard_api.py (Flask) |
| Foundation Site | http://127.0.0.1:8787 | site/foundation/ (static) |
| Ophtxn Shell | http://127.0.0.1:8797/app/ophtxn | Interactive shell |

## 4. Site Pages (13 total)

| Page | File | Purpose |
|------|------|---------|
| Lobby | index.html | Landing page |
| Control Room | local_hub.html | Local ops hub |
| Command Center | command_center.html | Dashboard |
| Trading Room | trading_room.html | Market interface |
| Night Capital | night_capital.html | Venture intelligence |
| Daily Planner | daily_planner.html | Planning interface |
| Terminal | ophtxn_shell.html | Shell/REPL |
| Tower | rooms.html | Workspace rooms |
| AI School | ai_school.html | Education |
| App Studio | official_app.html | App interface |
| Agent View | agent_view.html | FaceTime-like agent UI |
| Comms Hub | comms_hub.html | Unified messaging |
| Mind Map | press_kit.html | Mind mapping |

## 5. Naming Conventions

| Type | Pattern | Example |
|------|---------|---------|
| Commits | feat(scope): description / fix(scope): description | feat(site): add glassmorphism cards |
| Branches | codex/upgrade-YYYYMMDD or claude/[name] | codex/upgrade-20260313 |
| Dated docs | YYYY-MM-DD_[topic].md | 2026-03-13_routing_overhaul.md |
| Versioned docs | [name]_v[N]_[status].md | canon_v2_draft.md |

## 6. Global Standards

### Python
- try/except on ALL file reads and network calls
- AbortController on all fetches
- No bare exceptions -- catch specific error types

### HTML and CSS
- Staggered animations via .animate:nth-child
- CSS custom properties in :root
- Glassmorphism cards as the default card style

### Fonts (approved set only)
- Sora -- body text
- IBM Plex Mono -- code
- Orbitron -- display/headings
- DM Mono -- labels and metadata

### Colors
- --c1 (teal), --c2 (gold), --c3 (blue), --rose, --violet

### General
- NO emojis anywhere in the codebase
- NO Inter, Roboto, Arial, or Space Grotesk fonts

## 7. Never Touch

- Do NOT commit API keys or tokens
- Do NOT remove governance/approval gates
- Do NOT write DOM without diffing current value first
- Do NOT use setInterval < 30000ms for health polling
- Do NOT use unapproved fonts (see Section 6)

## 8. Routing Instructions

1. When starting a task, read the context.md in the relevant workspace folder first (if one exists).
2. Do not read files outside the routed path unless requested.
3. Complex tasks: OBSERVE > THINK > PLAN > BUILD > VERIFY
4. Simple tasks: just do it.
5. Uncertain: ask ONE specific question before proceeding.

## 9. Success Definition

| Check | Target |
|-------|--------|
| pytest -q | 0 failures (772+ tests) |
| Secret scanner | clean |
| local_hub | green |
| Pages | excellent at 1440px + 375px |
