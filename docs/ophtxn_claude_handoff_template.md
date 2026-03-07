# Ophtxn Claude Handoff (Template)

Copy this to:
`private/ophtxn_claude_handoff.local.md`

## Mission Context

- Primary objective:
- Current milestone:
- Constraints (budget, timeline, risk):

## System State

- Local services currently running:
- Known failures:
- Last successful checks:

## Credential Map (Local Only)

Do not commit raw values.

- `ANTHROPIC_API_KEY`: stored in `.env` (line: )
- `OPENAI_API_KEY`: stored in `.env` (line: )
- `X_BEARER_TOKEN`: stored in `private/secrets/` file:
- `TELEGRAM_BOT_TOKEN`: stored in:
- `DISCORD_BOT_TOKEN`: stored in:
- `CLOUDFLARE_API_TOKEN`: stored in:

## CLI Runbook

### Daily

```bash
python cli.py comms-status
python cli.py no-spend-audit --strict
python cli.py telegram-control --action poll --enable-commands --ack --max-commands 5
```

### Weekly

```bash
python cli.py ophtxn-ops-pack --action run --strict
python cli.py openclaw-status
python cli.py secret-scan --staged
```

## Integrations

- Telegram:
- Discord:
- OpenClaw:
- Cloudflare:
- GitHub:

## Approval Boundaries

- Auto-allowed:
- Requires explicit approval:
- Never allowed:

## Open Tasks

1. 
2. 
3. 

## Notes for Claude Code

- Preferred response style:
- Risk tolerance:
- Definition of done:
