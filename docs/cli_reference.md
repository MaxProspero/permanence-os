# Permanence OS CLI Reference

## Core Commands

### `python cli.py run`
Execute a governed task through the full pipeline.

### `python cli.py status`
Display system status (latest task, logs, outputs, OpenClaw status).

### `python cli.py briefing`
Generate a daily briefing (includes latest OpenClaw status excerpt).

### `python cli.py email-triage`
Run Email Agent triage on local inbox files.

### `python cli.py gmail-ingest`
Ingest Gmail messages (read-only) into the local inbox file.
- No API key is required; this uses Google OAuth desktop credentials (`credentials.json` + `token.json`).
- First run opens browser consent, then token is reused locally.

### Google Local Sync (No API Mode)
For Drive docs/files, you can avoid Google API calls by ingesting from your local Google Drive Desktop sync folder:
- `python cli.py ingest-docs --doc-dir ~/Library/CloudStorage/GoogleDrive-<account>/My\\ Drive --output memory/working/sources.json`

### `python cli.py health-summary`
Run Health Agent summary on local health files.

### `python cli.py social-summary`
Run Social Agent summary or save a draft.

### `python cli.py logos-gate`
Evaluate Logos Praktikos activation tiers.

### `python cli.py dashboard`
Generate a consolidated dashboard report.

### `python cli.py integration-readiness`
Check credential/integration readiness and write latest readiness report.
- `PERMANENCE_REQUIRE_REVENUE_LINKS=1` enforces booking/payment links as required checks

### `python cli.py anthropic-keychain`
Install/check/remove Anthropic API key in macOS Keychain and keep `.env` key blank.
- Install from one-time file: `python cli.py anthropic-keychain --from-file /path/to/key.txt --remove-source`
- Check status: `python cli.py anthropic-keychain --status`
- Remove key: `python cli.py anthropic-keychain --clear`

### `python cli.py connector-keychain`
Install/check/remove connector read tokens in macOS Keychain and keep token vars blank in `.env`.
- OpenAI API key: `python cli.py connector-keychain --target openai-api-key --from-file /path/to/openai_api_key.txt --remove-source`
- GitHub read token: `python cli.py connector-keychain --target github-read --from-file /path/to/github_token.txt --remove-source`
- Social read token: `python cli.py connector-keychain --target social-read --from-file /path/to/social_token.txt --remove-source`
- Discord alert webhook: `python cli.py connector-keychain --target discord-alert-webhook --from-file /path/to/discord_webhook.txt --remove-source`
- Discord bot token (server/channel ingest): `python cli.py connector-keychain --target discord-bot-token --from-file /path/to/discord_bot_token.txt --remove-source`
- Telegram bot token: `python cli.py connector-keychain --target telegram-bot-token --from-file /path/to/telegram_bot_token.txt --remove-source`
- xAI API key (Grok): `python cli.py connector-keychain --target xai-api-key --from-file /path/to/xai_api_key.txt --remove-source`
- Alpha Vantage API key: `python cli.py connector-keychain --target alpha-vantage --from-file /path/to/alpha_vantage_key.txt --remove-source`
- Finnhub API key: `python cli.py connector-keychain --target finnhub --from-file /path/to/finnhub_key.txt --remove-source`
- Polygon API key: `python cli.py connector-keychain --target polygon --from-file /path/to/polygon_key.txt --remove-source`
- CoinMarketCap API key: `python cli.py connector-keychain --target coinmarketcap --from-file /path/to/coinmarketcap_key.txt --remove-source`
- Glassnode API key: `python cli.py connector-keychain --target glassnode --from-file /path/to/glassnode_key.txt --remove-source`
- Check status: `python cli.py connector-keychain --target github-read --status`

### `python cli.py secret-scan`
Scan for likely secrets before commit/push.
- Default mode scans staged files
- `--all-files` scans all tracked files

### `python cli.py external-access-policy`
Generate connector security policy + risk report for GitHub and social integrations.
- Writes/updates `memory/working/agent_access_policy.json`
- Outputs `outputs/external_access_policy_latest.md`
- `--strict` exits non-zero when high-risk write mode is enabled

### `python cli.py github-research-ingest`
Run read-only GitHub repository research and backlog action suggestions.
- Uses `memory/working/github_research_targets.json`
- Optional token: `PERMANENCE_GITHUB_READ_TOKEN`
- No write API calls

### `python cli.py github-trending-ingest`
Run read-only GitHub trending ingest and rank ecosystem opportunities.
- Uses `memory/working/github_trending_focus.json`
- Tracks daily/weekly/monthly windows and language slices
- Scores watchlist overlap + keyword relevance + stars momentum
- Writes `outputs/github_trending_ingest_latest.md`
- Writes `memory/tool/github_trending_ingest_*.json`

### `python cli.py ecosystem-research-ingest`
Run read-only ecosystem ingest across repos, developers, docs, and communities.
- Uses `memory/working/ecosystem_watchlist.json`
- Tracks GitHub repository metadata (stars/forks/issues/language)
- Tracks developer momentum (followers/public repos)
- Checks docs/community link health for stale-source detection
- Writes `outputs/ecosystem_research_ingest_latest.md`
- Writes `memory/tool/ecosystem_research_ingest_*.json`

### `python cli.py social-research-ingest`
Run read-only social/trend feed ranking for opportunity discovery.
- Uses `memory/working/social_research_feeds.json`
- Uses discernment policy `memory/working/social_discernment_policy.json` (keep/drop logic)
- Optional keywords override: `PERMANENCE_SOCIAL_KEYWORDS`
- Supports RSS/Atom feeds and optional X recent-search feeds (`platform: "x"` + `query`)
- Supports YouTube reviewer feed ingest (`platform: "youtube"` + `channel_id` or direct RSS `url`)
- Supports optional Discord channel ingest (`platform: "discord"` + `channel_id`) using `PERMANENCE_DISCORD_BOT_TOKEN`
- Optional X token for live query feeds: `PERMANENCE_SOCIAL_READ_TOKEN`
- `--force-policy` rewrites the discernment policy template file
- No publish actions

