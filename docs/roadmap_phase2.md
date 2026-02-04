# Phase 2 Roadmap — Capability Buildout

## 1) Researcher Pipeline (Priority 1)
**Goal:** real source gathering with provenance.
- Tool adapters (web/search/doc APIs)
- Source dominance checks
- Automatic sources.json generation
 - URL fetch adapter (read-only, blocks private/localhost)

**Done when:**
- Researcher can collect 3+ sources with provenance
- Reviewer blocks single‑source outputs by default
 - URL adapter produces sources.json and tool memory entries

## 2) Executor Pipeline (Priority 2)
**Goal:** generate outputs strictly from plan + sources.
- Spec‑bound output generation
- Explicit provenance sections
- Reviewer‑proof output formatting

**Done when:**
- Outputs pass Reviewer in 3 consecutive runs

## 3) Evaluation Harness Expansion (Priority 3)
**Goal:** adversarial + failure‑injection tests.
- Hallucination tests
- Budget breach tests
- Canon conflict tests
- Tool failure simulation

## 4) Department Agents (Priority 4)
**Goal:** stub → functional for 1 department at a time.
Recommended order:
1) Email
2) Briefing
3) Health
4) Social

**Status:** Email triage implemented (local JSON/JSONL inbox).
**Status:** Briefing aggregation implemented (local outputs + OpenClaw + HR + email + health).
**Status:** Health summary implemented (local JSON/JSONL health data).

## 5) Memory Promotion Protocol (Priority 5)
**Goal:** human‑approved Canon updates from episodic patterns.
- Promotion queue hygiene
- Review rubric adherence

## 6) Logos Praktikos Gate (Future)
**Goal:** tiered activation per Canon thresholds.
- Observer → Advisor → Limited Executor → Full Trust

---
Owner: Dax  
Last updated: 2026-02-03
