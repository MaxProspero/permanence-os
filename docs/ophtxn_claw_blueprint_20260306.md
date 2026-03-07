# Ophtxn Claw Blueprint (2026-03-06)

Objective: build an Ophtxn-native agent runtime (`ophtxn-claw`) that keeps the speed and UX appeal of OpenFang/OpenClaw patterns while preserving your governance model, memory continuity, and no-spend-first controls.

## Strategic Positioning

- `ophtxn-claw`: real-time personal agent runtime + channel execution engine.
- `Permanence OS`: governed intelligence system and decision layer on top.
- `Ophtxn app`: user-facing shell where personality, memory, planning, and approvals are visible.

This gives you one coherent stack instead of disconnected bots.

## Inputs and Inspiration

- OpenFang model: open-source agent platform with app/plugin ecosystem and local/cloud model support.
- OpenFang recent release trajectory (permissions, app management, variables context).
- OpenClaw model: robust local gateway, channel adapters, CLI/operator workflows.
- User-shared X post context was used directionally; the exact post payload for `2029637900204171457` was not retrievable via unauthenticated endpoint at execution time.

## Product Architecture

### Layer A: Runtime Core (`ophtxn-claw`)
- Session engine (chat + task execution).
- Adapter bus (Telegram, Discord, Web, iMessage later).
- Model router (ollama-first, paid fallback only by policy).
- Tool runtime with explicit capability scopes.

### Layer B: Governance and Memory (`Permanence OS`)
- Approval gates before high-impact actions.
- Personal memory graph (facts, habits, preferences, commitments).
- Chronicle timeline (what changed, when, why).
- Cost and risk controls (no-spend + low-cost policies).

### Layer C: Operator Surfaces (`Ophtxn`)
- App dashboard for status, queues, and recommendations.
- Telegram/Discord conversation interface.
- Admin surface for permissions, connectors, and release controls.

## Capability Targets (v1)

1. Unified identity + memory across Telegram, Discord, and app shell.
2. Command + natural-chat hybrid flow (chat by default, commands when needed).
3. Zero-ambiguity change logs and execution board visibility.
4. Strict governance for spend, posting, and external writes.
5. Research ingestion pipeline that proposes improvements rather than auto-mutating core behavior.

## Build Plan

## Phase 0 - Stabilize Current Stack (Now)
- Keep OpenClaw channels healthy and visible in `comms-status`.
- Reduce approval backlog to controlled levels.
- Freeze security posture and tighten Telegram group controls with allowlists.

Deliverable:
- Daily operations stable with warnings near zero.

## Phase 1 - Extract Runtime Contract (`ophtxn-claw` alpha)
- Define a provider-agnostic runtime contract:
  - input envelope
  - execution context
  - action proposal
  - approval state
  - output envelope
- Move channel handlers behind this contract.

Deliverable:
- `ophtxn-claw` service API spec + adapter compliance tests.

## Phase 2 - App/Plugin System
- Build app registry with permission scopes (read memory, write tasks, send message, external API call).
- Add variables/context layer for reusable runtime context packs.
- Add kill-switch and per-app spending caps.

Deliverable:
- Controlled app/plugin marketplace for your personal stack.

## Phase 3 - Personal Agent Mode (You-first)
- Personality modes with persistent preference tuning.
- Habit loop + accountability + planning integration.
- Finance/work execution tracks with measurable outcomes.

Deliverable:
- Your full personal second-brain operator.

## Phase 4 - Multi-user Productization
- Onboarding wizard to create personal assistants from templates.
- Team/corporate mode with department agents and coordination logic.
- Tenant isolation and enterprise governance model.

Deliverable:
- Public Ophtxn platform with personal and enterprise tiers.

## Engineering Principles

- Local-first by default.
- No autonomous spending.
- Approval required for irreversible or external-write actions.
- Every automation must produce auditable artifacts.
- Keep interfaces simple; complexity stays behind governance layers.

## Immediate Next 10 Technical Steps

1. Lock Telegram group security posture (allowlist + approved sender IDs).
2. Add `ophtxn-claw` runtime schema (`core/ophtxn_claw_contract.py` or equivalent module).
3. Add adapter conformance tests for Telegram and Discord.
4. Add `ophtxn-claw status` command in CLI.
5. Add app/plugin manifest format and validator.
6. Add permission middleware for tool invocation.
7. Add per-session cost ledger and fail-closed budget guards.
8. Add memory write classifier (fact/habit/decision/task).
9. Add deployment profile presets (`personal`, `build`, `enterprise-preview`).
10. Add benchmark harness for latency, reliability, and quality.

## Risks and Controls

- Risk: over-automation before stable governance.
  - Control: approvals + staging lanes + simulation before promotion.
- Risk: token/cost drift.
  - Control: no-spend defaults, provider caps, audit checks.
- Risk: channel fragility.
  - Control: runtime probe in health loop + fallback paths.
- Risk: persona inconsistency.
  - Control: canonical profile + memory conflict checks.

## Success Criteria

- You can talk naturally to Ophtxn and it reliably remembers + executes.
- Commands from Telegram/Discord map to the same governed runtime.
- Daily status answers: healthy, affordable, and improving.
- New features are proposed, tested, and approved through one consistent flow.

## References

- https://github.com/RightNow-AI/openfang
- https://github.com/RightNow-AI/openfang/releases
