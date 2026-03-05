# Ophtxn External Ideas Backlog

Created: 2026-03-05 (UTC)  
Status: queued for review

This file tracks external links you send (X posts, GitHub repos, tools) so they can be reviewed and either integrated, deferred, or rejected with rationale.

## Review Method

Each item is scored on:
1. Strategic fit with Ophtxn mission.
2. Cost impact (no-spend/local-first compatibility).
3. Integration complexity and maintenance burden.
4. Security/privacy risk.
5. Time-to-value.

Decision states:
- `queued`
- `researching`
- `accepted`
- `deferred`
- `rejected`

## Current Queue

### Repos / tools
- [tanishqkumar/ssd](https://github.com/tanishqkumar/ssd) — `queued`
- [pliny-the-prompter/obliteratus (HF Space)](https://huggingface.co/spaces/pliny-the-prompter/obliteratus) — `queued`
- [elder-plinius/OBLITERATUS](https://github.com/elder-plinius/OBLITERATUS) — `queued`
- [googleworkspace/cli](https://github.com/googleworkspace/cli) — `queued`
- [Claude Cowork sub-agents article](https://mikefutia.com/claude-cowork-sub-agents-lm/) — `queued`

### X links
- [elder_plinius post](https://x.com/elder_plinius/status/2029317072765784156?s=42) — `queued`
- [abhijitwt post](https://x.com/abhijitwt/status/2029154197678252279?s=46) — `queued`
- [heynavtoor post](https://x.com/heynavtoor/status/2028922003365986705?s=46) — `queued`
- [paulo_kombucha post](https://x.com/paulo_kombucha/status/2029204450246623288) — `queued`
- [defi_scribbler post](https://x.com/defi_scribbler/status/2029270671235133633) — `queued`
- [try_nova_app post](https://x.com/try_nova_app/status/2010149082421940336) — `queued`
- [roundtablespace post A](https://x.com/roundtablespace/status/2029191380212257159?s=46) — `queued`
- [perplexity_ai post](https://x.com/perplexity_ai/status/2029302896026853379?s=46) — `queued`
- [roundtablespace post B](https://x.com/roundtablespace/status/2029183844180512888?s=46) — `queued`
- [roundtablespace post C](https://x.com/roundtablespace/status/2029478270438133918?s=46) — `queued`
- [mikefutia post](https://x.com/mikefutia/status/2029220162818453968?s=46) — `queued`

## Next Review Pass (Planned)

1. Do metadata pass: repo activity, license, stack, stars, recency.
2. Do architecture pass: where it fits in Ophtxn (comms, agent runtime, memory, research, UI, cost controls).
3. Produce integration recommendations with one of:
   - copy pattern
   - prototype in branch
   - watchlist only
   - reject

## First Pass Review (2026-03-05)

### 1) tanishqkumar/ssd
- Decision: `deferred`
- Why:
  - Strong inference research repo, but hardware and stack expectations are high (CUDA + modern GPUs/H100-focused benchmarking).
  - Current Ophtxn priorities are orchestration, memory, comms, approvals, and cost governance rather than custom inference kernel work.
- Potential future use:
  - Borrow ideas for async/speculative routing policy, not direct engine adoption now.

### 2) pliny-the-prompter/obliteratus (HF Space)
- Decision: `rejected` for core system
- Why:
  - Focus is refusal-removal / model “liberation”; high governance, policy, and misuse risk for your main assistant stack.
  - Not aligned with “safe, reliable personal OS + future business product” posture.
- Allowed scope:
  - Only isolated red-team sandbox experiments if explicitly requested.

### 3) elder-plinius/OBLITERATUS (GitHub)
- Decision: `rejected` for core system
- Why:
  - Same risk profile as above plus AGPL obligations and security posture complexity.
  - Increases legal/compliance and brand risk for a production assistant product.
- Allowed scope:
  - Isolated research-only environment, never merged into default runtime.

### 4) googleworkspace/cli
- Decision: `accepted` (prototype path)
- Why:
  - Directly relevant for your “assistant operating system” goals across Gmail/Calendar/Drive/Docs/Sheets.
  - Strong leverage for user productivity workflows.
- Next step:
  - Add read-only prototype integration in Ophtxn first (list/search/fetch), then gated write actions.

### 5) mikefutia.com/claude-cowork-sub-agents-lm
- Decision: `deferred` (content unavailable from current crawler session)
- Why:
  - Direct page failed fetch in this run, so details could not be validated.
  - Concept direction (parallel sub-agents + token management) is already aligned with our architecture.
- Next step:
  - Re-review once reachable and compare against our existing ops-pack + approval governance model.

## Second Pass Review (2026-03-05)

### 6) OpenPipe/ART
- Link: [OpenPipe/ART](https://github.com/OpenPipe/ART), [docs](https://art.openpipe.ai/)
- Decision: `accepted` (sandbox only)
- Why:
  - Strong fit for reinforcement-style response quality tuning and preference shaping.
  - Good candidate to improve "assistant style + decision quality" for your personal agent.
- Guardrails:
  - Keep in a separate training sandbox; do not let training loops auto-ship to production prompts/models.
  - Require manual review checkpoints on eval metrics before adoption.

### 7) rtk-ai/rtk
- Link: [rtk-ai/rtk](https://github.com/rtk-ai/rtk)
- Decision: `deferred`
- Why:
  - Useful orchestrator ideas, but current Ophtxn already has working orchestration + approval pathways.
  - Integrating a second orchestration framework now adds complexity without immediate ROI.
- Potential future use:
  - Borrow targeted patterns (task graph structure + run tracing) if we need stronger observability later.

### 8) Google Workspace developer tools
- Link: [googleworkspace/developer-tools](https://github.com/googleworkspace/developer-tools)
- Decision: `accepted` (priority)
- Why:
  - Highest direct utility for money-making and life-management workflows (mail, calendar, docs, sheets).
  - Good enterprise bridge for eventual app/commercial product.
- Next step:
  - Build read-only first (search/list/get), then gated writes with explicit approval.

### 9) Agent hardening checklist gist
- Link: [Agent Security.md gist](https://gist.github.com/sebiomoa/ad034f728a32466326e7e58e358b27dd)
- Decision: `accepted` (policy references)
- Why:
  - Contains practical controls for prompt-injection, tool scopes, and approval boundaries.
  - Aligns with existing no-spend + human-approval governance model.
- Next step:
  - Convert into explicit Ophtxn policy checks in `no-spend-audit` and approval triage docs.

### 10) npmx.dev/touch-all
- Link: [touch-all package](https://npmx.dev/package/touch-all)
- Decision: `rejected` for core
- Why:
  - Utility package with low strategic leverage for your assistant architecture.
  - Not a meaningful differentiator for product direction.

### 11) pashov/skills
- Link: [pashov/skills](https://github.com/pashov/skills)
- Decision: `deferred` (vertical-specific)
- Why:
  - Strong for Solidity/smart-contract security workflows, but narrow relative to your current priorities.
  - Keep as a potential vertical add-on if you launch a security/crypto-focused branch later.

### 12) Education wedge (Blackboard/Canvas/LockDown ecosystem)
- Links:
  - [Blackboard developer platform](https://developer.blackboard.com/portal/displayApi)
  - [Canvas LMS API docs](https://canvas.instructure.com/doc/api/index.html)
  - [Respondus partner SDK](https://web.respondus.com/he/lockdownbrowser-sdk/)
- Decision: `accepted` (market exploration track)
- Why:
  - Real distribution channel for a "study OS + compliance-safe agent coach" product.
  - API ecosystems exist; path to institution-level pilots is realistic.
- Constraint:
  - Must prioritize compliance, auditability, and integrity-safe assist modes over unrestricted outputs.

## Notes on X link review

- Public X links often fail direct crawler extraction in this environment.
- Reliable path in Ophtxn is to ingest via your configured X watch feeds (`x-account-watch` + `social-research-ingest`) and then rank via opportunity queue.
- Current tracked watched accounts include: `@roundtablespace`, `@xdevelopers`, `@chiefofautism`, `@juliangoldieseo`.

## Third Pass Review (2026-03-05)

### 13) Smart-contract audit skill packs (portfolio vertical)
- Links:
  - [pashov/skills](https://github.com/pashov/skills)
  - [trailofbits/skills](https://github.com/trailofbits/skills)
  - [Cyfrin/solskill](https://github.com/Cyfrin/solskill)
  - [hackenproof-public/skills](https://github.com/hackenproof-public/skills)
- Decision: `accepted` (vertical module, not core runtime)
- Why:
  - Strong opportunity for a paid "Audit Copilot" vertical without changing Ophtxn core architecture.
  - Can become a high-ticket services lane (audit prep, issue triage, remediation planning).
- Implementation note:
  - Keep this as `verticals/smart_contract_audit/` with explicit legal + risk disclaimers.

### 14) OpenAI Symphony
- Link: [openai/symphony](https://github.com/openai/symphony)
- Decision: `accepted` (pattern adoption)
- Why:
  - Useful reference for typed multi-agent orchestration, handoffs, and reproducible pipelines.
  - Directly aligns with Ophtxn's existing planner/research/execution model.
- Next step:
  - Borrow design ideas for role contracts, lifecycle hooks, and traceability; do not hard-couple runtime yet.

### 15) Cloudflare MCP
- Link: [cloudflare/mcp](https://github.com/cloudflare/mcp)
- Decision: `accepted` (infra priority)
- Why:
  - Gives scalable tool access + remote execution patterns for cross-device assistant workflows.
  - Helps long-term portability for app deployment and external integrations.
- Next step:
  - Build a single read-only MCP service first (research/search context) before write-capable tools.

### 16) Agent Experience
- Link: [ygwyg/agent-experience](https://github.com/ygwyg/agent-experience)
- Decision: `accepted` (UX/reference)
- Why:
  - Relevant to your request for "best friend + second brain" interaction quality and memory feel.
  - Useful patterns for conversation state, memory recall, and control surfaces.

### 17) build-your-own-x
- Link: [codecrafters-io/build-your-own-x](https://github.com/codecrafters-io/build-your-own-x)
- Decision: `accepted` (internal curriculum)
- Why:
  - High value as a structured capability roadmap for your team/agents.
  - Not a dependency to integrate directly; best used as learning + implementation templates.

### 18) Nolen Royalty repos
- Links:
  - [nolenroyalty/yt-browse](https://github.com/nolenroyalty/yt-browse)
  - [nolenroyalty/concave](https://github.com/nolenroyalty/concave)
- Decision: `deferred` (sandbox R&D)
- Why:
  - Interesting for content research and app framework experimentation, but not immediate core leverage.
  - Keep in prototyping queue until core money loops and comms reliability are fully stable.

### 19) tinyfish-cookbook
- Link: [tinyfish-io/tinyfish-cookbook](https://github.com/tinyfish-io/tinyfish-cookbook)
- Decision: `accepted` (reference patterns)
- Why:
  - Good idea source for agent recipes and implementation snippets.
  - Can accelerate experimentation without introducing heavy new infra commitments.

### 20) MIT Sloan business-model signal
- Link: [How digital business models are evolving in the age of agentic AI](https://mitsloan.mit.edu/ideas-made-to-matter/how-digital-business-models-are-evolving-age-agentic-ai?utm_source=mitsloanthreads&utm_medium=social&utm_campaign=aibizmodel)
- Decision: `accepted` (strategy reference)
- Why:
  - Supports product strategy around service-layer monetization and AI-native workflows.
  - Useful for deciding between agency/services, SaaS product, and hybrid pricing models.

### 21) Low-confidence/unclear domains from this batch
- Links:
  - [answerthis.io](https://answerthis.io/home-2?fpr=faheem42)
  - [numberresearch.xyz](https://numberresearch.xyz/info)
  - [appstar.world](https://www.appstar.world/)
  - [alembic.space](https://alembic.space/)
  - [geospatialml.com](https://geospatialml.com/)
  - [confbuild.com](https://confbuild.com/)
- Decision: `researching`
- Why:
  - Some pages are thin/JS-heavy or hard to validate quickly.
  - Keep on watchlist and only adopt if they show durable product fit + strong execution quality.

## Third Pass Priority Ranking (summary)

1. Cloudflare MCP (`accepted`)
2. OpenAI Symphony patterns (`accepted`)
3. Google Workspace integration (`accepted`)
4. Smart-contract audit vertical packs (`accepted`)
5. Agent Experience UX patterns (`accepted`)
6. tinyfish-cookbook patterns (`accepted`)
7. build-your-own-x internal curriculum (`accepted`)

## Fourth Pass Review (2026-03-05, latest live batch)

### 22) MaxProspero/permanence-os + release v0.2.1
- Links:
  - [MaxProspero/permanence-os](https://github.com/MaxProspero/permanence-os)
  - [release v0.2.1](https://github.com/MaxProspero/permanence-os/releases/tag/v0.2.1)
- Decision: `accepted` (execution priority)
- Why:
  - Highest leverage is shipping current branch to `main` and cutting a new release tag, not adding net-new dependencies.
  - Current repo already has an open PR for the workstream and the branch is ahead of `main`.
- Next step:
  - Merge PR #8, tag next release, and publish release notes tied to launchpad + production runbook.

### 23) limitless-labs-group/limitless-cli
- Link: [limitless-labs-group/limitless-cli](https://github.com/limitless-labs-group/limitless-cli)
- Decision: `researching`
- Why:
  - Potentially useful CLI patterns for agent workflows.
  - Needs repo-level architecture and governance compatibility review before adoption.
- Next step:
  - Run adopt/adapt/reject memo with one reversible prototype in a sandbox branch.

### 24) skills.sh
- Link: [skills.sh](https://skills.sh/)
- Decision: `accepted` (product benchmark)
- Why:
  - Strong reference for the "AI learning that people keep returning to" product direction.
  - Valuable for mechanics benchmarking (daily streaks, interactive drills, progression loops).
- Next step:
  - Borrow engagement mechanics only; implement an Ophtxn-branded micro-learning lane with AI assistant context.

### 25) cbc-company.org/canada
- Link: [cbc-company.org/canada](https://cbc-company.org/canada/)
- Decision: `deferred`
- Why:
  - No clear direct fit to current Ophtxn product roadmap from initial pass.
  - Keep off critical path until strategic relevance is established.

### 26) New X link cluster (live idea stream)
- Links:
  - [nyk_builderz post](https://x.com/nyk_builderz/status/2029515375214498208?s=46)
  - [tetsuoai post](https://x.com/tetsuoai/status/2029500977959887018?s=46)
  - [roundtablespace post](https://x.com/roundtablespace/status/2029251778223521966?s=46)
  - [obscicron post](https://x.com/obscicron/status/2029125852873801796?s=46)
  - [himanshustwts post](https://x.com/himanshustwts/status/2029214792196735003?s=46)
  - [jacobsklug post](https://x.com/jacobsklug/status/2029550513747112377?s=46)
  - [gregisenberg post](https://x.com/gregisenberg/status/2028533746073321919?s=46)
  - [markknd post](https://x.com/markknd/status/2029529584174252226?s=46)
  - [zodchiii post](https://x.com/zodchiii/status/2029501247212925373?s=46)
  - [coreyganim post](https://x.com/coreyganim/status/2029562564384882868?s=46)
  - [prajwaltomar_ post](https://x.com/prajwaltomar_/status/2029564848909189301?s=46)
  - [morganlinton post](https://x.com/morganlinton/status/2029345389086949506?s=46)
  - [roundtablespace post B](https://x.com/roundtablespace/status/2029546218779545962?s=46)
  - [clydedevv post](https://x.com/clydedevv/status/1886447422517444932?s=46)
  - [roundtablespace post C](https://x.com/roundtablespace/status/2029583967155106193?s=46)
  - [ihtesham2005 post](https://x.com/ihtesham2005/status/2029567530457563306?s=46)
- Decision: `watchlist`
- Why:
  - High idea volume and fast novelty cycle; direct integration risk is high without primary-source validation.
  - Best path is feed -> rank -> gated approval -> reversible prototypes.
- Current status:
  - Intake processed and queued 3 medium-priority approvals from this batch.
8. MIT Sloan strategy reference (`accepted`)
9. yt-browse / concave (`deferred`)
10. unclear domains (`researching`)
