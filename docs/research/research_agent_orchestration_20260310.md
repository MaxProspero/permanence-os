# Agent Orchestration & Architecture Report

> Generated: 2026-03-10 | Status: RESEARCH REPORT
> Purpose: Inform agent framework improvements, workflow patterns, and novel capabilities

---

## Executive Summary

Analysis of 10+ agent orchestration frameworks reveals that the most effective
architectures are the most constrained. Permanence OS's v0.4 architecture
(11 agents + 4 workflows with Polemarch governance) aligns with industry best
practices. This report identifies specific patterns to adopt from Karpathy's
autoresearch, ByteDance DeerFlow, Anthropic's agent patterns, the AI Hedge Fund,
and meta-agent research.

---

## 1. KEY FRAMEWORK PATTERNS

### Karpathy AutoResearch: Constraint-Driven Autonomy
- **Pattern**: Single agent, single file, single metric, 5-min timeout
- **Insight**: Extreme constraint prevents coordination failures entirely
- **Key concept**: `program.md` as "research org code" -- human optimizes the
  organizational structure, agent optimizes within it
- **Apply to Permanence**: Create per-agent instruction files: `agents/<id>/SKILL.md`
  Human-editable markdown defining constraints, style, operating parameters.
  Polemarch loads relevant SKILL.md when routing. Separates agent behavior
  from agent code.

### ByteDance DeerFlow: Progressive Context Loading
- **Pattern**: Lead agent spawns sub-agents dynamically with isolated context
- **Key innovation**: Skills loaded only when needed, keeping context lean
- **Apply to Permanence**: Polemarch should only load context for the routed
  agent, not all 12. When researcher is dispatched, only researcher's tools
  and context are loaded. Reduces token waste.

### Anthropic Building Effective Agents: The Five Patterns
1. **Prompt Chaining** -- sequential steps with gates (= our WORKFLOW_REGISTRY)
2. **Routing** -- classify input, direct to handler (= our Polemarch)
3. **Parallelization** -- independent subtasks in parallel (enhancement needed)
4. **Orchestrator-Workers** -- central LLM delegates dynamically (planner evolution)
5. **Evaluator-Optimizer** -- generate + evaluate loop (= our executor + reviewer)
- **Critical insight**: Anthropic spent more time optimizing tools than prompts.
  Changing tools to require absolute filepaths eliminated entire error classes.

### AI Hedge Fund (virattt): Fan-Out/Fan-In Consensus
- **Pattern**: 12 strategy agents + 4 analysis agents + Risk Manager + Portfolio Manager
- **Key innovation**: Persona-driven analysis creates interpretable decision chains
- **Apply to Permanence**: compliance_gate = Risk Manager. Polemarch = Portfolio Manager.
  For complex tasks, route to multiple agents simultaneously (researcher +
  briefing_agent + compliance_gate in parallel), synthesize results.

### Microsoft Experiential RL: Reflection Loop
- **Pattern**: Experience -> Reflection -> Consolidation
- **Apply to Permanence**: When reviewer rejects executor output:
  1. Capture what was attempted
  2. Generate explicit reflection on what went wrong
  3. Feed reflection to executor for retry
  4. Over time, consolidate successful patterns into agent's SKILL.md

### Andrew Ng Context Hub: Documentation as Agent Memory
- **Pattern**: Agents fetch versioned docs on demand, attach local annotations
- **Apply to Permanence**: Add annotation layer to zero_point. When agents write
  to memory, allow attaching annotations to existing entries. Future retrievals
  surface both the entry and all annotations. Creates learning flywheel.

---

## 2. NOVEL CAPABILITIES TO BUILD

### A. Agent Freelancer Marketplace (User Idea)
Evolve static Polemarch routing into dynamic bidding:

