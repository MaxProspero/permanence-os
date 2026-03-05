# PERMANENCE OS

> A governed personal intelligence system that compounds judgment without losing agency, authenticity, or coherence over time.

## ✅ Current State (2026-02-03)
- OpenClaw connected; status/health captured into `outputs/` + `memory/tool/`
- Governed pipeline wired (Polemarch → Planner → Researcher → Executor → Reviewer → Compliance Gate)
- HR Agent active with system health reporting + tool degradation awareness
- Episodic memory logging in both per-task JSON and daily JSONL
- Automations scheduled for daily briefing/dashboard and weekly HR/cleanup

## 🎯 What Is This?

This is **not** a typical AI agent system.

This is a structured intelligence governance framework designed to:
- Convert complexity into actionable principles
- Maintain human authority at all times
- Compound learning without losing coherence
- Survive variance (work at 2 AM, not just peak states)
- Fail cleanly and learn from failures

## 🏗️ Architecture

```
Layer 0: Human Authority (Dax / Payton) ─────────── Final Authority
         │
Layer 1: Base Canon ─────────────── Constitutional Law
         │
Layer 2: Polemarch ──────────────── Governor & Router
         │
Layer 2.5: System Services ─────── Compliance Gate, HR Agent, Briefing Agent
         │
Layer 3: Executive Bots ─────────── Strategy Translation
         │
Layer 4: Department Bots ────────── Specialized Work
         │
Layer 5: Audit Loop ─────────────── Evolution & Learning
```

## ⚔️ The Polemarch

**King Bot** is formally known as **The Polemarch** (Greek: πολέμαρχος - "war leader").

This isn't metaphorical. The Polemarch operates like a military commander:

- **Receives orders** (task goals)
- **Consults doctrine** (Canon)
- **Assesses terrain** (complexity, risk)
- **Assigns forces** (routes to agents)
- **Enforces discipline** (budgets, constraints)
- **Calls for reinforcements** (escalates to human)
- **Records engagements** (logs every decision)

Core principle: *"Discipline under fire, clarity under fog, structure under chaos."*

Implementation note: the Polemarch code lives in `agents/king_bot.py` for backward compatibility.

## 🪪 Identity Protocol

The system supports dual identities:
- **Kael Dax** (internal / system use)
- **Payton Hicks** (public / legal use)

Routing rules are defined in `identity_config.yaml`. Agents use internal identity for logs and
escalations, and public identity for outward-facing or binding actions.

## 📁 Directory Structure

```
permanence-os/
├── canon/              # Constitutional law (YAML)
│   └── base_canon.yaml
├── agents/             # Agent implementations
│   ├── king_bot.py
│   ├── planner.py
│   ├── researcher.py
│   ├── executor.py
│   └── reviewer.py
│   ├── conciliator.py
│   ├── compliance_gate.py
│   └── departments/
│       ├── email_agent.py
│       ├── device_agent.py
│       ├── social_agent.py
│       ├── health_agent.py
│       ├── briefing_agent.py
│       ├── trainer_agent.py
│       └── therapist_agent.py
├── identity_config.yaml
├── run_task.py
├── scripts/
├── memory/             # Persistent storage
│   ├── episodic/       # Task logs
│   ├── working/        # Temporary scratchpad
│   └── tool/           # Raw tool outputs
├── logs/               # Append-only system logs
├── tests/              # Test suites
└── outputs/            # Final deliverables
```

## 🚀 Quick Start

### 1. Initialize
```bash
git clone <your-repo>
cd permanence-os
pip install -r requirements.txt
```

### 2. Configure
```bash
cp .env.example .env
# Add your API keys to .env
```

Optional: set path overrides in `.env` if you need custom locations.

### 3. Run
```bash
python agents/king_bot.py
```

### 4. Governed Task Runner
```bash
python run_task.py "Your task goal"
python run_task.py "Your task goal" --sources /path/to/sources.json --draft /path/to/draft.md
python run_task.py "Your task goal" --allow-single-source
```

When OpenClaw is installed locally, the runner captures OpenClaw status + health
before execution (stored in `outputs/` and `memory/tool/`).

This runner expects a provenance list at `memory/working/sources.json` with:
- At least two distinct sources by default (override with `--allow-single-source`)

- `source`
- `timestamp`
- `confidence`

Example format: `docs/sources_example.json`

Helper to build sources:
```bash
python scripts/new_sources.py "source-name" 0.7 "optional notes"
```

Ingest tool outputs into sources.json:
```bash
python scripts/ingest_tool_outputs.py --tool-dir memory/tool --output memory/working/sources.json
```

Ingest local documents into sources.json:
```bash
python scripts/ingest_documents.py --doc-dir memory/working/documents --output memory/working/sources.json
```

Optional draft input:
- Place a markdown draft at `memory/working/draft.md` to have the Executor package it.

Cleanup helper:
```bash
python scripts/clean_artifacts.py --all
```

Status helper:
```bash
python scripts/status.py
```

