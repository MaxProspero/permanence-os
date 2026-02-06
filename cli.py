#!/usr/bin/env python3
"""
Unified CLI for Permanence OS.
Commands: run, add-source, status, clean, test, ingest, ingest-docs, ingest-sources, ingest-drive-all, sources-digest, sources-brief, synthesis-brief, notebooklm-sync, promote, promotion-review, queue, hr-report, briefing, email-triage, gmail-ingest, health-summary, social-summary, logos-gate, dashboard, snapshot, openclaw-status, openclaw-sync, cleanup-weekly, git-autocommit
"""

import argparse
import os
import subprocess
import sys

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__)))


def _run(cmd: list[str]) -> int:
    return subprocess.call(cmd)


def cmd_run(args: argparse.Namespace) -> int:
    cmd = [sys.executable, os.path.join(BASE_DIR, "run_task.py"), args.goal]
    if args.sources:
        cmd += ["--sources", args.sources]
    if args.draft:
        cmd += ["--draft", args.draft]
    if args.allow_single_source:
        cmd += ["--allow-single-source"]
    return _run(cmd)


def cmd_add_source(args: argparse.Namespace) -> int:
    cmd = [
        sys.executable,
        os.path.join(BASE_DIR, "scripts", "new_sources.py"),
        args.source,
        str(args.confidence),
    ]
    if args.notes:
        cmd.append(args.notes)
    return _run(cmd)


def cmd_status(_args: argparse.Namespace) -> int:
    return _run([sys.executable, os.path.join(BASE_DIR, "scripts", "status.py")])


def cmd_clean(args: argparse.Namespace) -> int:
    cmd = [sys.executable, os.path.join(BASE_DIR, "scripts", "clean_artifacts.py")]
    if args.logs:
        cmd.append("--logs")
    if args.episodic:
        cmd.append("--episodic")
    if args.outputs:
        cmd.append("--outputs")
    if args.all or not (args.logs or args.episodic or args.outputs):
        cmd.append("--all")
    return _run(cmd)


def cmd_test(_args: argparse.Namespace) -> int:
    tests = [
        os.path.join(BASE_DIR, "tests", "test_polemarch.py"),
        os.path.join(BASE_DIR, "tests", "test_agents.py"),
        os.path.join(BASE_DIR, "tests", "test_compliance_gate.py"),
        os.path.join(BASE_DIR, "tests", "test_researcher_ingest.py"),
        os.path.join(BASE_DIR, "tests", "test_researcher_documents.py"),
        os.path.join(BASE_DIR, "tests", "test_memory_promotion.py"),
        os.path.join(BASE_DIR, "tests", "test_promotion_queue.py"),
        os.path.join(BASE_DIR, "tests", "test_promotion_review.py"),
        os.path.join(BASE_DIR, "tests", "test_hr_agent.py"),
        os.path.join(BASE_DIR, "tests", "test_episodic_memory.py"),
        os.path.join(BASE_DIR, "tests", "test_openclaw_health_sync.py"),
        os.path.join(BASE_DIR, "tests", "test_briefing_run.py"),
        os.path.join(BASE_DIR, "tests", "test_email_agent.py"),
        os.path.join(BASE_DIR, "tests", "test_health_agent.py"),
        os.path.join(BASE_DIR, "tests", "test_social_agent.py"),
        os.path.join(BASE_DIR, "tests", "test_logos_gate.py"),
        os.path.join(BASE_DIR, "tests", "test_researcher_web_search.py"),
        os.path.join(BASE_DIR, "tests", "test_researcher_google_docs.py"),
        os.path.join(BASE_DIR, "tests", "test_researcher_drive_pdfs.py"),
        os.path.join(BASE_DIR, "tests", "test_ingest_sources_append.py"),
        os.path.join(BASE_DIR, "tests", "test_gmail_ingest.py"),
    ]
    exit_code = 0
    for t in tests:
        code = _run([sys.executable, t])
        if code != 0:
            exit_code = code
    return exit_code


