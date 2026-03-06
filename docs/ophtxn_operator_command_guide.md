# Ophtxn Operator Command Guide

Last updated: 2026-03-06 (UTC)

This is your practical command map for running Ophtxn day-to-day.

Policy reference:
- `docs/ophtxn_access_vpn_policy_20260306.md`
- `docs/ophtxn_master_execution_board_20260306.md`

## 0. Connectivity Quick Check (Run First)

```bash
python cli.py openclaw-status
openclaw channels status --probe
python cli.py telegram-control --action status
python cli.py discord-feed-manager --action list
python cli.py discord-telegram-relay --action status
python cli.py comms-status
python cli.py comms-doctor
```

If OpenClaw UI is connected but not responsive, verify OpenClaw-side session/channel setup separately. Telegram/Discord relays in this repository can still run normally.
`comms-status` now includes an OpenClaw Telegram/Discord/iMessage probe summary line so channel drift is visible without opening OpenClaw directly.

## 0.1 Interface Launch (One Command)

```bash
python cli.py operator-surface --no-open
```

Local URLs:
- Dashboard API / command center: `http://127.0.0.1:8000`
- Foundation site: `http://127.0.0.1:8787`
- Ophtxn app shell: `http://127.0.0.1:8797/app/ophtxn`
- OpenClaw dashboard: `openclaw dashboard`

### Optional iMessage Channel (OpenClaw)

If you want iMessage as an additional operator surface later:

```bash
# one-time macOS prerequisite (if brew install errors on CLT)
softwareupdate --list
# then install one of:
# sudo softwareupdate -i "Command Line Tools for Xcode-16.4"
# or run: xcode-select --install

# install iMessage bridge CLI required by OpenClaw
brew install steipete/tap/imsg
imsg rpc --help

openclaw plugins enable imessage
openclaw channels add --channel imessage --name ophtxn-imessage
openclaw config set channels.imessage.groupPolicy disabled
openclaw channels status --probe
openclaw channels logs --channel imessage
```

Notes:
- If `channels status --probe` shows `imsg not found (imsg)`, `imsg` is not installed in PATH for the gateway user.
- macOS privacy prompts may appear (Messages database and automation permissions depending on runtime mode).
- Keep iMessage staged: install `imsg` -> enable channel -> probe -> test one controlled path.

## 1. Daily Command Flow (Recommended)

### Morning (start)
1. `/ops-morning`
2. `/no-spend-audit strict`
3. `/approvals-top 10 source=phase3_opportunity_queue`
4. `/comms-status`

### Midday (correction pass)
1. `/ops-midday`
2. `/approvals-status`
3. `/approve-batch-safe 3 source=phase3_opportunity_queue max-priority=low max-risk=medium`
4. `/platform-watch`
5. `/launch-status min-score=80`

### Evening (closeout)
1. `/ops-evening`
2. `/ops-hygiene 1`
3. `/approvals-list 10`
4. `/comms-digest`
5. `/prod-estimate`

### Single-shot daily sweep
- `/ops-cycle`
- `/ops-pack strict` (runs cycle + strict no-spend audit + approvals top)
- `/ops-pack decision=defer count=3 source=phase3_opportunity_queue max-priority=low max-risk=medium` (adds safe batch decision)

## 2. Weekly Command Flow (Recommended)

1. `/comms-doctor`
2. `/comms-escalations`
3. `/chronicle-status`
4. `/chronicle-execution 12`
5. `/brain-sync`
6. `/improve-list`
7. `/launch-plan`

## 3. Full Telegram Command List (All Accessible)

### Core help + identity
- `/comms-mode`
- `/comms-whoami`
- `/memory-help`
- `/memory`

### Memory + profile
- `/remember <note>`
- `/share <long note>`
- `/recall`
- `/profile`
- `/profile-set <field> <value>`
- `/profile-get`
- `/profile-history [field]`
- `/profile-conflicts`

### Personality + habits
- `/personality [mode]`
- `/personality-modes`
- `/habit-add <name> | cue: ... | plan: ...`
- `/habit-plan <name> | cue: ... | plan: ...`
- `/habit-done <name>`
- `/habit-nudge`
- `/habit-list`
- `/habit-drop <name>`
- `/forget-last`

### Terminal task queue
- `/terminal <task>`
- `/terminal-list`
- `/terminal-status`
- `/terminal-complete <task-id|latest>`

### Model/provider controls
- `/provider-status`
- `/provider-set <anthropic|openai|xai|ollama>`
- `/low-cost-status`
- `/low-cost-enable [budget=<usd>] [milestone=<usd>] [chat-agent=1]`
- `/low-cost-disable`
- `/no-spend-audit [strict]`

### Comms controls
- `/comms-status`
- `/comms-doctor`
- `/comms-doctor-fix`
- `/comms-digest`
- `/comms-digest-send`
- `/comms-escalations`
- `/comms-escalations-send`
- `/comms-escalation-status`
- `/comms-escalation-enable`
- `/comms-escalation-disable`
- `/comms-run`
- `/comms-auto-status`