### Unified CLI
```bash
python cli.py run "Your task goal"
python cli.py run "Your task goal" --allow-single-source
python cli.py add-source "source-name" 0.7 "optional notes"
python cli.py ingest --tool-dir memory/tool --output memory/working/sources.json
python cli.py ingest-docs --doc-dir memory/working/documents --output memory/working/sources.json
python cli.py ingest-sources --adapter tool_memory --output memory/working/sources.json
python cli.py ingest-sources --adapter url_fetch --urls https://example.com --output memory/working/sources.json
python cli.py ingest-sources --adapter web_search --query "AI governance frameworks" --output memory/working/sources.json
python cli.py server --host 127.0.0.1 --port 8000
python cli.py scrimmage --last-hours 24 --replays 10
python cli.py looking-glass "Test scenario"
python cli.py hyper-sim --iterations 1000 --warp-speed
python cli.py arcana scan --last 50
python cli.py status
python cli.py openclaw-status
python cli.py openclaw-status --health
python cli.py openclaw-sync --once
python cli.py clean --all
python cli.py test
python cli.py queue list
python cli.py hr-report
python cli.py briefing
python cli.py automation-report --days 1
python cli.py reliability-watch --arm --days 7 --check-interval-minutes 30
python cli.py reliability-watch --status
python cli.py reliability-watch --disarm
python cli.py reliability-gate --days 7
python cli.py reliability-streak
python cli.py phase-gate --days 7
python cli.py status-glance
python cli.py dell-cutover-verify
python cli.py ari-reception --action summary
python cli.py sandra-reception --action summary
python cli.py remote-ready
python cli.py ari-reception --action intake --sender "Payton" --message "Need review of weekly phase gate" --channel discord
python cli.py glasses-bridge --action ingest --from-json ~/Downloads/nearby_glasses_detected_123.json
python cli.py glasses-bridge --action intake --source visionclaw --channel telegram --text "What am I looking at?" --media ~/Downloads/pov.jpg
python cli.py telegram-control --action status
python cli.py telegram-control --action poll --ack
python cli.py telegram-control --action poll --enable-commands --ack --max-commands 3
python cli.py telegram-control --action poll --chat-agent --max-chat-replies 3
python cli.py ophtxn-simulation --seed 11 --memory-trials 300 --habit-days 90
python cli.py ophtxn-completion
python cli.py ophtxn-completion --target 95 --strict
python cli.py ophtxn-ops-pack --action status
python cli.py ophtxn-ops-pack --strict --approval-source phase3_opportunity_queue --approval-decision defer --approval-batch-size 3 --safe-max-priority low --safe-max-risk medium
python cli.py idea-intake --action status
python cli.py idea-intake --action intake --text "Cloudflare MCP https://github.com/cloudflare/mcp and Symphony https://github.com/openai/symphony"
python cli.py idea-intake --action process --max-items 30 --min-score 30
python cli.py idea-intake --action process --queue-approvals --queue-limit 5 --queue-min-score 65
bash automation/setup_completion_automation.sh /Users/paytonhicks/Code/permanence-os 21600
bash automation/disable_completion_automation.sh /Users/paytonhicks/Code/permanence-os
python cli.py telegram-control --action poll --voice-priority high --voice-channel telegram-voice
python cli.py telegram-control --action poll --voice-transcribe-queue ~/permanence-os/memory/working/transcription_queue.json
python cli.py glasses-autopilot --action run
python cli.py discord-feed-manager --action list
python cli.py discord-feed-manager --action add --name "Permanence" --channel-link https://discord.com/channels/<guild_id>/<channel_id>
python cli.py discord-feed-manager --action add --channel-id <channel_id> --priority urgent
python cli.py discord-feed-manager --action add --channel-id <channel_id> --include-keyword gold --include-keyword xauusd --exclude-keyword spam --min-chars 15
python cli.py discord-telegram-relay --action status
python cli.py discord-telegram-relay --action run
python cli.py discord-telegram-relay --action run --intake-path /Users/paytonhicks/Code/permanence-os/memory/inbox/telegram_share_intake.jsonl
python cli.py discord-telegram-relay --action run --escalate --escalation-keyword outage --escalation-min-priority high
python cli.py discord-telegram-relay --action run --escalation-notify --escalation-telegram-min-priority high --escalation-discord-min-priority urgent
python cli.py comms-digest --send
python cli.py comms-escalation-digest --send
python cli.py comms-status
python cli.py comms-status --require-escalation-digest --escalation-warn-count 10 --voice-queue-warn-count 20
python cli.py comms-doctor --allow-warnings
python cli.py comms-doctor --require-escalation-digest --allow-warnings
python cli.py comms-doctor --check-live --auto-repair --allow-warnings
python cli.py comms-automation --action status
python cli.py comms-automation --action digest-now
python cli.py comms-automation --action escalation-status
python cli.py comms-automation --action escalation-enable
python cli.py comms-automation --action escalation-digest-now
python cli.py comms-automation --action doctor-status
python cli.py comms-loop
python cli.py email-triage
python cli.py gmail-ingest
python cli.py health-summary
python cli.py social-summary
python cli.py logos-gate
python cli.py dashboard
python cli.py command-center
python cli.py command-center --run-horizon --demo-horizon
python cli.py money-loop
python cli.py revenue-action-queue
python cli.py revenue-architecture
python cli.py revenue-execution-board
python cli.py revenue-weekly-summary
python cli.py sales-pipeline list --open-only
python cli.py foundation-site
python cli.py snapshot
python cli.py v04-snapshot
python cli.py cleanup-weekly
python cli.py git-autocommit
python cli.py git-autocommit --push
python cli.py git-sync
python cli.py chronicle-backfill
python cli.py chronicle-capture --note "session summary"
python cli.py chronicle-report --days 365
python cli.py chronicle-publish --docx
```

Automation writes a one-line quick status file to storage logs:
- `status_today.txt`

One-click desktop launcher:
- `/Users/paytonhicks/Desktop/Start_Permanence_Command_Center.command`
- `/Users/paytonhicks/Desktop/Run_Permanence_Money_Loop.command`
- `status_today.json`

Ari receptionist can run in automation mode:
- set `PERMANENCE_ARI_ENABLED=1`
- set `PERMANENCE_ARI_SLOT=19` (or `all`)

Custom receptionist name/command can run in automation mode:
- set `PERMANENCE_RECEPTIONIST_NAME=Sandra`
- set `PERMANENCE_RECEPTIONIST_ENABLED=1`
- set `PERMANENCE_RECEPTIONIST_SLOT=19` (or `all`)
- optional command override: `PERMANENCE_RECEPTIONIST_COMMAND=sandra-reception` (defaults to `ari-reception`)

Reliability watch can run in background for a fixed 7-day window:
- `python cli.py reliability-watch --arm --days 7`
- `python cli.py reliability-watch --status`
- `python cli.py reliability-watch --disarm`
- helper scripts: `bash automation/setup_reliability_watch.sh` and `bash automation/disable_reliability_watch.sh`

Chronicle auto-publish in automation runs:
- `automation/run_briefing.sh` now runs `chronicle-capture`, `chronicle-report`, and `chronicle-publish` when `PERMANENCE_CHRONICLE_AUTOPUBLISH=1` (default).
- Optional env vars: `PERMANENCE_CHRONICLE_DAYS` and `PERMANENCE_CHRONICLE_DRIVE_DIR`.
- If Drive mirror copy is blocked by macOS permissions in launchd context, automation retries local-only Chronicle publish.

