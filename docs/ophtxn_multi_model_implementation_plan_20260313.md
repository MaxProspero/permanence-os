# Ophtxn Multi-Model Implementation Plan

Last updated: 2026-03-13

## Goal

Turn Ophtxn from a governed operator shell into a governed multi-model personal operating system with:

- local-first routing,
- smart provider escalation,
- shared human-agent workspaces,
- project/task/document/workflow primitives,
- and premium product surfaces that feel more like a desktop computer than a dashboard.

This plan is the implementation companion to:

- [ophtxn_multi_model_personal_os_brief_20260313.md](/Users/permanence-os/Code/permanence-os/docs/ophtxn_multi_model_personal_os_brief_20260313.md)

## Strategic Direction

Build the product in this order:

1. router
2. schema
3. workspace
4. workflow builder
5. agent habitat
6. governed self-improvement

Do not expand page count or decorative UI before these primitives exist.

## Existing Assets To Reuse

### Runtime and governance

- `core/model_router.py`
- `core/polemarch.py`
- `core/model_judge.py`
- `core/spending_gate.py`
- `core/memory.py`

### App shell and storage

- `app/foundation/server.py`
- `app/foundation/storage.py`
- `app/foundation/memory_schema.json`

### Frontend shell

- `site/foundation/surface-system.js`
- `site/foundation/ophtxn_shell.html`
- `site/foundation/command_center.html`
- `site/foundation/local_hub.html`

These should become the base for the new OS rather than being replaced.

## External Reference Patterns Worth Adapting

These are useful inputs, not products to imitate directly.

### Perplexity-style research UX

- `boldsbrainai/perplexity-clone`
- `kamranxdev/Perplexify`
- `langchain-ai/local-deep-researcher`

Patterns to adapt:

- grounded answer layout
- source-first research flow
- local + cloud model support
- explicit search planning

### Workflow-builder UX

- `run-llama/flow-maker`
- `firecrawl/open-agent-builder`
- `vercel-labs/workflow-builder-template`
- `React Flow / XYFlow`

Patterns to adapt:

- node-based workflows
- visual execution graph
- step-by-step run/debug states
- reusable node definitions

### Agent workspace UX

- `microsoft/autogen` and AutoGen Studio
- `The-AI-Alliance/agent-lab-ui`
- `EpicStaff/EpicStaff`
- `eigent-ai/eigent`

Patterns to adapt:

- project-scoped agent teams
- role-based orchestration
- workspace-level model and tool config
- visible multi-agent flows

### Collaboration and document work

- Proof-style collaborative editing direction
- shared comments, edits, provenance, and version history

Patterns to adapt:

- human + agent edits in one surface
- suggestions vs direct edits
- source-linked revisions

## Product Architecture To Implement

## 1. Router Layer

### Outcome

A first-class routing engine that decides:

- local vs hosted,
- provider choice,
- model choice,
- fallback order,
- and governance tier.

### Current starting point

- `core/model_router.py` already contains provider maps, budget tiers, and append-only logging.

### Gaps to close

- task complexity classifier
- privacy/risk classifier
- explicit route rationale object
- route visibility in the UI
- Gemini/provider-extension support
- local-model capability profiles

### Deliverables

- `core/model_policy.py`
  - task class, privacy class, risk class, latency class
- `core/model_capabilities.py`
  - provider/model registry and strengths
- `core/model_router.py`
  - upgraded to emit structured route rationale
- `memory/working/model_routes.jsonl`
  - append-only route records
- foundation API endpoint
  - `/api/router/explain`

### UI exposure

Add route badges and route reasons to:

- `ophtxn_shell.html`
- `command_center.html`
- future workspace and document views

## 2. Workspace Schema Layer

### Outcome

The system stops thinking in isolated pages and starts thinking in durable objects.

### Canonical objects

- Project
- Task
- Document
- Workflow
- AgentProfile
- Approval
- ModelRoute
- ActivityEvent

### Deliverables

- `app/foundation/schemas/project.schema.json`
- `app/foundation/schemas/task.schema.json`
- `app/foundation/schemas/document.schema.json`
- `app/foundation/schemas/workflow.schema.json`
- `app/foundation/schemas/agent_profile.schema.json`
- `app/foundation/schemas/approval.schema.json`
- `app/foundation/schemas/model_route.schema.json`

- storage helpers in:
  - `app/foundation/storage.py`

- new storage root shape under:
  - `memory/working/app_foundation/projects/`
  - `memory/working/app_foundation/tasks/`
  - `memory/working/app_foundation/documents/`
  - `memory/working/app_foundation/workflows/`
  - `memory/working/app_foundation/agents/`

### Rules

- every object gets `id`, `created_at`, `updated_at`, `status`, `owner`
- every high-impact mutation creates an activity event
- every approval-targeted object points to an approval record

## 3. Shared Workspace Layer

### Outcome

One real product surface where:

- humans and agents collaborate,
- projects hold docs/tasks/workflows,
- and the shell becomes operationally useful beyond chat.

### Build target

Use `official_app.html` as the initial workspace studio surface.

Repurpose it into:

- project overview
- task lane
- shared document rail
- agent roster panel
- model/router inspector

### Why `official_app.html`

