#!/usr/bin/env python3
"""
Unified CLI for Permanence OS.
Commands: run, add-source, status, clean, test, ingest, ingest-docs, ingest-sources, ingest-drive-all, sources-digest, sources-brief, synthesis-brief, notebooklm-sync, automation-verify, automation-report, reliability-watch, reliability-gate, reliability-streak, phase-gate, status-glance, dell-cutover-verify, dell-remote, remote-ready, promote, promotion-review, promotion-daily, queue, hr-report, briefing, ari-reception, sandra-reception, research-inbox, email-triage, gmail-ingest, health-summary, social-summary, logos-gate, dashboard, command-center, snapshot, v04-snapshot, openclaw-status, openclaw-sync, organize-files, cleanup-weekly, git-autocommit, git-sync, chronicle-backfill, chronicle-capture, chronicle-report, chronicle-publish
"""

import argparse
import os
import subprocess
import sys

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__)))


def _run(cmd: list[str]) -> int:
    env = os.environ.copy()
    current = env.get("PYTHONPATH", "")
    paths = [p for p in current.split(os.pathsep) if p]
    if BASE_DIR not in paths:
        env["PYTHONPATH"] = os.pathsep.join([BASE_DIR, *paths]) if paths else BASE_DIR
    return subprocess.call(cmd, cwd=BASE_DIR, env=env)


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
        os.path.join(BASE_DIR, "tests", "test_promotion_queue_auto.py"),
        os.path.join(BASE_DIR, "tests", "test_promotion_review.py"),
        os.path.join(BASE_DIR, "tests", "test_promotion_daily.py"),
        os.path.join(BASE_DIR, "tests", "test_hr_agent.py"),
        os.path.join(BASE_DIR, "tests", "test_episodic_memory.py"),
        os.path.join(BASE_DIR, "tests", "test_openclaw_health_sync.py"),
        os.path.join(BASE_DIR, "tests", "test_briefing_run.py"),
        os.path.join(BASE_DIR, "tests", "test_v03_components.py"),
        os.path.join(BASE_DIR, "tests", "test_interface_agent.py"),
        os.path.join(BASE_DIR, "tests", "test_practice_squad.py"),
        os.path.join(BASE_DIR, "tests", "test_arcana_engine.py"),
        os.path.join(BASE_DIR, "tests", "test_sibling_dynamics.py"),
        os.path.join(BASE_DIR, "tests", "test_synthesis_brief.py"),
        os.path.join(BASE_DIR, "tests", "test_v04_snapshot.py"),
        os.path.join(BASE_DIR, "tests", "test_automation_reporting.py"),
        os.path.join(BASE_DIR, "tests", "test_reliability_gate.py"),
        os.path.join(BASE_DIR, "tests", "test_reliability_streak.py"),
        os.path.join(BASE_DIR, "tests", "test_phase_gate.py"),
        os.path.join(BASE_DIR, "tests", "test_status_glance.py"),
        os.path.join(BASE_DIR, "tests", "test_dell_cutover_verify.py"),
        os.path.join(BASE_DIR, "tests", "test_dell_remote.py"),
        os.path.join(BASE_DIR, "tests", "test_ari_reception.py"),
        os.path.join(BASE_DIR, "tests", "test_email_agent.py"),
        os.path.join(BASE_DIR, "tests", "test_health_agent.py"),
        os.path.join(BASE_DIR, "tests", "test_social_agent.py"),
        os.path.join(BASE_DIR, "tests", "test_logos_gate.py"),
        os.path.join(BASE_DIR, "tests", "test_researcher_web_search.py"),
        os.path.join(BASE_DIR, "tests", "test_researcher_google_docs.py"),
        os.path.join(BASE_DIR, "tests", "test_researcher_drive_pdfs.py"),
        os.path.join(BASE_DIR, "tests", "test_ingest_sources_append.py"),
        os.path.join(BASE_DIR, "tests", "test_gmail_ingest.py"),
        os.path.join(BASE_DIR, "tests", "test_research_inbox.py"),
        os.path.join(BASE_DIR, "tests", "test_file_organizer.py"),
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

    server_p = sub.add_parser("server", help="Start Interface Agent listener")
    server_p.add_argument("--host", default="127.0.0.1", help="Bind host")
    server_p.add_argument("--port", type=int, default=8000, help="Bind port")
    server_p.add_argument("--max-payload-bytes", type=int, default=64_000, help="Payload cap")
    server_p.set_defaults(
        func=lambda args: _run(
            [
                sys.executable,
                os.path.join(BASE_DIR, "scripts", "interface_server.py"),
                "--host",
                args.host,
                "--port",
                str(args.port),
                "--max-payload-bytes",
                str(args.max_payload_bytes),
            ]
        )
    )

    scrimmage_p = sub.add_parser("scrimmage", help="Run Practice Squad scrimmage")
    scrimmage_p.add_argument("--last-hours", type=int, default=24, help="Lookback window")
    scrimmage_p.add_argument("--replays", type=int, default=10, help="Replay count per entry")
    scrimmage_p.set_defaults(
        func=lambda args: _run(
            [
                sys.executable,
                os.path.join(BASE_DIR, "scripts", "practice_squad_run.py"),
                "--mode",
                "scrimmage",
                "--last-hours",
                str(args.last_hours),
                "--replays",
                str(args.replays),
            ]
        )
    )

    looking_glass_p = sub.add_parser("looking-glass", help="Run Arcana looking-glass projection")
    looking_glass_p.add_argument("query", nargs="?", help="Query/context text (positional)")
    looking_glass_p.add_argument("--query", dest="query_flag", help="Query/context text (flag)")
    looking_glass_p.add_argument("--branches", type=int, default=3, help="Branch count")
    looking_glass_p.set_defaults(
        func=lambda args: _run(
            [
                sys.executable,
                os.path.join(BASE_DIR, "scripts", "arcana_cli.py"),
                "--mode",
                "looking-glass",
                "--query",
                (args.query_flag or args.query or ""),
                "--branches",
                str(args.branches),
            ]
        )
    )

    hyper_sim_p = sub.add_parser("hyper-sim", help="Run Practice Squad hyper simulation")
    hyper_sim_p.add_argument("--iterations", type=int, default=10000, help="Iteration count")
    hyper_sim_p.add_argument("--last-hours", type=int, default=24, help="Lookback window")
    hyper_sim_p.add_argument("--warp-speed", action="store_true", help="Enable warp speed")
    hyper_sim_p.set_defaults(
        func=lambda args: _run(
            [
                sys.executable,
                os.path.join(BASE_DIR, "scripts", "practice_squad_run.py"),
                "--mode",
                "hyper-sim",
                "--iterations",
                str(args.iterations),
                "--last-hours",
                str(args.last_hours),
                *(["--warp-speed"] if args.warp_speed else []),
            ]
        )
    )

    arcana_p = sub.add_parser("arcana", help="Arcana Engine actions")
    arcana_p.add_argument("action", choices=["scan"], help="Arcana action")
    arcana_p.add_argument("--last", type=int, default=50, help="Entry count for scan")
    arcana_p.set_defaults(
        func=lambda args: _run(
            [
                sys.executable,
                os.path.join(BASE_DIR, "scripts", "arcana_cli.py"),
                "--mode",
                args.action,
                "--last",
                str(args.last),
            ]
        )
    )

    automation_verify_p = sub.add_parser("automation-verify", help="Verify launchd schedule + load state")
    automation_verify_p.add_argument("--label", default="com.permanence.briefing", help="Launchd label")
    automation_verify_p.add_argument("--plist", help="LaunchAgent plist path")
    automation_verify_p.set_defaults(
        func=lambda args: _run(
            [
                sys.executable,
                os.path.join(BASE_DIR, "scripts", "automation_verify.py"),
                *(["--label", args.label] if args.label else []),
                *(["--plist", args.plist] if args.plist else []),
            ]
        )
    )

    automation_report_p = sub.add_parser("automation-report", help="Generate automation daily report")
    automation_report_p.add_argument("--days", type=int, default=1, help="Lookback window in days")
    automation_report_p.add_argument("--label", default="com.permanence.briefing", help="Launchd label")
    automation_report_p.add_argument("--log-dir", help="Automation log directory")
    automation_report_p.add_argument("--output", help="Output markdown path")
    automation_report_p.set_defaults(
        func=lambda args: _run(
            [
                sys.executable,
                os.path.join(BASE_DIR, "scripts", "automation_daily_report.py"),
                *(["--days", str(args.days)] if args.days else []),
                *(["--label", args.label] if args.label else []),
                *(["--log-dir", args.log_dir] if args.log_dir else []),
                *(["--output", args.output] if args.output else []),
            ]
        )
    )

    reliability_watch_p = sub.add_parser(
        "reliability-watch",
        help="7-day background reliability watcher (failure-only alerts)",
    )
    reliability_watch_p.add_argument("--arm", action="store_true", help="Start watch and install background agent")
    reliability_watch_p.add_argument("--disarm", action="store_true", help="Stop watch and remove background agent")
    reliability_watch_p.add_argument("--start", action="store_true", help="Start watch window only")
    reliability_watch_p.add_argument("--check", action="store_true", help="Run one check pass")
    reliability_watch_p.add_argument("--status", action="store_true", help="Show watch status")
    reliability_watch_p.add_argument("--stop", action="store_true", help="Stop watch (state only)")
    reliability_watch_p.add_argument("--install-agent", action="store_true", help="Install watcher launch agent")
    reliability_watch_p.add_argument("--uninstall-agent", action="store_true", help="Remove watcher launch agent")
    reliability_watch_p.add_argument("--force", action="store_true", help="Force restart on --start/--arm")
    reliability_watch_p.add_argument("--days", type=int, default=7, help="Watch duration in days")
    reliability_watch_p.add_argument("--slots", default="7,12,19", help="Comma-separated slot hours")
    reliability_watch_p.add_argument(
        "--tolerance-minutes",
        type=int,
        default=90,
        help="Allowed drift from each slot",
    )
    reliability_watch_p.add_argument(
        "--check-interval-minutes",
        type=int,
        default=30,
        help="Background check interval",
    )
    reliability_watch_p.add_argument("--state-file", help="Watcher state file path")
    reliability_watch_p.add_argument("--log-dir", help="Automation run log directory")
    reliability_watch_p.add_argument("--alert-log", help="Failure/completion alert log path")
    reliability_watch_p.add_argument("--plist-path", help="LaunchAgent plist path")
    reliability_watch_p.add_argument(
        "--no-immediate-check",
        action="store_true",
        help="Do not run immediate check after --arm",
    )
    reliability_watch_p.set_defaults(
        func=lambda args: _run(
            [
                sys.executable,
                os.path.join(BASE_DIR, "scripts", "reliability_watch.py"),
                *(["--arm"] if args.arm else []),
                *(["--disarm"] if args.disarm else []),
                *(["--start"] if args.start else []),
                *(["--check"] if args.check else []),
                *(["--status"] if args.status else []),
                *(["--stop"] if args.stop else []),
                *(["--install-agent"] if args.install_agent else []),
                *(["--uninstall-agent"] if args.uninstall_agent else []),
                *(["--force"] if args.force else []),
                *(["--days", str(args.days)] if args.days else []),
                *(["--slots", args.slots] if args.slots else []),
                *(["--tolerance-minutes", str(args.tolerance_minutes)] if args.tolerance_minutes else []),
                *(
                    ["--check-interval-minutes", str(args.check_interval_minutes)]
                    if args.check_interval_minutes
                    else []
                ),
                *(["--state-file", args.state_file] if args.state_file else []),
                *(["--log-dir", args.log_dir] if args.log_dir else []),
                *(["--alert-log", args.alert_log] if args.alert_log else []),
                *(["--plist-path", args.plist_path] if args.plist_path else []),
                *(["--no-immediate-check"] if args.no_immediate_check else []),
            ]
        )
    )

    reliability_gate_p = sub.add_parser(
        "reliability-gate",
        help="Enforce strict automation reliability gate",
    )
    reliability_gate_p.add_argument("--days", type=int, default=7, help="Number of days to evaluate")
    reliability_gate_p.add_argument(
        "--slots",
        default="7,12,19",
        help="Comma-separated scheduled hours (local time)",
    )
    reliability_gate_p.add_argument(
        "--tolerance-minutes",
        type=int,
        default=90,
        help="Allowed drift from each slot",
    )
    reliability_gate_p.add_argument(
        "--require-notebooklm",
        action="store_true",
        help="Require NotebookLM status=0 for slot pass",
    )
    reliability_gate_p.add_argument(
        "--include-today",
        action="store_true",
        help="Include current day in the evaluation window",
    )
    reliability_gate_p.add_argument("--log-dir", help="Automation log directory")
    reliability_gate_p.add_argument("--output", help="Output report path")
    reliability_gate_p.set_defaults(
        func=lambda args: _run(
            [
                sys.executable,
                os.path.join(BASE_DIR, "scripts", "reliability_gate.py"),
                *(["--days", str(args.days)] if args.days else []),
                *(["--slots", args.slots] if args.slots else []),
                *(["--tolerance-minutes", str(args.tolerance_minutes)] if args.tolerance_minutes else []),
                *(["--require-notebooklm"] if args.require_notebooklm else []),
                *(["--include-today"] if args.include_today else []),
                *(["--log-dir", args.log_dir] if args.log_dir else []),
                *(["--output", args.output] if args.output else []),
            ]
        )
    )

    reliability_streak_p = sub.add_parser(
        "reliability-streak",
        help="View or update reliability streak",
    )
    reliability_streak_p.add_argument("--update", action="store_true", help="Update streak mode")
    reliability_streak_p.add_argument("--status", type=int, choices=[0, 1], help="Gate status code")
    reliability_streak_p.add_argument("--date", help="Date override (YYYY-MM-DD)")
    reliability_streak_p.set_defaults(
        func=lambda args: _run(
            [
                sys.executable,
                os.path.join(BASE_DIR, "scripts", "reliability_streak.py"),
                *(["--update"] if args.update else []),
                *(["--status", str(args.status)] if args.status is not None else []),
                *(["--date", args.date] if args.date else []),
            ]
        )
    )

    phase_gate_p = sub.add_parser(
        "phase-gate",
        help="Enforce weekly phase gate (strict reliability + streak)",
    )
    phase_gate_p.add_argument("--days", type=int, default=7, help="Reliability window days")
    phase_gate_p.add_argument(
        "--slots",
        default="7,12,19",
        help="Comma-separated scheduled hours (local time)",
    )
    phase_gate_p.add_argument(
        "--tolerance-minutes",
        type=int,
        default=90,
        help="Allowed drift from each slot",
    )
    phase_gate_p.add_argument(
        "--require-notebooklm",
        action="store_true",
        help="Require NotebookLM status=0 for slot pass",
    )
    phase_gate_p.add_argument(
        "--include-today",
        action="store_true",
        help="Include current day in the reliability window",
    )
    phase_gate_p.add_argument(
        "--target-streak",
        type=int,
        default=7,
        help="Required consecutive-pass days",
    )
    phase_gate_p.add_argument("--log-dir", help="Automation log directory")
    phase_gate_p.add_argument("--streak-file", help="Reliability streak JSON path")
    phase_gate_p.add_argument("--output", help="Output report path")
    phase_gate_p.set_defaults(
        func=lambda args: _run(
            [
                sys.executable,
                os.path.join(BASE_DIR, "scripts", "phase_gate.py"),
                *(["--days", str(args.days)] if args.days else []),
                *(["--slots", args.slots] if args.slots else []),
                *(["--tolerance-minutes", str(args.tolerance_minutes)] if args.tolerance_minutes else []),
                *(["--require-notebooklm"] if args.require_notebooklm else []),
                *(["--include-today"] if args.include_today else []),
                *(["--target-streak", str(args.target_streak)] if args.target_streak else []),
                *(["--log-dir", args.log_dir] if args.log_dir else []),
                *(["--streak-file", args.streak_file] if args.streak_file else []),
                *(["--output", args.output] if args.output else []),
            ]
        )
    )

    status_glance_p = sub.add_parser(
        "status-glance",
        help="Write one-line glance status file (text + json)",
    )
    status_glance_p.add_argument("--log-dir", help="Directory containing phase/reliability logs")
    status_glance_p.add_argument("--automation-log-dir", help="Directory containing run_*.log")
    status_glance_p.add_argument("--streak-file", help="Path to reliability_streak.json")
    status_glance_p.add_argument("--slots", default="7,12,19", help="Comma-separated slot hours")
    status_glance_p.add_argument("--tolerance-minutes", type=int, default=90, help="Allowed slot drift")
    status_glance_p.add_argument("--output", help="One-line status output path")
    status_glance_p.add_argument("--json-output", help="JSON status output path")
    status_glance_p.set_defaults(
        func=lambda args: _run(
            [
                sys.executable,
                os.path.join(BASE_DIR, "scripts", "status_glance.py"),
                *(["--log-dir", args.log_dir] if args.log_dir else []),
                *(["--automation-log-dir", args.automation_log_dir] if args.automation_log_dir else []),
                *(["--streak-file", args.streak_file] if args.streak_file else []),
                *(["--slots", args.slots] if args.slots else []),
                *(["--tolerance-minutes", str(args.tolerance_minutes)] if args.tolerance_minutes else []),
                *(["--output", args.output] if args.output else []),
                *(["--json-output", args.json_output] if args.json_output else []),
            ]
        )
    )

    dell_cutover_verify_p = sub.add_parser(
        "dell-cutover-verify",
        help="Verify Dell cron cutover prerequisites and schedule block",
    )
    dell_cutover_verify_p.add_argument("--repo-path", help="Repo path to verify")
    dell_cutover_verify_p.add_argument("--env-file", help="Path to .env for required keys check")
    dell_cutover_verify_p.set_defaults(
        func=lambda args: _run(
            [
                sys.executable,
                os.path.join(BASE_DIR, "scripts", "dell_cutover_verify.py"),
                *(["--repo-path", args.repo_path] if args.repo_path else []),
                *(["--env-file", args.env_file] if args.env_file else []),
            ]
        )
    )

    dell_remote_p = sub.add_parser(
        "dell-remote",
        help="Mac->Dell bridge for SSH command execution and code sync",
    )
    dell_remote_p.add_argument(
        "--action",
        choices=["configure", "show", "test", "run", "sync-code"],
        default="show",
        help="Bridge action",
    )
    dell_remote_p.add_argument("--config", help="Config JSON path")
    dell_remote_p.add_argument("--host", help="Dell host or IP")
    dell_remote_p.add_argument("--user", help="Dell SSH user")
    dell_remote_p.add_argument("--repo-path", help="Repo path on Dell")
    dell_remote_p.add_argument("--port", type=int, help="SSH port")
    dell_remote_p.add_argument("--key-path", help="SSH private key path")
    dell_remote_p.add_argument("--cmd", help="Remote command for run action")
    dell_remote_p.add_argument("--no-repo", action="store_true", help="Do not cd into repo before run")
    dell_remote_p.add_argument("--no-venv", action="store_true", help="Do not auto-activate .venv")
    dell_remote_p.add_argument("--local-path", help="Local path for sync-code")
    dell_remote_p.add_argument("--dry-run", action="store_true", help="Dry run for sync-code")
    dell_remote_p.add_argument("--print-cmd", action="store_true", help="Print underlying SSH/rsync command")
    dell_remote_p.set_defaults(
        func=lambda args: _run(
            [
                sys.executable,
                os.path.join(BASE_DIR, "scripts", "dell_remote.py"),
                "--action",
                args.action,
                *(["--config", args.config] if args.config else []),
                *(["--host", args.host] if args.host else []),
                *(["--user", args.user] if args.user else []),
                *(["--repo-path", args.repo_path] if args.repo_path else []),
                *(["--port", str(args.port)] if args.port else []),
                *(["--key-path", args.key_path] if args.key_path else []),
                *(["--cmd", args.cmd] if args.cmd else []),
                *(["--no-repo"] if args.no_repo else []),
                *(["--no-venv"] if args.no_venv else []),
                *(["--local-path", args.local_path] if args.local_path else []),
                *(["--dry-run"] if args.dry_run else []),
                *(["--print-cmd"] if args.print_cmd else []),
            ]
        )
    )

    remote_ready_p = sub.add_parser(
        "remote-ready",
        help="Check away-mode readiness (Tailscale, SSH, awake, automation)",
    )
    remote_ready_p.add_argument(
        "--skip-awake-check",
        action="store_true",
        help="Do not require caffeinate keep-awake for readiness",
    )
    remote_ready_p.add_argument("--json-output", help="Optional path to write JSON result")
    remote_ready_p.set_defaults(
        func=lambda args: _run(
            [
                sys.executable,
                os.path.join(BASE_DIR, "scripts", "remote_ready.py"),
                *(["--skip-awake-check"] if args.skip_awake_check else []),
                *(["--json-output", args.json_output] if args.json_output else []),
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

    daily_p = sub.add_parser("promotion-daily", help="Run daily queue auto + promotion review")
    daily_p.add_argument("--since-hours", type=int, default=24, help="Window for queue auto candidates")
    daily_p.add_argument("--max-add", type=int, default=5, help="Maximum episodes to add to queue")
    daily_p.add_argument(
        "--reason",
        default="auto: daily gated promotion candidate",
        help="Reason text for queue entries",
    )
    daily_p.add_argument("--pattern", default="automation_success", help="Pattern label for queue entries")
    daily_p.add_argument("--allow-medium-risk", action="store_true", help="Allow MEDIUM-risk episodes")
    daily_p.add_argument("--min-sources", type=int, default=2, help="Minimum source count required")
    daily_p.add_argument("--no-require-glance-pass", action="store_true", help="Do not require status_today PASS")
    daily_p.add_argument("--no-require-phase-pass", action="store_true", help="Do not require latest phase gate PASS")
    daily_p.add_argument(
        "--phase-policy",
        choices=["auto", "always", "never"],
        default="auto",
        help="Phase gate policy (auto requires phase at/after enforce hour)",
    )
    daily_p.add_argument(
        "--phase-enforce-hour",
        type=int,
        default=19,
        help="Local hour when auto phase policy enforces phase gate",
    )
    daily_p.add_argument("--dry-run", action="store_true", help="Show queue candidates without writing")
    daily_p.add_argument("--output", help="Promotion review output path")
    daily_p.add_argument("--min-count", type=int, default=2, help="Minimum queue size target in review")
    daily_p.add_argument("--rubric", help="Rubric path")
    daily_p.add_argument("--strict-gates", action="store_true", help="Fail when queue auto is blocked by gates")
    daily_p.set_defaults(
        func=lambda args: _run(
            [
                sys.executable,
                os.path.join(BASE_DIR, "scripts", "promotion_daily.py"),
                "--since-hours",
                str(args.since_hours),
                "--max-add",
                str(args.max_add),
                "--reason",
                args.reason,
                "--pattern",
                args.pattern,
                "--min-sources",
                str(args.min_sources),
                *(["--allow-medium-risk"] if args.allow_medium_risk else []),
                *(["--no-require-glance-pass"] if args.no_require_glance_pass else []),
                *(["--no-require-phase-pass"] if args.no_require_phase_pass else []),
                "--phase-policy",
                args.phase_policy,
                "--phase-enforce-hour",
                str(args.phase_enforce_hour),
                *(["--dry-run"] if args.dry_run else []),
                *(["--output", args.output] if args.output else []),
                *(["--min-count", str(args.min_count)] if args.min_count else []),
                *(["--rubric", args.rubric] if args.rubric else []),
                *(["--strict-gates"] if args.strict_gates else []),
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

    ari_p = sub.add_parser("ari-reception", help="Run Ari receptionist intake/summary")
    ari_p.add_argument("--action", choices=["intake", "summary"], default="summary", help="Ari action")
    ari_p.add_argument("--queue-dir", help="Queue directory override")
    ari_p.add_argument("--sender", help="Sender (intake)")
    ari_p.add_argument("--message", help="Message body (intake)")
    ari_p.add_argument("--channel", help="Channel (intake)")
    ari_p.add_argument("--source", help="Source system (intake)")
    ari_p.add_argument("--priority", choices=["urgent", "high", "normal", "low"], help="Priority override")
    ari_p.add_argument("--max-items", type=int, default=20, help="Max items in summary")
    ari_p.set_defaults(
        func=lambda args: _run(
            [
                sys.executable,
                os.path.join(BASE_DIR, "scripts", "ari_reception.py"),
                "--action",
                args.action,
                *(["--queue-dir", args.queue_dir] if args.queue_dir else []),
                *(["--sender", args.sender] if args.sender else []),
                *(["--message", args.message] if args.message else []),
                *(["--channel", args.channel] if args.channel else []),
                *(["--source", args.source] if args.source else []),
                *(["--priority", args.priority] if args.priority else []),
                *(["--max-items", str(args.max_items)] if args.max_items else []),
            ]
        )
    )

    sandra_p = sub.add_parser("sandra-reception", help="Run Sandra receptionist intake/summary")
    sandra_p.add_argument("--action", choices=["intake", "summary"], default="summary", help="Sandra action")
    sandra_p.add_argument("--queue-dir", help="Queue directory override")
    sandra_p.add_argument("--sender", help="Sender (intake)")
    sandra_p.add_argument("--message", help="Message body (intake)")
    sandra_p.add_argument("--channel", help="Channel (intake)")
    sandra_p.add_argument("--source", help="Source system (intake)")
    sandra_p.add_argument("--priority", choices=["urgent", "high", "normal", "low"], help="Priority override")
    sandra_p.add_argument("--max-items", type=int, default=20, help="Max items in summary")
    sandra_p.set_defaults(
        func=lambda args: _run(
            [
                sys.executable,
                os.path.join(BASE_DIR, "scripts", "ari_reception.py"),
                "--action",
                args.action,
                "--name",
                "Sandra",
                *(["--queue-dir", args.queue_dir] if args.queue_dir else []),
                *(["--sender", args.sender] if args.sender else []),
                *(["--message", args.message] if args.message else []),
                *(["--channel", args.channel] if args.channel else []),
                *(["--source", args.source] if args.source else []),
                *(["--priority", args.priority] if args.priority else []),
                *(["--max-items", str(args.max_items)] if args.max_items else []),
            ]
        )
    )

    research_inbox_p = sub.add_parser(
        "research-inbox",
        help="Capture links/text and ingest into sources via URL fetch",
    )
    research_inbox_p.add_argument("--action", choices=["add", "process", "status"], default="process")
    research_inbox_p.add_argument("--text", help="Text payload for add action")
    research_inbox_p.add_argument("--source", help="Capture source id (for add)")
    research_inbox_p.add_argument("--channel", help="Capture channel id (for add)")
    research_inbox_p.add_argument("--inbox-path", help="Inbox JSONL path")
    research_inbox_p.add_argument("--state-path", help="State JSON path")
    research_inbox_p.add_argument("--sources-path", help="sources.json path")
    research_inbox_p.add_argument("--output-dir", help="Report output directory")
    research_inbox_p.add_argument("--max-sources", type=int, default=30, help="Max URL sources per run")
    research_inbox_p.add_argument("--excerpt", type=int, default=280, help="Excerpt chars")
    research_inbox_p.add_argument("--timeout", type=int, default=15, help="URL fetch timeout seconds")
    research_inbox_p.add_argument("--max-bytes", type=int, default=1_000_000, help="Max bytes per URL fetch")
    research_inbox_p.add_argument("--user-agent", help="HTTP user agent override")
    research_inbox_p.add_argument("--tool-dir", help="Tool memory output directory")
    research_inbox_p.set_defaults(
        func=lambda args: _run(
            [
                sys.executable,
                os.path.join(BASE_DIR, "scripts", "research_inbox.py"),
                "--action",
                args.action,
                *(["--text", args.text] if args.text else []),
                *(["--source", args.source] if args.source else []),
                *(["--channel", args.channel] if args.channel else []),
                *(["--inbox-path", args.inbox_path] if args.inbox_path else []),
                *(["--state-path", args.state_path] if args.state_path else []),
                *(["--sources-path", args.sources_path] if args.sources_path else []),
                *(["--output-dir", args.output_dir] if args.output_dir else []),
                *(["--max-sources", str(args.max_sources)] if args.max_sources else []),
                *(["--excerpt", str(args.excerpt)] if args.excerpt else []),
                *(["--timeout", str(args.timeout)] if args.timeout else []),
                *(["--max-bytes", str(args.max_bytes)] if args.max_bytes else []),
                *(["--user-agent", args.user_agent] if args.user_agent else []),
                *(["--tool-dir", args.tool_dir] if args.tool_dir else []),
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

    cc_p = sub.add_parser(
        "command-center",
        help="Run live dashboard API and command center UI",
    )
    cc_p.add_argument("--host", default="127.0.0.1", help="Bind host")
    cc_p.add_argument("--port", type=int, default=8000, help="Bind port")
    cc_p.add_argument("--no-open", action="store_true", help="Do not auto-open browser")
    cc_p.add_argument("--run-horizon", action="store_true", help="Run Horizon Agent before boot")
    cc_p.add_argument(
        "--demo-horizon",
        action="store_true",
        help="Use deterministic mock signals with --run-horizon",
    )
    cc_p.set_defaults(
        func=lambda args: _run(
            [
                sys.executable,
                os.path.join(BASE_DIR, "scripts", "command_center.py"),
                *(["--host", args.host] if args.host else []),
                *(["--port", str(args.port)] if args.port else []),
                *(["--no-open"] if args.no_open else []),
                *(["--run-horizon"] if args.run_horizon else []),
                *(["--demo-horizon"] if args.demo_horizon else []),
            ]
        )
    )

    snap_p = sub.add_parser("snapshot", help="Generate aggregated system snapshot")
    snap_p.set_defaults(
        func=lambda _args: _run([sys.executable, os.path.join(BASE_DIR, "scripts", "system_snapshot.py")])
    )

    v04_snap_p = sub.add_parser("v04-snapshot", help="Generate v0.4 operational snapshot")
    v04_snap_p.add_argument("--output", help="Output markdown path")
    v04_snap_p.set_defaults(
        func=lambda args: _run(
            [
                sys.executable,
                os.path.join(BASE_DIR, "scripts", "v04_snapshot.py"),
                *(["--output", args.output] if args.output else []),
            ]
        )
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

    organizer_p = sub.add_parser(
        "organize-files",
        help="Safe file organizer: scan/apply quarantine plan or open Storage settings",
    )
    organizer_p.add_argument("--action", choices=["scan", "apply", "open-storage"], default="scan")
    organizer_p.add_argument("--roots", nargs="*", help="Roots to scan")
    organizer_p.add_argument("--stale-days", type=int, default=30, help="Stale threshold in days")
    organizer_p.add_argument("--min-large-mb", type=int, default=500, help="Min size for large-file report")
    organizer_p.add_argument("--top-large", type=int, default=40, help="Top large files to include")
    organizer_p.add_argument("--duplicate-min-kb", type=int, default=64, help="Min size for duplicate hash scan")
    organizer_p.add_argument("--max-stale-actions", type=int, default=500, help="Max stale move candidates in plan")
    organizer_p.add_argument("--quarantine-root", help="Quarantine root directory")
    organizer_p.add_argument("--output-dir", help="Output directory for plan/report")
    organizer_p.add_argument("--plan", help="Plan path for apply action")
    organizer_p.add_argument("--dry-run", action="store_true", help="Simulate apply")
    organizer_p.add_argument("--confirm", action="store_true", help="Required for non-dry-run apply")
    organizer_p.add_argument("--limit", type=int, default=0, help="Apply only first N actions")
    organizer_p.set_defaults(
        func=lambda args: _run(
            [
                sys.executable,
                os.path.join(BASE_DIR, "scripts", "file_organizer.py"),
                "--action",
                args.action,
                *(["--roots"] + args.roots if args.roots else []),
                *(["--stale-days", str(args.stale_days)] if args.stale_days else []),
                *(["--min-large-mb", str(args.min_large_mb)] if args.min_large_mb else []),
                *(["--top-large", str(args.top_large)] if args.top_large else []),
                *(["--duplicate-min-kb", str(args.duplicate_min_kb)] if args.duplicate_min_kb else []),
                *(["--max-stale-actions", str(args.max_stale_actions)] if args.max_stale_actions else []),
                *(["--quarantine-root", args.quarantine_root] if args.quarantine_root else []),
                *(["--output-dir", args.output_dir] if args.output_dir else []),
                *(["--plan", args.plan] if args.plan else []),
                *(["--dry-run"] if args.dry_run else []),
                *(["--confirm"] if args.confirm else []),
                *(["--limit", str(args.limit)] if args.limit else []),
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
    git_auto_p.add_argument("--push", action="store_true", help="Push after commit")
    git_auto_p.add_argument("--remote", default="origin", help="Remote name for push")
    git_auto_p.add_argument("--branch", help="Branch name override for push")
    git_auto_p.set_defaults(
        func=lambda args: _run(
            [
                sys.executable,
                os.path.join(BASE_DIR, "scripts", "git_autocommit.py"),
                "--repo",
                BASE_DIR,
                *(["--message", args.message] if args.message else []),
                *(["--push"] if args.push else []),
                *(["--remote", args.remote] if args.remote else []),
                *(["--branch", args.branch] if args.branch else []),
            ]
        )
    )

    git_sync_p = sub.add_parser("git-sync", help="Auto-commit and push to remote")
    git_sync_p.add_argument("--message", help="Commit message")
    git_sync_p.add_argument("--remote", default="origin", help="Remote name for push")
    git_sync_p.add_argument("--branch", help="Branch name override for push")
    git_sync_p.set_defaults(
        func=lambda args: _run(
            [
                sys.executable,
                os.path.join(BASE_DIR, "scripts", "git_autocommit.py"),
                "--repo",
                BASE_DIR,
                "--push",
                *(["--message", args.message] if args.message else []),
                *(["--remote", args.remote] if args.remote else []),
                *(["--branch", args.branch] if args.branch else []),
            ]
        )
    )

    chronicle_backfill_p = sub.add_parser(
        "chronicle-backfill",
        help="Backfill timeline artifacts from local folders",
    )
    chronicle_backfill_p.add_argument("--roots", nargs="*", help="Roots to scan")
    chronicle_backfill_p.add_argument("--since-days", type=int, help="Lookback window in days")
    chronicle_backfill_p.add_argument("--max-files", type=int, default=4000, help="Maximum files to process")
    chronicle_backfill_p.add_argument("--sample-chars", type=int, default=1200, help="Excerpt chars for signal scan")
    chronicle_backfill_p.add_argument("--output", help="Output markdown path")
    chronicle_backfill_p.add_argument("--no-events", action="store_true", help="Do not append event entry")
    chronicle_backfill_p.set_defaults(
        func=lambda args: _run(
            [
                sys.executable,
                os.path.join(BASE_DIR, "scripts", "chronicle_backfill.py"),
                *(["--roots"] + args.roots if args.roots else []),
                *(["--since-days", str(args.since_days)] if args.since_days else []),
                *(["--max-files", str(args.max_files)] if args.max_files else []),
                *(["--sample-chars", str(args.sample_chars)] if args.sample_chars else []),
                *(["--output", args.output] if args.output else []),
                *(["--no-events"] if args.no_events else []),
            ]
        )
    )

    chronicle_capture_p = sub.add_parser(
        "chronicle-capture",
        help="Capture current session state into chronicle log",
    )
    chronicle_capture_p.add_argument("--note", default="", help="Session note")
    chronicle_capture_p.add_argument("--chat-file", help="Optional chat export/text file path")
    chronicle_capture_p.add_argument("--tag", action="append", default=[], help="Tag (repeatable)")
    chronicle_capture_p.add_argument("--max-log-lines", type=int, default=200, help="Recent lines per log file")
    chronicle_capture_p.add_argument("--sample-chars", type=int, default=1200, help="Excerpt chars for chat signal scan")
    chronicle_capture_p.set_defaults(
        func=lambda args: _run(
            [
                sys.executable,
                os.path.join(BASE_DIR, "scripts", "chronicle_capture.py"),
                *(["--note", args.note] if args.note else []),
                *(["--chat-file", args.chat_file] if args.chat_file else []),
                *([arg for tag in args.tag for arg in ("--tag", tag)] if args.tag else []),
                *(["--max-log-lines", str(args.max_log_lines)] if args.max_log_lines else []),
                *(["--sample-chars", str(args.sample_chars)] if args.sample_chars else []),
            ]
        )
    )

    chronicle_report_p = sub.add_parser(
        "chronicle-report",
        help="Generate timeline report from chronicle + git history",
    )
    chronicle_report_p.add_argument("--days", type=int, default=180, help="Lookback window in days")
    chronicle_report_p.add_argument("--max-events", type=int, default=400, help="Maximum timeline events")
    chronicle_report_p.add_argument("--max-commits", type=int, default=120, help="Maximum commits")
    chronicle_report_p.add_argument("--output", help="Output markdown path")
    chronicle_report_p.set_defaults(
        func=lambda args: _run(
            [
                sys.executable,
                os.path.join(BASE_DIR, "scripts", "chronicle_report.py"),
                *(["--days", str(args.days)] if args.days else []),
                *(["--max-events", str(args.max_events)] if args.max_events else []),
                *(["--max-commits", str(args.max_commits)] if args.max_commits else []),
                *(["--output", args.output] if args.output else []),
            ]
        )
    )

    chronicle_publish_p = sub.add_parser(
        "chronicle-publish",
        help="Publish latest chronicle report for agents, Drive mirror, and optional email",
    )
    chronicle_publish_p.add_argument("--report-json", help="Chronicle report JSON path")
    chronicle_publish_p.add_argument("--report-md", help="Chronicle report markdown path")
    chronicle_publish_p.add_argument("--output-dir", help="Shared output directory")
    chronicle_publish_p.add_argument("--drive-dir", help="Optional Google Drive desktop-sync destination")
    chronicle_publish_p.add_argument("--docx", action="store_true", help="Also export summary as DOCX")
    chronicle_publish_p.add_argument("--email-to", action="append", default=[], help="Email recipient (repeatable)")
    chronicle_publish_p.add_argument("--email-subject", help="Email subject")
    chronicle_publish_p.add_argument("--smtp-host", help="SMTP host")
    chronicle_publish_p.add_argument("--smtp-port", type=int, help="SMTP port")
    chronicle_publish_p.add_argument("--smtp-user", help="SMTP username")
    chronicle_publish_p.add_argument("--smtp-password", help="SMTP password")
    chronicle_publish_p.add_argument("--smtp-from", help="SMTP sender address")
    chronicle_publish_p.add_argument("--no-starttls", action="store_true", help="Disable SMTP STARTTLS")
    chronicle_publish_p.set_defaults(
        func=lambda args: _run(
            [
                sys.executable,
                os.path.join(BASE_DIR, "scripts", "chronicle_publish.py"),
                *(["--report-json", args.report_json] if args.report_json else []),
                *(["--report-md", args.report_md] if args.report_md else []),
                *(["--output-dir", args.output_dir] if args.output_dir else []),
                *(["--drive-dir", args.drive_dir] if args.drive_dir else []),
                *(["--docx"] if args.docx else []),
                *([arg for recipient in args.email_to for arg in ("--email-to", recipient)] if args.email_to else []),
                *(["--email-subject", args.email_subject] if args.email_subject else []),
                *(["--smtp-host", args.smtp_host] if args.smtp_host else []),
                *(["--smtp-port", str(args.smtp_port)] if args.smtp_port else []),
                *(["--smtp-user", args.smtp_user] if args.smtp_user else []),
                *(["--smtp-password", args.smtp_password] if args.smtp_password else []),
                *(["--smtp-from", args.smtp_from] if args.smtp_from else []),
                *(["--no-starttls"] if args.no_starttls else []),
            ]
        )
    )
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
