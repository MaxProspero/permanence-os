# Ophtxn Governance Operating Model

Last updated: 2026-03-06

This document defines how Ophtxn operates safely while still moving fast.

## Core Principles

1. Human authority is final.
2. High-impact changes require explicit review.
3. No-spend and risk controls are defaults, not optional.
4. Every automation should produce auditable artifacts.
5. Reliability beats novelty.

## Control Layers

- Layer 0: Human decision maker
- Layer 1: Canon and policy constraints
- Layer 2: Routing + governance controls (Polemarch, gates, approvals)
- Layer 3: Domain execution agents
- Layer 4: Interfaces (Telegram, Discord, OpenClaw, local web)
- Layer 5: Audit and improvement loops

## Approval Policy

Changes that can impact money, security, user identity, or external publishing should enter approval queues before execution.

Typical approval-driven actions:

- runtime/provider switches
- production deployment changes
- outbound social/publish actions
- connector permission escalations

## Cost Policy

- Keep low-cost mode enabled by default.
- Keep no-spend audit strict in daily operations.
- Route to local/low-cost providers first unless an explicit override is approved.

Reference commands:

```bash
python cli.py low-cost-mode --action status
python cli.py no-spend-audit --strict
python cli.py ophtxn-ops-pack --action run --strict
```

## Communication Policy

- Telegram is the primary operator interface.
- Discord is feed/research intake and relay.
- OpenClaw is an adjacent runtime and should be health-checked explicitly.
- Optional channels (like iMessage) should remain disabled until prerequisites are verified.

## Reliability Policy

- Prefer small, auditable loops over large opaque automation.
- Every major workflow should emit:
  - human-readable markdown report in `outputs/`
  - machine payload in `memory/tool/`
- Any failing automation should degrade cleanly and preserve diagnostics.

## Documentation Policy

- Keep `README.md` and `docs/README.md` aligned with actual files.
- Move stale versioned plans into `docs/archive/`.
- Append major implementation changes to `docs/ophtxn_journey_change_log.md`.

## Branch and Release Policy

- `main` is the single source of truth.
- Use short-lived `codex/*` branches for feature or cleanup passes.
- Merge only after test + readiness validation.
- Close accidental reverse-direction PRs immediately.

## Daily Operator Checklist

1. `python cli.py comms-status`
2. `python cli.py no-spend-audit --strict`
3. `python cli.py ophtxn-ops-pack --action run --strict`
4. `python cli.py approval-triage --action top --limit 12 --source phase3_opportunity_queue`
5. `python cli.py ophtxn-production --action status --strict --min-score 80`