### `python cli.py x-account-watch`
Manage read-only personal X account watch feeds used by `social-research-ingest`.
- List watched handles:
`python cli.py x-account-watch --action list`
- Add a watched handle:
`python cli.py x-account-watch --action add --handle @yourhandle`
- Remove a watched handle:
`python cli.py x-account-watch --action remove --handle @yourhandle`
- Optional flags:
`--max-results`, `--include-replies`, `--label`, `--feeds-path`
- This command only edits feed config. It does not publish/post.

### `python cli.py world-watch`
Ingest high-impact situational feeds (war/conflict signals, market stress, earthquakes, weather, humanitarian reports).
- Uses `memory/working/world_watch_sources.json`
- Includes your map links (World Monitor, XED) in outputs
- Includes market monitor stack (stocks, crypto, FX, macro calendars) from `market_monitors`
- Supports strict market-only mode with `alert_focus.market_only=true` in sources file
- Supports local weather focus via `home_location` in sources file or env: `PERMANENCE_HOME_LAT`, `PERMANENCE_HOME_LON`, `PERMANENCE_HOME_LABEL`
- Writes `outputs/world_watch_latest.md`
- Writes `memory/tool/world_watch_*.json`

### `python cli.py world-watch-alerts`
Build major-event alert digest and optionally dispatch to Discord/Telegram.
- Draft-only by default
- Use `--send` to dispatch to configured channels
- Uses compact notification format by default (short lines, no long links)
- Add `--include-links` only when you want full URLs in the message body
- Optional envs: `PERMANENCE_DISCORD_ALERT_WEBHOOK_URL`, `PERMANENCE_TELEGRAM_BOT_TOKEN`, `PERMANENCE_TELEGRAM_CHAT_ID`, `PERMANENCE_HOME_LAT`, `PERMANENCE_HOME_LON`, `PERMANENCE_HOME_LABEL`
- Writes `outputs/world_watch_alerts_latest.md`
- Writes `memory/tool/world_watch_alerts_*.json`

### `python cli.py market-focus-brief`
Generate compact market control brief from latest world-watch payload.
- Prioritizes highest-impact market signals (stocks, crypto, FX, volatility)
- Builds core watchlist status ladder (ALERT / WATCH / QUIET)
- Includes XAUUSD pulse when `POLYGON_API_KEY` is available
- Writes `outputs/market_focus_brief_latest.md`
- Writes `memory/tool/market_focus_brief_*.json`

### `python cli.py market-backtest-queue`
Build market backtest queue from social/news/video evidence.
- Uses `memory/working/market_backtest_watchlist.json`
- Reads latest `social_research_ingest`, `prediction_ingest`, `prediction_lab`, and `world_watch` payloads
- Writes `outputs/market_backtest_queue_latest.md`
- Writes `memory/tool/market_backtest_queue_*.json`
- Advisory only (no autonomous trading)

### `python cli.py narrative-tracker`
Track high-uncertainty narratives (including conspiracy-style claims) with evidence states.
- Uses `memory/working/narrative_tracker_hypotheses.json`
- States are `supported`, `unverified`, or `contradicted` based on current evidence
- Uses follow-the-money keyword sets per hypothesis
- Alias command: `python cli.py conspiracy-tracker`
- Writes `outputs/narrative_tracker_latest.md`
- Writes `memory/tool/narrative_tracker_*.json`

### `python cli.py opportunity-ranker`
Rank opportunities from social/GitHub/ecosystem/prediction/portfolio signals for Phase 3 review.
- Uses latest tool payloads in `memory/tool/`
- Writes `outputs/opportunity_ranker_latest.md`
- Writes `memory/tool/opportunity_ranker_*.json`
- `--force-policy` rewrites `memory/working/opportunity_rank_policy.json`

### `python cli.py opportunity-approval-queue`
Queue ranked opportunities into `memory/approvals.json` with `PENDING_HUMAN_REVIEW`.
- Uses latest `memory/tool/opportunity_ranker_*.json`
- Writes `outputs/opportunity_approval_queue_latest.md`
- Writes `memory/tool/opportunity_approval_queue_*.json`
- `--force-policy` rewrites `memory/working/opportunity_queue_policy.json`

### `python cli.py phase3-refresh`
Run the full Phase 3 governed sequence:
- social research ingest
- GitHub research ingest
- GitHub trending ingest
- ecosystem research ingest
- side-business portfolio refresh
- prediction ingest + prediction lab
- world watch ingest
- world watch alerts draft
- market backtest queue
- narrative tracker
- opportunity ranker
- opportunity approval queue
- second-brain report

### `python cli.py approval-execution-board`
Build an actionable execution board from approved queue items.
- Reads `memory/approvals.json` for `APPROVED` records
- Writes `outputs/approval_execution_board_latest.md`
- Writes `memory/working/approved_execution_tasks.json`
- Adds `execution_status=QUEUED_FOR_EXECUTION` metadata by default (use `--no-mark-queued` to skip)

### `python cli.py money-loop`
Run the full revenue money loop (`scripts/run_money_loop.sh`) end-to-end.

