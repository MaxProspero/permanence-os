# Ophtxn Official Launch Path

Date: 2026-03-05 (UTC)  
Scope: Convert Ophtxn from private system into an official product presence.

## Direction

Build in this order:
1. Personal runtime quality.
2. Repeatable outcomes.
3. Public brand + launch.
4. Revenue-backed expansion.

This keeps the system aligned with your goal: legendary quality first, scale second.

## Phase Targets

### Phase 1: Personal Runtime Stability (0-30 days)
- Keep no-spend + governance defaults active.
- Run daily ops loops and idea ranking flow.
- Tighten memory/profile/habit workflows.
- KPI targets:
  - 0 paid-provider calls in default mode.
  - Daily ops cycle completion >= 85%.
  - Approvals backlog median age <= 48h.

### Phase 2: Public Presence + Early Offer (30-60 days)
- Launch official site + app studio + press kit.
- Publish one clear offer using existing revenue tooling.
- Start weekly content cadence from system insights.
- KPI targets:
  - First 10 qualified leads.
  - First 3 paid engagements.
  - One case-study style outcome report.

### Phase 3: Productized Pack (60-90 days)
- Ship one vertical pack with clear deliverable boundaries.
- Candidate: smart-contract audit copilot or creator/research ops pack.
- Build onboarding flow into repeatable template.
- KPI targets:
  - Weekly recurring revenue from at least one pack.
  - Time-to-onboard new user <= 20 minutes.
  - Support requests resolved <= 24h.

### Phase 4: Team + Enterprise Mode (90+ days)
- Add multi-user orchestration and role permissions.
- Add auditable policy controls for corporate deployments.
- Package compliance-safe deployment templates.

## Go-To-Market System

### Messaging
- Core message: "Personal intelligence operating system for execution."
- Secondary message: "Governed automation with memory, approvals, and cost control."

### Content Lanes
1. Build logs (what shipped this week).
2. Operator insights (what worked, what did not).
3. Comparative teardowns (why Ophtxn design choices differ).

### Promotion cadence
- 3 short posts/week.
- 1 medium writeup/week.
- 1 demo clip/week.
- 1 case snapshot/week.

## What To Build Next

1. Cloudflare MCP read-only integration scaffold.
2. Google Workspace read-only connector scaffold.
3. Offer page + intake flow connected to sales pipeline.
4. Weekly published "Operator Notes" generated from chronicle/report outputs.
5. Production deploy lane (`ophtxn-production`) with strict readiness + cost estimate gate.

## Guardrails

- No autonomous financial execution.
- No autonomous social posting by default.
- Every write action logs provenance + approval metadata.
- Paid provider use only with explicit budget decision.

## Launch Control Commands

- Readiness score:
  - `python cli.py ophtxn-launchpad --action status`
- Strict launch gate:
  - `python cli.py ophtxn-launchpad --action status --strict --min-score 80`
- Plan view:
  - `python cli.py ophtxn-launchpad --action plan`
- Telegram shortcuts:
  - `/launch-status [min-score=<n>] [strict]`
  - `/launch-plan`

## Research Anchors (Verified 2026-03-05 UTC)

- Telegram bot behavior:
  - Bots are third-party apps and cannot initiate end-user conversations directly unless the user starts them first (`/start`).
  - Ref: <https://core.telegram.org/bots>
- Telegram API compatibility:
  - Bot API keeps backward compatibility guarantees; this supports stable integration planning.
  - Ref: <https://core.telegram.org/bots/api>
- Discord policy guardrail:
  - Self-bot usage is prohibited; keep automation on official bot accounts only.
  - Ref: <https://support.discord.com/hc/en-us/articles/115002192352-Automated-User-Accounts-Self-Bots>
- X API cost model:
  - X API is documented as pay-per-use; maintain no-spend defaults and controlled provider routing.
  - Ref: <https://developer.x.com/en/docs/x-api>
- Cloudflare model-context integration:
  - Cloudflare now provides an MCP server + remote MCP endpoint; use this as a controlled read-first connector path.
  - Ref: <https://github.com/cloudflare/mcp-server-cloudflare>
- OpenAI orchestration reference:
  - Symphony is available as a multi-agent orchestration framework reference.
  - Ref: <https://github.com/openai/symphony>
- Local model lane:
  - Ollama model library remains a practical local-first option for low-cost/no-spend operation.
  - Ref: <https://ollama.com/library>