Promotion daily automation in briefing runs:
- `automation/run_briefing.sh` runs `python cli.py promotion-daily` at slot `19` by default.
- Optional env vars:
  - `PERMANENCE_PROMOTION_DAILY_ENABLED=1|0`
  - `PERMANENCE_PROMOTION_DAILY_SLOT=19|all`
  - `PERMANENCE_PROMOTION_DAILY_STRICT=0|1`
  - `PERMANENCE_PROMOTION_DAILY_SINCE_HOURS=24`
  - `PERMANENCE_PROMOTION_DAILY_MAX_ADD=5`
  - `PERMANENCE_PROMOTION_DAILY_PHASE_POLICY=auto|always|never`
  - `PERMANENCE_PROMOTION_DAILY_PHASE_ENFORCE_HOUR=19`

### OpenClaw Integration (Local)
Set the OpenClaw CLI path (if not default):
```bash
export OPENCLAW_CLI="$HOME/.openclaw/bin/openclaw"
```

Capture OpenClaw gateway status for audit logs:
```bash
python scripts/openclaw_status.py
python scripts/openclaw_status.py --health
```
OpenClaw health sync (degradation detection):
```bash
python scripts/openclaw_health_sync.py --once
python cli.py openclaw-sync --once
```

Briefing Agent includes the most recent OpenClaw status file in its notes when present.

### Evaluation Harness
```bash
python scripts/eval_harness.py
# Optional: override report path
PERMANENCE_EVAL_OUTPUT=/tmp/eval_report.json python scripts/eval_harness.py
```

### HR Report
```bash
python scripts/hr_report.py
python cli.py hr-report
```
HR reports include the latest OpenClaw status file when present.

### Briefing Agent
```bash
python scripts/briefing_run.py
python cli.py briefing
```
Briefing outputs include the most recent OpenClaw status excerpt when present.

### Email Triage
Store email JSON/JSONL in `memory/working/email/` and run:
```bash
python scripts/email_triage.py
python cli.py email-triage
```

### Gmail Ingest (Read-only)
1) Create OAuth credentials in Google Cloud (Gmail API enabled).
2) Save credentials to `memory/working/google/credentials.json`.
3) Run once interactively to generate token:
```bash
python cli.py gmail-ingest --max 50
```
This creates `memory/working/google/token.json` for future non-interactive runs.

### Money Loop (Revenue Ops)
Run one command to refresh inbox intelligence and generate:
- email triage
- social summary
- revenue action queue
- revenue architecture scorecard
- revenue cost-recovery plan (API/tool spend coverage)
- revenue execution board
- revenue outreach message pack

```bash
python cli.py money-loop
python cli.py revenue-action-queue
python cli.py revenue-cost-recovery
python cli.py revenue-execution-board
python cli.py revenue-outreach-pack
python cli.py revenue-followup-queue
python cli.py revenue-eval
python cli.py revenue-playbook show
python cli.py revenue-playbook set --offer-name "Permanence OS Foundation Setup" --cta-keyword FOUNDATION --cta-public 'DM me "FOUNDATION".' --booking-link "https://cal.com/..." --payment-link "https://buy.stripe.com/..." --pricing-tier Core --price-usd 1500
python cli.py revenue-targets show
python cli.py revenue-targets set --weekly-revenue-target 5000 --monthly-revenue-target 20000 --daily-outreach-target 12
python cli.py integration-readiness
python cli.py external-access-policy
python cli.py revenue-backup
```
`revenue-action-queue` now prioritizes from live pipeline/intake/funnel signals first (urgent leads + bottleneck), then fills remaining slots with template actions.
Desktop launcher:
- `/Users/paytonhicks/Desktop/Run_Permanence_Money_Loop.command`

Optional env vars:
- `PERMANENCE_MONEY_LOOP_GMAIL_INGEST=1|0`
- `PERMANENCE_MONEY_LOOP_GMAIL_MAX=100`
- `PERMANENCE_MONEY_LOOP_GMAIL_QUERY="newer_than:14d -category:social -category:promotions"`
- `PERMANENCE_MONEY_LOOP_TRIAGE_MAX_ITEMS=40`
- `PERMANENCE_GMAIL_CREDENTIALS=~/.../credentials.json` (if not using default path)
- `PERMANENCE_GMAIL_TOKEN=~/.../token.json` (required for non-interactive automation)

### External Connector Safety (GitHub + Social)
Generate and review the staged-access policy before granting agent connectors:
```bash
python cli.py anthropic-keychain --status
python cli.py external-access-policy
python cli.py external-access-policy --strict
```
Creates:
- `memory/working/agent_access_policy.json`
- `outputs/external_access_policy_latest.md`

Recommended rollout:
- phase 1: read-only research connectors
- phase 2: supervised write with manual approvals
- phase 3: limited autopilot only for pre-approved low-risk actions

Optional env vars for read-only research:
- `PERMANENCE_GITHUB_READ_TOKEN=...`
- `PERMANENCE_SOCIAL_READ_TOKEN=...`
- `PERMANENCE_SOCIAL_KEYWORDS=ai,agent,automation,saas,growth,monetize`
- `PERMANENCE_X_RECENT_SEARCH_URL=https://api.twitter.com/2/tweets/search/recent` (override only if needed)
- `PERMANENCE_X_MAX_RESULTS=25`
- `PERMANENCE_AGENT_EXTERNAL_WRITE_ENABLE=0`
- `PERMANENCE_REQUIRE_REVENUE_LINKS=0` (set to `1` only when you want booking/payment links enforced as required)

Anthropic keychain workflow (recommended):
```bash
python cli.py anthropic-keychain --from-file /absolute/path/to/anthropic_key.txt --remove-source
python cli.py anthropic-keychain --status
```
This keeps `ANTHROPIC_API_KEY=` blank in `.env` and loads the key from macOS Keychain at runtime.

