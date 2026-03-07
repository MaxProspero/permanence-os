# Ophtxn Access and VPN Policy (2026-03-06)

This policy answers two operator questions:
- Should NordVPN be connected while agents run?
- Should local setup use custom config only or full access defaults?

## Decision Summary

1. Use custom, explicit config by default.
2. Do not run full-access automation by default.
3. Keep VPN OFF for always-on bot loops unless there is a specific need.
4. Allow VPN ON for manual research sessions only.

## Why

- Telegram/Discord polling and webhook flows are more stable on a consistent, non-rotating network identity.
- VPN rotation can trigger rate limits, bot trust issues, and harder debugging.
- Full-access defaults increase blast radius if a command is misrouted.

## Recommended Runtime Modes

### Mode A: Operations (default)
Use for comms loop, approvals, daily ops, production checks.

- VPN: OFF
- No-spend mode: ON
- Low-cost mode: ON
- Provider: ollama-first
- Access: custom/least-privilege

### Mode B: Research Sweep (manual)
Use when you intentionally need region/network privacy for browsing.

- VPN: ON (manual switch)
- Long-running bot loops: paused or monitored
- Posting/actions: approval-gated only

## Agent Control Policy for VPN

Do not let autonomous agents toggle VPN on their own.

If VPN control is needed, require explicit human command and log every change event in chronicle.

## Current Host State

- `nordvpn` CLI: not installed on this Mac (`command not found`)

If you want terminal control later, install NordVPN CLI first and gate it behind explicit approval commands.

## Access Model Recommendation

Use custom config (least privilege), not global full access.

- Keep secrets in Keychain, not plaintext files.
- Keep external write actions approval-gated.
- Keep OpenClaw sandbox policy explicit and reviewed.
- Recheck with:
  - `python cli.py no-spend-audit --strict`
  - `python cli.py comms-status`
  - `python cli.py comms-doctor`

## Operational Rule

If a new integration requires broader permissions, add temporary scoped access for that integration only, then remove it after validation.