def cmd_promote(args: argparse.Namespace) -> int:
    cmd = [
        sys.executable,
        os.path.join(BASE_DIR, "scripts", "promote_memory.py"),
    ]
    if args.since:
        cmd += ["--since", args.since]
    if args.count is not None:
        cmd += ["--count", str(args.count)]
    if args.output:
        cmd += ["--output", args.output]
    if args.template:
        cmd += ["--template", args.template]
    if args.rubric:
        cmd += ["--rubric", args.rubric]
    return _run(cmd)


def main() -> int:
    parser = argparse.ArgumentParser(description="Permanence OS CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    run_p = sub.add_parser("run", help="Run governed task workflow")
    run_p.add_argument("goal", help="Task goal")
    run_p.add_argument("--sources", help="Override sources.json path")
    run_p.add_argument("--draft", help="Override draft.md path")
    run_p.add_argument(
        "--allow-single-source",
        action="store_true",
        help="Allow proceeding with a single source (override logged)",
    )
    run_p.set_defaults(func=cmd_run)

    add_p = sub.add_parser("add-source", help="Append a source provenance entry")
    add_p.add_argument("source", help="Source identifier or URL")
    add_p.add_argument("confidence", type=float, help="Confidence (0-1)")
    add_p.add_argument("notes", nargs="?", default="", help="Optional notes")
    add_p.set_defaults(func=cmd_add_source)

    status_p = sub.add_parser("status", help="Show system status")
    status_p.set_defaults(func=cmd_status)

    clean_p = sub.add_parser("clean", help="Clean artifacts")
    clean_p.add_argument("--logs", action="store_true")
    clean_p.add_argument("--episodic", action="store_true")
    clean_p.add_argument("--outputs", action="store_true")
    clean_p.add_argument("--all", action="store_true")
    clean_p.set_defaults(func=cmd_clean)

    test_p = sub.add_parser("test", help="Run test suite")
    test_p.set_defaults(func=cmd_test)

    ingest_p = sub.add_parser("ingest", help="Ingest tool outputs into sources.json")
    ingest_p.add_argument("--tool-dir", help="Tool memory directory")
    ingest_p.add_argument("--output", help="Output sources.json path")
    ingest_p.add_argument("--confidence", type=float, default=0.5, help="Default confidence")
    ingest_p.add_argument("--max", type=int, default=100, help="Max entries")
    ingest_p.set_defaults(
        func=lambda args: _run(
            [
                sys.executable,
                os.path.join(BASE_DIR, "scripts", "ingest_tool_outputs.py"),
                *(["--tool-dir", args.tool_dir] if args.tool_dir else []),
                *(["--output", args.output] if args.output else []),
                *(["--confidence", str(args.confidence)] if args.confidence else []),
                *(["--max", str(args.max)] if args.max else []),
            ]
        )
    )

    docs_p = sub.add_parser("ingest-docs", help="Ingest documents into sources.json")
    docs_p.add_argument("--doc-dir", help="Document directory")
    docs_p.add_argument("--output", help="Output sources.json path")
    docs_p.add_argument("--confidence", type=float, default=0.6, help="Default confidence")
    docs_p.add_argument("--max", type=int, default=100, help="Max entries")
    docs_p.add_argument("--excerpt", type=int, default=280, help="Excerpt length")
    docs_p.set_defaults(
        func=lambda args: _run(
            [
                sys.executable,
                os.path.join(BASE_DIR, "scripts", "ingest_documents.py"),
                *(["--doc-dir", args.doc_dir] if args.doc_dir else []),
                *(["--output", args.output] if args.output else []),
                *(["--confidence", str(args.confidence)] if args.confidence else []),
                *(["--max", str(args.max)] if args.max else []),
                *(["--excerpt", str(args.excerpt)] if args.excerpt else []),
            ]
        )
    )

    ingest_sources_p = sub.add_parser("ingest-sources", help="Ingest sources via adapter registry")
    ingest_sources_p.add_argument("--adapter", default="tool_memory", help="Adapter name")
    ingest_sources_p.add_argument("--list", action="store_true", help="List adapters")
    ingest_sources_p.add_argument("--query", help="Search query (web_search adapter)")
    ingest_sources_p.add_argument("--urls", nargs="*", help="URLs to fetch (url_fetch adapter)")
    ingest_sources_p.add_argument("--urls-path", help="File containing URLs (url_fetch adapter)")
    ingest_sources_p.add_argument("--doc-ids", nargs="*", help="Google Doc IDs (google_docs adapter)")
    ingest_sources_p.add_argument("--doc-ids-path", help="File containing Google Doc IDs")
    ingest_sources_p.add_argument("--folder-id", help="Google Drive folder ID (google_docs adapter)")
    ingest_sources_p.add_argument("--file-ids", nargs="*", help="Google Drive file IDs (drive_pdfs adapter)")
    ingest_sources_p.add_argument("--file-ids-path", help="File containing Drive file IDs (drive_pdfs adapter)")
    ingest_sources_p.add_argument("--credentials", help="Google OAuth credentials.json path")
    ingest_sources_p.add_argument("--token", help="Google OAuth token.json path")
    ingest_sources_p.add_argument("--cursor", help="Cursor file path (resume processed IDs)")
    ingest_sources_p.add_argument("--resume", action="store_true", help="Resume using default cursor file")
    ingest_sources_p.add_argument("--max-seconds", type=int, default=25, help="Per-file max seconds (Drive PDFs)")
    ingest_sources_p.add_argument("--max-pdf-bytes", type=int, default=8_000_000, help="Skip PDFs larger than this size")
    ingest_sources_p.add_argument("--max-doc-chars", type=int, default=50_000, help="Max chars per Google Doc")
    ingest_sources_p.add_argument("--max-seen", type=int, default=5000, help="Max IDs to keep in cursor")
    ingest_sources_p.add_argument("--skip-failures", action="store_true", help="Mark failed items as processed")
    ingest_sources_p.add_argument("--tool-dir", help="Tool memory directory")
    ingest_sources_p.add_argument("--doc-dir", help="Documents directory")
    ingest_sources_p.add_argument("--output", help="Output sources.json path")
    ingest_sources_p.add_argument("--append", action="store_true", help="Append to existing sources.json")
    ingest_sources_p.add_argument("--confidence", type=float, default=0.5, help="Default confidence")
    ingest_sources_p.add_argument("--max", type=int, default=100, help="Max entries")
    ingest_sources_p.add_argument("--excerpt", type=int, default=280, help="Excerpt length")
    ingest_sources_p.add_argument("--timeout", type=int, default=20, help="Timeout (seconds)")
    ingest_sources_p.add_argument("--url-timeout", type=int, default=15, help="URL fetch timeout (seconds)")
    ingest_sources_p.add_argument("--max-bytes", type=int, default=1_000_000, help="Max bytes per URL")
    ingest_sources_p.add_argument("--user-agent", default="PermanenceOS-Researcher/0.2", help="URL fetch user agent")
    ingest_sources_p.set_defaults(
        func=lambda args: _run(
            [
                sys.executable,
                os.path.join(BASE_DIR, "scripts", "ingest_sources.py"),
                "--adapter",
                args.adapter,
                *(["--list"] if args.list else []),
                *(["--query", args.query] if args.query else []),
                *(["--urls"] + args.urls if args.urls else []),
                *(["--urls-path", args.urls_path] if args.urls_path else []),
                *(["--doc-ids"] + args.doc_ids if args.doc_ids else []),
                *(["--doc-ids-path", args.doc_ids_path] if args.doc_ids_path else []),
                *(["--folder-id", args.folder_id] if args.folder_id else []),
                *(["--file-ids"] + args.file_ids if args.file_ids else []),
                *(["--file-ids-path", args.file_ids_path] if args.file_ids_path else []),
                *(["--credentials", args.credentials] if args.credentials else []),
                *(["--token", args.token] if args.token else []),
                *(["--cursor", args.cursor] if args.cursor else []),
                *(["--resume"] if args.resume else []),
                *(["--max-seconds", str(args.max_seconds)] if args.max_seconds else []),
                *(["--max-pdf-bytes", str(args.max_pdf_bytes)] if args.max_pdf_bytes else []),
                *(["--max-doc-chars", str(args.max_doc_chars)] if args.max_doc_chars else []),
                *(["--max-seen", str(args.max_seen)] if args.max_seen else []),
                *(["--skip-failures"] if args.skip_failures else []),
                *(["--tool-dir", args.tool_dir] if args.tool_dir else []),
                *(["--doc-dir", args.doc_dir] if args.doc_dir else []),
                *(["--output", args.output] if args.output else []),
                *(["--append"] if args.append else []),
                *(["--confidence", str(args.confidence)] if args.confidence else []),
                *(["--max", str(args.max)] if args.max else []),
                *(["--excerpt", str(args.excerpt)] if args.excerpt else []),
                *(["--timeout", str(args.timeout)] if args.timeout else []),
                *(["--url-timeout", str(args.url_timeout)] if args.url_timeout else []),
                *(["--max-bytes", str(args.max_bytes)] if args.max_bytes else []),
                *(["--user-agent", args.user_agent] if args.user_agent else []),
            ]
        )
    )

    ingest_drive_all_p = sub.add_parser(
        "ingest-drive-all",
        help="Batch ingest Drive PDFs + Docs with resume",
    )
    ingest_drive_all_p.add_argument("--folder-id", required=True, help="Google Drive folder ID")
    ingest_drive_all_p.add_argument("--max", type=int, default=10, help="Max items per batch")
    ingest_drive_all_p.add_argument("--max-batches", type=int, default=0, help="Stop after N batches (0 = no limit)")
    ingest_drive_all_p.add_argument("--sleep", type=int, default=2, help="Seconds between batches")
    ingest_drive_all_p.add_argument("--max-seconds", type=int, default=25, help="Per-file max seconds")
    ingest_drive_all_p.add_argument("--max-pdf-bytes", type=int, default=8_000_000, help="Skip PDFs larger than this size")
    ingest_drive_all_p.add_argument("--max-doc-chars", type=int, default=50_000, help="Max chars per Google Doc")
    ingest_drive_all_p.add_argument("--skip-failures", action="store_true", help="Mark failed items as processed")
    ingest_drive_all_p.set_defaults(
        func=lambda args: _run(
            [
                sys.executable,
                os.path.join(BASE_DIR, "scripts", "ingest_drive_all.py"),
                "--folder-id",
                args.folder_id,
                "--max",
                str(args.max),
                "--max-batches",
                str(args.max_batches),
                "--sleep",
                str(args.sleep),
                "--max-seconds",
                str(args.max_seconds),
                "--max-pdf-bytes",
                str(args.max_pdf_bytes),
                "--max-doc-chars",
                str(args.max_doc_chars),
                *(["--skip-failures"] if args.skip_failures else []),
            ]
        )
    )

    sources_digest_p = sub.add_parser("sources-digest", help="Generate a sources digest (no LLM)")
    sources_digest_p.set_defaults(
        func=lambda _args: _run(
            [
                sys.executable,
                os.path.join(BASE_DIR, "scripts", "sources_digest.py"),
            ]
        )
    )

    sources_brief_p = sub.add_parser("sources-brief", help="Generate a sources synthesis brief (no LLM)")
    sources_brief_p.set_defaults(
        func=lambda _args: _run(
            [
                sys.executable,
                os.path.join(BASE_DIR, "scripts", "sources_brief.py"),
            ]
        )
    )

    synth_p = sub.add_parser("synthesis-brief", help="Generate governed synthesis brief (draft + approval)")
    synth_p.add_argument("--days", type=int, default=30, choices=[7, 30, 90], help="Lookback window")
    synth_p.add_argument("--max-sources", type=int, default=50, help="Max sources to include")
    synth_p.add_argument("--no-prompt", action="store_true", help="Skip approval prompt (draft only)")
    synth_p.add_argument("--approve", action="store_true", help="Auto-approve draft to final")
    synth_p.set_defaults(
        func=lambda args: _run(
            [
                sys.executable,
                os.path.join(BASE_DIR, "scripts", "synthesis_brief.py"),
                "--days",
                str(args.days),
                "--max-sources",
                str(args.max_sources),
                *(["--no-prompt"] if args.no_prompt else []),
                *(["--approve"] if args.approve else []),
            ]
        )
    )

    notebook_p = sub.add_parser("notebooklm-sync", help="Sync NotebookLM exports from Drive")
    notebook_p.add_argument("--folder-id", help="Google Drive folder ID")
    notebook_p.add_argument("--credentials", help="Google OAuth credentials.json path")
    notebook_p.add_argument("--token", help="Google OAuth token path")
    notebook_p.add_argument("--cursor", help="Cursor file path")
    notebook_p.add_argument("--max-files", type=int, default=50, help="Max files per run")
    notebook_p.add_argument("--max-seconds", type=int, default=120, help="Max seconds per run")
    notebook_p.add_argument("--max-bytes", type=int, default=25_000_000, help="Skip files larger than this")
    notebook_p.add_argument("--split-max-chars", type=int, default=40_000, help="Max chars per split part")
    notebook_p.set_defaults(
        func=lambda args: _run(
            [
                sys.executable,
                os.path.join(BASE_DIR, "scripts", "notebooklm_sync.py"),
                *(["--folder-id", args.folder_id] if args.folder_id else []),
                *(["--credentials", args.credentials] if args.credentials else []),
                *(["--token", args.token] if args.token else []),
                *(["--cursor", args.cursor] if args.cursor else []),
                "--max-files",
                str(args.max_files),
                "--max-seconds",
                str(args.max_seconds),
                "--max-bytes",
                str(args.max_bytes),
                "--split-max-chars",
                str(args.split_max_chars),
            ]
        )
    )

    promote_p = sub.add_parser("promote", help="Generate Canon change draft from episodic memory")
    promote_p.add_argument("--since", help="ISO date/time filter (UTC)")
    promote_p.add_argument("--count", type=int, help="Limit to N most recent episodes")
    promote_p.add_argument("--output", help="Output markdown path")
    promote_p.add_argument("--template", help="Template path override")
    promote_p.add_argument("--rubric", help="Rubric path override")
    promote_p.set_defaults(func=cmd_promote)

    review_p = sub.add_parser("promotion-review", help="Generate Canon promotion review checklist")
    review_p.add_argument("--output", help="Output markdown path")
    review_p.add_argument("--min-count", type=int, default=2, help="Minimum queue size")
    review_p.add_argument("--rubric", help="Rubric path")
    review_p.set_defaults(
        func=lambda args: _run(
            [
                sys.executable,
                os.path.join(BASE_DIR, "scripts", "promotion_review.py"),
                *(["--output", args.output] if args.output else []),
                *(["--min-count", str(args.min_count)] if args.min_count else []),
                *(["--rubric", args.rubric] if args.rubric else []),
            ]
        )
    )

    queue_p = sub.add_parser("queue", help="Manage Canon promotion queue")
    queue_p.add_argument("queue_args", nargs=argparse.REMAINDER)
    queue_p.set_defaults(
        func=lambda args: _run(
            [sys.executable, os.path.join(BASE_DIR, "scripts", "promotion_queue.py")]
            + args.queue_args
        )
    )

    hr_p = sub.add_parser("hr-report", help="Generate weekly HR system health report")
    hr_p.add_argument("--output", help="Output report path")
    hr_p.set_defaults(
        func=lambda args: _run(
            [
                sys.executable,
                os.path.join(BASE_DIR, "scripts", "hr_report.py"),
                *(["--output", args.output] if args.output else []),
            ]
        )
    )

    briefing_p = sub.add_parser("briefing", help="Run Briefing Agent and write output")
    briefing_p.add_argument("--output", help="Output report path")
    briefing_p.set_defaults(
        func=lambda args: _run(
            [
                sys.executable,
                os.path.join(BASE_DIR, "scripts", "briefing_run.py"),
                *(["--output", args.output] if args.output else []),
            ]
        )
    )

    email_p = sub.add_parser("email-triage", help="Run Email Agent triage")
    email_p.add_argument("--inbox-dir", help="Inbox directory")
    email_p.add_argument("--vip", nargs="*", default=[], help="VIP sender emails")
    email_p.add_argument("--ignore", nargs="*", default=[], help="Ignored sender emails")
    email_p.add_argument("--max-items", type=int, default=25, help="Max items to include")
    email_p.set_defaults(
        func=lambda args: _run(
            [
                sys.executable,
                os.path.join(BASE_DIR, "scripts", "email_triage.py"),
                *(["--inbox-dir", args.inbox_dir] if args.inbox_dir else []),
                *(["--vip"] + args.vip if args.vip else []),
                *(["--ignore"] + args.ignore if args.ignore else []),
                *(["--max-items", str(args.max_items)] if args.max_items else []),
            ]
        )
    )

    gmail_p = sub.add_parser("gmail-ingest", help="Ingest Gmail messages (read-only)")
    gmail_p.add_argument("--credentials", help="OAuth credentials.json path")
    gmail_p.add_argument("--token", help="OAuth token.json path")
    gmail_p.add_argument("--output", help="Output inbox json path")
    gmail_p.add_argument("--max", type=int, default=50, help="Max messages to fetch")
    gmail_p.add_argument("--query", help="Gmail search query")
    gmail_p.set_defaults(
        func=lambda args: _run(
            [
                sys.executable,
                os.path.join(BASE_DIR, "scripts", "gmail_ingest.py"),
                *(["--credentials", args.credentials] if args.credentials else []),
                *(["--token", args.token] if args.token else []),
                *(["--output", args.output] if args.output else []),
                *(["--max", str(args.max)] if args.max else []),
                *(["--query", args.query] if args.query else []),
            ]
        )
    )

    health_p = sub.add_parser("health-summary", help="Run Health Agent summary")
    health_p.add_argument("--data-dir", help="Health data directory")
    health_p.add_argument("--max-days", type=int, default=14, help="Max days to analyze")
    health_p.set_defaults(
        func=lambda args: _run(
            [
                sys.executable,
                os.path.join(BASE_DIR, "scripts", "health_summary.py"),
                *(["--data-dir", args.data_dir] if args.data_dir else []),
                *(["--max-days", str(args.max_days)] if args.max_days else []),
            ]
        )
    )

    social_p = sub.add_parser("social-summary", help="Run Social Agent summary or save draft")
    social_p.add_argument("--queue-dir", help="Social queue directory")
    social_p.add_argument("--max-items", type=int, default=20, help="Max items to include")
    social_p.add_argument("--draft-title", help="Draft title")
    social_p.add_argument("--draft-body", help="Draft body")
    social_p.add_argument("--draft-platform", help="Draft platform")
    social_p.add_argument("--draft-tag", action="append", default=[], help="Draft tags (repeatable)")
    social_p.set_defaults(
        func=lambda args: _run(
            [
                sys.executable,
                os.path.join(BASE_DIR, "scripts", "social_summary.py"),
                *(["--queue-dir", args.queue_dir] if args.queue_dir else []),
                *(["--max-items", str(args.max_items)] if args.max_items else []),
                *(["--draft-title", args.draft_title] if args.draft_title else []),
                *(["--draft-body", args.draft_body] if args.draft_body else []),
                *(["--draft-platform", args.draft_platform] if args.draft_platform else []),
                *([arg for tag in args.draft_tag for arg in ("--draft-tag", tag)] if args.draft_tag else []),
            ]
        )
    )

    logos_p = sub.add_parser("logos-gate", help="Evaluate Logos Praktikos activation tiers")
    logos_p.add_argument("--output", help="Output report path")
    logos_p.set_defaults(
        func=lambda args: _run(
            [
                sys.executable,
                os.path.join(BASE_DIR, "scripts", "logos_gate.py"),
                *(["--output", args.output] if args.output else []),
            ]
        )
    )

    dash_p = sub.add_parser("dashboard", help="Generate dashboard report")
    dash_p.add_argument("--output", help="Output report path")
    dash_p.set_defaults(
        func=lambda args: _run(
            [
                sys.executable,
                os.path.join(BASE_DIR, "scripts", "dashboard_report.py"),
                *(["--output", args.output] if args.output else []),
            ]
        )
    )

    snap_p = sub.add_parser("snapshot", help="Generate aggregated system snapshot")
    snap_p.set_defaults(
        func=lambda _args: _run([sys.executable, os.path.join(BASE_DIR, "scripts", "system_snapshot.py")])
    )

    oc_p = sub.add_parser("openclaw-status", help="Fetch OpenClaw status/health output")
    oc_p.add_argument("--health", action="store_true", help="Run openclaw health instead of status")
    oc_p.add_argument("--output", help="Write output to path (default: outputs/...)")
    oc_p.set_defaults(
        func=lambda args: _run(
            [
                sys.executable,
                os.path.join(BASE_DIR, "scripts", "openclaw_status.py"),
                *(["--health"] if args.health else []),
                *(["--output", args.output] if args.output else []),
            ]
        )
    )

    sync_p = sub.add_parser("openclaw-sync", help="Run OpenClaw health sync job")
    sync_p.add_argument("--interval", type=int, default=60, help="Poll interval in seconds")
    sync_p.add_argument("--once", action="store_true", help="Single check then exit")
    sync_p.set_defaults(
        func=lambda args: _run(
            [
                sys.executable,
                os.path.join(BASE_DIR, "scripts", "openclaw_health_sync.py"),
                *(["--interval", str(args.interval)] if args.interval else []),
                *(["--once"] if args.once else []),
            ]
        )
    )

    clean_weekly_p = sub.add_parser("cleanup-weekly", help="Weekly cleanup with retention")
    clean_weekly_p.add_argument("--outputs-days", type=int, default=14)
    clean_weekly_p.add_argument("--tool-days", type=int, default=14)
    clean_weekly_p.add_argument("--log-days", type=int, default=30)
    clean_weekly_p.set_defaults(
        func=lambda args: _run(
            [
                sys.executable,
                os.path.join(BASE_DIR, "scripts", "cleanup_weekly.py"),
                "--outputs-days",
                str(args.outputs_days),
                "--tool-days",
                str(args.tool_days),
                "--log-days",
                str(args.log_days),
            ]
        )
    )

    git_auto_p = sub.add_parser("git-autocommit", help="Auto-commit tracked changes")
    git_auto_p.add_argument("--message", help="Commit message")
    git_auto_p.set_defaults(
        func=lambda args: _run(
            [
                sys.executable,
                os.path.join(BASE_DIR, "scripts", "git_autocommit.py"),
                "--repo",
                BASE_DIR,
                *(["--message", args.message] if args.message else []),
            ]
        )
    )
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
