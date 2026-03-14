# AI Paper Insights — Applied to Permanence OS

## Papers Reviewed (March 2026)

### 1. ParamMem — Parameter-Level Memory for LLMs
**Key insight:** Temperature-controlled reflection diversity. Higher temperature during self-improvement/brainstorming phases generates more diverse improvement candidates; lower temperature during execution ensures reliability.

**Applied in:** `core/model_router.py` — `get_temperature()` method
- Reflection tasks (strategy, canon_interpretation, adversarial_review): temp 0.7
- Execution tasks (formatting, tagging, classification): temp 0.3
- Configurable via `PERMANENCE_REFLECTION_TEMP` and `PERMANENCE_EXECUTION_TEMP` env vars

### 2. Auton Framework — Agent Evaluation
**Key insight:** Standardized evaluation harness with fixed compute budgets per experiment. Measure single clear metric, iterate.

**Applied in:** Adopted Karpathy's AutoResearch pattern — constrain agent to single file, fixed time budget, single evaluation metric. Future Phase B work will use this for hybrid search optimization.

### 3. Theory of Mind for LLMs
**Key insight:** Strong models (GPT-4+, Claude Sonnet+) exhibit genuine ToM reasoning. Weak/small models hallucinate social reasoning and produce worse outputs when forced to simulate ToM.

**Applied in:** `core/model_router.py` — `requires_tom()` method
- ToM-sensitive tasks: conciliation, social_drafting, strategy
- Only dispatched to `TOM_CAPABLE_MODELS` (claude-sonnet+, gpt-4+, grok-3)
- Automatically stripped from Ollama/qwen tasks to avoid hallucination
- Guards against prompting local models with "consider the user's perspective" when they can't

### 4. Numina-Lean-Agent — Mathematical Reasoning
**Key insight:** Chain-of-thought with formal verification catches errors that pure language reasoning misses.

**Future application:** Phase B contradiction detector could use structured reasoning chains for evidence evaluation. Not implemented yet — needs Synthesis Ledger entries to detect against.

### 5. Agent Laboratory — Automated Research
**Key insight:** Research agents produce better results with explicit hypothesis → experiment → conclusion loops rather than open-ended exploration.

**Future application:** Phase C prediction signal pipeline should structure market analysis as hypothesis-driven experiments rather than broad scanning. Pattern compatible with existing `scripts/prediction_ingest.py`.

### 6. STILL-ALIVE — Long-Horizon Agent Persistence
**Key insight:** Agents that maintain persistent state across sessions outperform stateless agents on multi-day tasks. Key mechanism: structured checkpoint-resume with explicit state serialization.

**Future application:** Mac Mini always-on architecture naturally supports this. Phase C agent identity files + Synthesis Ledger provide the persistent state layer. Each agent's `memory/working/` directory is the checkpoint store.

### 7. Karpathy's AutoResearch
**Key insight:** Constrain agent to single file modification, fixed 5-minute compute budget, single evaluation metric (val_bpb). ~12 experiments/hour, ~100 overnight.

**Applied in:** Design principle for future automation loops:
- `scripts/governed_learning_loop.py` — already follows this pattern (single task, evaluation, iterate)
- Mac Mini can run experiments overnight with fixed budgets
- `PERMANENCE_LLM_MONTHLY_BUDGET_USD` enforces cost ceiling

### 8. OpenClaw v2026.3.8
**Key insight:** Latest version adds pluggable context providers and hybrid search. The "Synthesis Layer" thesis — own the cross-system context layer.

**Applied in:** Architecture validation. Permanence OS's Phase A (SQLite Synthesis Ledger) + Phase B (hybrid search + context engine) maps directly to OpenClaw's pattern. Our implementation uses Canon governance which OpenClaw lacks.

## Integration Summary

| Paper | Status | Where Applied |
|-------|--------|--------------|
| ParamMem | ✅ Implemented | `core/model_router.py` — temperature control |
| Theory of Mind | ✅ Implemented | `core/model_router.py` — ToM guard |
| AutoResearch | ✅ Pattern adopted | Design principle for automation loops |
| STILL-ALIVE | ✅ Architecture aligned | Mac Mini always-on + persistent state |
| Numina-Lean | 📋 Phase B | Contradiction detector structured reasoning |
| Agent Laboratory | 📋 Phase C | Prediction signal hypothesis loops |
| Auton Framework | 📋 Phase B | Hybrid search evaluation harness |
| OpenClaw v2026.3.8 | ✅ Architecture validated | Synthesis Layer thesis confirmed |