### `python cli.py comms-loop`
Run the full communication sync loop (`scripts/run_comms_loop.sh`) end-to-end:
- telegram control poll (ingest new chat instructions)
- discord -> telegram relay
- glasses exports autopilot ingest
- research inbox process
- status glance + integration readiness snapshots
- optional comms status snapshot with escalation/backlog thresholds
- optional digest step (set `PERMANENCE_COMMS_LOOP_DIGEST_ENABLED=1`)
- optional doctor step (set `PERMANENCE_COMMS_LOOP_DOCTOR_ENABLED=1`)
- optional escalation digest step (set `PERMANENCE_COMMS_LOOP_ESCALATION_DIGEST_ENABLED=1`)
- comms status loop controls:
  `PERMANENCE_COMMS_LOOP_COMMS_STATUS_ENABLED`,
  `PERMANENCE_COMMS_LOOP_COMMS_STATUS_REQUIRE_ESCALATION_DIGEST`,
  `PERMANENCE_COMMS_LOOP_COMMS_STATUS_LOG_STALE_MINUTES`,
  `PERMANENCE_COMMS_LOOP_COMMS_STATUS_COMPONENT_STALE_MINUTES`,
  `PERMANENCE_COMMS_LOOP_COMMS_STATUS_ESCALATION_DIGEST_STALE_MINUTES`,
  `PERMANENCE_COMMS_LOOP_COMMS_STATUS_ESCALATION_HOURS`,
  `PERMANENCE_COMMS_LOOP_COMMS_STATUS_ESCALATION_WARN_COUNT`,
  `PERMANENCE_COMMS_LOOP_COMMS_STATUS_VOICE_QUEUE_WARN_COUNT`

### `python cli.py second-brain-loop`
Run the full second-brain loop (`scripts/run_second_brain_loop.sh`) end-to-end:
- life brief
- GitHub research ingest
- GitHub trending ingest
- ecosystem research ingest
- social trend ingest
- side-business portfolio board
- prediction news ingest (signal refresh)
- prediction lab (advisory only)
- world watch ingest
- world watch alerts draft/dispatch module
- market focus brief (compact control panel + XAUUSD pulse)
- market backtest queue (article + YouTube + news evidence)
- narrative tracker (supported / unverified / contradicted board)
- opportunity ranker
- opportunity approval queue (manual review only)
- clipping transcript ingest
- clipping pipeline manager
- revenue execution board refresh
- revenue cost-recovery plan (cover API/tool spend first)
- unified second-brain report

### `python cli.py second-brain-init`
Initialize editable working templates for the second-brain modules.
- `--force` overwrite existing templates

### `python cli.py life-os-brief`
Generate a daily life-operations brief (identity principles, non-negotiables, top tasks).

### `python cli.py side-business-portfolio`
Generate prioritized side-business action board with weekly target/actual/gap scoring.

### `python cli.py prediction-ingest`
Ingest RSS/news feeds and update hypothesis `signal_score` + evidence rows in `memory/working/prediction_hypotheses.json`.
- Advisory only
- No trade execution

### `python cli.py prediction-lab`
Generate prediction-market research brief with Bayesian + simulation metrics.
- Advisory only
- No trade execution
- Manual approval required

### `python cli.py clipping-transcript-ingest`
Ingest transcript files from `memory/working/clipping_transcripts/` into `memory/working/clipping_jobs.json`.
- Supports `.txt`, `.md`, `.json`, `.srt`
- Converts timestamped lines into scored candidate segments

### `python cli.py clipping-pipeline`
Generate clipping queue summary and ranked candidate clips from transcript segments.

### `python cli.py second-brain-report`
Generate unified report across life layer + revenue layer + side-income modules.

### `python cli.py revenue-action-queue`
Generate the latest 7-action revenue queue from email/social plus pipeline + intake funnel signals.

### `python cli.py revenue-architecture`
Generate Revenue Architecture v1 scorecard and pipeline snapshot.

### `python cli.py revenue-cost-recovery`
Generate a cost-recovery plan that maps API/tool spend to required closes/leads/outreach.
- Uses `memory/working/api_cost_plan.json` (auto-created if missing)
- Uses locked offer price from `memory/working/revenue_playbook.json`
- `--force-template` rewrites cost-plan defaults

### `python cli.py revenue-execution-board`
Generate the daily revenue execution board.

### `python cli.py revenue-weekly-summary`
Generate a weekly revenue scorecard from pipeline + intake + latest queue.

### `python cli.py revenue-outreach-pack`
Generate outreach message drafts from prioritized open leads.

### `python cli.py revenue-followup-queue`
Generate outreach follow-up queue from sent/not-replied records.

### `python cli.py revenue-eval`
Run revenue artifact/data-contract evaluation checks.

### `python cli.py revenue-backup`
Create timestamped backup archive for revenue working state + latest outputs.

### `python cli.py revenue-playbook ...`
Manage locked offer + CTA playbook.
Examples:
- `python cli.py revenue-playbook init`
- `python cli.py revenue-playbook show`
- `python cli.py revenue-playbook set --offer-name "Permanence OS Foundation Setup" --cta-keyword FOUNDATION --cta-public 'DM me "FOUNDATION".' --booking-link "https://cal.com/..." --payment-link "https://buy.stripe.com/..." --pricing-tier Core --price-usd 1500`

### `python cli.py revenue-targets ...`
Manage locked revenue targets.
Examples:
- `python cli.py revenue-targets init`
- `python cli.py revenue-targets show`
- `python cli.py revenue-targets set --weekly-revenue-target 5000 --monthly-revenue-target 20000 --daily-outreach-target 12`

### `python cli.py sales-pipeline ...`
Forward pipeline commands to `scripts/sales_pipeline.py`.
Examples:
- `python cli.py sales-pipeline init`
- `python cli.py sales-pipeline add --name "Lead" --source "X DM" --est-value 1500`
- `python cli.py sales-pipeline list --open-only`