Connector keychain workflow (recommended):
```bash
python cli.py connector-keychain --target openai-api-key --from-file /absolute/path/to/openai_api_key.txt --remove-source
python cli.py connector-keychain --target github-read --from-file /absolute/path/to/github_read_token.txt --remove-source
python cli.py connector-keychain --target social-read --from-file /absolute/path/to/social_read_token.txt --remove-source
python cli.py connector-keychain --target xai-api-key --from-file /absolute/path/to/xai_api_key.txt --remove-source
python cli.py connector-keychain --target openai-api-key --status
python cli.py connector-keychain --target github-read --status
python cli.py connector-keychain --target social-read --status
python cli.py connector-keychain --target xai-api-key --status
```
This keeps `OPENAI_API_KEY=`, `PERMANENCE_GITHUB_READ_TOKEN=`, `PERMANENCE_SOCIAL_READ_TOKEN=`, and `XAI_API_KEY=` blank in `.env` and loads them from Keychain at runtime.

Model provider routing defaults to Anthropic, with optional local Ollama + OpenAI/xAI fallback:
```bash
export PERMANENCE_MODEL_PROVIDER=anthropic
export PERMANENCE_MODEL_PROVIDER_FALLBACKS=anthropic,ollama,openai,xai
export PERMANENCE_MODEL_PROVIDER_CAPS_USD=anthropic=35,openai=10,xai=5,ollama=0
# optional explicit tier overrides
export PERMANENCE_MODEL_OPUS=claude-opus-4-6
export PERMANENCE_MODEL_SONNET=claude-sonnet-4-6
export PERMANENCE_MODEL_HAIKU=claude-haiku-4-5-20251001
# optional local provider defaults (Ollama)
export PERMANENCE_OLLAMA_BASE_URL=http://127.0.0.1:11434
export PERMANENCE_OLLAMA_MODEL_OPUS=qwen3:8b
export PERMANENCE_OLLAMA_MODEL_SONNET=qwen3:4b
export PERMANENCE_OLLAMA_MODEL_HAIKU=qwen2.5:3b
```

Secret leak guard (recommended before every push):
```bash
python cli.py secret-scan
bash automation/setup_secret_scan_hook.sh
```
This installs a pre-push hook that blocks pushes when likely secrets are detected.

### Second Brain Loop (Life + Business + Income Streams)
Run one command to refresh your personal operating layer plus supervised side-income modules:
```bash
python cli.py second-brain-init
python cli.py second-brain-loop
python cli.py life-os-brief
python cli.py github-research-ingest
python cli.py social-research-ingest
python cli.py side-business-portfolio
python cli.py prediction-ingest
python cli.py prediction-lab
python cli.py clipping-transcript-ingest
python cli.py clipping-pipeline
python cli.py revenue-cost-recovery
python cli.py second-brain-report
```
Outputs:
- `outputs/life_os_brief_latest.md`
- `outputs/github_research_ingest_latest.md`
- `outputs/social_research_ingest_latest.md`
- `outputs/side_business_portfolio_latest.md`
- `outputs/prediction_ingest_latest.md`
- `outputs/prediction_lab_latest.md`
- `outputs/clipping_transcript_ingest_latest.md`
- `outputs/clipping_pipeline_latest.md`
- `outputs/revenue_cost_recovery_latest.md`
- `outputs/second_brain_report_latest.md`

Working files to edit:
- `memory/working/github_research_targets.json` (repos to monitor read-only)
- `memory/working/social_research_feeds.json` (RSS and optional X query feeds to rank)
- `memory/working/social_discernment_policy.json` (what the social agent keeps vs filters out)
- `memory/working/prediction_news_feeds.json` (feed list for signal ingest)
- `memory/working/clipping_transcripts/` (drop transcript files here for auto ingest)
- `memory/working/api_cost_plan.json` (monthly API/tool budget + payback assumptions)

Example X feed row (`social_research_feeds.json`):
```json
{
  "name": "X Agents/Automation",
  "platform": "x",
  "query": "(ai OR agent OR automation OR saas) -is:retweet lang:en",
  "max_results": 25
}
```

Governance model:
- prediction and trading logic is advisory only
- publishing/trading actions remain manual approval
- no autonomous broker/exchange execution in this stack

### Revenue Architecture v1 (Pipeline + KPI Scorecard)
Generate report:
```bash
python cli.py revenue-architecture
```
Manage sales pipeline:
```bash
python cli.py sales-pipeline init
python cli.py sales-pipeline add --name "Lead Name" --source "X DM" --est-value 1500 --next-action "Book fit call" --next-action-due 2026-02-26
python cli.py sales-pipeline list --open-only
python cli.py sales-pipeline update --lead-id L-YYYYMMDD-HHMMSS --stage call_scheduled --next-action "Run discovery call" --next-action-due 2026-02-27
python cli.py sales-pipeline close --lead-id L-YYYYMMDD-HHMMSS --result won --actual-value 1500
```
Files created/used:
- `memory/working/revenue_targets.json`
- `memory/working/revenue_streams.json`
- `memory/working/sales_pipeline.json`
- `memory/working/revenue_playbook.json`
- `outputs/revenue_architecture_latest.md`
- `outputs/revenue_execution_board_latest.md`
- `outputs/revenue_outreach_pack_latest.md`

Revenue data is also visible in Command Center under **Revenue Ops**.
- Revenue Ops now includes a live conversion funnel and automatic bottleneck detection (Intake -> Lead -> Qualified -> Call -> Proposal -> Won).
- Revenue Ops queue actions can now be marked done/undone in-dashboard with completion-rate tracking.
- Revenue Ops includes one-click loop controls in-dashboard: **Run Money Loop Now** and **Refresh Queue + Board**.
- Revenue Ops now displays the latest Outreach Draft Pack inside the dashboard.
- Outreach drafts now support status tracking in-dashboard (pending/sent/replied) plus one-click copy for subject/body.
- Revenue Ops now includes editable Revenue Targets lock (weekly/monthly revenue, funnel targets, outreach target) with live progress percentages.
- Revenue Ops now includes follow-up queue rendering, deal-event logging (proposal/invoice/payment), site funnel telemetry, and a revenue eval status panel.

