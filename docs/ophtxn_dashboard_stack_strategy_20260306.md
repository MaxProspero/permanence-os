# Ophtxn Dashboard Stack Strategy (March 2026)

Last updated: 2026-03-06

## Decision Summary

Use a hybrid model:

1. **Own dashboard as source of truth** for approvals, memory, task execution, and no-spend governance.
2. **External tools as focused infrastructure** for domain-specific jobs (domain + edge hosting + analytics + workspace apps).
3. **OpenClaw as an adjacent runtime console**, not the canonical product dashboard.

This keeps product identity and user experience under Ophtxn control while avoiding unnecessary rebuilds of mature infra.

## Why this is the best path now

- Your key differentiator is the governed agent operating model, not commodity hosting UI.
- A first-party dashboard gives consistent behavior across Telegram, Discord, local shell, and future app surfaces.
- External tooling reduces launch risk and time-to-market for March 7 while preserving optionality.

## Recommended Stack

### Core product-owned layer

- Command center + approvals + memory + ops summary (local-first).
- Foundation UX pages and operator shell.
- Governance controls: no-spend, low-cost mode, and approval gates.

### External infra layer

- **Cloudflare** for domain + Pages hosting + edge controls.
- **Google Workspace** for Calendar/Gmail identity workflows where needed.
- **OpenClaw** for channel/runtime operations and plugin ecosystem.

### Optional analytics layer

- Keep first-party event capture for core product metrics.
- Add external analytics only for aggregated behavior and acquisition funnel visibility.

## UX Principle

One visual language across all local surfaces:

- Command center (`:8000`) for execution and governance.
- Foundation/local hub (`:8787`) as launch cockpit and user-facing front door.
- App shell (`:8797/app/ophtxn`) for personal operating context and live status.

## March 7 Launch Path

1. Run local stack and verify all three surfaces render.
2. Run launchpad and production readiness checks.
3. Verify docs + runbooks + command guide match real commands.
4. Ship one coherent hosted surface with domain routing and fallback runtime config.
5. Keep no-spend and approval gates on by default at launch.

## Execution Commands

```bash
python cli.py operator-surface --run-horizon
python cli.py ophtxn-launchpad --action status --strict --min-score 80
python cli.py ophtxn-production --action status --strict --min-score 80
python cli.py comms-status
```

## Guardrails

- Do not collapse everything into OpenClaw UI.
- Do not outsource core memory/approval logic to third-party dashboards.
- Do not enable paid model routes by default.
