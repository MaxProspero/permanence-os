# Ophtxn Multi-Model Personal OS Brief

Last updated: 2026-03-13

## Purpose

Define the next product shape for Permanence OS / Ophtxn:

- a governed personal operating system,
- with premium design and shared agent-user workspaces,
- powered by a smart multi-model router,
- local-first for routine work,
- and capable of research, coding, planning, execution, and system improvement.

This brief merges:

- the current repository architecture and guardrails,
- the handoff/session docs,
- and external inspiration from Perplexity-style search systems, collaborative AI editors, and agent orchestration tooling.

## Product Thesis

Ophtxn should become a governed personal AI operating system with multi-model orchestration.

It is not just:

- a chatbot,
- a wrapper around model APIs,
- or a themed dashboard.

It is:

- a control plane for the user,
- a workspace for human and agent collaboration,
- a router that chooses the right model for the right job,
- and an execution environment where agents can research, build, review, and improve under policy.

## Core Promise

For normal, cheap, private, or repetitive tasks:

- use local models first.

For harder or more specialized tasks:

- escalate intelligently to Claude, GPT, Gemini, or other providers.

For sensitive or high-impact tasks:

- require governance, approvals, audit logs, and clear routing rationale.

## Design Position

The interface should feel like:

- a Perplexity Computer for deep search and answer synthesis,
- a Cursor-like environment for building software with agents,
- a Notion-like workspace for documents, projects, and living knowledge,
- and a sovereign desktop shell where the user and agents operate together.

But it must still feel like one coherent operating system, not a bag of features.

## Non-Negotiables

These remain unchanged from the current system direction:

1. Human authority is final.
2. Canon and governance remain explicit and versioned.
3. Memory must compound with auditability.
4. High-impact actions require approval or policy clearance.
5. Local-first and low-cost modes stay on by default.
6. The system explains why a model, agent, or action path was chosen.
7. Self-improvement is allowed only through scoped and reversible change paths.

## What Changes From the Current Product

The current system is strongest as:

- a governed operator dashboard,
- a local shell,
- and a bounded agent stack.

The next version must elevate these to first-class product primitives:

- model routing,
- shared workspace objects,
- multi-agent project execution,
- collaborative editing,
- and controlled system self-improvement.

## Product Objects

The operating system should be built around these core objects.

### 1. Project

A project is the top-level container for work.

It contains:

- goals,
- tasks,
- agents,
- documents,
- workflows,
- approvals,
- outputs,
- and model/runtime preferences.

### 2. Task

A task is a unit of work with:

- owner,
- assignee agent or human,
- priority,
- success criteria,
- risk tier,
- budget tier,
- dependencies,
- and review status.

### 3. Document

A document is a live collaboration surface where:

- users and agents can read, comment, suggest, and edit,
- change history is preserved,
- provenance is attached,
- and permissions determine who can apply changes.

### 4. Workflow

A workflow is a reusable execution graph.

It can include:

- triggers,
- branches,
- tool steps,
- model calls,
- approvals,
- retries,
- and review gates.

### 5. Agent

An agent is a named worker with:

- a role,
- tool permissions,
- memory scope,
- model preferences,
- escalation limits,
- and collaboration rights.

### 6. Model Route

A model route records:

- chosen model,
- fallback path,
- cost tier,
- privacy tier,
- latency target,
- and selection rationale.

### 7. Approval

An approval is a governed checkpoint for:

- external posting,
- code merges,
- financial actions,
- system self-edits,
- or any high-impact task.

### 8. Memory

Memory stores:

- personal preferences,
- project history,
- workflow outcomes,
- agent learnings,
- and decision context.

Memory must support both retrieval and temporal understanding of change over time.

## Model Router Architecture

The model router becomes a first-class product feature.

### Router Goals

- minimize spend when cheap/local is sufficient,
- preserve privacy when local is preferred,
- use frontier models only when task complexity justifies it,
- and always expose the reason for routing.