### Learning + self-improvement
- `/learn-status`
- `/learn-run`
- `/improve-status`
- `/improve-pitch`
- `/improve-list`
- `/improve-approve [proposal-id] [decision-code]`
- `/improve-reject [proposal-id] [decision-code]`
- `/improve-defer [proposal-id] [decision-code]`

### Brain
- `/brain-status`
- `/brain-sync`
- `/brain-recall <query>`

### X + platform watch
- `/x-watch <handle|url>`
- `/x-unwatch <handle|url>`
- `/x-watch-list`
- `/idea-status`
- `/idea-intake <links/text>`
- `/idea-run [max=<n>] [min-score=<n>] [queue=1]`
- `/idea-queue [max=<n>] [min-score=<n>]`
- `/launch-status [min-score=<n>] [strict]`
- `/launch-plan`
- `/platform-watch [strict] [no-queue]`

### Production deployment
- `/prod-status [min-score=<n>] [strict]`
- `/prod-preflight [strict]`
- `/prod-estimate`
- `/prod-plan`
- `/prod-runtime`
- `/prod-config domain=<domain> api-domain=<domain> [site-url=<url>] [api-base=<url>] [no-spend]`

### Ops
- `/ops-status`
- `/ops-morning`
- `/ops-midday`
- `/ops-evening`
- `/ops-cycle`
- `/ops-pack [status|strict] [decision=approve|reject|defer] [count=<n>] [source=<source>] [max-priority=<level>] [max-risk=<level>]`
- `/ops-hygiene [target-pending]`

### Approval triage
- `/approvals-status [source=<source>]`
- `/approvals-list [limit] [source=<source>]`
- `/approvals-top [limit] [source=<source>]`
- `/approve-next [proposal-id] [source=<source>] [optional note]`
- `/reject-next [proposal-id] [source=<source>] [optional note]`
- `/defer-next [proposal-id] [source=<source>] [optional note]`
- `/approve-batch [count] [source=<source>] [optional note]`
- `/reject-batch [count] [source=<source>] [optional note]`
- `/defer-batch [count] [source=<source>] [optional note]`
- `/approve-batch-safe [count] [source=<source>] [max-priority=<level>] [max-risk=<level>] [optional note]`
- `/reject-batch-safe [count] [source=<source>] [max-priority=<level>] [max-risk=<level>] [optional note]`
- `/defer-batch-safe [count] [source=<source>] [max-priority=<level>] [max-risk=<level>] [optional note]`

### Chronicle
- `/chronicle-help`
- `/chronicle-status [source=<source>]`
- `/chronicle-run [strict] [no-canon] [queue=<n>] [exec=<n>]`
- `/chronicle-list [limit]`
- `/chronicle-approve [proposal-id] [optional note]`
- `/chronicle-reject [proposal-id] [optional note]`
- `/chronicle-defer [proposal-id] [optional note]`
- `/chronicle-execution [limit] [no-canon]`

## 4. High-Impact Commands (Use Deliberately)

These mutate state or can change direction significantly:
- `/provider-set ...`
- `/low-cost-enable ...`
- `/low-cost-disable`
- `/prod-runtime`
- `/prod-preflight ...`
- `/prod-config ...`
- `/learn-run`
- `/approve-next`, `/reject-next`, `/defer-next`
- `/approve-batch`, `/reject-batch`, `/defer-batch`
- `/approve-batch-safe`, `/reject-batch-safe`, `/defer-batch-safe`
- `/chronicle-run`
- `/chronicle-approve`, `/chronicle-reject`, `/chronicle-defer`

## 5. Safe Defaults

When you are protecting spend and reducing risk:
- Keep provider on `ollama`.
- Keep no-spend enabled.
- Prefer `*-safe` approval batch commands over broad batch commands.
- Prefer source-scoped commands:
  - `source=phase3_opportunity_queue`
  - `source=chronicle_refinement_queue`

## 6. How To Share New Ideas (Tweets/GitHub/Tools)

Yes, keep sending them. Best flow:

1. Send in Telegram with context:
   - what it is
   - what problem it solves
   - why now
2. Log it directly to idea intake:
   - `/idea-intake <your long idea + links>`
3. Run ranking pass:
   - `/idea-run max=30 min-score=30`
4. Queue top ideas for governance:
   - `/idea-queue max=20 min-score=65`
5. I run evaluation and return:
   - keep / skip
   - implementation complexity
   - security/privacy risks
   - cost impact
   - recommended next action

Current tracked intake backlog:
- `docs/ophtxn_external_idea_backlog_20260305.md`

## 7. Evaluation Rubric For New Ideas

Each external idea is scored on:
1. Strategic fit with Ophtxn mission.
2. Cost profile (no-spend/local-first compatible or not).
3. Integration complexity (low/medium/high).
4. Security and abuse risk.
5. Time-to-value (quick win vs long R&D).
6. Maintainability (will this break often with upstream API changes?).

## 8. CLI Coverage

For complete CLI commands and flags:
- see `docs/cli_reference.md`
- or run: `python cli.py -h`

For app shell:
- `python cli.py foundation-api`
- open: `http://127.0.0.1:8797/app/ophtxn`