- it already reads like a build surface
- it is lower-risk to evolve than the command center shell
- it can become the place where apps, docs, and workflows are created

### Deliverables

- workspace API routes in `app/foundation/server.py`
- project and task CRUD
- document CRUD
- activity timeline
- assignment UI for agents

## 4. Shared Document Layer

### Outcome

Agents and users can work in the same document without chaos.

### MVP capability

- create a document inside a project
- add user edits
- add agent suggestions
- accept/reject changes
- attach provenance
- show revision history

### Implementation recommendation

Start simple:

- markdown-backed document model
- patch/suggestion objects stored separately
- no rich-text editor dependency in v1

Then evolve to richer collaborative editing later.

### Deliverables

- `document.md`
- `document.meta.json`
- `document.suggestions.jsonl`
- `document.revisions.jsonl`

### UI surface

Likely best home:

- `official_app.html`
- then later `agent_view.html`

## 5. Workflow Builder Layer

### Outcome

Users can create reusable flows with approvals, agents, and model routes.

### Design direction

Use XYFlow / React Flow style interaction patterns:

- clean canvas
- dark premium node cards
- clear execution state
- minimal but strong chrome

### Core nodes

- Start
- Task
- Agent
- Model Route
- Search/Research
- Tool
- Document Edit
- Approval
- Branch
- Review
- End

### Implementation recommendation

Do not build a full general-purpose no-code engine first.

Instead:

- store workflows as JSON graphs
- ship a small fixed node set
- compile to execution specs for the governor/router

### UI surface

Either:

- evolve `official_app.html` into Studio + Workflow Builder
- or add `workflow_builder.html` later if the current page gets too dense

## 6. Agent Habitat Layer

### Outcome

Agents become first-class collaborators with clear identity and permissions.

### Build target

Use `agent_view.html` and `rooms.html` together:

- `agent_view.html`
  - roster, role config, model preferences, permissions
- `rooms.html`
  - habitat / district / team map / social metaphor

### Agent permissions

Each agent should have independent scopes for:

- read
- suggest
- edit
- execute
- approve
- self-improve

### Required controls

- project-level membership
- task-level assignment
- edit rights by document/project
- system-edit scopes separately gated

## 7. Governed Self-Improvement Layer

### Outcome

Agents can improve the system, but inside policy.

### Build target

Reuse and extend current improvement loop concepts already present in the docs and automations.

### Deliverables

- proposal object
- improvement queue
- approval requirement
- validation hook
- rollback metadata
- improvement analytics

### Hard rule

No silent system rewrites.

## UI Design Direction

The next design phase should shift from "page polish" to "product grammar."

### Visual grammar

- fewer dashboard cards
- more intentional work surfaces
- stronger hierarchy between navigation, workspace, and inspectors
- compact side panels
- clearer mode switching
- richer activity trails

### Typography direction

- keep current premium shell tone
- reduce decorative label noise
- use stronger primary headings and quieter metadata
- make route/approval/agent states easy to scan

### Interaction direction

- command palette
- split panes
- inspector drawers
- document suggestions
- workflow node detail panels
- agent activity feed

### Design benchmark

Aim for:

- better than generic Figma-style SaaS dashboards
- more coherent than open-source agent labs
- calmer than flashy AI tools
- more premium than existing self-hosted Perplexity clones

## Page Map Transition

### Keep and evolve

- `ophtxn_shell.html`
  - conversational and live execution shell
- `command_center.html`
  - approvals, queue, operations, review
- `local_hub.html`
  - home / launch / system overview
- `official_app.html`
  - build studio + project workspace
- `agent_view.html`
  - agent roster + permissions + assignments
- `rooms.html`
  - habitat / team district / social coordination

### Keep but deprioritize

- `press_kit.html`
- `ai_school.html`
- `night_capital.html`
- `markets_terminal.html`
- `trading_room.html`
- `daily_planner.html`
- `comms_hub.html`

These still matter, but the next core work should focus on primitives, not more polish.

## Immediate Engineering Plan

### Sprint 1: Router and schemas

- add route rationale object
- add provider/model registry
- add schema files for core objects
- add CRUD storage helpers
- add route explanation endpoint

### Sprint 2: Workspace MVP

- turn `official_app.html` into a real project workspace
- add project/task/document endpoints
- add activity timeline
- add router badges and approval badges

### Sprint 3: Document collaboration

- add suggestions/revisions
- add agent comments and proposed edits
- add accept/reject flow

### Sprint 4: Workflow builder MVP

- add workflow graph schema
- add minimal canvas
- add fixed node palette
- add compile-to-execution config

### Sprint 5: Agent habitat

- add agent permissions and project assignment
- connect `agent_view.html` and `rooms.html` to real data

## What Not To Do Next

- do not add more static pages before workspace objects exist
- do not overbuild rich-text editing before patch/suggestion flow works
- do not add unrestricted self-editing
- do not let model routing stay hidden in backend code only
- do not let UI inspiration turn into copied open-source aesthetics

## Success Criteria

The next milestone is complete when:

1. the user can create a project
2. the user can create a task and assign an agent
3. the system can explain why it chose local, Claude, GPT, or another model
4. a document can be edited by both a human and an agent with visible revision history
5. one workflow can be visually created and executed under approval rules