### Suggested Routing Policy

#### Tier 1: Local Runtime

Default for:

- routine summarization,
- lightweight drafting,
- note cleanup,
- low-risk classification,
- first-pass coding assistance,
- and repeated personal workflows.

Suggested engines:

- latest strong local Llama-family model,
- or other local reasoning/coding model when operationally better.

#### Tier 2: Claude

Preferred for:

- codebase reasoning,
- architecture,
- careful editing,
- spec writing,
- and high-quality implementation work.

#### Tier 3: GPT

Preferred for:

- broad utility tasks,
- transformation work,
- general-purpose generation,
- and tasks where tool ecosystem compatibility matters.

#### Tier 4: Gemini

Preferred for:

- multimodal tasks,
- long-context operations,
- and provider-specific strengths where validated.

### Routing Inputs

Every task route should consider:

- task type,
- required quality,
- privacy sensitivity,
- expected latency,
- cost ceiling,
- file/context size,
- and whether tool use is required.

### Routing Outputs

The UI should show:

- chosen model,
- why it was selected,
- what fallback exists,
- and what the approximate cost/risk tier is.

## Agent Society Architecture

The system should support an agent society, but not uncontrolled autonomy.

### Agent Classes

- Governor: policy, routing, budgets, approvals
- Planner: project specs and decomposition
- Researcher: evidence, web, docs, synthesis
- Builder: code, workflows, implementation
- Reviewer: quality and regression checks
- Conciliator: retry, merge, escalate decisions
- Domain agents: finance, comms, design, product, operations, learning

### Collaboration Model

Agents should be able to:

- work in the same project,
- read shared documents,
- comment on each other's outputs,
- propose edits,
- and hand off work through explicit task states.

### Overriding and Improvement

Agents may propose overriding another agent's work only when:

- they provide rationale,
- they preserve version history,
- the task policy permits intervention,
- and the result still goes through the right review or approval stage.

## Shared Workspace Architecture

The workspace should support three collaboration modes.

### 1. Human-led

The user directs agents and approves key changes.

### 2. Agent-assisted

Agents prepare, draft, review, and suggest while the user remains active in the loop.

### 3. Governed Autonomy

Agents can execute bounded workflows independently inside pre-approved scopes.

## Memory Architecture Direction

The system should move beyond static retrieval-only memory.

### Memory Requirements

- user memory
- project memory
- workflow memory
- agent memory
- system-improvement memory

### Memory Principles

- store event time and decision time separately where relevant
- preserve revision lineage
- distinguish durable memory from scratch context
- attach provenance to generated claims or edits

This aligns with the handoff emphasis on compounding memory and with current research arguing for more temporal, stateful agent memory designs.

## Self-Improvement Framework

The system should be able to improve itself, but only through governed loops.

### Allowed Self-Improvement Actions

- propose new workflows
- propose prompt or routing updates
- propose UI improvements
- propose new agents or capabilities
- patch bounded system areas when explicitly authorized

### Required Controls

- change proposal record
- approval state
- test or validation requirement
- rollback path
- audit log

### Forbidden Default Behavior

- silent self-modification
- unrestricted prompt mutation
- unrestricted system rewrites
- hidden cost escalation

## Product Surface Map

The current pages should evolve into product modes, not isolated demos.

### Existing Surfaces and Their Future Roles

- `index.html`
  - public or front-door overview of the OS
- `local_hub.html`
  - launch cockpit and user home surface
- `command_center.html`
  - execution, approvals, and operating queue
- `ophtxn_shell.html`
  - live personal shell and conversational runtime
- `markets_terminal.html`
  - research and market intelligence mode
- `trading_room.html`
  - execution room for strategy and signals
- `night_capital.html`
  - capital planning and venture/portfolio mode
- `daily_planner.html`
  - personal planning and routine layer
- `comms_hub.html`
  - outreach, messaging, and communication workflows