### `python cli.py foundation-site`
Serve `site/foundation/index.html` locally.
- `--host` bind host (default `127.0.0.1`)
- `--port` bind port (default `8787`)
- `--no-open` disable auto-open browser
- `--site-dir` override site root
- Intake form posts to local Command Center API (`/api/revenue/intake`) when available, otherwise falls back to email.

### `python cli.py foundation-api`
Run FOUNDATION API scaffold for auth + onboarding + memory.
- `--host` bind host (default `127.0.0.1`)
- `--port` bind port (default `8797`)
- `--debug` enable Flask debug mode
- Endpoints: `/health`, `/auth/session`, `/onboarding/start`, `/memory/schema`, `/memory/entry`

### `python cli.py command-center`
Run live dashboard API + Command Center UI.
- `--host` bind host (default `127.0.0.1`)
- `--port` bind port (default `8000`)
- `--no-open` disable auto-open browser
- `--run-horizon` run Horizon before boot
- `--demo-horizon` deterministic Horizon mode (requires `--run-horizon`)

### `python cli.py operator-surface`
Run Command Center + FOUNDATION site together.
- `--host` bind host for both services
- `--dashboard-port` dashboard API port (default `8000`)
- `--foundation-port` FOUNDATION site port (default `8787`)
- `--money-loop` run one money-loop refresh before launch
- `--run-horizon` run Horizon before dashboard boot
- `--demo-horizon` deterministic Horizon mode (requires `--run-horizon`)
- `--no-open` disable browser auto-open
- `--dry-run` print launch commands without starting services

### `python cli.py setup-launchers`
Create Desktop `.command` launchers for daily workflows.
- `--desktop-dir` override destination directory (default `~/Desktop`)
- `--force` overwrite existing launcher files
- Includes operator/command-center/foundation/money-loop plus comms launchers
  (`Run_Permanence_Comms_Loop.command`, `Run_Permanence_Comms_Status.command`, `Run_Permanence_Discord_Relay.command`, `Run_Permanence_Comms_Digest.command`, `Run_Permanence_Comms_Doctor.command`, `Run_Permanence_Comms_Escalation_Digest.command`, `Run_Permanence_Comms_Escalation_Status.command`)

### `python cli.py snapshot`
Generate a system snapshot with status + OpenClaw + HR + briefing.

### `python cli.py hr-report`
Generate weekly system health report (includes OpenClaw status excerpt).

### `python cli.py openclaw-status`
Capture OpenClaw status to outputs + tool memory.

### `python cli.py openclaw-sync`
Run OpenClaw health sync job.
- `--interval N` poll interval seconds
- `--once` single check then exit

### `python cli.py cleanup-weekly`
Rotate outputs/tool memory/logs with retention defaults.

### `python cli.py git-autocommit`
Auto-commit tracked changes with a weekly message.

## Memory Commands

### `python cli.py promote`
Generate Canon change draft from episodic memory.

### `python cli.py promotion-review`
Generate promotion review checklist.

### `python cli.py promotion-daily`
Run the daily promotion cycle (gated `queue auto` + `promotion-review`).
- Daytime-friendly policy example: `python cli.py promotion-daily --phase-policy auto --phase-enforce-hour 19`

### `python cli.py queue`
Manage promotion queue.

Queue subcommands:
- `python scripts/promotion_queue.py add --task-id T-... --reason "..." --pattern "..."`  
- `python scripts/promotion_queue.py audit --prune`
- `python scripts/promotion_queue.py auto --dry-run`
- `python scripts/promotion_queue.py auto --since-hours 24 --max-add 5`

## Ingestion Commands

### `python cli.py ingest`
Ingest tool outputs into sources.json.

### `python cli.py ingest-docs`
Ingest documents into sources.json.

### `python cli.py ingest-sources`
Ingest sources via adapter registry.

Adapters:
- `web_search` (Tavily; requires `TAVILY_API_KEY`)
- `google_docs` (Google Docs/Drive; requires OAuth credentials.json)
- `drive_pdfs` (Google Drive PDFs; requires OAuth credentials.json)

Example:
`python cli.py ingest-sources --adapter google_docs --doc-ids 1A2B3C --output memory/working/sources.json`

Append mode (merge instead of overwrite):
`python cli.py ingest-sources --adapter drive_pdfs --folder-id FOLDER_ID --append`

Resume mode (skip already ingested IDs with a cursor):
`python cli.py ingest-sources --adapter drive_pdfs --folder-id FOLDER_ID --append --resume`
`python cli.py ingest-sources --adapter google_docs --folder-id FOLDER_ID --append --resume`

Tuning:
- `--max-pdf-bytes` skip oversized PDFs (default 8,000,000)
- `--max-seconds` per-file timeout (default 25)
- `--max-doc-chars` cap doc text extraction (default 50,000)
- `--skip-failures` mark failed items as processed (avoids repeated timeouts)

### `python cli.py ingest-drive-all`
Batch ingest Drive PDFs + Docs with resume.

Example:
`python cli.py ingest-drive-all --folder-id FOLDER_ID --max 10`

Tuning:
`python cli.py ingest-drive-all --folder-id FOLDER_ID --max 5 --max-seconds 40 --max-pdf-bytes 15000000 --skip-failures`

### `python cli.py sources-digest`
Generate a markdown digest from sources.json (no LLM).

### `python cli.py sources-brief`
Generate a synthesis brief from sources.json (heuristic, no LLM).

### `python cli.py synthesis-brief`
Generate a governed synthesis brief (draft + optional approval).
- `--days 7|30|90` lookback window (default 30)
- `--max-sources N` limit source count
- `--no-prompt` skip approval (draft only)
- `--approve` auto-approve draft to final

