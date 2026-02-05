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

### `python cli.py queue`
Manage promotion queue.

Queue subcommands:
- `python scripts/promotion_queue.py add --task-id T-... --reason "..." --pattern "..."`  
- `python scripts/promotion_queue.py audit --prune`

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
## Maintenance Commands

### `python cli.py clean`
Clean artifacts (logs/outputs/episodic).

### `python cli.py test`
Run test suite.
