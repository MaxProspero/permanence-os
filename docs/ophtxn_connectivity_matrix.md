# Ophtxn Connectivity Matrix

Last updated: 2026-03-06 (UTC)

## Purpose

Clarify which systems are directly connected, which are bridged through scripts, and what must be configured manually.

## Runtime Surfaces

| Surface | Primary function | Current integration path | Writes enabled by default |
|---|---|---|---|
| OpenClaw Desktop/Gateway | Local agent runtime and session UX | Health/status captured through `python cli.py openclaw-status` and `python cli.py openclaw-sync` | No |
| Telegram Bot | Main operator chat interface | `python cli.py telegram-control --action poll` (or comms loop) | Controlled replies only |
| Discord Bot + Feeds | Research ingest and relay source | `python cli.py discord-feed-manager` + `python cli.py discord-telegram-relay --action run` | No outbound posting |
| X Research | Trend and account signal ingest | `python cli.py social-research-ingest` + `python cli.py x-account-watch` | No |

## Why OpenClaw Can Look \"Empty\"

OpenClaw UI can show a connected gateway but still appear inactive when one or more of these are missing:

1. Channel/plugin mappings inside OpenClaw.
2. Active model/session route in OpenClaw.
3. Memory source wiring in OpenClaw.

This does not mean Telegram or Discord relays are down. They are separate pipelines in this repository.

## Verify Each Surface

```bash
python cli.py openclaw-status
python cli.py telegram-control --action status
python cli.py discord-feed-manager --action list
python cli.py discord-telegram-relay --action status
python cli.py comms-status
python cli.py comms-doctor
```

## Recommended Operating Mode

1. Keep OpenClaw as local runtime and observability source.
2. Keep Telegram as primary user interface.
3. Keep Discord/X in read-only ingest mode until approval-governed write workflows are explicitly enabled.
