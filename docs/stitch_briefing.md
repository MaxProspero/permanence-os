# Permanence OS / Ophtxn -- Design System Briefing for Stitch/Figma

## What This Is

Permanence OS is a governed personal intelligence operating system. It combines persistent memory, multi-agent coordination, trading intelligence, content pipelines, and human approval gates in a single local-first runtime. The frontend is called **Ophtxn** (the operator interface).

## Brand Identity

- **Product name:** Ophtxn (operator-facing) / Permanence OS (platform)
- **Tagline:** "The personal intelligence OS with governance built in."
- **Aesthetic:** Warm precision -- Apple HIG meets Linear meets Arc Browser. Tech + southern charm. Governed intelligence that feels like home.
- **NOT:** Startup cute, SaaS generic, cold terminal. If it looks like a SaaS homepage, it's wrong. If it looks like a governed intelligence system, it's right.

## Design Tokens (Current)

### Colors
- **Base dark:** #0A0A0F (warm dark, not pure black)
- **Surface 1:** #12121A
- **Surface 2:** #1A1A24
- **Surface 3:** #23232F
- **Surface 4:** #2D2D3A
- **Primary text:** #E0E0E0 (off-white, not pure white)
- **Secondary text:** #7B96AF
- **Tertiary text:** rgba(255,255,255,0.3)
- **Accent primary (teal):** #00e5c4 (WGSN Color of Year 2026)
- **Accent secondary (gold):** #efbb5f
- **Accent tertiary (blue):** #73b8ff
- **Rose:** #ff5c8a
- **Violet:** #7b6fff

### Typography
- **Body:** Sora (400/600/700/800)
- **Code/Data:** IBM Plex Mono (400/600) -- all numbers use this with tabular-nums
- **Display/Headings:** Orbitron (700/900)
- **Labels/Metadata:** DM Mono (400/500)

### Spacing (4px base grid)
4, 8, 12, 16, 24, 32, 48, 64, 80, 100px

### Border Radius
- Cards: 12px
- Buttons: 8px
- Pills: 9999px
- Inputs: 10px

### Signature Element: Left-Border Accent Stripe
Every card has a 3px left border in an accent color. This is the visual DNA of the system.
- Teal stripe = primary/default
- Gold stripe = financial/secondary
- Rose stripe = alerts/approval queue
- Violet stripe = AI/agents
- Blue stripe = data/analytics

### Glass Card Pattern
- Background: rgba(255,255,255,0.03)
- Border: 1px solid rgba(255,255,255,0.06)
- Border-left: 3px solid [accent color]
- Border-radius: 12px
- Hover: background lightens to 0.05, transform translateY(-2px)

### Menubar (macOS-style, top of every page)
- Height: 28px
- Background: translucent dark with backdrop-filter blur
- Left: Logo (hexagon) + "Ophtxn" + File / View / Go buttons
- Right: Dark/Light toggle + Clock + Date
- Logo click: Opens Permanence OS (port 8000)

## The 14 Pages

### 01. Lobby (index.html)
**Purpose:** Landing page. System overview and quick navigation.
**Key elements:** Hero with tagline, two CTA buttons (Command Center + Terminal), stat row ($0.00 revenue, Human approved, Local-first), differentiators list, outcomes section.
**Connects to:** Everything -- it's the front door.

### 02. Control Room (local_hub.html)
**Purpose:** Local ops hub. System health, runtime status, service controls.
**Key elements:** Hero with 2 CTAs, three service cards (Command Center :8000, Foundation Site :8787, Ophtxn Shell :8797) with status dots, approval queue panel, stat row (services/approvals/uptime).
**Connects to:** Command Center, Terminal, approval queue API.

### 03. Command Center (command_center.html)
**Purpose:** The main dashboard. Agent coordination, approvals, system metrics.
**Key elements:** Three-panel layout with sidebar tabs, boot sequence animation, OPHTXN wordmark, agent console, briefing viewer, revenue ops, memory inspector, canon viewer, audit log.
**Connects to:** All backend APIs at port 8000.

### 04. Trading Room (trading_room.html)
**Purpose:** Market interface with live chart, positions, signals, and trading agents.
**Key elements:** Candlestick chart (canvas), agent status cards (4 agents), signal panel, backtest tab, ticker tape, activity feed. Time range buttons (1D-ALL).
**Connects to:** /api/markets/ohlcv, /api/analysis/smc-ict, /api/backtest/run.

### 05. Markets Terminal (markets_terminal.html)
**Purpose:** Cross-market data terminal. Live equities, crypto, forex, commodities.
**Key elements:** Tab bar (Predictions, Equities, FX, Crypto, Futures), data tables per asset class, watchlist sidebar, market status bar, split view toggle.
**Connects to:** /api/markets/snapshot, real-time data refresh every 60s.

