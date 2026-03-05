# Ophtxn Personal Agent Roadmap

## Mission
Build Ophtxn as a governed personal AI operating system that is useful every day across life, business, learning, execution, and decision support. Prove it personally first. Productize second. Enterprise third.

## Product Sequence
1. Personal OS (now): one user, high trust, high frequency, daily utility.
2. Guided App (next): onboarding flow that builds a governed assistant per user.
3. Workforce Mode (long arc): coordinated multi-user agents with governance and role-based authority.

## Non-Negotiables
- Canon is law and remains human-controlled.
- Agents are bounded roles with bounded tools.
- Human authority is final for sensitive or irreversible actions.
- Memory compounds with auditability.
- Every action path is observable and testable.

## Ophtxn Core Capabilities (Personal Phase)
- Conversational daily assistant in Telegram with command + chat routing.
- Persistent memory of user preferences, goals, and context.
- Action control surface for status, health checks, and operating tasks.
- Intake pipeline for text, links, media, and voice into structured queues.
- Daily and weekly brief generation from unified memory.

## Current State (March 4, 2026)
- Telegram bot is live and reachable (`@Teleophtxnbot`).
- Chat-agent replies are active with Anthropic API.
- Personal memory commands are implemented:
  - `/memory-help`
  - `/memory`
  - `/remember <note>`
  - `/recall`
  - `/profile`
  - `/profile-set <field> <value>`
  - `/profile-get`
  - `/profile-history [field]`
  - `/profile-conflicts`
  - `/personality [mode]`
  - `/personality-modes`
  - `/habit-add <name> | cue: ... | plan: ...`
  - `/habit-plan <name> | cue: ... | plan: ...`
  - `/habit-done <name>`
  - `/habit-nudge`
  - `/habit-list`
  - `/habit-drop <name>`
  - `/forget-last`
- A dedicated 30-second Telegram chat automation loop is active for near-real-time response.
- Governed learning loop is available (`python cli.py governed-learning`) with explicit approval gates and read-only ingest scope for AI/finance/excel/media.
- Self-improvement pitch loop is available (`python cli.py self-improvement`) to propose upgrades, request approval, and queue approved ideas.

## Program Scoreboard (March 5, 2026)
Measured from live status outputs (`integration-readiness`, `comms-status`, `comms-doctor`, `ophtxn-brain`, `self-improvement`, `terminal-task-queue`).

- Personal agent core (chat + memory + commands): 70%
- Communications reliability (Telegram/Discord automation): 82%
- Governed learning + self-improvement loops: 55%
- Research ingest and watchlists (GitHub/X/Discord): 62%
- Monetization/revenue operating layer: 58%
- Productized app layer (multi-user onboarding/UI/backend): 20%
- Corporate/enterprise coordination mode: 5%

Mission-level overall progress: 43%

## Definition of 100% (Personal-First Program)
100% for this stage means:
1. Ophtxn personal system is stable and trusted for daily use (30+ days).
2. Telegram primary interface is reliable in both DM and channel contexts.
3. Terminal task queue drains to near-zero daily with measurable completion rate.
4. Governed learning is enabled, scheduled, and producing approved updates consistently.
5. External connectors stay read-only by default, with explicit approval gates for writes.
6. Daily/weekly brief loops run automatically with zero blocker warnings.
7. Cost governance is active (no autonomous spend; free/local-first routing).
8. App foundation exists (auth, user profile, memory schema, onboarding wizard, role policy).
9. Cross-device continuity works (desktop + phone + tablet without jailbreak dependency).
10. Security and observability are production-grade (secret hygiene, audits, recoverability).

## 30% -> 100% Execution Map

### Phase 1: 43% -> 60% (Operational Consistency)
Goal: make current personal stack reliable every day.

Deliverables:
- Telegram routing hardening:
  - support DM + channel scope explicitly
  - verify command/chat loops process new updates every cycle
- Fix/close pending terminal task queue items (currently 6 pending).
- Enable xAI keychain target for Grok fallback routing.
- Resolve self-improvement pending pitch and either approve or reject.

Exit criteria:
- `python cli.py comms-status` warnings = 0 for 7 consecutive daily runs.
- `python cli.py terminal-task-queue --action status` pending <= 1.
- Telegram receives and responds within expected loop interval.

### Phase 2: 60% -> 80% (Autonomy Under Governance)
Goal: controlled self-improvement and research compounding.

Deliverables:
- Turn governed learning policy from disabled to enabled under approval model.
- Run scheduled governed-learning + self-improvement automation with audit logs.
- Expand research feeds with quality filters and weekly synthesis outputs.
- Implement model-routing policy (Anthropic/OpenAI/xAI) based on task + budget.

Exit criteria:
- At least 10 approved improvement proposals with low rollback rate.
- Weekly research brief generated automatically and consumed in planning loop.
- No unauthorized external write actions.

### Phase 3: 80% -> 90% (App Foundation)
Goal: productize personal system into reusable app core.

Deliverables:
- Build onboarding flow that creates a personalized assistant configuration.
- Implement user profile schema + persistent memory boundary model.
- Ship core app surfaces: chat, memory viewer, goals/routines, task board, approval queue.
- Add billing-safe mode: hard spend caps and approval guardrails.

Exit criteria:
- New test user can complete onboarding and run personal assistant loops in under 20 minutes.
- All core surfaces pass smoke and integration tests.

### Phase 4: 90% -> 100% (Launch Readiness)
Goal: production-quality system ready for personal scale-up and pilot users.

Deliverables:
- Hardening: backup/restore drills, incident playbook, regression suite coverage.
- Security posture: keychain-first secret management, secret scan gates, least privilege tokens.
- Observability: uptime, loop freshness, command latency, task completion dashboards.
- Pilot package: docs, support flow, and migration path to enterprise mode.

Exit criteria:
- 30-day stability window with no Sev-1 failures.
- Full launch checklist complete and signed off.

## Immediate Build Track
1. Fix Telegram scope for both primary channel and DM thread; verify real-time response loop.
2. Clear terminal queue backlog and enforce daily queue hygiene.
3. Approve/reject pending self-improvement proposal and execute resulting action.
4. Enable governed-learning policy with explicit approval actor and cadence.
5. Wire model routing policy (Anthropic/OpenAI/xAI) with fallback and cost caps.
6. Add structured daily operating loop (morning plan, midday correction, evening review).
7. Add decision and execution protocols tied to measurable outcomes.
8. Finalize app onboarding spec and data model for multi-user rollout.
9. Add production observability metrics and alert thresholds.
10. Build launch checklist and complete reliability/security gates.

## Graduation Criteria (Personal -> App)
- Ophtxn is used daily for 30+ consecutive days.
- It supports planning, execution, and reflection with measurable value.
- Memory stays coherent and useful across sessions.
- Governance prevents unsafe or unauthorized actions.
- Repeatable onboarding prompts exist to generate a personalized assistant for a new user.

## Enterprise Direction (Later)
- Per-user agents with local memory boundaries.
- Cross-agent collaboration through policy-controlled channels.
- Work distribution based on role fit, energy, skill, and load.
- Manager visibility with privacy-safe summaries.
- Organizational governance layer on top of personal governance.
