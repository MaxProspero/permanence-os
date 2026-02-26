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

### `python cli.py health-summary`
Run Health Agent summary on local health files.

### `python cli.py social-summary`
Run Social Agent summary or save a draft.

### `python cli.py logos-gate`
Evaluate Logos Praktikos activation tiers.

### `python cli.py dashboard`
Generate a consolidated dashboard report.

### `python cli.py money-loop`
Run the full revenue money loop (`scripts/run_money_loop.sh`) end-to-end.

### `python cli.py revenue-action-queue`
Generate the latest 7-action revenue queue from email/social plus pipeline + intake funnel signals.

### `python cli.py revenue-architecture`
Generate Revenue Architecture v1 scorecard and pipeline snapshot.

### `python cli.py revenue-execution-board`
Generate the daily revenue execution board.

### `python cli.py revenue-weekly-summary`
Generate a weekly revenue scorecard from pipeline + intake + latest queue.

### `python cli.py revenue-outreach-pack`
Generate outreach message drafts from prioritized open leads.

### `python cli.py revenue-playbook ...`
Manage locked offer + CTA playbook.
Examples:
- `python cli.py revenue-playbook init`
- `python cli.py revenue-playbook show`
- `python cli.py revenue-playbook set --offer-name "Permanence OS Foundation Setup" --cta-keyword FOUNDATION --cta-public 'DM me "FOUNDATION".' --pricing-tier Core --price-usd 1500`

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
- Process captures:
`python cli.py research-inbox --action process`
- View queue status:
`python cli.py research-inbox --action status`
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
