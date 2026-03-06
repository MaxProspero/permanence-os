# Architecture

Permanence OS is a governed multi-surface operator system.

The architecture is designed for three constraints:

1. Human authority remains final.
2. Operational state is auditable.
3. Cost/risk controls are enforceable by default.

## Authority Model

```
Layer 0  Human authority (final decision)
Layer 1  Canon and governance policy
Layer 2  Polemarch/router and control gates
Layer 3  Execution agents and domain bots
Layer 4  Channels and interfaces (Telegram/Discord/OpenClaw/Web)
Layer 5  Audit, memory, and improvement loops
```

## Runtime Components

- `cli.py`
  - Unified command router.
  - Calls `scripts/*` modules with explicit action flags.

- `scripts/`
  - Operational logic and loops (comms, approvals, production checks, ops packs).
  - Writes structured output to `outputs/` and `memory/tool/`.

- `app/foundation/server.py`
  - Foundation/Ophtxn local API shell (`:8797`).
  - Provides `/health` and app shell routes.

- `dashboard_api.py` + command center scripts
  - Local dashboard/state surface (`:8000`).

- `site/foundation/`
  - Static web assets for local and hosted shell.

- OpenClaw gateway
  - External runtime that can be queried and integrated.
  - Treated as an adjacent system with explicit probes and adapters.

## Data and State

- `memory/working/`
  - Mutable workflow state (queues, policies, generated control files).

- `memory/tool/`
  - Machine-readable payloads from each automation/command run.

- `memory/approvals.json`
  - Human-review queue for governed changes.

- `outputs/`
  - Human-readable reports and latest status markdown files.

- `logs/automation/`
  - Launchd and loop runtime logs.

## Interface Surfaces

- Telegram
  - Primary operator command/chat interface.

- Discord
  - Feed intake + relay to operator context.

- OpenClaw
  - Runtime/dashboard/control surface with its own channel/plugin state.

- Local web
  - Command center + foundation/ophtxn shells for desktop operation.

Important: these surfaces are connected by explicit scripts and config, not by assumption.

## Governance and Safety Controls

- Approval gates: high-impact actions queue for explicit decisions.
- No-spend mode: local-first provider and budget-aware enforcement.
- Comms status doctoring: drift detection across channels and automation.
- Secret scanning: pre-push checks for sensitive material.

## Operational Flow (Baseline)

1. Ingest signals (Telegram/Discord/research feeds).
2. Rank and queue opportunities.
3. Triage approvals.
4. Execute constrained actions.
5. Emit reports and store tool payloads.
6. Run reliability and comms health loops.
7. Record changes in journey/changelog docs.

## Deployment Model

- Local-first development and control.
- Optional Cloudflare-hosted public surfaces.
- Production readiness validated through `ophtxn-launchpad` and `ophtxn-production` checks.
