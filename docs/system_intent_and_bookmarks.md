# System Intent And Bookmarks

This file captures what the user said they want this system to become, plus the concrete references surfaced in this session.

## Intended Direction

The user wants:
- a live system with Claude / Anthropic, OpenAI, xAI, Telegram, and OpenClaw configured
- governed autonomy instead of uncontrolled autonomy
- the ability for the system to do meaningful work on the user’s behalf
- strong finance capability
- dynamic provider/model selection based on task needs
- configuration and routing strong enough that the system can operate reliably when the user is not constantly present

## Non-Negotiable Constraint

The user does **not** want the system to run free without governance.

That means:
- approval gates stay in place for high-stakes actions
- financial actions require explicit approval
- external writes require explicit approval
- credential/config changes should remain auditable and governed

## Bookmarks / References Mentioned

OpenClaw:
- `https://docs.openclaw.ai/web/control-ui`
- `https://docs.openclaw.ai/cli`

Local OpenClaw URLs observed:
- `http://127.0.0.1:18789/`
- `http://127.0.0.1:18789/chat?session=main`

Repo handoff / context:
- `CODEX_HANDOFF.md`
- `docs/finance_governance.md`
- `docs/claude_continuation_handoff_2026-03-17.md`

## Important Clarification

This file only includes bookmarks and intent actually surfaced during this session.

If there are other personal bookmarks, product references, or design targets the user wants preserved, they should be added here explicitly in a later pass rather than guessed.
