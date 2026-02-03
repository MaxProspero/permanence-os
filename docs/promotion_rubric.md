# Canon Promotion Rubric

Use this rubric to decide whether episodic lessons should become Canon.

## Eligibility (must meet all)
- **Repeated pattern:** Observed at least twice across separate episodes.
- **Clear failure/benefit:** Documented outcome with concrete impact.
- **Actionable rule:** Can be expressed as an invariant, heuristic, tradeoff, or value.
- **No conflict:** Does not contradict existing Canon values/invariants.
- **Human approval:** Explicit sign-off planned before merge.

## Strength Signals (at least 2 recommended)
- **Cross-domain relevance:** Applies beyond a single project/task.
- **Second-order impact considered:** Side effects identified and acceptable.
- **Reversibility/rollback available:** A rollback plan is defined.
- **Testable:** Can be validated by an eval harness or deterministic check.
- **Compression achieved:** Replaces multiple ad-hoc decisions with one rule.

## Disqualifiers (any = do not promote)
- **Single occurrence** without strong evidence it will repeat.
- **Based on speculation** or unsourced assumptions.
- **Conflicts with Legal Integrity** or Human Authority.
- **Requires new tools** without evaluation or tool-adoption criteria.
- **Would reduce clarity** by adding ambiguous language.

## Required Outputs for Promotion
- **Rationale:** Why it belongs in Canon.
- **Impact analysis:** Who/what it affects.
- **Tradeoffs:** What we lose by adopting it.
- **Rollback plan:** How to undo if wrong.
- **Changelog entry:** Human-readable summary.

## Suggested Placement
- **Invariant:** If violation is unacceptable under all conditions.
- **Heuristic:** If it's a rule of thumb with known failure modes.
- **Tradeoff:** If it chooses between two values under tension.
- **Value:** If it defines priority at the highest level.
