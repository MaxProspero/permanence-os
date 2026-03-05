#!/usr/bin/env python3
"""
Unified CLI for Permanence OS.
Commands: run, add-source, status, clean, test, ingest, ingest-docs, ingest-sources, ingest-drive-all, sources-digest, sources-brief, synthesis-brief, notebooklm-sync, automation-verify, automation-report, reliability-watch, reliability-gate, reliability-streak, phase-gate, status-glance, dell-cutover-verify, dell-remote, remote-ready, promote, promotion-review, promotion-daily, queue, hr-report, briefing, ari-reception, sandra-reception, research-inbox, glasses-bridge, telegram-control, ophtxn-simulation, ophtxn-completion, ophtxn-brain, terminal-task-queue, governed-learning, self-improvement, glasses-autopilot, discord-feed-manager, discord-telegram-relay, comms-digest, comms-escalation-digest, comms-status, comms-doctor, comms-automation, email-triage, gmail-ingest, health-summary, social-summary, logos-gate, dashboard, integration-readiness, anthropic-keychain, connector-keychain, external-access-policy, secret-scan, github-research-ingest, github-trending-ingest, ecosystem-research-ingest, social-research-ingest, x-account-watch, world-watch, world-watch-alerts, market-focus-brief, market-backtest-queue, narrative-tracker, conspiracy-tracker, command-center, operator-surface, setup-launchers, comms-loop, money-loop, second-brain-init, second-brain-loop, attachment-pipeline, resume-brand-brief, phase2-refresh, opportunity-ranker, opportunity-approval-queue, phase3-refresh, approval-execution-board, revenue-action-queue, revenue-architecture, revenue-cost-recovery, revenue-execution-board, revenue-weekly-summary, revenue-outreach-pack, revenue-followup-queue, revenue-eval, revenue-backup, revenue-playbook, revenue-targets, sales-pipeline, life-os-brief, side-business-portfolio, prediction-ingest, prediction-lab, clipping-transcript-ingest, clipping-pipeline, second-brain-report, foundation-site, snapshot, v04-snapshot, openclaw-status, openclaw-sync, organize-files, cleanup-weekly, git-autocommit, git-sync, chronicle-backfill, chronicle-capture, chronicle-report, chronicle-publish
"""

import argparse
import os
import subprocess
import sys

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__)))


def _load_env_file(env: dict[str, str], env_path: str) -> None:
    if not os.path.exists(env_path):
        return
    try:
        lines = open(env_path, "r", encoding="utf-8", errors="ignore").read().splitlines()
    except OSError:
        return
    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key or key in env:
            continue
        value = value.strip()
        if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
            value = value[1:-1]
        env[key] = value


