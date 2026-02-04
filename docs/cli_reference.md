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

## Ingestion Commands

### `python cli.py ingest`
Ingest tool outputs into sources.json.

### `python cli.py ingest-docs`
Ingest documents into sources.json.

### `python cli.py ingest-sources`
Ingest sources via adapter registry.

## Maintenance Commands

### `python cli.py clean`
Clean artifacts (logs/outputs/episodic).

### `python cli.py test`
Run test suite.