### `python cli.py notebooklm-sync`
Sync NotebookLM exports from a Google Drive folder into storage archives.
- `--folder-id FOLDER_ID` (or set `PERMANENCE_NOTEBOOKLM_FOLDER_ID`)
- `--max-files N` (default 50)
- `--max-seconds N` (default 120)
- `--max-bytes N` skip large files (default 25,000,000)
- `--split-max-chars N` split oversized Docs into text parts (default 40,000)

### `python cli.py ari-reception`
Run Ari receptionist workflow.
- `--action intake --sender "Name" --message "..."` appends to queue
- `--action summary` writes latest receptionist summary report
- `--queue-dir` override queue location

### `python cli.py sandra-reception`
Run receptionist workflow with display name set to Sandra.
- Uses the same queue and actions as `ari-reception`
- Useful when you want Sandra labels in reports/automation logs

### `python cli.py research-inbox`
Capture links/text and process them into `sources.json` via URL fetch.
- Add capture:
`python cli.py research-inbox --action add --text "watch https://youtube.com/... and https://x.com/..."`
- Best for X bookmarks/manual curation: spend 5-10 minutes saving links, then ingest in one batch.
- You can paste multiple links in one command (space-separated).
- Process captures:
`python cli.py research-inbox --action process`
- View queue status:
`python cli.py research-inbox --action status`

### `python cli.py glasses-bridge`
Bridge smart-glasses events (Meta/VisionClaw/Nearby-Glasses exports) into local pipelines.
- Ingest exported JSON:
`python cli.py glasses-bridge --action ingest --from-json ~/Downloads/nearby_glasses_detected_123.json`
- Intake one ad-hoc POV note with media:
`python cli.py glasses-bridge --action intake --source visionclaw --channel telegram --text "What am I looking at? snapshot attached." --media ~/Downloads/pov.jpg`
- Check stored event status:
`python cli.py glasses-bridge --action status`
- Optional flags:
`--no-reception` skip Ari queue mirroring, `--no-research` skip research inbox mirroring, `--no-attachments` skip media copy/extract

### `python cli.py telegram-control`
Poll Telegram updates and convert them into glasses-bridge intake events.
- With chat-agent enabled, plain non-command messages receive model-backed assistant replies.
- Status check:
`python cli.py telegram-control --action status`
- Poll and ingest:
`python cli.py telegram-control --action poll`
- Poll, ingest, and send ack to channel:
`python cli.py telegram-control --action poll --ack`
- Poll + enable slash command control:
`python cli.py telegram-control --action poll --enable-commands --ack`
- Poll + force chat-agent replies for this run:
`python cli.py telegram-control --action poll --chat-agent --max-chat-replies 3`
- Example commands from Telegram chat:
`/comms-mode`, `/comms-whoami`, `/memory-help`, `/memory`, `/remember <note>`, `/share <long note>`, `/terminal <task>`, `/terminal-list`, `/recall [query]`, `/profile`, `/profile-set <field> <value>`, `/profile-get`, `/profile-history [field]`, `/profile-conflicts`, `/personality [mode]`, `/personality-modes`, `/habit-add <name> | cue: ... | plan: ...`, `/habit-plan <name> | cue: ... | plan: ...`, `/habit-done <name>`, `/habit-nudge`, `/habit-list`, `/habit-drop <name>`, `/forget-last`, `/learn-status`, `/learn-run`, `/improve-status`, `/improve-pitch`, `/improve-list`, `/improve-approve [proposal-id] [decision-code]`, `/improve-reject [proposal-id] [decision-code]`, `/improve-defer [proposal-id] [decision-code]`, `/brain-status`, `/brain-sync`, `/brain-recall <query>`, `/x-watch <handle|url>`, `/x-unwatch <handle|url>`, `/x-watch-list`, `/comms-status`, `/comms-doctor`, `/comms-doctor-fix`, `/comms-digest`, `/comms-escalations`, `/comms-escalations-send`, `/comms-escalation-status`, `/comms-escalation-enable`, `/comms-escalation-disable`, `/comms-run`
- Voice-note routing example (high-priority receptionist path):
`python cli.py telegram-control --action poll --voice-priority high --voice-channel telegram-voice`
- Voice-note queueing into transcription queue:
`python cli.py telegram-control --action poll --voice-transcribe-queue ~/permanence-os/memory/working/transcription_queue.json`
- Optional flags:
`--chat-id`, `--skip-media`, `--include-bot-messages`, `--dry-run`, `--no-commit-offset`, `--limit`, `--enable-commands`, `--command-prefix`, `--command-timeout`, `--max-commands`, `--command-allow-user-id`, `--command-allow-chat-id`, `--require-command-allowlist`, `--no-command-ack`, `--chat-agent`, `--no-chat-agent`, `--chat-task-type`, `--max-chat-replies`, `--chat-max-history`, `--chat-reply-max-chars`, `--chat-history-path`, `--chat-memory-max-notes`, `--chat-brain-max-notes`, `--chat-auto-memory`, `--no-chat-auto-memory`, `--memory-path`, `--intake-path`, `--terminal-queue-path`, `--brain-vault-path`, `--memory-max-notes`, `--voice-priority`, `--voice-channel`, `--voice-source`, `--voice-text-prefix`, `--voice-transcribe-queue`, `--no-voice-transcribe-queue`
- Command defaults can be set via env:
`PERMANENCE_TELEGRAM_CONTROL_ENABLE_COMMANDS`, `PERMANENCE_TELEGRAM_CONTROL_COMMAND_PREFIX`, `PERMANENCE_TELEGRAM_CONTROL_COMMAND_TIMEOUT`, `PERMANENCE_TELEGRAM_CONTROL_MAX_COMMANDS`, `PERMANENCE_TELEGRAM_CONTROL_COMMAND_ACK`, `PERMANENCE_TELEGRAM_CONTROL_COMMAND_USER_IDS`, `PERMANENCE_TELEGRAM_CONTROL_COMMAND_CHAT_IDS`, `PERMANENCE_TELEGRAM_CONTROL_REQUIRE_COMMAND_ALLOWLIST`, `PERMANENCE_TELEGRAM_CHAT_ID`, `PERMANENCE_TELEGRAM_CHAT_IDS`, `PERMANENCE_TELEGRAM_CONTROL_TARGET_CHAT_IDS`
- Telegram chat loop env (for `scripts/run_telegram_chat_loop.sh`):
`PERMANENCE_TELEGRAM_CHAT_LOOP_CHAT_IDS`, `PERMANENCE_TELEGRAM_CHAT_LOOP_BRAIN_SYNC`, `PERMANENCE_TELEGRAM_CHAT_LOOP_BRAIN_SYNC_MIN_AGE_SECONDS`
- Chat-agent defaults can be set via env:
`PERMANENCE_TELEGRAM_CONTROL_CHAT_AGENT_ENABLED`, `PERMANENCE_TELEGRAM_CONTROL_CHAT_TASK_TYPE`, `PERMANENCE_TELEGRAM_CONTROL_CHAT_MAX_REPLIES`, `PERMANENCE_TELEGRAM_CONTROL_CHAT_MAX_HISTORY`, `PERMANENCE_TELEGRAM_CONTROL_CHAT_REPLY_MAX_CHARS`, `PERMANENCE_TELEGRAM_CONTROL_CHAT_MEMORY_MAX_NOTES`, `PERMANENCE_TELEGRAM_CONTROL_CHAT_AUTO_MEMORY`, `PERMANENCE_TELEGRAM_CONTROL_MEMORY_MAX_NOTES`, `PERMANENCE_TELEGRAM_CONTROL_CHAT_PERSONALITY_DEFAULT`, `PERMANENCE_TELEGRAM_CONTROL_CHAT_FALLBACK_ACK`, `PERMANENCE_TELEGRAM_CONTROL_CHAT_HISTORY_PATH`, `PERMANENCE_TELEGRAM_CONTROL_MEMORY_PATH`, `PERMANENCE_TELEGRAM_CONTROL_INTAKE_PATH`, `PERMANENCE_TELEGRAM_CONTROL_TERMINAL_QUEUE_PATH`, `PERMANENCE_TERMINAL_TASK_QUEUE_PATH`, `PERMANENCE_TELEGRAM_CONTROL_REDACT_SENSITIVE`, `PERMANENCE_TELEGRAM_CONTROL_REDACT_PAYMENT_LINKS`, `PERMANENCE_TELEGRAM_CONTROL_IMESSAGE_MIRROR`, `PERMANENCE_TELEGRAM_CONTROL_IMESSAGE_TARGET`, `PERMANENCE_TELEGRAM_CONTROL_IMESSAGE_SERVICE`, `PERMANENCE_TELEGRAM_CONTROL_IMESSAGE_PREFIX`, `PERMANENCE_TELEGRAM_CONTROL_IMESSAGE_MAX_CHARS`, `PERMANENCE_TELEGRAM_CONTROL_CHAT_SYSTEM_PROMPT`