```
Task arrives -> Polemarch broadcasts RFP to eligible agents
-> Each agent evaluates: capability, load, confidence, estimated cost
-> Each submits Bid: {agent_id, confidence, tokens, time, skills}
-> Polemarch evaluates: filter by risk_tier, score by confidence/cost
-> Winner gets task; others released
```

Benefits: natural load balancing, capability discovery, surfaces when no agent
is confident (triggering human escalation).

**Implementation priority**: Medium-term. Current static routing works well for
11 agents. Marketplace makes sense at 20+ agents or when agents have overlapping
capabilities.

### B. Meta-Agent Skill Creation (User Idea: "Don't install skills, build an agent that creates them")
Research sources: Voyager (NVIDIA), ADAS, EvoSkill (March 2026), Skill Factory

**Pattern**: Meta-agent watches task completions, identifies reusable patterns,
generates SKILL.md entries for the skill library.

**Implementation**:
1. Observe which tasks Polemarch routes frequently
2. Identify patterns in successful executor outputs
3. Generate reusable skill definitions as markdown
4. Store in skill library (new directory: `skills/`)
5. Make available to future executor runs

**Priority**: Medium-term. Requires stable base system first.

### C. Agent Phone Escalation (User Idea: "Agent could call you")
Research: Twilio, Vapi, Bland AI, Retell

**Tiered Escalation Ladder**:
- Tier 0: Silent log (LOW risk, auto-approved)
- Tier 1: Dashboard notification (MEDIUM risk)
- Tier 2: Telegram push (MEDIUM risk, time-sensitive)
- Tier 3: Apple push notification / phone call (HIGH risk, urgent)
- Tier 4: Full stop (CRITICAL risk) -- all channels simultaneously

**Key insight**: Escalation based on risk_tier AND time-sensitivity. HIGH-risk
with 24h deadline = Tier 2. MEDIUM-risk with 5-min window = Tier 3.

**Priority**: High. Approval queue already exists. Adding Telegram bot for
Tier 2 is the fastest high-value addition.

---

## 3. IMMEDIATE RECOMMENDATIONS

### 3.1 Per-Agent SKILL.md Files (This Week)
Create `agents/skills/` directory with markdown specs:
- `agents/skills/planner.md`
- `agents/skills/researcher.md`
- `agents/skills/executor.md`
- `agents/skills/reviewer.md`
- etc.

Each contains: role description, constraints, preferred patterns, example
outputs. Polemarch loads the relevant file when dispatching.

### 3.2 Progressive Context Loading (This Week)
Modify Polemarch dispatch to only load the routed agent's context:
- Only import the dispatched agent's module
- Only load its SKILL.md
- Only pass relevant memory entries

### 3.3 Tool Interface Hardening (This Week)
Review every `allowed_tools` entry. Ensure:
- Tool parameters use absolute paths (not relative)
- Tool docstrings include usage examples
- Each tool has clear input/output schema

### 3.4 Parallel Fan-Out for Complex Tasks (This Month)
When Polemarch receives a multi-faceted task:
- Route to multiple agents simultaneously
- Researcher + briefing_agent + compliance_gate in parallel
- Synthesize results before returning to requester

### 3.5 Experience-Reflection Loop (This Month)
Enhance reviewer -> executor retry cycle:
- Capture rejection reason as structured data
- Generate reflection prompt for executor retry
- Log reflection in episodic memory for pattern analysis

---

## 4. ARCHITECTURE VALIDATION

The research converges on one meta-insight: **winning multi-agent architectures
are the most constrained, not the most complex.**

- Karpathy: one file, one metric
- Anthropic: start with simple prompts
- AI Hedge Fund: independent agents, no peer communication
- DeerFlow: isolated sub-agent context

Permanence OS v0.4 already embodies this through:
- Polemarch governance model
- Risk tiering
- forbidden_actions lists
- Department separation

The architecture is validated. Extend incrementally, measure before adding complexity.

---

*This report informs architecture decisions for Permanence OS. No code changes made.*
