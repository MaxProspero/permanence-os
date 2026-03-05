# Ophtxn Fastlane Execution Plan

Date: 2026-03-05 (UTC)  
Goal: ship faster, generate revenue quickly, and build the AI-learning product lane in parallel.

## 0) Current Reality (where you are now)

- Core branch is active and pushed: `codex/ophtxn-stability-20260305`
- Open PR exists: [#8](https://github.com/MaxProspero/permanence-os/pull/8)
- Production config path is ready (no-spend defaults):
  - primary: `ophtxn.permanencesystems.com`
  - api: `api.permanencesystems.com`
- Deploy preflight now catches missing toolchain/auth and blocks unsafe deploy attempts.

## 1) 72-Hour Targets

1. Publish code to `main` + cut next release (so GitHub visibly updates).
2. Complete Cloudflare Wrangler auth and run production deploy.
3. Put waitlist and lead capture fully live on public domain.
4. Launch first AI education offer page (simple, high-conversion, no-spend stack).

## 2) Fastest Revenue Path (no-spend compatible)

Use a 3-offer ladder:

1. `Starter` ($49-$99): 45-minute AI setup call (personal workflow + prompts + tooling plan)
2. `Builder` ($299-$599): "AI Operating System Setup" for creators/freelancers
3. `Sprint` ($999+): 7-day done-with-you automation + agent workflow build

Execution rule:
- Every feature must either:
  - increase close rate,
  - increase lead flow, or
  - reduce delivery time.

## 3) AI Education Product Wedge (your "dad asked what is Claude" moment)

Build this as a separate lane inside Ophtxn:

1. `What is Claude/ChatGPT/Grok?` 5-minute explainers
2. "Use AI today" micro-actions (copy/paste prompts + immediate payoff)
3. Daily streak loop (1 lesson/day, 1 action/day, 1 win/day)
4. Progress milestones (Beginner -> Operator -> Builder)
5. Certificate/share card for social proof

This creates an "addictive learning" loop without social-media toxicity:
- low friction
- quick wins
- visible progress
- identity reinforcement ("I am becoming AI-capable")

## 4) Commands to Run Daily

1. `/ops-morning`
2. `/prod-preflight strict`
3. `/launch-status min-score=80 strict`
4. `/idea-run max=25 min-score=35 queue=1`
5. `/approvals-top 10 source=idea_intake_queue`
6. `/comms-status`

## 5) GitHub Publish Fix (why release looked stale)

Cause:
- Release tag is still `v0.2.1`; new branch work has not been merged/tagged as a new release.

Fix:
1. Merge PR #8 into `main`
2. Tag next release (example: `v0.3.0`)
3. Publish release notes from merged changes

## 6) What I Need From You

1. Complete Cloudflare auth in local terminal:
   - `wrangler login`
   - `wrangler whoami`
2. Confirm release version to cut after merge (`v0.3.0` recommended).
3. Keep sending links; I will keep filtering them through intake + approval gates.

## 7) Governance Guardrails (stay fast without breaking things)

- No auto-spend actions without explicit approval.
- No direct production writes from unverified external ideas.
- All new external patterns go through:
  - intake -> rank -> approval -> reversible prototype -> rollout.
