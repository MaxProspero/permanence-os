# Ophtxn Best Path (March 2026)

Last updated: 2026-03-06

This is the recommended path based on implemented commits, operating results, and current repo state.

## Current State Summary

- Interface stack is operational (`8000`, `8787`, `8797`).
- Telegram and Discord command flows are working.
- No-spend controls and low-cost routing are available.
- Launchpad/production status checks can pass at strict thresholds.
- Repo documentation is now structured, with archive separation for legacy material.

## Phase 1: Stability Lock (Now)

Goal: keep operations reliable and deterministic.

1. Keep `main` as only long-lived branch.
2. Run strict daily ops pack.
3. Keep no-spend mode and audit strict.
4. Resolve failures before adding net-new features.

Commands:

```bash
python cli.py comms-status
python cli.py no-spend-audit --strict
python cli.py ophtxn-ops-pack --action run --strict
python cli.py ophtxn-launchpad --action status --strict --min-score 80
```

## Phase 2: Signal-to-Action Quality (Next)

Goal: convert research intake into high-quality approved actions.

1. Keep intake disciplined (`idea-intake`, ranked opportunities).
2. Limit queue growth with source-specific triage.
3. Prefer safe batch decisions for low-risk items.
4. Track acceptance/rejection reasons for better ranking policy tuning.

Commands:

```bash
python cli.py idea-intake --action process --max-items 30 --min-score 30
python cli.py opportunity-ranker
python cli.py opportunity-approval-queue
python cli.py approval-triage --action top --limit 12 --source phase3_opportunity_queue
```

## Phase 3: Productization Readiness

Goal: make external delivery consistent without breaking core operations.

1. Keep foundation and production preflight checks green.
2. Keep docs and runbooks synchronized with real commands.
3. Freeze destructive refactors unless test coverage is present.
4. Use short codex branches and merge frequently.

Commands:

```bash
python cli.py ophtxn-production --action preflight --check-wrangler
python cli.py ophtxn-production --action status --strict --min-score 80
python cli.py comms-doctor
python cli.py secret-scan --staged
```

## Phase 4: Expansion (Only After Phases 1-3 Hold)

Goal: add capabilities without degrading reliability.

- Optional channel expansion (iMessage) only when local dependencies are healthy.
- Additional model/provider strategies only with no-spend safeguards.
- New UI/app surfaces only if operations and approvals stay stable.

## What Not To Do

- Do not let docs drift from actual file state.
- Do not keep stale duplicate snapshots in root.
- Do not merge large feature sets without tests and runbook updates.
- Do not treat OpenClaw and Telegram/Discord as implicitly identical execution paths.

## Operating KPI Baseline

- `comms-status` warnings: 0 (target)
- launchpad score: >= 80 (target 100 when stable)
- strict ops pack failures: 0
- open approval queue growth: controlled by daily triage cadence

## Decision Rule

When in doubt: choose reliability, governance, and maintainability over velocity spikes.
