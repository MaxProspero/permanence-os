# Ophtxn Skill Stack (March 6, 2026)

Last updated: 2026-03-06 (US)

This is the practical skill layout across Codex, OpenClaw, and browser workflows.

## Lane 1: Codex (Build + Deploy + Governance)

Use these skill families as defaults:

- `playwright`: browser automation and UI validation loops.
- `cloudflare-deploy`: domain/hosting deployment path.
- `openai-docs`: official-source API verification.
- `security-best-practices`, `security-threat-model`: secure-by-default checks.
- `gh-fix-ci`, `gh-address-comments`: keep PR/CI cycle fast.

## Lane 2: OpenClaw (Runtime + Channels + Skills)

Use OpenClaw for controlled runtime tasks:

- Channel orchestration (Telegram/Discord/iMessage where enabled).
- Skill-based repeatable tasks for research and intake.
- Action execution that can be constrained by approvals.

Reference docs:

- [Channels guide](https://docs.openclaw.ai/guides/channels)
- [Skills guide](https://docs.openclaw.ai/guides/skills)

## Lane 3: Browser / Chrome (Research Surface)

Recommended setup:

- Keep a dedicated profile for agent ops only.
- Pin only critical tabs: Local Hub, Command Center, App Shell, selected research tools.
- Do not run broad extension stacks that can interfere with automation stability.

## Skill Governance Rules

1. Every skill/action path maps to an approval level.
2. Money-impacting tasks require explicit human approval.
3. No-spend defaults remain on unless intentionally changed.
4. New skills must be logged in journey changelog after adoption.

## What Not To Do

- Do not let external platforms become the only memory source.
- Do not install high-privilege browser extensions in the same profile used for finance/admin sessions.
- Do not bypass model safety or policy checks; adjust behavior through explicit governance layers.