### `python cli.py ophtxn-simulation`
Run offline simulations for Ophtxn memory retrieval and habit logic.
- Default run:
`python cli.py ophtxn-simulation`
- Custom run:
`python cli.py ophtxn-simulation --seed 11 --memory-trials 300 --habit-days 90`
- Outputs:
  - report markdown: `outputs/ophtxn_simulation_*.md`
  - latest report: `outputs/ophtxn_simulation_latest.md`
  - includes memory retrieval, habit streak consistency, profile conflict logging, and habit nudge checks

### `python cli.py ophtxn-completion`
Score progress to 100% from live telemetry and list blockers/actions.
- Standard run:
`python cli.py ophtxn-completion`
- Strict target gate (non-zero exit if below target):
`python cli.py ophtxn-completion --target 95 --strict`
- Outputs:
  - report markdown: `outputs/ophtxn_completion_*.md`
  - latest report: `outputs/ophtxn_completion_latest.md`
  - tool payload: `memory/tool/ophtxn_completion_*.json`
- Optional automation loop (governed-learning + completion check every 6h):
`bash automation/setup_completion_automation.sh /Users/paytonhicks/Code/permanence-os 21600`
`bash automation/disable_completion_automation.sh /Users/paytonhicks/Code/permanence-os`

### `python cli.py ophtxn-brain`
Sync and query the persistent Ophtxn brain vault from docs/reports/memory/intake files.
- Status:
`python cli.py ophtxn-brain --action status`
- Sync brain from system files:
`python cli.py ophtxn-brain --action sync`
- Recall relevant knowledge:
`python cli.py ophtxn-brain --action recall --query "mission and workflow"`
- Optional flags:
`--vault-path`, `--limit`, `--max-chunks`
- Outputs:
  - report markdown: `outputs/ophtxn_brain_*.md`
  - latest report: `outputs/ophtxn_brain_latest.md`
  - tool payload: `memory/tool/ophtxn_brain_*.json`

### `python cli.py terminal-task-queue`
Manage queued terminal tasks captured from Telegram `/terminal` messages.
- Queue status:
`python cli.py terminal-task-queue --action status`
- List recent tasks:
`python cli.py terminal-task-queue --action list --limit 12`
- Add task manually:
`python cli.py terminal-task-queue --action add --text "harden telegram retry logic" --source manual`
- Mark task done:
`python cli.py terminal-task-queue --action complete --task-id TERM-XXXXXXXXXXXX`
- Optional flags:
`--queue-path`, `--source`, `--sender`, `--sender-user-id`, `--chat-id`, `--limit`
- Outputs:
  - report markdown: `outputs/terminal_task_queue_*.md`
  - latest report: `outputs/terminal_task_queue_latest.md`
  - tool payload: `memory/tool/terminal_task_queue_*.json`

