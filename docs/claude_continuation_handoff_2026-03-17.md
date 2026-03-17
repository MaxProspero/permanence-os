# Claude Continuation Handoff

Date: 2026-03-17
Branch: `main`
Remote: `origin https://github.com/MaxProspero/permanence-os.git`

## Current Repo State

The repo is in a stable, pushed-ready state.

Recent completed work includes:
- workflow execution engine with pause/resume
- workflow node templates and condition language
- grouped, quoted, regex, list, numeric, and function-style condition support
- OpenClaw provider integration and verifier improvements
- Studio visibility upgrades for workflow runs
- foundation server fixes and end-to-end workflow execution tests
- governed finance routing profile

Only local untracked path left alone:
- `docs/session_handoff/`

Do not modify or delete that path unless the user explicitly asks.

## What Was Not Finished In-UI

The user wanted live OpenClaw auth profiles for:
- Anthropic / Claude
- OpenAI
- xAI

This was not completed directly in the browser because that configuration is inside the user’s OpenClaw Control UI session.

The local OpenClaw UI is working:
- local gateway reachable at `http://127.0.0.1:18789/`
- user reached the Control UI

## Required Next Live Steps

### 1. OpenClaw Auth Profiles

In OpenClaw Control UI:
- go to `Settings > Config > Authentication`
- create auth profiles for:
  - `anthropic`
  - `openai`
  - `xai`
- for each profile:
  - `Provider` = provider name only, e.g. `openai`
  - `Mode` = `api_key`
  - do not put the API key in the `Provider` field

### 2. OpenClaw Secrets

In OpenClaw Control UI:
- go to `Settings > Config > Secrets`
- add the real API keys for those auth profiles
- if the field is raw JSON/string, use quoted string values
- if it is a normal input, paste the key directly

Then:
- `Save`
- `Apply`

### 3. Verify Live Use

After config:
- go to `Logs` and confirm there are no auth failures
- go to `Chat` and send a simple test prompt

## Governance Model The User Wants

The user explicitly wants:
- more autonomy for the system
- task-aware provider/model switching
- strong finance performance
- no uncontrolled free-running behavior
- approval governance for high-stakes actions

This is now encoded repo-side as governed autonomy, not unrestricted autonomy.

Relevant repo files:
- `core/model_policy.py`
- `core/model_router.py`
- `docs/finance_governance.md`

## Finance Routing Model

New finance task types added:
- `finance_analysis`
- `financial_review`
- `market_monitoring`
- `portfolio_risk`
- `valuation`

Expected use:
- use these task types in workflows and future live agent orchestration
- keep `requires_approval: true` for money movement, external writes, and credential changes

## OpenClaw Notes

Verified during setup:
- `openclaw setup` completed successfully
- local gateway responded with HTTP 200
- dashboard/control UI reachable

OpenClaw docs referenced during setup:
- `https://docs.openclaw.ai/web/control-ui`
- `https://docs.openclaw.ai/cli`

## Recommended Next Session Order

1. Confirm repo is pushed and clean.
2. Finish OpenClaw auth profiles and secrets in the UI.
3. Test Anthropic / OpenAI / xAI from OpenClaw chat.
4. Decide whether OpenClaw is only a control plane, or also part of live agent execution for Permanence OS.
5. Add finance-specialized agent prompts / skills / workflows after provider auth is proven.

## Constraint

Do not remove governance:
- financial actions must still require approval
- secret rotation / credential changes must still require approval
- provider switching is allowed
- unattended irreversible action is not allowed