### Revenue Weekly Summary
Generate the weekly operator scorecard:
```bash
python cli.py revenue-weekly-summary
```
Outputs:
- `outputs/revenue_weekly_summary_latest.md`
- `memory/tool/revenue_weekly_summary_*.json`

### FOUNDATION Landing Page (Local Preview)
Serve the local offer page:
```bash
python cli.py foundation-site
python cli.py foundation-api
```
Then open: `http://127.0.0.1:8787/`
- FOUNDATION API default: `http://127.0.0.1:8797/`
- If Command Center API is running on `http://127.0.0.1:8000`, intake submissions are captured automatically to:
  - `memory/working/revenue_intake.jsonl`
  - `memory/working/sales_pipeline.json` (new lead created)
- If API is unreachable, the page falls back to `mailto:` intake.

### Operator Surface (Dashboard + Offer Site)
Run both operator-facing surfaces together in one command:
```bash
python cli.py operator-surface --money-loop
```
This starts:
- Command Center API/UI at `http://127.0.0.1:8000`
- FOUNDATION site at `http://127.0.0.1:8787/`

Helper launcher script:
- `scripts/launch_operator_surface.sh`

Create Desktop click-launch files:
```bash
python cli.py setup-launchers --force
```
Creates:
- `~/Desktop/Run_Permanence_Operator_Surface.command`
- `~/Desktop/Run_Permanence_Command_Center.command`
- `~/Desktop/Run_Permanence_Foundation_Site.command`
- `~/Desktop/Run_Permanence_Money_Loop.command`
- `~/Desktop/Run_Permanence_Comms_Loop.command`
- `~/Desktop/Run_Permanence_Comms_Status.command`
- `~/Desktop/Run_Permanence_Discord_Relay.command`
- `~/Desktop/Run_Permanence_Comms_Digest.command`
- `~/Desktop/Run_Permanence_Comms_Doctor.command`
- `~/Desktop/Run_Permanence_Comms_Escalation_Digest.command`
- `~/Desktop/Run_Permanence_Comms_Escalation_Status.command`

### Money Loop Automation Schedule
Schedule money loop at 07:15, 12:15, 19:15 local time:
```bash
bash automation/setup_money_loop_automation.sh
```
Disable schedule:
```bash
bash automation/disable_money_loop_automation.sh
```

### Comms Loop Automation Schedule
Run cross-platform communication sync every 5 minutes (Telegram poll, Discord relay, glasses/autopilot, inbox process):
```bash
bash automation/setup_comms_loop_automation.sh
```
Disable schedule:
```bash
bash automation/disable_comms_loop_automation.sh
```
CLI alternative:
```bash
python cli.py comms-automation --action enable
python cli.py comms-automation --action status
python cli.py comms-automation --action run-now
python cli.py comms-automation --action disable
```
Optional stricter status snapshot inside loop:
- leave `PERMANENCE_COMMS_LOOP_COMMS_STATUS_ENABLED=1`
- tune thresholds with:
  - `PERMANENCE_COMMS_LOOP_COMMS_STATUS_ESCALATION_WARN_COUNT` (default `6`)
  - `PERMANENCE_COMMS_LOOP_COMMS_STATUS_VOICE_QUEUE_WARN_COUNT` (default `12`)
  - `PERMANENCE_COMMS_LOOP_COMMS_STATUS_ESCALATION_DIGEST_STALE_MINUTES` (default `720`)
  - `PERMANENCE_COMMS_LOOP_COMMS_STATUS_REQUIRE_ESCALATION_DIGEST=1` if you want missing escalation digest to warn

### Comms Digest Automation Schedule
Send daily Telegram comms digest at 21:05 local time:
```bash
bash automation/setup_comms_digest_automation.sh
```
Disable schedule:
```bash
bash automation/disable_comms_digest_automation.sh
```
CLI alternative:
```bash
python cli.py comms-automation --action digest-enable
python cli.py comms-automation --action digest-status
python cli.py comms-automation --action digest-now
python cli.py comms-automation --action digest-disable
```

### Comms Escalation Digest Automation Schedule
Run escalation digest every 4 hours:
```bash
bash automation/setup_comms_escalation_digest_automation.sh
```
Disable schedule:
```bash
bash automation/disable_comms_escalation_digest_automation.sh
```
CLI alternative:
```bash
python cli.py comms-automation --action escalation-enable
python cli.py comms-automation --action escalation-status
python cli.py comms-automation --action escalation-digest-now
python cli.py comms-automation --action escalation-disable
```

### Comms Doctor Automation Schedule
Run comms health doctor every 30 minutes (secrets/feed/automation/freshness checks):
```bash
bash automation/setup_comms_doctor_automation.sh
```
Disable schedule:
```bash
bash automation/disable_comms_doctor_automation.sh
```
CLI alternative:
```bash
python cli.py comms-automation --action doctor-enable
python cli.py comms-automation --action doctor-status
python cli.py comms-automation --action doctor-now
python cli.py comms-automation --action doctor-disable
```

### Second Brain Automation Schedule
Schedule second-brain loop at 06:40, 13:40, 20:40 local time:
```bash
bash automation/setup_second_brain_automation.sh
```
Disable schedule:
```bash
bash automation/disable_second_brain_automation.sh
```

### Revenue Ops Automation + Services
Schedule nightly revenue maintenance (integration readiness, revenue eval, weekly summary, backup):
```bash
bash automation/setup_revenue_ops_automation.sh
```
Disable:
```bash
bash automation/disable_revenue_ops_automation.sh
```
Run operator surface as an always-on service (launchd/@reboot):
```bash
bash automation/setup_operator_surface_service.sh
```
Disable:
```bash
bash automation/disable_operator_surface_service.sh
```

### Health Summary
Store health JSON/JSONL in `memory/working/health/` and run:
```bash
python scripts/health_summary.py
python cli.py health-summary
```

### Social Drafts
Store social drafts in `memory/working/social/` and run:
```bash
python scripts/social_summary.py
python cli.py social-summary
```

