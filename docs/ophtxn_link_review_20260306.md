# Ophtxn External Link Review (2026-03-06 UTC)

## Scope
User-submitted links reviewed for fit with Ophtxn personal-agent roadmap (no-spend-first, local-first, governed execution).

## Decision Framework
Each item is scored on:
- Mission fit (personal OS + future productization)
- Cost impact (free/local > paid/API-heavy)
- Integration friction (fast add vs heavy re-architecture)
- Governance/security risk

## Adopt Now

1. OpenAI curated skills catalog (`t.co/gNFHV3MD2j` -> `openai/skills/.curated`)
- Decision: Adopt now
- Why: Direct fit for extending Codex/OpenClaw workflows with maintainable skills
- Action:
  - Add shortlisted curated skills to internal watchlist
  - Import only skills that map to current lanes (deploy, docs, browser automation, security)

2. `googleworkspace/cli`
- Source context: surfaced in X thread by `@NickSpisak_` (install + OAuth + MCP wiring)
- Decision: Adopt now (read-first)
- Why: High leverage for email/calendar/task automation with immediate founder value
- Action:
  - Add a read-only integration track first
  - Keep write operations approval-gated

3. `nicobailon/visual-explainer`
- Decision: Adopt now (internal tooling)
- Why: Improves readability of complex plans/reviews and speeds operator decision cycles
- Action:
  - Use for architecture recap, diff review, plan review outputs
  - Keep as optional presentation layer (no core runtime dependency)

4. `langchain-ai/skills-benchmarks`
- Decision: Adopt now (evaluation pattern, not direct runtime dependency)
- Why: Strong methodology for testing skill quality and adherence
- Action:
  - Reuse benchmark ideas for Ophtxn command/skill acceptance tests

## Watchlist (Do Not Integrate Yet)

1. `msitarzewski/agency-agents`
- Why watch: rich persona templates and team-role structure ideas
- Why not now: large prompt surface area can add noise and governance drift

2. [Liquid AI](https://www.liquid.ai/)
- Why watch: strong on-device/local model positioning and efficiency narrative
- Why not now: provider switch adds integration and eval overhead before current core is fully stable

3. [skills.sh](https://skills.sh)
- Why watch: discovery surface for high-signal reusable skills
- Why not now: curate manually; avoid bulk imports

4. [spottedinprod.com](https://spottedinprod.com)
- Why watch: strong design pattern library for mobile-grade UX references
- Why not now: inspirational source, not engineering dependency

5. [sutera.ch](https://sutera.ch)
- Why watch: useful design language references around human-machine interface narratives
- Why not now: inspiration source only

6. [Chamath tokenization post](https://chamath.substack.com/p/equity-tokenization)
- Why watch: useful market signal for future finance vertical ideas
- Why not now: outside current core milestone (personal agent reliability + deployment)

## Ignore for Current Phase

1. X threads that are trend/opinion-only without reproducible implementation artifacts
- Examples from this batch: some posts by `@ViralOps_`, `@fomomofosol` contain useful narrative but no stable technical package
- Keep as inspiration, not immediate build input

2. Inaccessible X links in this environment
- `@karankendre`, `@augmentcode`, `@VadimStrizheus` links were access-limited or returned no content snapshot
- Re-review later when full content is accessible

## Research Pipeline Upgrade (Recommended)

1. Intake
- All links go through `/idea-intake`

2. Triage
- Auto-score by mission fit, cost, and integration risk

3. Proof stage
- One-file sandbox or script-level prototype only

4. Governance gate
- Approval queue before production integration

5. Rollout
- Docs update + tests + change log entry required for every accepted integration

## What This Means For Current Build

Priority remains:
1. Reliable comms stack (Telegram/Discord + iMessage staged)
2. Interface polish and production launch path
3. Revenue-first workflows (approvals, no-spend, execution loops)
4. Controlled expansion via curated integrations

## Source Links Reviewed
- https://www.liquid.ai/
- https://t.co/gNFHV3MD2j
- https://x.com/karankendre/status/2029490561586212923
- https://x.com/augmentcode/status/2029672126148661590
- https://x.com/ViralOps_/status/2029387368877441417
- https://x.com/NickSpisak_/status/2029412739303494131
- https://x.com/fomomofosol/status/2029623265287958684
- https://x.com/VadimStrizheus/status/2029631180312563734
- https://github.com/langchain-ai/skills-benchmarks
- https://github.com/nicobailon/visual-explainer
- http://spottedinprod.com
- http://skills.sh
- http://sutera.ch
- https://github.com/msitarzewski/agency-agents