def _keychain_secret(service: str, account: str) -> str:
    if sys.platform != "darwin":
        return ""
    if not service or not account:
        return ""
    try:
        proc = subprocess.run(
            ["security", "find-generic-password", "-s", service, "-a", account, "-w"],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return ""
    if proc.returncode != 0:
        return ""
    return (proc.stdout or "").strip()


def _inject_keychain_env(env: dict[str, str]) -> None:
    mappings = [
        (
            "ANTHROPIC_API_KEY",
            "PERMANENCE_ANTHROPIC_KEYCHAIN_SERVICE",
            "PERMANENCE_ANTHROPIC_KEYCHAIN_ACCOUNT",
            "permanence_os_anthropic_api_key",
        ),
        (
            "PERMANENCE_GITHUB_READ_TOKEN",
            "PERMANENCE_GITHUB_READ_KEYCHAIN_SERVICE",
            "PERMANENCE_GITHUB_READ_KEYCHAIN_ACCOUNT",
            "permanence_os_github_read_token",
        ),
        (
            "PERMANENCE_SOCIAL_READ_TOKEN",
            "PERMANENCE_SOCIAL_READ_KEYCHAIN_SERVICE",
            "PERMANENCE_SOCIAL_READ_KEYCHAIN_ACCOUNT",
            "permanence_os_social_read_token",
        ),
        (
            "PERMANENCE_DISCORD_ALERT_WEBHOOK_URL",
            "PERMANENCE_DISCORD_ALERT_WEBHOOK_KEYCHAIN_SERVICE",
            "PERMANENCE_DISCORD_ALERT_WEBHOOK_KEYCHAIN_ACCOUNT",
            "permanence_os_discord_alert_webhook",
        ),
        (
            "PERMANENCE_DISCORD_BOT_TOKEN",
            "PERMANENCE_DISCORD_BOT_TOKEN_KEYCHAIN_SERVICE",
            "PERMANENCE_DISCORD_BOT_TOKEN_KEYCHAIN_ACCOUNT",
            "permanence_os_discord_bot_token",
        ),
        (
            "PERMANENCE_TELEGRAM_BOT_TOKEN",
            "PERMANENCE_TELEGRAM_BOT_TOKEN_KEYCHAIN_SERVICE",
            "PERMANENCE_TELEGRAM_BOT_TOKEN_KEYCHAIN_ACCOUNT",
            "permanence_os_telegram_bot_token",
        ),
        (
            "XAI_API_KEY",
            "XAI_KEYCHAIN_SERVICE",
            "XAI_KEYCHAIN_ACCOUNT",
            "permanence_os_xai_api_key",
        ),
        (
            "ALPHA_VANTAGE_API_KEY",
            "ALPHA_VANTAGE_KEYCHAIN_SERVICE",
            "ALPHA_VANTAGE_KEYCHAIN_ACCOUNT",
            "permanence_os_alpha_vantage_api_key",
        ),
        (
            "FINNHUB_API_KEY",
            "FINNHUB_KEYCHAIN_SERVICE",
            "FINNHUB_KEYCHAIN_ACCOUNT",
            "permanence_os_finnhub_api_key",
        ),
        (
            "POLYGON_API_KEY",
            "POLYGON_KEYCHAIN_SERVICE",
            "POLYGON_KEYCHAIN_ACCOUNT",
            "permanence_os_polygon_api_key",
        ),
        (
            "COINMARKETCAP_API_KEY",
            "COINMARKETCAP_KEYCHAIN_SERVICE",
            "COINMARKETCAP_KEYCHAIN_ACCOUNT",
            "permanence_os_coinmarketcap_api_key",
        ),
        (
            "GLASSNODE_API_KEY",
            "GLASSNODE_KEYCHAIN_SERVICE",
            "GLASSNODE_KEYCHAIN_ACCOUNT",
            "permanence_os_glassnode_api_key",
        ),
    ]
    user = os.getenv("USER", "")
    for env_key, service_key, account_key, default_service in mappings:
        current = (env.get(env_key) or "").strip()
        if current:
            continue
        service = (env.get(service_key) or default_service).strip()
        account = (env.get(account_key) or user).strip()
        secret = _keychain_secret(service=service, account=account)
        if secret:
            env[env_key] = secret


def _run(cmd: list[str]) -> int:
    env = os.environ.copy()
    _load_env_file(env, os.path.join(BASE_DIR, ".env"))
    _inject_keychain_env(env)
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
        os.path.join(BASE_DIR, "tests", "test_glasses_bridge.py"),
        os.path.join(BASE_DIR, "tests", "test_telegram_control.py"),
        os.path.join(BASE_DIR, "tests", "test_ophtxn_brain.py"),
        os.path.join(BASE_DIR, "tests", "test_terminal_task_queue.py"),
        os.path.join(BASE_DIR, "tests", "test_glasses_autopilot.py"),
        os.path.join(BASE_DIR, "tests", "test_discord_feed_manager.py"),
        os.path.join(BASE_DIR, "tests", "test_discord_telegram_relay.py"),
        os.path.join(BASE_DIR, "tests", "test_comms_digest.py"),
        os.path.join(BASE_DIR, "tests", "test_comms_escalation_digest.py"),
        os.path.join(BASE_DIR, "tests", "test_comms_status.py"),
        os.path.join(BASE_DIR, "tests", "test_comms_doctor.py"),
        os.path.join(BASE_DIR, "tests", "test_comms_automation.py"),
        os.path.join(BASE_DIR, "tests", "test_file_organizer.py"),
        os.path.join(BASE_DIR, "tests", "test_dashboard_api_helpers.py"),
        os.path.join(BASE_DIR, "tests", "test_revenue_execution_board.py"),
        os.path.join(BASE_DIR, "tests", "test_revenue_weekly_summary.py"),
        os.path.join(BASE_DIR, "tests", "test_revenue_cost_recovery.py"),
        os.path.join(BASE_DIR, "tests", "test_anthropic_keychain.py"),
        os.path.join(BASE_DIR, "tests", "test_connector_keychain.py"),
        os.path.join(BASE_DIR, "tests", "test_cli_keychain_injection.py"),
        os.path.join(BASE_DIR, "tests", "test_secret_scan.py"),
        os.path.join(BASE_DIR, "tests", "test_external_access_policy.py"),
        os.path.join(BASE_DIR, "tests", "test_github_research_ingest.py"),
        os.path.join(BASE_DIR, "tests", "test_github_trending_ingest.py"),
        os.path.join(BASE_DIR, "tests", "test_ecosystem_research_ingest.py"),
        os.path.join(BASE_DIR, "tests", "test_social_research_ingest.py"),
        os.path.join(BASE_DIR, "tests", "test_x_account_watch.py"),
        os.path.join(BASE_DIR, "tests", "test_world_watch_ingest.py"),
        os.path.join(BASE_DIR, "tests", "test_world_watch_alerts.py"),
        os.path.join(BASE_DIR, "tests", "test_market_focus_brief.py"),
        os.path.join(BASE_DIR, "tests", "test_market_backtest_queue.py"),
        os.path.join(BASE_DIR, "tests", "test_narrative_tracker.py"),
        os.path.join(BASE_DIR, "tests", "test_life_os_brief.py"),
        os.path.join(BASE_DIR, "tests", "test_side_business_portfolio.py"),
        os.path.join(BASE_DIR, "tests", "test_prediction_ingest.py"),
        os.path.join(BASE_DIR, "tests", "test_prediction_lab.py"),
        os.path.join(BASE_DIR, "tests", "test_clipping_transcript_ingest.py"),
        os.path.join(BASE_DIR, "tests", "test_clipping_pipeline_manager.py"),
        os.path.join(BASE_DIR, "tests", "test_attachment_pipeline.py"),
        os.path.join(BASE_DIR, "tests", "test_resume_brand_brief.py"),
        os.path.join(BASE_DIR, "tests", "test_phase2_refresh.py"),
        os.path.join(BASE_DIR, "tests", "test_opportunity_ranker.py"),
        os.path.join(BASE_DIR, "tests", "test_opportunity_approval_queue.py"),
        os.path.join(BASE_DIR, "tests", "test_phase3_refresh.py"),
        os.path.join(BASE_DIR, "tests", "test_approval_execution_board.py"),
        os.path.join(BASE_DIR, "tests", "test_second_brain_report.py"),
        os.path.join(BASE_DIR, "tests", "test_second_brain_init.py"),
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

    glasses_bridge_p = sub.add_parser(
        "glasses-bridge",
        help="Ingest smart-glasses events into attachment, reception, and research queues",
    )
    glasses_bridge_p.add_argument("--action", choices=["ingest", "intake", "status"], default="status")
    glasses_bridge_p.add_argument("--from-json", action="append", default=[], help="Path to exported JSON event file")
    glasses_bridge_p.add_argument("--text", help="Direct event text for intake")
    glasses_bridge_p.add_argument("--source", help="Source override")
    glasses_bridge_p.add_argument("--channel", help="Channel override")
    glasses_bridge_p.add_argument("--sender", help="Sender override")
    glasses_bridge_p.add_argument("--url", action="append", default=[], help="Attach URL (repeatable)")
    glasses_bridge_p.add_argument("--media", action="append", default=[], help="Media path (repeatable)")
    glasses_bridge_p.add_argument("--events-path", help="Events JSONL path")
    glasses_bridge_p.add_argument("--attachments-dir", help="Attachment inbox directory")
    glasses_bridge_p.add_argument("--reception-queue-dir", help="Reception queue directory")
    glasses_bridge_p.add_argument("--research-inbox-path", help="Research inbox JSONL path")
    glasses_bridge_p.add_argument("--max-items", type=int, default=20, help="Status max recent items")
    glasses_bridge_p.add_argument("--no-reception", action="store_true", help="Skip Ari intake mirroring")
    glasses_bridge_p.add_argument("--no-research", action="store_true", help="Skip research inbox mirroring")
    glasses_bridge_p.add_argument("--no-attachments", action="store_true", help="Skip media copy/extract")
    glasses_bridge_p.set_defaults(
        func=lambda args: _run(
            [
                sys.executable,
                os.path.join(BASE_DIR, "scripts", "glasses_bridge.py"),
                "--action",
                args.action,
                *([arg for path in args.from_json for arg in ("--from-json", path)] if args.from_json else []),
                *(["--text", args.text] if args.text else []),
                *(["--source", args.source] if args.source else []),
                *(["--channel", args.channel] if args.channel else []),
                *(["--sender", args.sender] if args.sender else []),
                *([arg for url in args.url for arg in ("--url", url)] if args.url else []),
                *([arg for media in args.media for arg in ("--media", media)] if args.media else []),
                *(["--events-path", args.events_path] if args.events_path else []),
                *(["--attachments-dir", args.attachments_dir] if args.attachments_dir else []),
                *(["--reception-queue-dir", args.reception_queue_dir] if args.reception_queue_dir else []),
                *(["--research-inbox-path", args.research_inbox_path] if args.research_inbox_path else []),
                *(["--max-items", str(args.max_items)] if args.max_items else []),
                *(["--no-reception"] if args.no_reception else []),
                *(["--no-research"] if args.no_research else []),
                *(["--no-attachments"] if args.no_attachments else []),
            ]
        )
    )

    telegram_control_p = sub.add_parser(
        "telegram-control",
        help="Poll Telegram and route channel messages into glasses/research/reception queues",
    )
    telegram_control_p.add_argument("--action", choices=["status", "poll"], default="status")
    telegram_control_p.add_argument(
        "--chat-id",
        help="Target Telegram chat id or comma-separated ids (also reads PERMANENCE_TELEGRAM_CHAT_ID(S))",
    )
    telegram_control_p.add_argument("--source", default="telegram-control", help="Source label for events")
    telegram_control_p.add_argument("--channel", default="telegram", help="Channel label for events")
    telegram_control_p.add_argument("--limit", type=int, default=50, help="Max updates per poll")
    telegram_control_p.add_argument("--state-path", help="Offset state path")
    telegram_control_p.add_argument("--download-dir", help="Media download directory")
    telegram_control_p.add_argument("--timeout", type=int, default=20, help="Network timeout seconds")
    telegram_control_p.add_argument("--skip-media", action="store_true", help="Skip media download")
    telegram_control_p.add_argument(
        "--include-bot-messages",
        action="store_true",
        help="Include Telegram messages where sender is marked bot",
    )
    telegram_control_p.add_argument("--no-commit-offset", action="store_true", help="Do not persist next offset")
    telegram_control_p.add_argument("--ack", action="store_true", help="Send summary ack back to Telegram")
    telegram_control_p.add_argument("--enable-commands", action="store_true", help="Enable slash command execution")
    telegram_control_p.add_argument("--command-prefix", default="/", help="Command prefix token")
    telegram_control_p.add_argument("--command-timeout", type=int, default=90, help="Max seconds per command")
    telegram_control_p.add_argument("--max-commands", type=int, default=3, help="Max commands per poll")
    telegram_control_p.add_argument(
        "--command-allow-user-id",
        action="append",
        default=[],
        help="Allowed Telegram user id for command execution (repeatable)",
    )
    telegram_control_p.add_argument(
        "--command-allow-chat-id",
        action="append",
        default=[],
        help="Allowed Telegram chat id for command execution (repeatable)",
    )
    telegram_control_p.add_argument(
        "--require-command-allowlist",
        action="store_true",
        help="Require configured command user/chat allowlist before command execution",
    )
    telegram_control_p.add_argument("--no-command-ack", action="store_true", help="Do not send command ack responses")
    telegram_control_p.add_argument("--chat-agent", action="store_true", help="Reply to non-command messages")
    telegram_control_p.add_argument("--no-chat-agent", action="store_true", help="Disable chat-agent replies")
    telegram_control_p.add_argument(
        "--chat-task-type",
        default="execution",
        help="Model routing task type for chat-agent replies",
    )
    telegram_control_p.add_argument("--max-chat-replies", type=int, default=3, help="Max chat-agent replies per poll")
    telegram_control_p.add_argument("--chat-max-history", type=int, default=12, help="Max history messages per chat")
    telegram_control_p.add_argument(
        "--chat-reply-max-chars",
        type=int,
        default=1400,
        help="Max characters per chat-agent reply",
    )
    telegram_control_p.add_argument("--chat-history-path", help="Chat history JSON path")
    telegram_control_p.add_argument(
        "--chat-memory-max-notes",
        type=int,
        default=8,
        help="Max personal-memory notes added to chat prompt",
    )
    telegram_control_p.add_argument("--chat-auto-memory", action="store_true", help="Auto-store non-command chat notes")
    telegram_control_p.add_argument(
        "--no-chat-auto-memory",
        action="store_true",
        help="Disable auto-store of non-command chat notes",
    )
    telegram_control_p.add_argument("--memory-path", help="Personal memory JSON path")
    telegram_control_p.add_argument("--memory-max-notes", type=int, default=500, help="Max memory notes per user")
    telegram_control_p.add_argument(
        "--voice-priority",
        choices=["urgent", "high", "normal", "low"],
        default="high",
        help="Priority for voice-note events",
    )
    telegram_control_p.add_argument("--voice-channel", default="telegram-voice", help="Channel label for voice notes")
    telegram_control_p.add_argument("--voice-source", help="Optional source label for voice notes")
    telegram_control_p.add_argument("--voice-text-prefix", default="[Voice Note]", help="Prefix for voice-note messages")
    telegram_control_p.add_argument("--voice-transcribe-queue", help="Transcription queue JSON path")
    telegram_control_p.add_argument("--no-voice-transcribe-queue", action="store_true", help="Disable voice queueing")
    telegram_control_p.add_argument("--dry-run", action="store_true", help="Fetch + parse only")
    telegram_control_p.set_defaults(
        func=lambda args: _run(
            [
                sys.executable,
                os.path.join(BASE_DIR, "scripts", "telegram_control.py"),
                "--action",
                args.action,
                *([f"--chat-id={args.chat_id}"] if args.chat_id else []),
                *(["--source", args.source] if args.source else []),
                *(["--channel", args.channel] if args.channel else []),
                *(["--limit", str(args.limit)] if args.limit else []),
                *(["--state-path", args.state_path] if args.state_path else []),
                *(["--download-dir", args.download_dir] if args.download_dir else []),
                *(["--timeout", str(args.timeout)] if args.timeout else []),
                *(["--skip-media"] if args.skip_media else []),
                *(["--include-bot-messages"] if args.include_bot_messages else []),
                *(["--no-commit-offset"] if args.no_commit_offset else []),
                *(["--ack"] if args.ack else []),
                *(["--enable-commands"] if args.enable_commands else []),
                *(["--command-prefix", args.command_prefix] if args.command_prefix else []),
                *(["--command-timeout", str(args.command_timeout)] if args.command_timeout else []),
                *(["--max-commands", str(args.max_commands)] if args.max_commands is not None else []),
                *(
                    [arg for value in args.command_allow_user_id for arg in ("--command-allow-user-id", value)]
                    if args.command_allow_user_id
                    else []
                ),
                *(
                    [f"--command-allow-chat-id={value}" for value in args.command_allow_chat_id]
                    if args.command_allow_chat_id
                    else []
                ),
                *(["--require-command-allowlist"] if args.require_command_allowlist else []),
                *(["--no-command-ack"] if args.no_command_ack else []),
                *(["--chat-agent"] if args.chat_agent else []),
                *(["--no-chat-agent"] if args.no_chat_agent else []),
                *(["--chat-task-type", args.chat_task_type] if args.chat_task_type else []),
                *(["--max-chat-replies", str(args.max_chat_replies)] if args.max_chat_replies is not None else []),
                *(["--chat-max-history", str(args.chat_max_history)] if args.chat_max_history is not None else []),
                *(
                    ["--chat-reply-max-chars", str(args.chat_reply_max_chars)]
                    if args.chat_reply_max_chars is not None
                    else []
                ),
                *(["--chat-history-path", args.chat_history_path] if args.chat_history_path else []),
                *(
                    ["--chat-memory-max-notes", str(args.chat_memory_max_notes)]
                    if args.chat_memory_max_notes is not None
                    else []
                ),
                *(["--chat-auto-memory"] if args.chat_auto_memory else []),
                *(["--no-chat-auto-memory"] if args.no_chat_auto_memory else []),
                *(["--memory-path", args.memory_path] if args.memory_path else []),
                *(["--memory-max-notes", str(args.memory_max_notes)] if args.memory_max_notes is not None else []),
                *(["--voice-priority", args.voice_priority] if args.voice_priority else []),
                *(["--voice-channel", args.voice_channel] if args.voice_channel else []),
                *(["--voice-source", args.voice_source] if args.voice_source else []),
                *(["--voice-text-prefix", args.voice_text_prefix] if args.voice_text_prefix else []),
                *(["--voice-transcribe-queue", args.voice_transcribe_queue] if args.voice_transcribe_queue else []),
                *(["--no-voice-transcribe-queue"] if args.no_voice_transcribe_queue else []),
                *(["--dry-run"] if args.dry_run else []),
            ]
        )
    )

    ophtxn_simulation_p = sub.add_parser(
        "ophtxn-simulation",
        help="Run offline Ophtxn memory + habit simulations",
    )
    ophtxn_simulation_p.add_argument("--seed", type=int, default=7, help="Random seed")
    ophtxn_simulation_p.add_argument("--memory-trials", type=int, default=120, help="Memory retrieval trial count")
    ophtxn_simulation_p.add_argument("--habit-days", type=int, default=60, help="Habit simulation day count")
    ophtxn_simulation_p.set_defaults(
        func=lambda args: _run(
            [
                sys.executable,
                os.path.join(BASE_DIR, "scripts", "ophtxn_simulation.py"),
                "--seed",
                str(args.seed),
                "--memory-trials",
                str(args.memory_trials),
                "--habit-days",
                str(args.habit_days),
            ]
        )
    )

    governed_learning_p = sub.add_parser(
        "governed-learning",
        help="Run governed continuous learning (X/media/AI/finance/excel) under explicit approval gates",
    )
    governed_learning_p.add_argument(
        "--action",
        choices=["status", "run", "init-policy"],
        default="status",
        help="Status-only, execute a run, or reset policy template",
    )
    governed_learning_p.add_argument("--policy-path", help="Policy JSON path override")
    governed_learning_p.add_argument("--state-path", help="State JSON path override")
    governed_learning_p.add_argument("--force-template", action="store_true", help="Rewrite policy template")
    governed_learning_p.add_argument("--approved-by", help="Approval actor for run action")
    governed_learning_p.add_argument("--approval-note", help="Approval note for run action")
    governed_learning_p.add_argument("--skip-pipeline", action="append", default=[], help="Skip pipeline by name")
    governed_learning_p.add_argument("--timeout", type=int, default=180, help="Per-pipeline timeout seconds")
    governed_learning_p.add_argument("--force", action="store_true", help="Override daily run cap")
    governed_learning_p.add_argument("--dry-run", action="store_true", help="Render run plan but skip execution")
    governed_learning_p.set_defaults(
        func=lambda args: _run(
            [
                sys.executable,
                os.path.join(BASE_DIR, "scripts", "governed_learning_loop.py"),
                "--action",
                args.action,
                *(["--policy-path", args.policy_path] if args.policy_path else []),
                *(["--state-path", args.state_path] if args.state_path else []),
                *(["--force-template"] if args.force_template else []),
                *(["--approved-by", args.approved_by] if args.approved_by else []),
                *(["--approval-note", args.approval_note] if args.approval_note else []),
                *([arg for row in args.skip_pipeline for arg in ("--skip-pipeline", row)] if args.skip_pipeline else []),
                *(["--timeout", str(args.timeout)] if args.timeout is not None else []),
                *(["--force"] if args.force else []),
                *(["--dry-run"] if args.dry_run else []),
            ]
        )
    )

    self_improvement_p = sub.add_parser(
        "self-improvement",
        help="Generate and govern Ophtxn self-improvement pitches with explicit approval decisions",
    )
    self_improvement_p.add_argument(
        "--action",
        choices=["status", "pitch", "list", "decide", "init-policy"],
        default="status",
        help="Inspect status, generate pitches, list pending, or decide",
    )
    self_improvement_p.add_argument("--policy-path", help="Policy JSON path override")
    self_improvement_p.add_argument("--proposals-path", help="Proposals JSON path override")
    self_improvement_p.add_argument("--force-template", action="store_true", help="Rewrite policy template")
    self_improvement_p.add_argument("--decision", choices=["approve", "reject", "defer"], help="Decision verb")
    self_improvement_p.add_argument("--proposal-id", help="Target proposal id")
    self_improvement_p.add_argument("--decided-by", help="Decision actor")
    self_improvement_p.add_argument("--note", help="Decision note")
    self_improvement_p.add_argument("--decision-code", help="Decision code/PIN for protected decisions")
    self_improvement_p.add_argument("--set-decision-code", help="Set or rotate required decision code")
    self_improvement_p.add_argument("--clear-decision-code", action="store_true", help="Disable required decision code")
    self_improvement_p.add_argument("--send-telegram", action="store_true", help="Send summary to Telegram")
    self_improvement_p.add_argument("--telegram-chat-id", help="Telegram chat id override")
    self_improvement_p.set_defaults(
        func=lambda args: _run(
            [
                sys.executable,
                os.path.join(BASE_DIR, "scripts", "self_improvement_loop.py"),
                "--action",
                args.action,
                *(["--policy-path", args.policy_path] if args.policy_path else []),
                *(["--proposals-path", args.proposals_path] if args.proposals_path else []),
                *(["--force-template"] if args.force_template else []),
                *(["--decision", args.decision] if args.decision else []),
                *(["--proposal-id", args.proposal_id] if args.proposal_id else []),
                *(["--decided-by", args.decided_by] if args.decided_by else []),
                *(["--note", args.note] if args.note else []),
                *(["--decision-code", args.decision_code] if args.decision_code else []),
                *(["--set-decision-code", args.set_decision_code] if args.set_decision_code else []),
                *(["--clear-decision-code"] if args.clear_decision_code else []),
                *(["--send-telegram"] if args.send_telegram else []),
                *(["--telegram-chat-id", args.telegram_chat_id] if args.telegram_chat_id else []),
            ]
        )
    )

    glasses_autopilot_p = sub.add_parser(
        "glasses-autopilot",
        help="Auto-scan Downloads for new smart-glasses exports and ingest them",
    )
    glasses_autopilot_p.add_argument("--action", choices=["run", "status"], default="status")
    glasses_autopilot_p.add_argument("--downloads-dir", help="Directory to scan")
    glasses_autopilot_p.add_argument("--state-path", help="Autopilot state path")
    glasses_autopilot_p.add_argument("--pattern", action="append", default=[], help="Glob pattern (repeatable)")
    glasses_autopilot_p.add_argument("--max-files", type=int, default=60, help="Max candidate files to inspect")
    glasses_autopilot_p.add_argument("--no-attachment-pipeline", action="store_true", help="Skip attachment follow-up")
    glasses_autopilot_p.add_argument("--no-research-process", action="store_true", help="Skip research follow-up")
    glasses_autopilot_p.add_argument("--dry-run", action="store_true", help="Scan only")
    glasses_autopilot_p.set_defaults(
        func=lambda args: _run(
            [
                sys.executable,
                os.path.join(BASE_DIR, "scripts", "glasses_autopilot.py"),
                "--action",
                args.action,
                *(["--downloads-dir", args.downloads_dir] if args.downloads_dir else []),
                *(["--state-path", args.state_path] if args.state_path else []),
                *([arg for pattern in args.pattern for arg in ("--pattern", pattern)] if args.pattern else []),
                *(["--max-files", str(args.max_files)] if args.max_files else []),
                *(["--no-attachment-pipeline"] if args.no_attachment_pipeline else []),
                *(["--no-research-process"] if args.no_research_process else []),
                *(["--dry-run"] if args.dry_run else []),
            ]
        )
    )

    discord_feed_manager_p = sub.add_parser(
        "discord-feed-manager",
        help="Manage Discord channel feed rows in social_research_feeds.json",
    )
    discord_feed_manager_p.add_argument("--action", choices=["list", "add", "enable", "disable", "remove"], default="list")
    discord_feed_manager_p.add_argument("--name", default="", help="Discord feed display name")
    discord_feed_manager_p.add_argument("--channel-id", default="", help="Discord channel id")
    discord_feed_manager_p.add_argument("--channel-link", default="", help="Discord channel URL")
    discord_feed_manager_p.add_argument("--invite-url", default="", help="Optional invite URL")
    discord_feed_manager_p.add_argument("--max-messages", type=int, default=50, help="Max messages per poll")
    discord_feed_manager_p.add_argument("--include-keyword", action="append", default=[], help="Include keyword filter")
    discord_feed_manager_p.add_argument("--exclude-keyword", action="append", default=[], help="Exclude keyword filter")
    discord_feed_manager_p.add_argument(
        "--priority",
        choices=["urgent", "high", "normal", "low"],
        help="Feed priority level",
    )
    discord_feed_manager_p.add_argument("--min-chars", type=int, help="Minimum message length filter")
    discord_feed_manager_p.add_argument("--clear-filters", action="store_true", help="Clear feed filters")
    discord_feed_manager_p.add_argument("--feeds-path", help="Feeds JSON path")
    discord_feed_manager_p.add_argument("--disabled", action="store_true", help="For add: create disabled row")
    discord_feed_manager_p.set_defaults(
        func=lambda args: _run(
            [
                sys.executable,
                os.path.join(BASE_DIR, "scripts", "discord_feed_manager.py"),
                "--action",
                args.action,
                *(["--name", args.name] if args.name else []),
                *(["--channel-id", args.channel_id] if args.channel_id else []),
                *(["--channel-link", args.channel_link] if args.channel_link else []),
                *(["--invite-url", args.invite_url] if args.invite_url else []),
                *(["--max-messages", str(args.max_messages)] if args.max_messages else []),
                *(
                    [arg for keyword in args.include_keyword for arg in ("--include-keyword", keyword)]
                    if args.include_keyword
                    else []
                ),
                *(
                    [arg for keyword in args.exclude_keyword for arg in ("--exclude-keyword", keyword)]
                    if args.exclude_keyword
                    else []
                ),
                *(["--priority", args.priority] if args.priority else []),
                *(["--min-chars", str(args.min_chars)] if args.min_chars is not None else []),
                *(["--clear-filters"] if args.clear_filters else []),
                *(["--feeds-path", args.feeds_path] if args.feeds_path else []),
                *(["--disabled"] if args.disabled else []),
            ]
        )
    )

    discord_telegram_relay_p = sub.add_parser(
        "discord-telegram-relay",
        help="Relay new Discord feed messages into Telegram",
    )
    discord_telegram_relay_p.add_argument("--action", choices=["status", "run"], default="status")
    discord_telegram_relay_p.add_argument("--feeds-path", help="Discord feeds JSON path")
    discord_telegram_relay_p.add_argument("--state-path", help="State JSON path")
    discord_telegram_relay_p.add_argument("--chat-id", help="Telegram chat/channel id")
    discord_telegram_relay_p.add_argument("--max-per-feed", type=int, default=20, help="Max messages pulled per feed")
    discord_telegram_relay_p.add_argument("--timeout", type=int, default=20, help="Network timeout seconds")
    discord_telegram_relay_p.add_argument("--escalate", action="store_true", help="Enable escalation")
    discord_telegram_relay_p.add_argument("--no-escalate", action="store_true", help="Disable escalation")
    discord_telegram_relay_p.add_argument("--escalation-keyword", action="append", default=[], help="Escalation keyword")
    discord_telegram_relay_p.add_argument(
        "--escalation-min-priority",
        choices=["urgent", "high", "normal", "low"],
        default="high",
        help="Min feed priority required for escalation",
    )
    discord_telegram_relay_p.add_argument("--escalations-path", help="Escalation JSONL path")
    discord_telegram_relay_p.add_argument(
        "--escalate-to-reception",
        dest="escalate_to_reception",
        action="store_true",
        default=None,
        help="Mirror escalations to reception queue",
    )
    discord_telegram_relay_p.add_argument(
        "--no-escalate-to-reception",
        dest="escalate_to_reception",
        action="store_false",
        help="Do not mirror escalations to reception queue",
    )
    discord_telegram_relay_p.add_argument("--escalation-notify", action="store_true", help="Send escalation notifications")
    discord_telegram_relay_p.add_argument("--no-escalation-notify", action="store_true", help="Skip escalation notifications")
    discord_telegram_relay_p.add_argument(
        "--escalation-telegram-min-priority",
        choices=["urgent", "high", "normal", "low"],
        default="high",
        help="Min priority for Telegram escalation notification",
    )
    discord_telegram_relay_p.add_argument(
        "--escalation-discord-min-priority",
        choices=["urgent", "high", "normal", "low"],
        default="urgent",
        help="Min priority for Discord webhook escalation notification",
    )
    discord_telegram_relay_p.add_argument("--escalation-max-notify", type=int, default=5, help="Max escalation rows in notify")
    discord_telegram_relay_p.add_argument("--escalation-webhook-url", help="Discord webhook override for escalations")
    discord_telegram_relay_p.add_argument("--escalation-notify-timeout", type=int, default=15, help="Escalation notify timeout")
    discord_telegram_relay_p.add_argument("--intake-path", help="Shared intake JSONL path for mirrored Discord rows")
    discord_telegram_relay_p.add_argument("--no-intake-mirror", action="store_true", help="Disable intake mirroring")
    discord_telegram_relay_p.add_argument("--dry-run", action="store_true", help="Fetch only; do not send Telegram")
    discord_telegram_relay_p.add_argument("--no-commit-state", action="store_true", help="Do not persist relay state")
    discord_telegram_relay_p.set_defaults(
        func=lambda args: _run(
            [
                sys.executable,
                os.path.join(BASE_DIR, "scripts", "discord_telegram_relay.py"),
                "--action",
                args.action,
                *(["--feeds-path", args.feeds_path] if args.feeds_path else []),
                *(["--state-path", args.state_path] if args.state_path else []),
                *([f"--chat-id={args.chat_id}"] if args.chat_id else []),
                *(["--max-per-feed", str(args.max_per_feed)] if args.max_per_feed else []),
                *(["--timeout", str(args.timeout)] if args.timeout else []),
                *(["--escalate"] if args.escalate else []),
                *(["--no-escalate"] if args.no_escalate else []),
                *(
                    [arg for keyword in args.escalation_keyword for arg in ("--escalation-keyword", keyword)]
                    if args.escalation_keyword
                    else []
                ),
                *(
                    ["--escalation-min-priority", args.escalation_min_priority]
                    if args.escalation_min_priority
                    else []
                ),
                *(["--escalations-path", args.escalations_path] if args.escalations_path else []),
                *(["--escalate-to-reception"] if args.escalate_to_reception is True else []),
                *(["--no-escalate-to-reception"] if args.escalate_to_reception is False else []),
                *(["--escalation-notify"] if args.escalation_notify else []),
                *(["--no-escalation-notify"] if args.no_escalation_notify else []),
                *(
                    ["--escalation-telegram-min-priority", args.escalation_telegram_min_priority]
                    if args.escalation_telegram_min_priority
                    else []
                ),
                *(
                    ["--escalation-discord-min-priority", args.escalation_discord_min_priority]
                    if args.escalation_discord_min_priority
                    else []
                ),
                *(["--escalation-max-notify", str(args.escalation_max_notify)] if args.escalation_max_notify is not None else []),
                *(["--escalation-webhook-url", args.escalation_webhook_url] if args.escalation_webhook_url else []),
                *(
                    ["--escalation-notify-timeout", str(args.escalation_notify_timeout)]
                    if args.escalation_notify_timeout is not None
                    else []
                ),
                *(["--intake-path", args.intake_path] if args.intake_path else []),
                *(["--no-intake-mirror"] if args.no_intake_mirror else []),
                *(["--dry-run"] if args.dry_run else []),
                *(["--no-commit-state"] if args.no_commit_state else []),
            ]
        )
    )

    comms_digest_p = sub.add_parser(
        "comms-digest",
        help="Build and optionally send daily communication digest to Telegram",
    )
    comms_digest_p.add_argument("--send", action="store_true", help="Send digest to Telegram")
    comms_digest_p.add_argument("--chat-id", help="Override Telegram chat id")
    comms_digest_p.add_argument("--timeout", type=int, default=20, help="Network timeout seconds")
    comms_digest_p.add_argument("--max-warnings", type=int, default=8, help="Max warnings to include")
    comms_digest_p.add_argument("--include-paths", action="store_true", help="Include local payload paths")
    comms_digest_p.add_argument("--dry-run", action="store_true", help="Build only; do not send")
    comms_digest_p.add_argument("--no-history", action="store_true", help="Skip history append")
    comms_digest_p.add_argument("--history-path", help="Digest history JSONL path")
    comms_digest_p.set_defaults(
        func=lambda args: _run(
            [
                sys.executable,
                os.path.join(BASE_DIR, "scripts", "comms_digest.py"),
                *(["--send"] if args.send else []),
                *([f"--chat-id={args.chat_id}"] if args.chat_id else []),
                *(["--timeout", str(args.timeout)] if args.timeout else []),
                *(["--max-warnings", str(args.max_warnings)] if args.max_warnings is not None else []),
                *(["--include-paths"] if args.include_paths else []),
                *(["--dry-run"] if args.dry_run else []),
                *(["--no-history"] if args.no_history else []),
                *(["--history-path", args.history_path] if args.history_path else []),
            ]
        )
    )

    comms_escalation_digest_p = sub.add_parser(
        "comms-escalation-digest",
        help="Build and optionally dispatch escalation digest from comms escalation history",
    )
    comms_escalation_digest_p.add_argument("--escalations-path", help="Escalations JSONL path")
    comms_escalation_digest_p.add_argument("--hours", type=int, default=24, help="Lookback window in hours")
    comms_escalation_digest_p.add_argument("--max-items", type=int, default=8, help="Max escalation rows")
    comms_escalation_digest_p.add_argument("--send", action="store_true", help="Send to Telegram+Discord (configured)")
    comms_escalation_digest_p.add_argument("--send-telegram", action="store_true", help="Send to Telegram only")
    comms_escalation_digest_p.add_argument("--send-discord", action="store_true", help="Send to Discord only")
    comms_escalation_digest_p.add_argument("--chat-id", help="Telegram chat id override")
    comms_escalation_digest_p.add_argument("--webhook-url", help="Discord webhook override")
    comms_escalation_digest_p.add_argument("--timeout", type=int, default=15, help="Network timeout seconds")
    comms_escalation_digest_p.set_defaults(
        func=lambda args: _run(
            [
                sys.executable,
                os.path.join(BASE_DIR, "scripts", "comms_escalation_digest.py"),
                *(["--escalations-path", args.escalations_path] if args.escalations_path else []),
                *(["--hours", str(args.hours)] if args.hours is not None else []),
                *(["--max-items", str(args.max_items)] if args.max_items is not None else []),
                *(["--send"] if args.send else []),
                *(["--send-telegram"] if args.send_telegram else []),
                *(["--send-discord"] if args.send_discord else []),
                *([f"--chat-id={args.chat_id}"] if args.chat_id else []),
                *(["--webhook-url", args.webhook_url] if args.webhook_url else []),
                *(["--timeout", str(args.timeout)] if args.timeout is not None else []),
            ]
        )
    )

    comms_status_p = sub.add_parser(
        "comms-status",
        help="Generate communication stack health/status rollup",
    )
    comms_status_p.add_argument(
        "--comms-log-stale-minutes",
        type=int,
        default=20,
        help="Warn when comms loop log is older than this many minutes",
    )
    comms_status_p.add_argument(
        "--component-stale-minutes",
        type=int,
        default=120,
        help="Warn when core component payloads are older than this many minutes",
    )
    comms_status_p.add_argument(
        "--escalation-digest-stale-minutes",
        type=int,
        default=1500,
        help="Warn when escalation digest payload is older than this many minutes",
    )
    comms_status_p.add_argument("--escalation-hours", type=int, default=24, help="Escalation lookback window in hours")
    comms_status_p.add_argument(
        "--escalation-warn-count",
        type=int,
        default=8,
        help="Warn when escalations in lookback window are >= this value",
    )
    comms_status_p.add_argument(
        "--voice-queue-warn-count",
        type=int,
        default=15,
        help="Warn when pending voice transcription queue entries are >= this value",
    )
    comms_status_p.add_argument(
        "--require-escalation-digest",
        action="store_true",
        help="Warn when escalation digest payload is missing",
    )
    comms_status_p.set_defaults(
        func=lambda args: _run(
            [
                sys.executable,
                os.path.join(BASE_DIR, "scripts", "comms_status.py"),
                *(["--comms-log-stale-minutes", str(args.comms_log_stale_minutes)] if args.comms_log_stale_minutes else []),
                *(["--component-stale-minutes", str(args.component_stale_minutes)] if args.component_stale_minutes else []),
                *(
                    ["--escalation-digest-stale-minutes", str(args.escalation_digest_stale_minutes)]
                    if args.escalation_digest_stale_minutes
                    else []
                ),
                *(["--escalation-hours", str(args.escalation_hours)] if args.escalation_hours else []),
                *(["--escalation-warn-count", str(args.escalation_warn_count)] if args.escalation_warn_count else []),
                *(["--voice-queue-warn-count", str(args.voice_queue_warn_count)] if args.voice_queue_warn_count else []),
                *(["--require-escalation-digest"] if args.require_escalation_digest else []),
            ]
        )
    )

    comms_doctor_p = sub.add_parser(
        "comms-doctor",
        help="Run comms doctor checks for secrets, automation, and payload freshness",
    )
    comms_doctor_p.add_argument("--max-stale-minutes", type=int, default=45, help="Max stale minutes for core payloads")
    comms_doctor_p.add_argument(
        "--digest-max-stale-minutes",
        type=int,
        default=1500,
        help="Max stale minutes for digest payload",
    )
    comms_doctor_p.add_argument("--require-digest", action="store_true", help="Require digest automation/payload checks")
    comms_doctor_p.add_argument(
        "--require-escalation-digest",
        action="store_true",
        help="Require escalation digest automation/payload checks",
    )
    comms_doctor_p.add_argument("--check-live", action="store_true", help="Run live token checks")
    comms_doctor_p.add_argument("--live-timeout", type=int, default=8, help="Timeout for live token checks")
    comms_doctor_p.add_argument("--auto-repair", action="store_true", help="Attempt auto-enable of missing automations")
    comms_doctor_p.add_argument("--repair-timeout", type=int, default=120, help="Timeout for repair commands")
    comms_doctor_p.add_argument("--allow-warnings", action="store_true", help="Exit 0 even with warnings")
    comms_doctor_p.set_defaults(
        func=lambda args: _run(
            [
                sys.executable,
                os.path.join(BASE_DIR, "scripts", "comms_doctor.py"),
                *(["--max-stale-minutes", str(args.max_stale_minutes)] if args.max_stale_minutes else []),
                *(
                    ["--digest-max-stale-minutes", str(args.digest_max_stale_minutes)]
                    if args.digest_max_stale_minutes
                    else []
                ),
                *(["--require-digest"] if args.require_digest else []),
                *(["--require-escalation-digest"] if args.require_escalation_digest else []),
                *(["--check-live"] if args.check_live else []),
                *(["--live-timeout", str(args.live_timeout)] if args.live_timeout else []),
                *(["--auto-repair"] if args.auto_repair else []),
                *(["--repair-timeout", str(args.repair_timeout)] if args.repair_timeout else []),
                *(["--allow-warnings"] if args.allow_warnings else []),
            ]
        )
    )

    comms_automation_p = sub.add_parser(
        "comms-automation",
        help="Manage comms loop/digest/doctor automation lifecycle",
    )
    comms_automation_p.add_argument(
        "--action",
        choices=[
            "status",
            "enable",
            "disable",
            "run-now",
            "digest-status",
            "digest-enable",
            "digest-disable",
            "digest-now",
            "doctor-status",
            "doctor-enable",
            "doctor-disable",
            "doctor-now",
            "escalation-status",
            "escalation-enable",
            "escalation-disable",
            "escalation-digest-now",
        ],
        default="status",
    )
    comms_automation_p.add_argument("--label", default="com.permanence.comms_loop", help="launchd label")
    comms_automation_p.set_defaults(
        func=lambda args: _run(
            [
                sys.executable,
                os.path.join(BASE_DIR, "scripts", "comms_automation.py"),
                "--action",
                args.action,
                *(["--label", args.label] if args.label else []),
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

    integration_p = sub.add_parser(
        "integration-readiness",
        help="Check integration/credential readiness and write a readiness report",
    )
    integration_p.set_defaults(
        func=lambda _args: _run(
            [
                sys.executable,
                os.path.join(BASE_DIR, "scripts", "integration_readiness.py"),
            ]
        )
    )

    keychain_p = sub.add_parser(
        "anthropic-keychain",
        help="Install/check Anthropic key in macOS Keychain and keep .env key blank",
    )
    keychain_p.add_argument("--from-file", help="Path to file containing Anthropic API key")
    keychain_p.add_argument("--service", help="Keychain service label")
    keychain_p.add_argument("--account", help="Keychain account label")
    keychain_p.add_argument("--remove-source", action="store_true", help="Delete source key file after install")
    keychain_p.add_argument("--status", action="store_true", help="Check key presence in keychain")
    keychain_p.add_argument("--clear", action="store_true", help="Delete keychain entry")
    keychain_p.set_defaults(
        func=lambda args: _run(
            [
                sys.executable,
                os.path.join(BASE_DIR, "scripts", "anthropic_keychain.py"),
                *(["--from-file", args.from_file] if args.from_file else []),
                *(["--service", args.service] if args.service else []),
                *(["--account", args.account] if args.account else []),
                *(["--remove-source"] if args.remove_source else []),
                *(["--status"] if args.status else []),
                *(["--clear"] if args.clear else []),
            ]
        )
    )

    connector_keychain_p = sub.add_parser(
        "connector-keychain",
        help="Install/check connector read tokens in macOS Keychain (.env token stays blank)",
    )
    connector_keychain_p.add_argument(
        "--target",
        required=True,
        choices=[
            "github-read",
            "social-read",
            "discord-alert-webhook",
            "discord-bot-token",
            "telegram-bot-token",
            "xai-api-key",
            "alpha-vantage",
            "finnhub",
            "polygon",
            "coinmarketcap",
            "glassnode",
        ],
        help="Connector target",
    )
    connector_keychain_p.add_argument("--from-file", help="Path to file containing connector token")
    connector_keychain_p.add_argument("--service", help="Keychain service label")
    connector_keychain_p.add_argument("--account", help="Keychain account label")
    connector_keychain_p.add_argument("--remove-source", action="store_true", help="Delete source file after install")
    connector_keychain_p.add_argument("--status", action="store_true", help="Check token presence in keychain")
    connector_keychain_p.add_argument("--clear", action="store_true", help="Delete keychain entry")
    connector_keychain_p.set_defaults(
        func=lambda args: _run(
            [
                sys.executable,
                os.path.join(BASE_DIR, "scripts", "connector_keychain.py"),
                "--target",
                args.target,
                *(["--from-file", args.from_file] if args.from_file else []),
                *(["--service", args.service] if args.service else []),
                *(["--account", args.account] if args.account else []),
                *(["--remove-source"] if args.remove_source else []),
                *(["--status"] if args.status else []),
                *(["--clear"] if args.clear else []),
            ]
        )
    )

    secret_scan_p = sub.add_parser(
        "secret-scan",
        help="Scan staged/all tracked files for likely secret leaks",
    )
    secret_scan_p.add_argument("--all-files", action="store_true", help="Scan all tracked files")
    secret_scan_p.add_argument("--staged", action="store_true", help="Scan staged files")
    secret_scan_p.set_defaults(
        func=lambda args: _run(
            [
                sys.executable,
                os.path.join(BASE_DIR, "scripts", "secret_scan.py"),
                *(["--all-files"] if args.all_files else []),
                *(["--staged"] if args.staged else []),
            ]
        )
    )

    access_policy_p = sub.add_parser(
        "external-access-policy",
        help="Generate secure external connector access policy + risk report",
    )
    access_policy_p.add_argument(
        "--force-template",
        action="store_true",
        help="Overwrite memory/working/agent_access_policy.json template",
    )
    access_policy_p.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero when risk is high",
    )
    access_policy_p.set_defaults(
        func=lambda args: _run(
            [
                sys.executable,
                os.path.join(BASE_DIR, "scripts", "external_access_policy.py"),
                *(["--force-template"] if args.force_template else []),
                *(["--strict"] if args.strict else []),
            ]
        )
    )

    gh_research_p = sub.add_parser(
        "github-research-ingest",
        help="Run read-only GitHub research ingest and action suggestions",
    )
    gh_research_p.add_argument(
        "--force-template",
        action="store_true",
        help="Rewrite memory/working/github_research_targets.json template",
    )
    gh_research_p.add_argument("--max-items", type=int, help="Max open issues/PRs per repo")
    gh_research_p.add_argument("--stale-days", type=int, help="Stale threshold in days")
    gh_research_p.set_defaults(
        func=lambda args: _run(
            [
                sys.executable,
                os.path.join(BASE_DIR, "scripts", "github_research_ingest.py"),
                *(["--force-template"] if args.force_template else []),
                *(["--max-items", str(args.max_items)] if args.max_items else []),
                *(["--stale-days", str(args.stale_days)] if args.stale_days else []),
            ]
        )
    )

    gh_trending_p = sub.add_parser(
        "github-trending-ingest",
        help="Run read-only GitHub trending ingest and rank trend opportunities",
    )
    gh_trending_p.add_argument(
        "--force-template",
        action="store_true",
        help="Rewrite memory/working/github_trending_focus.json template",
    )
    gh_trending_p.add_argument(
        "--since",
        choices=["daily", "weekly", "monthly"],
        help="Override trending window",
    )
    gh_trending_p.set_defaults(
        func=lambda args: _run(
            [
                sys.executable,
                os.path.join(BASE_DIR, "scripts", "github_trending_ingest.py"),
                *(["--force-template"] if args.force_template else []),
                *(["--since", args.since] if args.since else []),
            ]
        )
    )

    ecosystem_research_p = sub.add_parser(
        "ecosystem-research-ingest",
        help="Run read-only ecosystem ingest (repos, developers, docs, communities)",
    )
    ecosystem_research_p.add_argument(
        "--force-template",
        action="store_true",
        help="Rewrite memory/working/ecosystem_watchlist.json template",
    )
    ecosystem_research_p.set_defaults(
        func=lambda args: _run(
            [
                sys.executable,
                os.path.join(BASE_DIR, "scripts", "ecosystem_research_ingest.py"),
                *(["--force-template"] if args.force_template else []),
            ]
        )
    )

    social_research_p = sub.add_parser(
        "social-research-ingest",
        help="Run read-only social trend ingest and ranking",
    )
    social_research_p.add_argument(
        "--force-template",
        action="store_true",
        help="Rewrite memory/working/social_research_feeds.json template",
    )
    social_research_p.add_argument(
        "--force-policy",
        action="store_true",
        help="Rewrite memory/working/social_discernment_policy.json template",
    )
    social_research_p.set_defaults(
        func=lambda args: _run(
            [
                sys.executable,
                os.path.join(BASE_DIR, "scripts", "social_research_ingest.py"),
                *(["--force-template"] if args.force_template else []),
                *(["--force-policy"] if args.force_policy else []),
            ]
        )
    )

    ophtxn_completion_p = sub.add_parser(
        "ophtxn-completion",
        help="Score Ophtxn completion progress vs 100% from live telemetry",
    )
    ophtxn_completion_p.add_argument("--target", type=int, default=100, help="Target completion percentage")
    ophtxn_completion_p.add_argument("--strict", action="store_true", help="Exit non-zero when below target")
    ophtxn_completion_p.set_defaults(
        func=lambda args: _run(
            [
                sys.executable,
                os.path.join(BASE_DIR, "scripts", "ophtxn_completion.py"),
                *(["--target", str(args.target)] if args.target is not None else []),
                *(["--strict"] if args.strict else []),
            ]
        )
    )

    ophtxn_brain_p = sub.add_parser(
        "ophtxn-brain",
        help="Sync and query Ophtxn persistent brain vault from system files",
    )
    ophtxn_brain_p.add_argument("--action", choices=["status", "sync", "recall"], default="status")
    ophtxn_brain_p.add_argument("--vault-path", help="Override vault JSON path")
    ophtxn_brain_p.add_argument("--query", help="Recall query for recall action")
    ophtxn_brain_p.add_argument("--limit", type=int, default=8, help="Max recall hits")
    ophtxn_brain_p.add_argument("--max-chunks", type=int, default=5000, help="Max vault chunks retained")
    ophtxn_brain_p.set_defaults(
        func=lambda args: _run(
            [
                sys.executable,
                os.path.join(BASE_DIR, "scripts", "ophtxn_brain.py"),
                "--action",
                args.action,
                *(["--vault-path", args.vault_path] if args.vault_path else []),
                *(["--query", args.query] if args.query else []),
                *(["--limit", str(args.limit)] if args.limit is not None else []),
                *(["--max-chunks", str(args.max_chunks)] if args.max_chunks is not None else []),
            ]
        )
    )

    terminal_queue_p = sub.add_parser(
        "terminal-task-queue",
        help="Manage queued terminal tasks captured from Telegram messages",
    )
    terminal_queue_p.add_argument("--action", choices=["status", "list", "add", "complete"], default="status")
    terminal_queue_p.add_argument("--queue-path", help="Override queue JSONL path")
    terminal_queue_p.add_argument("--text", help="Task text for add action")
    terminal_queue_p.add_argument("--task-id", help="Task id for complete action")
    terminal_queue_p.add_argument("--source", help="Task source label")
    terminal_queue_p.add_argument("--sender", help="Sender label")
    terminal_queue_p.add_argument("--sender-user-id", help="Sender user id")
    terminal_queue_p.add_argument("--chat-id", help="Chat id")
    terminal_queue_p.add_argument("--limit", type=int, default=12, help="Recent rows in report")
    terminal_queue_p.set_defaults(
        func=lambda args: _run(
            [
                sys.executable,
                os.path.join(BASE_DIR, "scripts", "terminal_task_queue.py"),
                "--action",
                args.action,
                *(["--queue-path", args.queue_path] if args.queue_path else []),
                *(["--text", args.text] if args.text else []),
                *(["--task-id", args.task_id] if args.task_id else []),
                *(["--source", args.source] if args.source else []),
                *(["--sender", args.sender] if args.sender else []),
                *(["--sender-user-id", args.sender_user_id] if args.sender_user_id else []),
                *([f"--chat-id={args.chat_id}"] if args.chat_id else []),
                *(["--limit", str(args.limit)] if args.limit is not None else []),
            ]
        )
    )

    x_watch_p = sub.add_parser(
        "x-account-watch",
        help="Manage read-only personal X account watch feeds for social-research ingest",
    )
    x_watch_p.add_argument("--action", choices=["list", "add", "remove"], default="list")
    x_watch_p.add_argument("--handle", action="append", default=[], help="X handle/@handle/profile URL (repeatable)")
    x_watch_p.add_argument("--max-results", type=int, default=25, help="Max results per account feed")
    x_watch_p.add_argument("--include-replies", action="store_true", help="Include replies in account query")
    x_watch_p.add_argument("--label", help="Optional feed label for single add")
    x_watch_p.add_argument("--feeds-path", help="Override social feeds JSON path")
    x_watch_p.set_defaults(
        func=lambda args: _run(
            [
                sys.executable,
                os.path.join(BASE_DIR, "scripts", "x_account_watch.py"),
                "--action",
                args.action,
                *(sum([["--handle", str(item)] for item in (args.handle or [])], [])),
                *(["--max-results", str(args.max_results)] if args.max_results is not None else []),
                *(["--include-replies"] if args.include_replies else []),
                *(["--label", args.label] if args.label else []),
                *(["--feeds-path", args.feeds_path] if args.feeds_path else []),
            ]
        )
    )

    world_watch_p = sub.add_parser(
        "world-watch",
        help="Ingest global world-watch feeds and produce ranked situational alerts",
    )
    world_watch_p.add_argument("--force-template", action="store_true", help="Rewrite world watch source template file")
    world_watch_p.set_defaults(
        func=lambda args: _run(
            [
                sys.executable,
                os.path.join(BASE_DIR, "scripts", "world_watch_ingest.py"),
                *(["--force-template"] if args.force_template else []),
            ]
        )
    )

    world_watch_alerts_p = sub.add_parser(
        "world-watch-alerts",
        help="Create world-watch alert brief and optionally dispatch to Discord/Telegram",
    )
    world_watch_alerts_p.add_argument("--send", action="store_true", help="Dispatch alerts to configured channels")
    world_watch_alerts_p.add_argument("--max-alerts", type=int, default=6, help="Max alerts in the message")
    world_watch_alerts_p.add_argument("--min-score", type=float, default=68.0, help="Minimum severity score")
    world_watch_alerts_p.add_argument("--include-links", action="store_true", help="Include URLs in alert message")
    world_watch_alerts_p.set_defaults(
        func=lambda args: _run(
            [
                sys.executable,
                os.path.join(BASE_DIR, "scripts", "world_watch_alerts.py"),
                *(["--send"] if args.send else []),
                *(["--max-alerts", str(args.max_alerts)] if args.max_alerts is not None else []),
                *(["--min-score", str(args.min_score)] if args.min_score is not None else []),
                *(["--include-links"] if args.include_links else []),
            ]
        )
    )

    market_focus_brief_p = sub.add_parser(
        "market-focus-brief",
        help="Generate compact market focus brief from latest world-watch payload",
    )
    market_focus_brief_p.set_defaults(
        func=lambda _args: _run(
            [
                sys.executable,
                os.path.join(BASE_DIR, "scripts", "market_focus_brief.py"),
            ]
        )
    )

    market_backtest_queue_p = sub.add_parser(
        "market-backtest-queue",
        help="Build market backtest queue from social/news/video evidence (advisory only)",
    )
    market_backtest_queue_p.add_argument(
        "--force-template",
        action="store_true",
        help="Rewrite memory/working/market_backtest_watchlist.json template",
    )
    market_backtest_queue_p.set_defaults(
        func=lambda args: _run(
            [
                sys.executable,
                os.path.join(BASE_DIR, "scripts", "market_backtest_queue.py"),
                *(["--force-template"] if args.force_template else []),
            ]
        )
    )

    narrative_tracker_p = sub.add_parser(
        "narrative-tracker",
        aliases=["conspiracy-tracker"],
        help="Track high-uncertainty narratives with evidence states (supported/unverified/contradicted)",
    )
    narrative_tracker_p.add_argument(
        "--force-template",
        action="store_true",
        help="Rewrite memory/working/narrative_tracker_hypotheses.json template",
    )
    narrative_tracker_p.set_defaults(
        func=lambda args: _run(
            [
                sys.executable,
                os.path.join(BASE_DIR, "scripts", "narrative_tracker.py"),
                *(["--force-template"] if args.force_template else []),
            ]
        )
    )

    money_loop_p = sub.add_parser(
        "money-loop",
        help="Run the end-to-end revenue money loop script",
    )
    money_loop_p.set_defaults(
        func=lambda _args: _run(
            [
                "/bin/bash",
                os.path.join(BASE_DIR, "scripts", "run_money_loop.sh"),
            ]
        )
    )

    comms_loop_p = sub.add_parser(
        "comms-loop",
        help="Run the cross-platform communication loop (Telegram, Discord relay, glasses intake)",
    )
    comms_loop_p.set_defaults(
        func=lambda _args: _run(
            [
                "/bin/bash",
                os.path.join(BASE_DIR, "scripts", "run_comms_loop.sh"),
            ]
        )
    )

    second_brain_init_p = sub.add_parser(
        "second-brain-init",
        help="Initialize editable working templates for second-brain modules",
    )
    second_brain_init_p.add_argument("--force", action="store_true", help="Overwrite existing working files")
    second_brain_init_p.set_defaults(
        func=lambda args: _run(
            [
                sys.executable,
                os.path.join(BASE_DIR, "scripts", "second_brain_init.py"),
                *(["--force"] if args.force else []),
            ]
        )
    )

    second_brain_loop_p = sub.add_parser(
        "second-brain-loop",
        help="Run life + research + side-business + prediction + clipping + unified second-brain report",
    )
    second_brain_loop_p.set_defaults(
        func=lambda _args: _run(
            [
                "/bin/bash",
                os.path.join(BASE_DIR, "scripts", "run_second_brain_loop.sh"),
            ]
        )
    )

    attachment_pipeline_p = sub.add_parser(
        "attachment-pipeline",
        help="Index attachment inbox files and build processing queues",
    )
    attachment_pipeline_p.add_argument("--inbox-dir", help="Attachment inbox directory")
    attachment_pipeline_p.add_argument("--max-files", type=int, default=250, help="Max files to index per run")
    attachment_pipeline_p.add_argument("--queue-path", help="Transcription queue JSON path")
    attachment_pipeline_p.set_defaults(
        func=lambda args: _run(
            [
                sys.executable,
                os.path.join(BASE_DIR, "scripts", "attachment_pipeline.py"),
                *(["--inbox-dir", args.inbox_dir] if args.inbox_dir else []),
                *(["--max-files", str(args.max_files)] if args.max_files else []),
                *(["--queue-path", args.queue_path] if args.queue_path else []),
            ]
        )
    )

    resume_brand_p = sub.add_parser(
        "resume-brand-brief",
        help="Generate resume + brand optimization brief from local context",
    )
    resume_brand_p.add_argument("--focus", choices=["resume", "brand", "both"], default="both")
    resume_brand_p.set_defaults(
        func=lambda args: _run(
            [
                sys.executable,
                os.path.join(BASE_DIR, "scripts", "resume_brand_brief.py"),
                *(["--focus", args.focus] if args.focus else []),
            ]
        )
    )

    phase2_refresh_p = sub.add_parser(
        "phase2-refresh",
        help="Run Phase 2 module refresh (attachments, ingest, life, resume/brand, report)",
    )
    phase2_refresh_p.add_argument("--strict", action="store_true", help="Exit non-zero when a step fails")
    phase2_refresh_p.add_argument("--timeout", type=int, default=900, help="Per-step timeout seconds")
    phase2_refresh_p.set_defaults(
        func=lambda args: _run(
            [
                sys.executable,
                os.path.join(BASE_DIR, "scripts", "phase2_refresh.py"),
                *(["--strict"] if args.strict else []),
                *(["--timeout", str(args.timeout)] if args.timeout else []),
            ]
        )
    )

    opportunity_ranker_p = sub.add_parser(
        "opportunity-ranker",
        help="Rank cross-source opportunities for manual approval queueing",
    )
    opportunity_ranker_p.add_argument(
        "--force-policy",
        action="store_true",
        help="Rewrite memory/working/opportunity_rank_policy.json with default values",
    )
    opportunity_ranker_p.add_argument("--max-items", type=int, help="Override max ranked opportunities")
    opportunity_ranker_p.add_argument("--min-score", type=float, help="Override minimum priority score threshold")
    opportunity_ranker_p.set_defaults(
        func=lambda args: _run(
            [
                sys.executable,
                os.path.join(BASE_DIR, "scripts", "opportunity_ranker.py"),
                *(["--force-policy"] if args.force_policy else []),
                *(["--max-items", str(args.max_items)] if args.max_items is not None else []),
                *(["--min-score", str(args.min_score)] if args.min_score is not None else []),
            ]
        )
    )

    opportunity_queue_p = sub.add_parser(
        "opportunity-approval-queue",
        help="Queue ranked opportunities into memory/approvals.json for human decision",
    )
    opportunity_queue_p.add_argument(
        "--force-policy",
        action="store_true",
        help="Rewrite memory/working/opportunity_queue_policy.json with default values",
    )
    opportunity_queue_p.add_argument("--max-items", type=int, help="Override max items queued this run")
    opportunity_queue_p.set_defaults(
        func=lambda args: _run(
            [
                sys.executable,
                os.path.join(BASE_DIR, "scripts", "opportunity_approval_queue.py"),
                *(["--force-policy"] if args.force_policy else []),
                *(["--max-items", str(args.max_items)] if args.max_items is not None else []),
            ]
        )
    )

    phase3_refresh_p = sub.add_parser(
        "phase3-refresh",
        help="Run Phase 3 module refresh (research -> ranking -> approval queue -> report)",
    )
    phase3_refresh_p.add_argument("--strict", action="store_true", help="Exit non-zero when a step fails")
    phase3_refresh_p.add_argument("--timeout", type=int, default=900, help="Per-step timeout seconds")
    phase3_refresh_p.set_defaults(
        func=lambda args: _run(
            [
                sys.executable,
                os.path.join(BASE_DIR, "scripts", "phase3_refresh.py"),
                *(["--strict"] if args.strict else []),
                *(["--timeout", str(args.timeout)] if args.timeout else []),
            ]
        )
    )

    approval_execution_board_p = sub.add_parser(
        "approval-execution-board",
        help="Build execution board from approved queue items",
    )
    approval_execution_board_p.add_argument("--limit", type=int, default=12, help="Max surfaced tasks")
    approval_execution_board_p.add_argument(
        "--no-mark-queued",
        action="store_true",
        help="Do not write execution metadata back to approvals.json",
    )
    approval_execution_board_p.set_defaults(
        func=lambda args: _run(
            [
                sys.executable,
                os.path.join(BASE_DIR, "scripts", "approval_execution_board.py"),
                *(["--limit", str(args.limit)] if args.limit is not None else []),
                *(["--no-mark-queued"] if args.no_mark_queued else []),
            ]
        )
    )

    revenue_queue_p = sub.add_parser(
        "revenue-action-queue",
        help="Generate the revenue action queue from latest agent outputs",
    )
    revenue_queue_p.set_defaults(
        func=lambda _args: _run(
            [
                sys.executable,
                os.path.join(BASE_DIR, "scripts", "revenue_action_queue.py"),
            ]
        )
    )

    revenue_arch_p = sub.add_parser(
        "revenue-architecture",
        help="Generate Revenue Architecture v1 scorecard + pipeline report",
    )
    revenue_arch_p.set_defaults(
        func=lambda _args: _run(
            [
                sys.executable,
                os.path.join(BASE_DIR, "scripts", "revenue_architecture_report.py"),
            ]
        )
    )

    revenue_recovery_p = sub.add_parser(
        "revenue-cost-recovery",
        help="Generate cost-recovery plan to cover API/tool spend via revenue actions",
    )
    revenue_recovery_p.add_argument(
        "--force-template",
        action="store_true",
        help="Rewrite memory/working/api_cost_plan.json with default values before planning",
    )
    revenue_recovery_p.set_defaults(
        func=lambda args: _run(
            [
                sys.executable,
                os.path.join(BASE_DIR, "scripts", "revenue_cost_recovery.py"),
                *(["--force-template"] if args.force_template else []),
            ]
        )
    )

    revenue_board_p = sub.add_parser(
        "revenue-execution-board",
        help="Generate the daily revenue execution board",
    )
    revenue_board_p.set_defaults(
        func=lambda _args: _run(
            [
                sys.executable,
                os.path.join(BASE_DIR, "scripts", "revenue_execution_board.py"),
            ]
        )
    )

    revenue_weekly_p = sub.add_parser(
        "revenue-weekly-summary",
        help="Generate weekly revenue summary report",
    )
    revenue_weekly_p.set_defaults(
        func=lambda _args: _run(
            [
                sys.executable,
                os.path.join(BASE_DIR, "scripts", "revenue_weekly_summary.py"),
            ]
        )
    )

    revenue_outreach_p = sub.add_parser(
        "revenue-outreach-pack",
        help="Generate outreach message drafts from open pipeline leads",
    )
    revenue_outreach_p.set_defaults(
        func=lambda _args: _run(
            [
                sys.executable,
                os.path.join(BASE_DIR, "scripts", "revenue_outreach_pack.py"),
            ]
        )
    )

    revenue_followup_p = sub.add_parser(
        "revenue-followup-queue",
        help="Generate outreach follow-up queue from sent/replied status",
    )
    revenue_followup_p.set_defaults(
        func=lambda _args: _run(
            [
                sys.executable,
                os.path.join(BASE_DIR, "scripts", "revenue_followup_queue.py"),
            ]
        )
    )

    revenue_eval_p = sub.add_parser(
        "revenue-eval",
        help="Run Revenue Ops evaluation harness",
    )
    revenue_eval_p.set_defaults(
        func=lambda _args: _run(
            [
                sys.executable,
                os.path.join(BASE_DIR, "scripts", "revenue_eval.py"),
            ]
        )
    )

    revenue_backup_p = sub.add_parser(
        "revenue-backup",
        help="Create timestamped revenue backup bundle",
    )
    revenue_backup_p.add_argument("--dest-dir", help="Backup destination directory")
    revenue_backup_p.set_defaults(
        func=lambda args: _run(
            [
                sys.executable,
                os.path.join(BASE_DIR, "scripts", "revenue_backup.py"),
                *(["--dest-dir", args.dest_dir] if args.dest_dir else []),
            ]
        )
    )

    revenue_playbook_p = sub.add_parser(
        "revenue-playbook",
        help="Manage locked offer + CTA playbook for revenue ops",
    )
    revenue_playbook_p.add_argument(
        "playbook_args",
        nargs=argparse.REMAINDER,
        help="Args for scripts/revenue_playbook.py (e.g. set --cta-keyword FOUNDATION)",
    )
    revenue_playbook_p.set_defaults(
        func=lambda args: _run(
            [
                sys.executable,
                os.path.join(BASE_DIR, "scripts", "revenue_playbook.py"),
                *args.playbook_args,
            ]
        )
    )

    revenue_targets_p = sub.add_parser(
        "revenue-targets",
        help="Manage locked revenue targets for revenue ops",
    )
    revenue_targets_p.add_argument(
        "targets_args",
        nargs=argparse.REMAINDER,
        help="Args for scripts/revenue_targets.py (e.g. set --weekly-revenue-target 5000)",
    )
    revenue_targets_p.set_defaults(
        func=lambda args: _run(
            [
                sys.executable,
                os.path.join(BASE_DIR, "scripts", "revenue_targets.py"),
                *args.targets_args,
            ]
        )
    )

    sales_pipeline_p = sub.add_parser(
        "sales-pipeline",
        help="Forward sales pipeline subcommands to scripts/sales_pipeline.py",
    )
    sales_pipeline_p.add_argument(
        "pipeline_args",
        nargs=argparse.REMAINDER,
        help="Args for sales_pipeline.py (e.g. add --name \"Lead\" ...)",
    )
    sales_pipeline_p.set_defaults(
        func=lambda args: _run(
            [
                sys.executable,
                os.path.join(BASE_DIR, "scripts", "sales_pipeline.py"),
                *args.pipeline_args,
            ]
        )
    )

    life_brief_p = sub.add_parser(
        "life-os-brief",
        help="Generate daily Life OS brief (personal second-brain layer)",
    )
    life_brief_p.set_defaults(
        func=lambda _args: _run(
            [
                sys.executable,
                os.path.join(BASE_DIR, "scripts", "life_os_brief.py"),
            ]
        )
    )

    side_portfolio_p = sub.add_parser(
        "side-business-portfolio",
        help="Generate side-business portfolio priorities and actions",
    )
    side_portfolio_p.set_defaults(
        func=lambda _args: _run(
            [
                sys.executable,
                os.path.join(BASE_DIR, "scripts", "side_business_portfolio.py"),
            ]
        )
    )

    prediction_ingest_p = sub.add_parser(
        "prediction-ingest",
        help="Ingest news feeds and refresh prediction hypothesis signals",
    )
    prediction_ingest_p.set_defaults(
        func=lambda _args: _run(
            [
                sys.executable,
                os.path.join(BASE_DIR, "scripts", "prediction_ingest.py"),
            ]
        )
    )

    prediction_lab_p = sub.add_parser(
        "prediction-lab",
        help="Generate prediction-market research brief (advisory only)",
    )
    prediction_lab_p.set_defaults(
        func=lambda _args: _run(
            [
                sys.executable,
                os.path.join(BASE_DIR, "scripts", "prediction_lab.py"),
            ]
        )
    )

    clipping_ingest_p = sub.add_parser(
        "clipping-transcript-ingest",
        help="Ingest transcript files into clipping queue working state",
    )
    clipping_ingest_p.set_defaults(
        func=lambda _args: _run(
            [
                sys.executable,
                os.path.join(BASE_DIR, "scripts", "clipping_transcript_ingest.py"),
            ]
        )
    )

    clipping_p = sub.add_parser(
        "clipping-pipeline",
        help="Generate clipping queue and candidate clip rankings",
    )
    clipping_p.set_defaults(
        func=lambda _args: _run(
            [
                sys.executable,
                os.path.join(BASE_DIR, "scripts", "clipping_pipeline_manager.py"),
            ]
        )
    )

    second_brain_p = sub.add_parser(
        "second-brain-report",
        help="Generate unified second-brain report across life + business layers",
    )
    second_brain_p.set_defaults(
        func=lambda _args: _run(
            [
                sys.executable,
                os.path.join(BASE_DIR, "scripts", "second_brain_report.py"),
            ]
        )
    )

    foundation_site_p = sub.add_parser(
        "foundation-site",
        help="Serve the local FOUNDATION landing page",
    )
    foundation_site_p.add_argument("--host", default="127.0.0.1", help="Bind host")
    foundation_site_p.add_argument("--port", type=int, default=8787, help="Bind port")
    foundation_site_p.add_argument("--no-open", action="store_true", help="Do not auto-open browser")
    foundation_site_p.add_argument("--site-dir", help="Override site directory")
    foundation_site_p.set_defaults(
        func=lambda args: _run(
            [
                sys.executable,
                os.path.join(BASE_DIR, "scripts", "foundation_site.py"),
                "--host",
                args.host,
                "--port",
                str(args.port),
                *(["--no-open"] if args.no_open else []),
                *(["--site-dir", args.site_dir] if args.site_dir else []),
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

    surface_p = sub.add_parser(
        "operator-surface",
        help="Run command center + FOUNDATION site in one command",
    )
    surface_p.add_argument("--host", default="127.0.0.1", help="Bind host for both services")
    surface_p.add_argument("--dashboard-port", type=int, default=8000, help="Dashboard API port")
    surface_p.add_argument("--foundation-port", type=int, default=8787, help="FOUNDATION site port")
    surface_p.add_argument("--no-open", action="store_true", help="Do not auto-open browser tabs")
    surface_p.add_argument("--money-loop", action="store_true", help="Run one money-loop refresh before launch")
    surface_p.add_argument("--run-horizon", action="store_true", help="Run Horizon Agent before dashboard boot")
    surface_p.add_argument(
        "--demo-horizon",
        action="store_true",
        help="Use deterministic Horizon demo mode with --run-horizon",
    )
    surface_p.add_argument("--dry-run", action="store_true", help="Print commands and exit")
    surface_p.set_defaults(
        func=lambda args: _run(
            [
                sys.executable,
                os.path.join(BASE_DIR, "scripts", "operator_surface.py"),
                "--host",
                args.host,
                "--dashboard-port",
                str(args.dashboard_port),
                "--foundation-port",
                str(args.foundation_port),
                *(["--no-open"] if args.no_open else []),
                *(["--money-loop"] if args.money_loop else []),
                *(["--run-horizon"] if args.run_horizon else []),
                *(["--demo-horizon"] if args.demo_horizon else []),
                *(["--dry-run"] if args.dry_run else []),
            ]
        )
    )

    launcher_p = sub.add_parser(
        "setup-launchers",
        help="Create Desktop .command launchers for core workflows",
    )
    launcher_p.add_argument(
        "--desktop-dir",
        help="Override destination directory (default: ~/Desktop)",
    )
    launcher_p.add_argument("--force", action="store_true", help="Overwrite existing launcher files")
    launcher_p.set_defaults(
        func=lambda args: _run(
            [
                sys.executable,
                os.path.join(BASE_DIR, "scripts", "setup_desktop_launchers.py"),
                *(["--desktop-dir", args.desktop_dir] if args.desktop_dir else []),
                *(["--force"] if args.force else []),
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
