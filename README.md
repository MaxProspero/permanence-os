# Permanence OS

Permanence OS is a governed personal intelligence system that runs local-first operations for planning, research, execution, and communication.

It is built around one rule: automation can assist, but human authority is final.

## Current Focus

- Stabilize Ophtxn as a personal operator system.
- Keep no-spend defaults active unless explicitly overridden.
- Maintain reliable Telegram and Discord command/control flows.
- Keep all changes auditable through reports, tests, and change logs.

## Live Local Surfaces

When the operator stack is running, these endpoints are available:

- Command center API/UI: `http://127.0.0.1:8000`
- Foundation site: `http://127.0.0.1:8787`
- Ophtxn shell: `http://127.0.0.1:8797/app/ophtxn`
- OpenClaw dashboard: `openclaw dashboard`

## Quick Start

1. Install dependencies.

```bash
git clone https://github.com/MaxProspero/permanence-os.git
cd permanence-os
python3 -m pip install -r requirements.txt
```

2. Configure local environment.

```bash
cp .env.example .env
```

3. Run readiness checks.

```bash
python cli.py integration-readiness
python cli.py ophtxn-launchpad --action status --strict --min-score 80
python cli.py ophtxn-production --action status --strict --min-score 80
python cli.py comms-status
```

4. Launch full local interface.

```bash
python cli.py operator-surface --no-open
```

## Core Operator Commands

```bash
python cli.py comms-status
python cli.py comms-doctor
python cli.py no-spend-audit --strict
python cli.py ophtxn-ops-pack --action run --strict
python cli.py telegram-control --action poll --enable-commands --ack --max-commands 5
python cli.py discord-telegram-relay --action run
```

## OpenClaw Notes

- OpenClaw runtime is related to Telegram/Discord flows, but not the same process.
- Telegram and Discord can be healthy even when OpenClaw has a separate channel issue.
- iMessage is optional and should be enabled only after `imsg` prerequisites are installed.

Useful checks:

```bash
python cli.py openclaw-status
openclaw channels status --probe
openclaw doctor --non-interactive
```

## No-Spend-First Mode

Keep budget control enabled while building:

```bash
python cli.py low-cost-mode --action enable
python cli.py no-spend-audit --strict
```

This keeps provider routing local-first and surfaces spend violations early.

## Repository Map

- `cli.py`: unified entrypoint for operational commands.
- `scripts/`: implementation modules used by `cli.py`.
- `agents/`: governed routing + specialist agent logic.
- `app/`: Flask services for foundation/ophtxn local app shell.
- `site/foundation/`: static web surface for local and hosted pages.
- `memory/`: approvals, queues, tool payloads, and working state.
- `outputs/`: generated markdown/text/json run artifacts.
- `automation/`: launchd and automation helper scripts.
- `docs/`: architecture, operations, governance, and runbooks.
- `tests/`: regression coverage for commands and workflows.

## Architecture

```
                    ┌─────────────────────────────────────┐
                    │         PERMANENCE OS / OPHTXN       │
                    │           Control Plane              │
                    └──────────────┬──────────────────────┘
                                   │
              ┌────────────────────┼────────────────────┐
              ▼                    ▼                    ▼
    ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
    │  Command Center │  │ Foundation Site │  │  Ophtxn Shell   │
    │  :8000 Flask    │  │  :8787 HTML     │  │  :8797 App      │
    └────────┬────────┘  └────────┬────────┘  └────────┬────────┘
             │                    │                    │
             └────────────────────┼────────────────────┘
                                  │
                    ┌─────────────▼─────────────┐
                    │      Horizon Agent         │
                    │  + Context Loader          │
                    │  + Task Runner             │
                    │  + Integrations            │
                    └─────────────┬─────────────┘
                                  │
                    ┌─────────────▼─────────────┐
                    │      External Workers      │
                    │  Telegram · OpenClaw · MCP │
                    └───────────────────────────┘
```

## Documentation

Start here:

- [Docs Index](docs/README.md)
- [Architecture](docs/architecture.md)
- [CLI Reference](docs/cli_reference.md)
- [Operator Command Guide](docs/ophtxn_operator_command_guide.md)
- [Journey Change Log](docs/ophtxn_journey_change_log.md)

## Security and Secrets

- Never commit `.env` or raw API tokens.
- Use keychain-backed helpers for supported connectors.
- Run secret scan before pushing:

```bash
python cli.py secret-scan --staged
```

## Branch and Merge Workflow

Repository homepage shows `main`. New work often lands on a `codex/*` branch first.

To verify updates:

```bash
git fetch origin --prune
git log --oneline origin/main -n 5
git log --oneline origin/codex/ophtxn-stability-20260305 -n 5
gh pr list --state open
```

## Contribution Standard

Any meaningful change should include:

1. Command or behavior validation.
2. Updated docs when interface/flow changes.
3. Tests for non-trivial logic updates.
4. Explicit handling of cost, security, and governance impact.