### `python cli.py governed-learning`
Run governed continuous learning across AI/finance/excel/media feeds under explicit approval gates.
- Policy status:
`python cli.py governed-learning --action status`
- Initialize/reset policy template:
`python cli.py governed-learning --action init-policy`
- Run loop (requires approval by default):
`python cli.py governed-learning --action run --approved-by payton --approval-note "daily learning pass"`
- Dry-run plan only:
`python cli.py governed-learning --action run --approved-by payton --approval-note "review plan" --dry-run`
- Skip specific pipelines:
`python cli.py governed-learning --action run --approved-by payton --approval-note "focus social+ai" --skip-pipeline world_watch --skip-pipeline market_focus_brief`
- Outputs:
  - report markdown: `outputs/governed_learning_*.md`
  - latest report: `outputs/governed_learning_latest.md`
  - tool payload: `memory/tool/governed_learning_*.json`

### `python cli.py self-improvement`
Generate and manage self-improvement pitches (ask approval before changes).
- Status:
`python cli.py self-improvement --action status`
- Generate new pitches:
`python cli.py self-improvement --action pitch`
- List pending pitches:
`python cli.py self-improvement --action list`
- Approve/reject next pending pitch:
`python cli.py self-improvement --action decide --decision approve --decided-by payton`
`python cli.py self-improvement --action decide --decision reject --decided-by payton`
- Decide a specific pitch id:
`python cli.py self-improvement --action decide --decision approve --proposal-id IMP-XXXXXXXXXX --decided-by payton --note "approved"`
- Require a decision code for approvals:
`python cli.py self-improvement --action status --set-decision-code 246810`
`python cli.py self-improvement --action decide --decision approve --proposal-id IMP-XXXXXXXXXX --decided-by payton --decision-code 246810`
- Disable decision-code requirement:
`python cli.py self-improvement --action status --clear-decision-code`
- Optional Telegram summary:
`python cli.py self-improvement --action pitch --send-telegram`
- Recurring automation scripts:
`bash automation/setup_self_improvement_automation.sh /Users/paytonhicks/Code/permanence-os 21600`
`bash automation/disable_self_improvement_automation.sh /Users/paytonhicks/Code/permanence-os`
- Outputs:
  - report markdown: `outputs/self_improvement_*.md`
  - latest report: `outputs/self_improvement_latest.md`
  - tool payload: `memory/tool/self_improvement_*.json`

### `python cli.py glasses-autopilot`
Auto-scan `~/Downloads` for new smart-glasses export JSON files and ingest them.
- Run importer:
`python cli.py glasses-autopilot --action run`
- Status:
`python cli.py glasses-autopilot --action status`
- Optional flags:
`--downloads-dir`, `--pattern` (repeatable), `--no-attachment-pipeline`, `--no-research-process`, `--dry-run`

### `python cli.py discord-feed-manager`
Manage Discord channel rows in `memory/working/social_research_feeds.json`.
- List configured Discord rows:
`python cli.py discord-feed-manager --action list`
- Add/update row:
`python cli.py discord-feed-manager --action add --name "Discord Alpha" --channel-id 1234567890 --invite-url https://discord.gg/...`
- Add using channel URL (auto-extract channel id):
`python cli.py discord-feed-manager --action add --name "Discord Alpha" --channel-link https://discord.com/channels/<guild_id>/<channel_id>`
- Add/update with content filters:
`python cli.py discord-feed-manager --action add --channel-id 1234567890 --include-keyword gold --include-keyword xauusd --exclude-keyword spam --min-chars 15`
- Set feed priority for multi-channel relay ordering:
`python cli.py discord-feed-manager --action add --channel-id 1234567890 --priority urgent`
- Enable/disable/remove:
`python cli.py discord-feed-manager --action enable --channel-id 1234567890`
`python cli.py discord-feed-manager --action disable --channel-id 1234567890`
`python cli.py discord-feed-manager --action remove --channel-id 1234567890`
- Clear filter fields on an existing feed:
`python cli.py discord-feed-manager --action add --channel-id 1234567890 --clear-filters`

### `python cli.py discord-telegram-relay`
Relay new Discord messages (from enabled feed rows) into your Telegram channel.
- Status:
`python cli.py discord-telegram-relay --action status`
- Run relay:
`python cli.py discord-telegram-relay --action run`
- Dry run (fetch only, no Telegram send):
`python cli.py discord-telegram-relay --action run --dry-run`
- Relay now supports per-feed filters from `social_research_feeds.json`:
`include_keywords`, `exclude_keywords`, `min_chars`
- Escalation example (keyword + priority-gated):
`python cli.py discord-telegram-relay --action run --escalate --escalation-keyword outage --escalation-min-priority high`
- Priority-based multi-destination escalation notify:
`python cli.py discord-telegram-relay --action run --escalation-notify --escalation-telegram-min-priority high --escalation-discord-min-priority urgent`
- Mirror Discord messages into shared Ophtxn intake (single memory stream with Telegram):
`python cli.py discord-telegram-relay --action run --intake-path /path/to/telegram_share_intake.jsonl`
- Optional flags:
`--feeds-path`, `--state-path`, `--chat-id`, `--max-per-feed`, `--escalate`, `--no-escalate`, `--escalation-keyword`, `--escalation-min-priority`, `--escalations-path`, `--escalate-to-reception`, `--no-escalate-to-reception`, `--escalation-notify`, `--no-escalation-notify`, `--escalation-telegram-min-priority`, `--escalation-discord-min-priority`, `--escalation-max-notify`, `--escalation-webhook-url`, `--escalation-notify-timeout`, `--intake-path`, `--no-intake-mirror`, `--no-commit-state`

