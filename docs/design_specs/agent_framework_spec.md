# Agent Navigation & Interaction Framework
# Source: User research (March 19, 2026)

## Four-Zone Autonomy Model
- Zone 1: Full Auto (read, draft, analyze, schedule high-confidence)
- Zone 2: Soft Approval (Smart Toast, 90s timeout)
- Zone 3: Explicit Approval (Plan Preview Panel, blocking)
- Zone 4: Always Human (credentials, deletions, permissions)

## Five Communication Patterns
1. Ambient Pulse (agent status bar, zero intrusion)
2. Smart Toast (bottom-right, timed, non-blocking)
3. OPTI Insight Card (strategic recommendation)
4. Plan Preview Panel (side panel, blocking, show full plan)
5. Agent Chat Channel (persistent conversation thread)

## Three-Brain LLM Architecture
- Layer 1: Local SLM (Phi-3/Qwen/Llama via Ollama) - classify, parse, template
- Layer 2: Mid-Tier Cloud (Haiku/GPT-4o-mini/Flash) - draft, reply, summarize
- Layer 3: Frontier (Opus/Sonnet/GPT-5) - plan mode, finance, strategy

## Plan Mode: Read-only research state, generates Plan Document
## Agent Roster: Team member cards with autonomy/tone sliders
## Undo Buffer: 30 min reversibility window on all actions