### CLI Reference
See `docs/cli_reference.md` for a full command list.
See `docs/ophtxn_operator_command_guide.md` for the Telegram command map + daily/weekly operating cadence.
See `docs/ophtxn_official_launch_path_20260305.md` for the official product launch sequencing.
See `docs/ophtxn_fastlane_execution_20260305.md` for the 72-hour acceleration plan (revenue + education product lane).
See `docs/ophtxn_production_deployment_runbook_20260305.md` for production deployment + no-spend rollout sequence.
Use `python cli.py ophtxn-launchpad --action status --strict --min-score 80` for launch-readiness scoring.
Use `python cli.py ophtxn-production --action preflight --check-wrangler` for deploy-environment readiness.
Use `python cli.py ophtxn-production --action status --check-api --check-wrangler` for production configuration readiness.
See `docs/ophtxn_external_idea_backlog_20260305.md` for queued external ideas and integration review status.

### Roadmap
Phase 2 build priorities are in `docs/roadmap_phase2.md`.

### Governance
Code ownership is defined in `CODEOWNERS`.

### Dashboard Report
```bash
python scripts/dashboard_report.py
python cli.py dashboard
```

### System Snapshot
```bash
python scripts/system_snapshot.py
python cli.py snapshot
python scripts/v04_snapshot.py
python cli.py v04-snapshot
```

### Weekly Cleanup + Auto-Commit
```bash
python scripts/cleanup_weekly.py
python scripts/git_autocommit.py
python scripts/git_autocommit.py --push
python cli.py cleanup-weekly
python cli.py git-autocommit
python cli.py git-autocommit --push
python cli.py git-sync
```
`git-autocommit` and `git-sync` now append a chronicle event when they create and/or push a commit.

### Chronicle (History + Book References)
Generate timestamped history reports from local artifacts and keep ongoing session logs:
```bash
python scripts/chronicle_backfill.py
python scripts/chronicle_capture.py --note "what changed today"
python scripts/chronicle_report.py --days 365
python scripts/chronicle_publish.py --docx
python cli.py chronicle-backfill
python cli.py chronicle-capture --note "what changed today"
python cli.py chronicle-report --days 365
python cli.py chronicle-publish --docx
```

Outputs:
- `outputs/chronicle/chronicle_backfill_*.md` and `.json`
- `outputs/chronicle/chronicle_report_*.md` and `.json`
- `memory/chronicle/events.jsonl`
- `memory/chronicle/shared/chronicle_latest.json`
- `memory/chronicle/shared/chronicle_latest.md`
- `memory/chronicle/shared/chronicle_latest_summary.md`
- `memory/chronicle/shared/chronicle_latest_manifest.json`

Note: private chat platforms (ChatGPT/Claude/Gemini/Grok) are only ingested when their exports are saved locally and provided as files.
Recommended drop zone for chat exports:
- `memory/chronicle/chat_exports/`

Google Drive/iPad visibility:
- Use `python cli.py chronicle-publish --drive-dir "/path/to/Google Drive/folder"` to mirror shareable files into a synced Drive folder.

Email delivery:
- `chronicle-publish` supports SMTP flags (`--email-to`, `--smtp-host`, `--smtp-user`, `--smtp-password`, `--smtp-from`) for sending the latest summary/report attachments.

### Away Mode (iPad / Remote)
Use one command to verify if the Mac is ready for remote operation:
```bash
python cli.py remote-ready
python cli.py remote-ready --json-output outputs/remote_ready.json
```

One-time setup if `remote-ready` reports SSH as OFF:
- macOS: `System Settings > General > Sharing > Remote Login` -> ON
- keep Tailscale running
- keep `caffeinate` running when away for long sessions

### Canon Change Draft (Memory Promotion)
```bash
python scripts/promote_memory.py --count 5
python cli.py promote --count 5
```

Promotion drafts include `docs/promotion_rubric.md` by default (override with `PERMANENCE_PROMOTION_RUBRIC`).

### Promotion Queue (Optional)
```bash
python cli.py queue list
python cli.py queue add --latest --reason "pattern repeat"
python cli.py queue auto --dry-run
python cli.py queue auto --since-hours 24 --max-add 5
python cli.py promotion-daily
python cli.py queue clear
python cli.py promotion-review --output outputs/promotion_review.md
```

### 5. Tests
```bash
python tests/test_polemarch.py
python tests/test_agents.py
python tests/test_compliance_gate.py
python tests/test_researcher_ingest.py
python tests/test_researcher_documents.py
python tests/test_memory_promotion.py
python tests/test_promotion_queue.py
python tests/test_promotion_queue_auto.py
python tests/test_promotion_daily.py
python tests/test_promotion_review.py
python tests/test_hr_agent.py
```

## 🎛️ Core Principles

### The Constitution
1. **Bots are roles, not beings** - Replaceable workers with bounded authority
2. **No autonomy without audit** - Every action is loggable and reviewable
3. **No memory without provenance** - Source, timestamp, confidence required
4. **Governance lives in structure** - Authority in state machines, not prompts
5. **Human authority is final** - System escalates, never overrides

### The Three Compression Layers

**Layer 1: Signal Compression** - Filter inputs before they compete for attention
**Layer 2: Decision Compression** - Convert repeated choices into automated rules
**Layer 3: Identity Compression** - Establish consistent behavior independent of mood

### The 2 AM Test

**The ultimate filter:** Will this work when willpower is depleted?

Systems must function at worst state, not peak state.

## 📊 Risk Tiers

| Tier | Characteristics | Handling |
|------|----------------|----------|
| **LOW** | Reversible, informational, no side effects | Auto-execute with review |
| **MEDIUM** | Strategic, resource-consuming, ambiguous | Reviewer approval required |
| **HIGH** | Irreversible, financial/legal/reputational impact | Human approval required |

## 🔧 Agent Roles

### Polemarch (Governor)
- Validates against Canon
- Assigns risk tiers
- Enforces budgets
- Routes execution
- Escalates when needed
- **NEVER** creates content or reasons about truth

### Planner Agent
- Converts goals to structured specs
- Defines success criteria
- Estimates resource needs
- **CANNOT** execute plans or gather data

### Researcher Agent
- Gathers verified information
- Cites all sources
- Assigns confidence levels
- **CANNOT** speculate beyond sources