### `python cli.py comms-digest`
Build a compact communication digest from latest relay/poll/autopilot runs and optionally send to Telegram.
- Build only:
`python cli.py comms-digest`
- Build and send:
`python cli.py comms-digest --send`
- Optional flags:
`--chat-id`, `--max-warnings`, `--include-paths`, `--dry-run`, `--no-history`

### `python cli.py comms-escalation-digest`
Build a digest from recent escalation history and optionally dispatch.
- Build only:
`python cli.py comms-escalation-digest`
- Send to Telegram + Discord (if configured):
`python cli.py comms-escalation-digest --send`
- Optional flags:
`--hours`, `--max-items`, `--send-telegram`, `--send-discord`, `--chat-id`, `--webhook-url`, `--timeout`

### `python cli.py comms-status`
Generate consolidated communication stack status:
- comms loop launchd state + run counters
- latest Discord relay metrics
- latest Telegram control metrics
- latest glasses autopilot metrics
- latest escalation digest metrics
- escalation volume + voice transcription queue backlog
- staleness + warning rollup
- Optional flags:
`--comms-log-stale-minutes`, `--component-stale-minutes`, `--escalation-digest-stale-minutes`, `--escalation-hours`, `--escalation-warn-count`, `--voice-queue-warn-count`, `--require-escalation-digest`

### `python cli.py comms-doctor`
Run comms health checks (secrets/config/automation/freshness).
- Run strict check (exit non-zero on warnings):
`python cli.py comms-doctor`
- Run non-blocking check:
`python cli.py comms-doctor --allow-warnings`
- Run with live token checks + auto repair:
`python cli.py comms-doctor --check-live --auto-repair --allow-warnings`
- Optional flags:
`--max-stale-minutes`, `--digest-max-stale-minutes`, `--require-digest`, `--require-escalation-digest`, `--check-live`, `--live-timeout`, `--auto-repair`, `--repair-timeout`

### `python cli.py comms-automation`
Manage comms loop automation lifecycle from CLI:
- status:
`python cli.py comms-automation --action status`
- enable:
`python cli.py comms-automation --action enable`
- disable:
`python cli.py comms-automation --action disable`
- run now:
`python cli.py comms-automation --action run-now`
- digest status:
`python cli.py comms-automation --action digest-status`
- digest enable/disable:
`python cli.py comms-automation --action digest-enable`
`python cli.py comms-automation --action digest-disable`
- digest run now:
`python cli.py comms-automation --action digest-now`
- doctor status:
`python cli.py comms-automation --action doctor-status`
- doctor enable/disable:
`python cli.py comms-automation --action doctor-enable`
`python cli.py comms-automation --action doctor-disable`
- doctor run now:
`python cli.py comms-automation --action doctor-now`
- escalation digest status:
`python cli.py comms-automation --action escalation-status`
- escalation digest enable/disable:
`python cli.py comms-automation --action escalation-enable`
`python cli.py comms-automation --action escalation-disable`
- escalation digest run now:
`python cli.py comms-automation --action escalation-digest-now`

## Maintenance Commands

### `python cli.py clean`
Clean artifacts (logs/outputs/episodic).

### `python cli.py test`
Run test suite.

### `python cli.py automation-verify`
Verify launchd schedule and load state on macOS.

### `python cli.py automation-report`
Generate daily automation run report.

### `python cli.py reliability-gate`
Evaluate strict slot-based reliability window.

### `python cli.py reliability-watch`
Run background 7-day reliability watch with failure-only notifications.
- `--arm --days 7` start watch and install launch agent
- `--status` check current watch state
- `--disarm` stop watch and remove launch agent
- `--check-interval-minutes 30` set background check cadence

### `python cli.py reliability-streak`
Show/update reliability streak.

### `python cli.py phase-gate`
Run weekly promotion gate (reliability + streak).

### `python cli.py status-glance`
Write one-line operator status files (`status_today.txt` and `status_today.json`).

### `python cli.py dell-cutover-verify`
Verify Dell cron cutover prerequisites and managed cron block.

### `python cli.py dell-remote`
Mac->Dell bridge for SSH execution and code sync (no terminal copy/paste).
- Configure once:
`python cli.py dell-remote --action configure --host DELL_HOST --user DELL_USER --repo-path ~/permanence-os --port 22 --key-path ~/.ssh/id_ed25519`
- Test SSH:
`python cli.py dell-remote --action test`
- Run a Dell command in repo + venv:
`python cli.py dell-remote --action run --cmd "python cli.py status"`
- Sync local code to Dell repo:
`python cli.py dell-remote --action sync-code`

### `python cli.py organize-files`
Safe file organizer for cleanup acceleration.
- Scan and generate plan/report (no file moves):
`python cli.py organize-files --action scan --roots ~/Downloads ~/Desktop --max-stale-actions 300`
- Apply plan by moving files into quarantine (never hard delete):
`python cli.py organize-files --action apply --plan outputs/file_organizer_plan_YYYYMMDD-HHMMSS.json --confirm`
- Open macOS Storage settings:
`python cli.py organize-files --action open-storage`

### PowerShell + WSL helpers (Dell)
For Windows-first operation on Dell, load:
`automation/dell_wsl_helpers.ps1`

Then use:
- `perm-bootstrap <repo-url>`
- `perm-test`
- `perm-cutover`
- `perm-run`

Detailed runbook: `docs/dell_cutover_powershell.md`.
