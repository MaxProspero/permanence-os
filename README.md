# Permanence OS / Ophtxn

A governed personal intelligence OS. Automation can assist, but human authority is final.

Permanence OS runs local-first operations for planning, research, execution, communication, and venture intelligence -- all behind approval gates and governance checks.

## Three Live Runtimes

| Runtime | Endpoint |
|---------|----------|
| Command Center | `http://127.0.0.1:8000` |
| Foundation Site | `http://127.0.0.1:8787` |
| Ophtxn Shell | `http://127.0.0.1:8797/app/ophtxn` |

## Site Pages (13)

All pages share a unified navigation bar and consistent design system (Sora / IBM Plex Mono / Orbitron / DM Mono).

| Page | File | Purpose |
|------|------|---------|
| Local Hub | `local_hub.html` | System health dashboard and quick links |
| Command Center | `command_center.html` | Operational control panel |
| Ophtxn Shell | `ophtxn_shell.html` | Agent operator terminal |
| Official App | `official_app.html` | Primary application surface |
| Foundation Home | `index.html` | Public landing page |
| Rooms | `rooms.html` | Workspace and room navigator |
| Trading Room | `trading_room.html` | Market and trading interface |
| Daily Planner | `daily_planner.html` | Day planning and task board |
| AI School | `ai_school.html` | Learning and training interface |
| Press Kit | `press_kit.html` | Brand and media resources |
| Night Capital | `night_capital.html` | Venture intelligence dashboard |
| Agent View | `agent_view.html` | FaceTime-like agent interface |
| Comms Hub | `comms_hub.html` | Unified Discord/Telegram/WhatsApp chat |

All pages live under `site/foundation/`.

## Three-Layer Architecture

Permanence OS uses a three-layer context architecture that governs how Claude agents interact with the codebase:

**Layer 1: CLAUDE.md** -- The root map. Defines identity, file locations, code standards, and hard rules (never-touch list). Every agent session reads this first.

**Layer 2: context.md files** -- Per-directory routing files. Each workspace or subdirectory can include a `context.md` that provides scoped instructions, reducing prompt size and keeping agents focused on the relevant slice of the project.

**Layer 3: Workspaces** -- `.vscode/` workspace configs and specialized directories (`docs/design/`, `docs/workflows/`) that bundle related files with their own rules and templates.

## Quick Start

1. Clone and install dependencies.

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

4. Launch the full operator surface (all three runtimes).

```bash
python cli.py operator-surface --run-horizon
```

## Tech Stack

- **Backend**: Python 3 / Flask (dashboard API, foundation server, Ophtxn shell)
- **Frontend**: Static HTML/CSS/JS with CSS custom properties and glassmorphism design
- **Automation**: macOS launchd for scheduled jobs (briefing, money loop, second brain)
- **Governance**: Canon-based approval gates, compliance checks, secret scanning
- **Agents**: Governed routing with specialist agents (Planner, Researcher, Executor, Reviewer, Compliance)

## Test Suite

772+ tests covering commands, workflows, agent logic, and governance gates.

```bash
pytest -q               # run all tests
python cli.py test      # run via CLI
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

## Repository Map

- `cli.py` -- Unified entrypoint for operational commands
- `dashboard_api.py` -- Command Center Flask API
- `horizon_agent.py` -- Horizon planning agent
- `context_loader.py` -- Task-aware context injection
- `scripts/` -- Implementation modules used by cli.py
- `agents/` -- Governed routing and specialist agent logic
- `app/` -- Flask services for foundation/ophtxn local app shell
- `site/foundation/` -- Static web surface (13 pages)
- `memory/` -- Approvals, queues, tool payloads, and working state
- `outputs/` -- Generated markdown/text/json run artifacts
- `automation/` -- launchd and automation helper scripts
- `docs/` -- Architecture, operations, governance, and runbooks
- `tests/` -- Regression coverage (772+ tests)
- `.vscode/` -- VS Code workspace configuration

## Documentation

Start here:

- [Docs Index](docs/README.md)
- [Architecture](docs/architecture.md)
- [CLI Reference](docs/cli_reference.md)
- [Operator Command Guide](docs/ophtxn_operator_command_guide.md)
- [Governance Operating Model](docs/ophtxn_governance_operating_model.md)

## Security and Secrets

- Never commit `.env` or raw API tokens.
- Use keychain-backed helpers for supported connectors.
- Run secret scan before pushing:

```bash
python cli.py secret-scan --staged
```

## Branch and Merge Workflow

Feature work uses `codex/*` branches and merges back to `main`.

```bash
git fetch origin --prune
git log --oneline origin/main -n 5
gh pr list --state open
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for change process and standards.