### Executor Agent
- Produces outputs per spec
- Tracks resource consumption
- **CANNOT** improvise scope changes

### Reviewer Agent
- Evaluates against rubrics
- Provides specific feedback
- **CANNOT** generate content or modify outputs


### HR Agent (The Shepherd)
- Monitors system health and agent relations
- Generates weekly System Health reports
- Surfaces patterns and recommendations
- **CANNOT** override or block execution

### Compliance Gate
- Reviews outbound actions for legal/ethical/identity compliance
- Verdicts: APPROVE | HOLD | REJECT
- Sits after Reviewer for external actions

## 📈 Success Metrics

- Canon fidelity (value alignment)
- Factual accuracy (source-backed claims)
- Tool discipline (budget adherence)
- Hallucination rate (unsupported assertions)
- Escalation correctness (appropriate human involvement)

## 🔄 Version Control

**Current Version:** 0.1.0
**Status:** Foundation Phase

All Canon changes require:
1. Written rationale
2. Impact analysis
3. Rollback plan
4. Version bump
5. Human approval
6. Changelog entry

**No silent updates. Ever.**

## 🚨 Failure Modes

The system is designed to fail cleanly:
- Budget violations → immediate halt
- Canon conflicts → escalation
- Source failures → refusal with explanation
- Quality degradation → reviewer blocks output

**Failures are logged, analyzed, and integrated into Canon.**

## 📚 Documentation

- `/canon/base_canon.yaml` - System constitution
- `/docs/architecture.md` - Detailed system design
- `/docs/agent_specs.md` - Individual agent specifications
- `/docs/memory_system.md` - Memory architecture
- `/docs/compression_framework.md` - Theoretical foundation
- `/docs/canon_change_template.md` - Canon update ceremony template
- `/docs/dell_cutover.md` - Linux (Dell) automation migration runbook
- `/docs/dell_cutover_powershell.md` - PowerShell + WSL Dell cutover workflow
- `/CHANGELOG.md` - Project change history
- `/docs/sources_example.json` - Sources provenance example
- `/identity_config.yaml` - Identity routing configuration

## 🤝 Contributing

This is a personal system, but the architecture is designed to be:
- **Observable** - All decisions logged
- **Auditable** - State machine driven
- **Forkable** - Adapt the Canon for your needs
- **Learnable** - Failure archive is public

## 📄 License

MIT License - See LICENSE file

## ⚠️ Critical Reminders

1. Intelligence is cheap. **Governance is rare.**
2. You don't rise to aspirations. **You fall to defaults.**
3. Agents are tools, not identities.
4. If it's not in the graph, **it cannot happen.**
5. Memory must never outrank law: **Canon > Episodic > Working**
6. Refusal is a valid output.
7. **Logs are not optional.**
8. Coherence > Intensity
9. The map is not the terrain.
10. **Compression over accumulation.**

---

*"This is how legendary systems are built. Not through cleverness, but through structure. Not through autonomy, but through constraint. Not through speed, but through compounding."*

**Permanence OS v0.1.0**
February 2026
Telegram command control notes:
- enable command mode with `PERMANENCE_TELEGRAM_CONTROL_ENABLE_COMMANDS=1`
- recommended limits: `PERMANENCE_TELEGRAM_CONTROL_MAX_COMMANDS=3`, `PERMANENCE_TELEGRAM_CONTROL_COMMAND_TIMEOUT=90`
- per-command ack on/off: `PERMANENCE_TELEGRAM_CONTROL_COMMAND_ACK=1|0`
- command prefix: `PERMANENCE_TELEGRAM_CONTROL_COMMAND_PREFIX=/`
- chat-agent mode:
  - enable with `PERMANENCE_TELEGRAM_CONTROL_CHAT_AGENT_ENABLED=1`
  - plain text/voice/media messages get assistant replies + still enter intake pipeline
  - tune with `PERMANENCE_TELEGRAM_CONTROL_CHAT_MAX_REPLIES`, `PERMANENCE_TELEGRAM_CONTROL_CHAT_MAX_HISTORY`, `PERMANENCE_TELEGRAM_CONTROL_CHAT_REPLY_MAX_CHARS`, `PERMANENCE_TELEGRAM_CONTROL_CHAT_MEMORY_MAX_NOTES`
  - auto-memory capture toggle: `PERMANENCE_TELEGRAM_CONTROL_CHAT_AUTO_MEMORY=1|0`
  - memory retention cap: `PERMANENCE_TELEGRAM_CONTROL_MEMORY_MAX_NOTES=500`
  - default personality mode: `PERMANENCE_TELEGRAM_CONTROL_CHAT_PERSONALITY_DEFAULT=adaptive|strategist|coach|operator|calm|creative`
  - optional memory path override: `PERMANENCE_TELEGRAM_CONTROL_MEMORY_PATH=.../personal_memory.json`
  - fallback ack on model error: `PERMANENCE_TELEGRAM_CONTROL_CHAT_FALLBACK_ACK=1`
- target chat scope:
  - single: `PERMANENCE_TELEGRAM_CHAT_ID=-100...`
  - multiple: `PERMANENCE_TELEGRAM_CHAT_IDS=-100...,123456789`
  - telegram-control-only override: `PERMANENCE_TELEGRAM_CONTROL_TARGET_CHAT_IDS=` (blank means accept all chats)
  - chat-loop override scope: `PERMANENCE_TELEGRAM_CHAT_LOOP_CHAT_IDS=-100...` (run loop polls only these chats)
- optional hard safety allowlist:
  - set `PERMANENCE_TELEGRAM_CONTROL_COMMAND_USER_IDS=123456789,987654321`
  - or set `PERMANENCE_TELEGRAM_CONTROL_COMMAND_CHAT_IDS=-1001234567890`
  - set `PERMANENCE_TELEGRAM_CONTROL_REQUIRE_COMMAND_ALLOWLIST=1`
  - send `/comms-whoami` to return your Telegram `user_id` / `sender_chat_id` / `chat_id`
