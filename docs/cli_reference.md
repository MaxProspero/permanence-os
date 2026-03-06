# CLI Reference

This is the canonical quick reference for `cli.py`.

For operator-oriented daily flow, use:
- [Operator Command Guide](ophtxn_operator_command_guide.md)

## Discovery

```bash
python cli.py --help
python cli.py <command> --help
```

## System Readiness

```bash
python cli.py integration-readiness
python cli.py ophtxn-launchpad --action status --strict --min-score 80
python cli.py ophtxn-production --action status --strict --min-score 80
python cli.py status
python cli.py status-glance
```

## Interface and Runtime

```bash
python cli.py operator-surface --no-open
python cli.py command-center
python cli.py foundation-site
python cli.py foundation-api
python cli.py openclaw-status
python cli.py openclaw-status --health
```

## Communication Control

```bash
python cli.py comms-status
python cli.py comms-doctor
python cli.py comms-automation --action run-now
python cli.py telegram-control --action status
python cli.py telegram-control --action poll --enable-commands --ack --max-commands 5
python cli.py discord-feed-manager --action list
python cli.py discord-telegram-relay --action status
python cli.py discord-telegram-relay --action run
```

## Governance and Approvals

```bash
python cli.py approval-triage --action status
python cli.py approval-triage --action top --limit 12 --source phase3_opportunity_queue
python cli.py chronicle-approval-queue --action status
python cli.py chronicle-execution-board --action status
```

## Budget and Provider Controls

```bash
python cli.py low-cost-mode --action status
python cli.py low-cost-mode --action enable
python cli.py no-spend-audit --strict
python cli.py money-first-gate --strict
python cli.py money-first-lane --strict
```

## Research and Opportunity Pipeline

```bash
python cli.py social-research-ingest
python cli.py github-research-ingest
python cli.py github-trending-ingest
python cli.py ecosystem-research-ingest
python cli.py platform-change-watch
python cli.py idea-intake --action process --max-items 30 --min-score 30
python cli.py opportunity-ranker
python cli.py opportunity-approval-queue
python cli.py phase3-refresh
```

## Ops Pack and Daily Cycle

```bash
python cli.py ophtxn-daily-ops --action cycle
python cli.py ophtxn-ops-pack --action status
python cli.py ophtxn-ops-pack --action run --strict
python cli.py ophtxn-completion --target 95 --strict
```

## Revenue and Execution

```bash
python cli.py revenue-action-queue
python cli.py revenue-architecture
python cli.py revenue-execution-board
python cli.py revenue-weekly-summary
python cli.py sales-pipeline list --open-only
```

## Memory and Chronicle

```bash
python cli.py second-brain-init
python cli.py second-brain-loop
python cli.py second-brain-report
python cli.py chronicle-backfill
python cli.py chronicle-capture --note "session summary"
python cli.py chronicle-report --days 365
python cli.py chronicle-publish --docx
```

## Maintenance and Hygiene

```bash
python cli.py clean --all
python cli.py cleanup-weekly
python cli.py secret-scan --staged
python cli.py test
python scripts/clean_artifacts.py --all --dry-run
```

## Recommended Daily Sequence

1. `python cli.py comms-status`
2. `python cli.py no-spend-audit --strict`
3. `python cli.py ophtxn-ops-pack --action run --strict`
4. `python cli.py approval-triage --action top --limit 12 --source phase3_opportunity_queue`
5. `python cli.py ophtxn-production --action status --strict --min-score 80`