- `rooms.html`
  - agent habitat / project district / role-based environment
- `official_app.html`
  - app and workflow builder studio
- `agent_view.html`
  - agent roster, assignment, and collaboration surface
- `ai_school.html`
  - learning, fine-tuning, and capability development

### Missing Product Surfaces

To fulfill the new thesis, add:

- model router inspector
- project workspace
- shared document editor
- workflow builder
- agent habitat / invite surface
- approval timeline
- self-improvement control board

## Build Strategy

The correct build sequence is not "add everything at once."

### Phase 1: Multi-Model Core

Ship:

- model routing policy engine
- local-first model configuration
- provider fallback rules
- route rationale in UI

Success means:

- the system can choose local vs frontier models by task class,
- and the user can see why.

### Phase 2: Workspace Core

Ship:

- projects
- tasks
- shared docs
- approvals as first-class objects

Success means:

- user and agents can work inside the same durable containers.

### Phase 3: Agent Collaboration

Ship:

- project agent assignment
- shared editing permissions
- review and override workflow
- agent conversation and handoff traces

Success means:

- multiple agents can cooperate on one outcome without chaos.

### Phase 4: Workflow Builder

Ship:

- reusable visual workflows
- triggers, approvals, retries, model steps
- local + provider model nodes

Success means:

- the OS becomes programmable by the user.

### Phase 5: Governed Self-Improvement

Ship:

- proposals,
- scoped self-edits,
- validation and rollback,
- system improvement analytics.

Success means:

- the system compounds improvements without losing control.

## External Research Signals Incorporated

These references support the product direction, but should be used as inputs, not as product identity.

### Perplexity-style local wrappers

- `bitun123/perplexity`
  - shows demand for self-hosted Perplexity-like research UX
- `foxy1402/perplexio`
  - shows a local-first alternative with grounded search experience
- `Casheu1/perplexity-2api-python`
  - shows OpenAI-compatible wrapping patterns and provider abstraction

### Collaborative AI workspaces

- `proof`-style direction
  - validates the need for human + agent document collaboration

### Memory and agent architecture

- research on agent memory
  - supports moving beyond static RAG toward richer temporal memory handling

### Reverse-engineering and prompt/system collections

- `x1xhlol/system-prompts-and-models-of-ai-tools`
  - useful for competitive analysis
  - not a product foundation

### Workflow builder inspiration

- dark premium flow-builder references
  - validate a visual automation layer
  - should be adapted into the Ophtxn visual language rather than copied

## Product Risks

### Risk 1: "Everything app" collapse

If every feature is added without clear primitives, the product becomes incoherent.

Mitigation:

- keep projects, tasks, docs, workflows, agents, approvals, and memory as the only core objects.

### Risk 2: Unbounded autonomy

If agents can freely rewrite system state, the product becomes unsafe and unstable.

Mitigation:

- scoped permissions, review gates, and reversible changes only.

### Risk 3: Model-spend drift

If routing defaults to frontier models too often, cost discipline disappears.

Mitigation:

- local-first default and explicit escalation rules.

### Risk 4: UX fragmentation

If each page becomes its own product, the system loses its operating-system feel.

Mitigation:

- one chrome layer, one object model, one routing language, one approval language.

## Decision

The system should evolve into:

**a governed multi-model personal operating system with shared agent-user workspaces and controlled self-improvement.**

That is the clean synthesis of:

- your vision,
- the handoff docs,
- the current repo architecture,
- and the external research direction.

## Immediate Next Actions

1. Add a first-class model router policy module and UI exposure.
2. Define persistent schemas for `Project`, `Task`, `Document`, `Workflow`, `Agent`, `Approval`, and `ModelRoute`.
3. Build a shared document/project workspace before adding more isolated pages.
4. Add agent permission scopes for read, suggest, edit, execute, and self-improve.
5. Keep UI work tied to these primitives instead of adding decorative surfaces.