### 06. Night Capital (night_capital.html)
**Purpose:** Venture intelligence and capital deployment tracking.
**Key elements:** Portfolio overview card (6 metrics: Total Deployed, Active Positions, P/L, Dry Powder, MOIC, IRR), deployment log table, add position form.
**Connects to:** Local state, future: deal pipeline API.

### 07. Daily Planner (daily_planner.html)
**Purpose:** Task planning and daily operations workflow.
**Key elements:** Date navigator with arrows, stat row (Total/Completed/Remaining), progress bar, task list with add input. localStorage-backed CRUD.
**Connects to:** Local localStorage for tasks.

### 08. Terminal (ophtxn_shell.html)
**Purpose:** Interactive shell. Run commands, query agents, chat with the system.
**Key elements:** Session login form, chat-style message area, sidebar with conversation history, status bar (completion/revenue/approvals/tasks), quick action pills, input bar with "Ask anything..." placeholder.
**Connects to:** /api/* endpoints on port 8797, agent execution.

### 09. Tower (rooms.html)
**Purpose:** Workspace directory. Every room is a workspace.
**Key elements:** 13 room cards in a 3-column grid. Each card has floor number, name, description, status, and color-coded left border. Cards link to their respective pages.
**Connects to:** All other pages via navigation.

### 10. AI School (ai_school.html)
**Purpose:** Knowledge library. Bookmarks, research, documents, agent training.
**Key elements:** Library sidebar with categories, research feed with pipeline visualization, skill cards by level (Beginner/Intermediate/Advanced/Expert), data sources panel, research request input, connected sources status.
**Connects to:** Bookmark pipeline, research APIs, document store.

### 11. App Studio (official_app.html)
**Purpose:** Developer console. Operator profile, command builder, integrations.
**Key elements:** Two-column layout (Operator Profile form + Command Builder with presets), command output console, integration status grid (6 services).
**Connects to:** Profile localStorage, command execution, health endpoints.

### 12. Agent View (agent_view.html)
**Purpose:** Watch your AI agents work. Mission control for agent monitoring.
**Key elements:** 6 agent cards in 2-column grid (Sentinel, Orchestrator, Adaptive Loop, Risk Manager, Social Listener, Whale Tracker). Each shows name, role, status dot, model. Activity feed below.
**Connects to:** Agent status APIs, future: live agent streaming.

### 13. Comms Hub (comms_hub.html)
**Purpose:** Unified messaging across platforms.
**Key elements:** 5 channel cards (Telegram, Discord, Email, WhatsApp, Internal) with connection status, message feed with empty state, compose bar.
**Connects to:** Future: messaging APIs, Telegram/Discord integrations.

### 14. Mind Map (press_kit.html)
**Purpose:** Visual thinking space for ideas and connections.
**Key elements:** Canvas-based mind map with toolbar (Select, Pan, Plan, Task, Note, Workflow, Link, zoom controls). Drag nodes, draw connections, keyboard shortcuts. localStorage persistence.
**Connects to:** Local state, future: knowledge graph API.

## How Pages Connect

```
LOBBY (front door)
  |
  +-- Control Room (system health)
  |     +-- Command Center API (:8000)
  |     +-- Foundation Site (:8787)
  |     +-- Terminal (:8797)
  |
  +-- Trading Room (markets)
  |     +-- Markets Terminal (data feeds)
  |     +-- Night Capital (venture/capital)
  |
  +-- Terminal (command line)
  |     +-- Agent View (monitor agents)
  |     +-- All APIs
  |
  +-- Tower (workspace directory)
  |     +-- Links to ALL other pages
  |
  +-- AI School (knowledge)
  |     +-- Mind Map (visual thinking)
  |     +-- Research pipeline
  |
  +-- App Studio (developer tools)
  |     +-- Integrations
  |
  +-- Comms Hub (messaging)
  |     +-- Telegram, Discord, Email
  |
  +-- Daily Planner (tasks)
```

## Screenshots

All 14 page screenshots are in: `/outputs/screenshots/`
- 01_lobby.png through 14_mind_map.png
- Captured at 1440x900 viewport, dark mode

## What Needs Design Next (Stitch/Figma Pipeline)

1. **Sports Betting page** -- Live Vegas odds, sportsbook tiers (DraftKings/FanDuel/BetMGM + PrizePicks/Underdog + Kalshi), channel links
2. **NotebookLM-style document system** -- Source upload, notes, search
3. **Chat-style terminal** -- Claude/ChatGPT-like interface powered by multiple LLMs
4. **Social OS module** -- Agent-managed social media (Watch Them Cook, Flip View, River)
5. **Settings page** -- Feature toggles, model selection, API key management
6. **Onboarding flow** -- First-time user setup
7. **Music player** -- Embedded streaming (Spotify/Apple Music integration or open-source)
8. **Bloomberg/news stream** -- Yahoo Finance Live, CNBC, TBPN embedded
9. **Drawing/whiteboard** -- Freehand canvas for trading ideas
10. **OPTI mascot** -- Animated brand character for empty states and notifications