- routing check from Telegram:
  - send `/comms-mode` to see agent-vs-terminal routing behavior
  - send `/memory-help` for persistent memory commands (`/remember`, `/share`, `/recall`, `/profile`, `/profile-history`, `/profile-conflicts`, `/forget-last`)
  - set profile and style with `/profile-set <field> <value>` and `/personality <mode>`
  - queue terminal work items from Telegram with `/terminal <task>`, review with `/terminal-list`, and manage completion with `/terminal-status` + `/terminal-complete <task-id|latest>`
  - track routines with `/habit-add ... | cue: ... | plan: ...`, `/habit-plan`, `/habit-done`, `/habit-nudge`, `/habit-list`
  - governed learning shortcuts: `/learn-status`, `/learn-run` (subject to command security scope)
  - improvement pitch shortcuts: `/improve-status`, `/improve-pitch`, `/improve-list`, `/improve-approve [proposal-id] [decision-code]`, `/improve-reject [proposal-id] [decision-code]`, `/improve-defer [proposal-id] [decision-code]`
  - brain shortcuts: `/brain-status`, `/brain-sync`, `/brain-recall <query>`
  - read-only X watch shortcuts: `/x-watch <handle|url>`, `/x-unwatch <handle|url>`, `/x-watch-list`
  - budget profile shortcuts: `/low-cost-status`, `/low-cost-enable`, `/low-cost-disable`
  - daily ops shortcuts: `/ops-status`, `/ops-morning`, `/ops-midday`, `/ops-evening`, `/ops-hygiene`
  - approval triage shortcuts: `/approvals-status`, `/approvals-list`, `/approve-next`, `/reject-next`, `/defer-next`
  - batch triage shortcuts: `/approve-batch`, `/reject-batch`, `/defer-batch`
  - loop brain-sync knobs: `PERMANENCE_TELEGRAM_CHAT_LOOP_BRAIN_SYNC=1|0`, `PERMANENCE_TELEGRAM_CHAT_LOOP_BRAIN_SYNC_MIN_AGE_SECONDS=900`
  - sensitive data guardrails: `PERMANENCE_TELEGRAM_CONTROL_REDACT_SENSITIVE=1`, `PERMANENCE_TELEGRAM_CONTROL_REDACT_PAYMENT_LINKS=1`
  - optional iMessage/SMS mirror for Telegram replies/acks:
    - enable `PERMANENCE_TELEGRAM_CONTROL_IMESSAGE_MIRROR=1`
    - set destination `PERMANENCE_TELEGRAM_CONTROL_IMESSAGE_TARGET=+1...` (or iMessage email)
    - choose channel `PERMANENCE_TELEGRAM_CONTROL_IMESSAGE_SERVICE=iMessage|SMS`
    - optional prefix/limit: `PERMANENCE_TELEGRAM_CONTROL_IMESSAGE_PREFIX`, `PERMANENCE_TELEGRAM_CONTROL_IMESSAGE_MAX_CHARS`
Governed continuous learning notes:
- run `python cli.py governed-learning --action status` to inspect policy/state
- run `python cli.py governed-learning --action init-policy` to scaffold/reset governance policy
- run `python cli.py governed-learning --action run --approved-by <name> --approval-note "<reason>"` for approved learning cycles
- default loop is read-only and blocks when `PERMANENCE_AGENT_EXTERNAL_WRITE_ENABLE=1`
- topics are managed in `memory/working/governed_learning_policy.json` (AI, finance, excel, media keywords)
Self-improvement pitch loop notes:
- run `python cli.py self-improvement --action pitch` to generate upgrade ideas from live system signals
- run `python cli.py self-improvement --action list` to review pending ideas
- run `python cli.py self-improvement --action decide --decision approve --proposal-id <id> --decided-by <name>` to approve a change
- set approval PIN/password: `python cli.py self-improvement --action status --set-decision-code <pin>`
- enforce PIN on decisions: `python cli.py self-improvement --action decide --decision approve --proposal-id <id> --decided-by <name> --decision-code <pin>`
- approved ideas can be auto-queued to `memory/approvals.json` for execution board tracking
- set up recurring pitch loop: `bash automation/setup_self_improvement_automation.sh /Users/paytonhicks/Code/permanence-os 21600`
- disable recurring pitch loop: `bash automation/disable_self_improvement_automation.sh /Users/paytonhicks/Code/permanence-os`
Terminal task queue notes:
- review queued Telegram terminal tasks: `python cli.py terminal-task-queue --action list`
- add one manually: `python cli.py terminal-task-queue --action add --text "task text"`
- complete one: `python cli.py terminal-task-queue --action complete --task-id TERM-XXXXXXXXXXXX`
Approval triage notes:
- review pending approvals quickly: `python cli.py approval-triage --action status`
- approve/reject/defer oldest pending: `python cli.py approval-triage --action decide --decision approve|reject|defer --decided-by <name>`
- review highest-priority pending first: `python cli.py approval-triage --action top --limit 20`
- safe batch decisions (source-scoped + risk ceiling): `python cli.py approval-triage --action decide-batch-safe --decision approve --source phase3_opportunity_queue --batch-size 3 --safe-max-priority low --safe-max-risk medium --decided-by <name>`
Cost and spend governance notes:
- keep all paid upgrades manual: no autonomous paid plan upgrades or purchases
- enable no-spend lock: `python cli.py low-cost-mode --action enable` (sets `PERMANENCE_NO_SPEND_MODE=1`)
- audit no-spend guardrails anytime: `python cli.py no-spend-audit --strict`
- external writes and money actions remain approval-gated (`PERMANENCE_AGENT_EXTERNAL_WRITE_ENABLE=0`)
X personal account read-only notes:
- add a watched account feed: `python cli.py x-account-watch --action add --handle @yourhandle`
- list watched feeds: `python cli.py x-account-watch --action list`
- remove watched feed: `python cli.py x-account-watch --action remove --handle @yourhandle`
- watched feeds are read-only trend ingest config and do not post/publish.
Ophtxn persistent brain notes:
- sync the vault from docs/reports/intake: `python cli.py ophtxn-brain --action sync`
- recall from vault: `python cli.py ophtxn-brain --action recall --query "<topic>"`
- Telegram chat replies can include this brain context when the vault exists.
