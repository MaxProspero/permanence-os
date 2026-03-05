# Ophtxn Deep Research Method (March 4, 2026)

## Why this exists
This document defines how Ophtxn research is done before shipping product changes. The goal is to make upgrades repeatable, evidence-backed, and testable.

## Scope for this cycle
- memory quality over long conversations
- habit formation support (cue-action and consistency)
- personality adaptation with governance boundaries
- profile consistency over time (versioning and conflict visibility)

## Research Protocol (How I do research)
1. Start from live product gaps (not abstract ideas).
2. Define measurable outcomes per gap before reading sources.
3. Pull primary sources first:
   - peer-reviewed papers and publisher pages
   - original arXiv papers for methods/benchmarks
4. Extract only claims tied to measured outcomes (hit rate, consistency, adherence, etc.).
5. Convert each claim into one implementation requirement.
6. Add regression tests and offline simulations before rollout.
7. Keep a changelog of what shipped from each research thread.

## Primary Sources Used
- [Generative Agents (arXiv 2304.03442)](https://arxiv.org/abs/2304.03442)
- [MemGPT (arXiv 2310.08560)](https://arxiv.org/abs/2310.08560)
- [Reflexion (arXiv 2303.11366)](https://arxiv.org/abs/2303.11366)
- [LoCoMo long-term conversational memory benchmark (arXiv 2402.17753)](https://arxiv.org/abs/2402.17753)
- [EverMemBench (arXiv 2602.01313)](https://arxiv.org/abs/2602.01313)
- [ES-MemEval (arXiv 2602.01885)](https://arxiv.org/abs/2602.01885)
- [How are habits formed: Modelling habit formation in the real world (EJSP, DOI 10.1002/ejsp.674)](https://doi.org/10.1002/ejsp.674)
- [Implementation Intentions and Health Behaviour: A Meta-Analysis (PubMed)](https://pubmed.ncbi.nlm.nih.gov/19119415/)
- [Psychometric framework for personality shaping in LLMs (Nature Machine Intelligence, 2025)](https://www.nature.com/articles/s42256-025-01115-6)
- [Constitutional AI (arXiv 2212.08073)](https://arxiv.org/abs/2212.08073)

## Research-to-Implementation Mapping (Shipped)
### Memory
- Requirement: memory retrieval should not depend on simple recency.
- Shipped:
  - hybrid retrieval scoring (token overlap + synonym expansion + fuzzy similarity + recency + source weighting)
  - improved recall selection path in `scripts/telegram_control.py`

### Profile consistency
- Requirement: profile updates need temporal traceability and conflict visibility.
- Shipped:
  - profile history log for every profile field update
  - conflict logging when the same field gets contradictory values
  - new commands: `/profile-history [field]`, `/profile-conflicts`

### Habit formation
- Requirement: habit support should include cue-action structure (not only streak counters).
- Shipped:
  - habit cue/plan/window parsing in `/habit-add`
  - new command: `/habit-plan <habit> | cue: ... | plan: ...`
  - new command: `/habit-nudge` for actionable next steps based on staleness + cues

### Personality + governance
- Requirement: personality adaptation must remain bounded by system truthfulness and safety policy.
- Shipped status:
  - personality modes remain configurable (`adaptive|strategist|coach|operator|calm|creative`)
  - governance guardrails remain in chat system prompt and command routing
  - new governed learning orchestrator (`python cli.py governed-learning`) enforces explicit approval + read-only learning pipelines
  - new self-improvement pitch loop (`python cli.py self-improvement`) continuously proposes upgrades from live metrics and requires explicit approval before queueing changes

## Validation Run (this cycle)
- Unit tests: `pytest -q tests/test_telegram_control.py` -> `22 passed`
- Compile checks: `python3 -m py_compile scripts/telegram_control.py scripts/ophtxn_simulation.py cli.py`
- Simulation run:
  - `python3 cli.py ophtxn-simulation --seed 17 --memory-trials 240 --habit-days 90`
  - report: `outputs/ophtxn_simulation_latest.md`

## Remaining Gaps (next)
1. Memory evaluation still synthetic; add multi-turn factual consistency and contradiction-rate tests from real chat logs.
2. Habit engine lacks scheduled cue windows with timezone-aware reminder scoring.
3. Personality adaptation lacks explicit user-rated A/B evaluation loop by mode.
4. Conflict system surfaces contradictions but does not yet support explicit conflict resolution workflow.
5. Retrieval still lexical-heavy; add embedding reranking with offline fallback.

## Immediate Next Experiments
1. Add `recall@k`, contradiction rate, and stale-memory rate to `scripts/ophtxn_simulation.py`.
2. Run 14-day habit intervention test: baseline reminders vs cue-action prompts.
3. Add `/profile-resolve <conflict-id>` and track resolution latency.
4. Add weekly personality mode audit using user feedback + task completion metrics.
