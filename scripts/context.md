# Scripts Workspace Context

## Goal
137 Python scripts powering automation, data pipelines, governance, and operations for Permanence OS.

## Routing Table
| Task | Read These Files | Skip These Files |
|------|-----------------|-----------------|
| Fix a Script | Target script, its test in /tests | /site, /design |
| Add Approval Gate | Target script, /scripts/approval_triage.py | /site, /design |
| Comms Bug | /scripts/comms_*.py, related test | /site, /agents |
| Revenue Feature | /scripts/revenue_*.py, related test | /site, /design |
| Chronicle Issue | /scripts/chronicle_*.py, related test | /site, /design |
| New Script | Similar existing script (template), /tests | /site, /design |

## Scripts by Category

### Approvals and Governance
| Script | Purpose | Test File |
|--------|---------|-----------|
| approval_execution_board.py | Approval execution dashboard | test_approval_execution_board.py |
| approval_triage.py | Triage incoming approval requests | test_approval_triage.py |
| external_access_policy.py | External access control | test_external_access_policy.py |
| logos_gate.py | Logos governance gate | test_logos_gate.py |
| money_first_gate.py | Spending approval gate | test_money_first_gate.py |
| money_first_lane.py | Revenue-prioritized lane routing | test_money_first_lane.py |
| no_spend_audit.py | Audit for zero-cost compliance | test_no_spend_audit.py |
| opportunity_approval_queue.py | Queue opportunities for approval | test_opportunity_approval_queue.py (if exists) |
| phase_gate.py | Phase transition governance | (none) |
| reliability_gate.py | Reliability threshold gate | (none) |
| spending_gate (core) | Core spending controls | (in /core) |

### Chronicle (Content Pipeline)
| Script | Purpose | Test File |
|--------|---------|-----------|
| chronicle_approval_queue.py | Queue chronicle items for approval | test_chronicle_approval_queue.py |
| chronicle_approve.py | Approve chronicle entries | test_chronicle_approve.py |
| chronicle_backfill.py | Backfill historical chronicle data | (none) |
| chronicle_capture.py | Capture new chronicle entries | (none) |
| chronicle_common.py | Shared chronicle utilities | (none) |
| chronicle_control.py | Chronicle pipeline control | test_chronicle_control.py |
| chronicle_execution_board.py | Chronicle execution dashboard | test_chronicle_execution_board.py |
| chronicle_publish.py | Publish chronicle content | test_chronicle_publish.py |
| chronicle_refinement.py | Refine chronicle entries | test_chronicle_refinement.py |
| chronicle_report.py | Generate chronicle reports | (none) |

### Communications
| Script | Purpose | Test File |
|--------|---------|-----------|
| comms_automation.py | Automated comms workflows | test_comms_automation.py |
| comms_digest.py | Daily comms digest | test_comms_digest.py |
| comms_doctor.py | Comms health diagnostics | test_comms_doctor.py |
| comms_escalation_digest.py | Escalation summary | test_comms_escalation_digest.py |
| comms_status.py | Comms channel status | test_comms_status.py |
| discord_feed_manager.py | Discord feed management | test_discord_feed_manager.py |
| discord_telegram_relay.py | Cross-platform relay | test_discord_telegram_relay.py |
| email_triage.py | Email classification and routing | (none) |
| gmail_ingest.py | Gmail data ingestion | test_gmail_ingest.py |
| telegram_control.py | Telegram bot control | (none) |

### Revenue and Business
| Script | Purpose | Test File |
|--------|---------|-----------|
| revenue_action_queue.py | Revenue action items queue | (none) |
| revenue_architecture_report.py | Revenue system architecture | (none) |
| revenue_backup.py | Revenue data backup | (none) |
| revenue_cost_recovery.py | Cost recovery tracking | (none) |
| revenue_eval.py | Revenue evaluation | (none) |
| revenue_execution_board.py | Revenue execution dashboard | (none) |
| revenue_followup_queue.py | Follow-up queue for revenue | (none) |
| revenue_outreach_pack.py | Outreach materials | (none) |
| revenue_playbook.py | Revenue playbook generator | (none) |
| revenue_targets.py | Revenue target tracking | (none) |
| revenue_weekly_summary.py | Weekly revenue summary | (none) |
| sales_pipeline.py | Sales pipeline management | (none) |
| side_business_portfolio.py | Side business tracking | (none) |

### Ophtxn Operations
| Script | Purpose | Test File |
|--------|---------|-----------|
| ophtxn_brain.py | Ophtxn AI brain logic | test_ophtxn_brain.py |
| ophtxn_completion.py | Completion engine | test_ophtxn_completion.py |
| ophtxn_daily_ops.py | Daily operations runner | test_ophtxn_daily_ops.py |
| ophtxn_launchpad.py | Launch sequence | test_ophtxn_launchpad.py |
| ophtxn_ops_pack.py | Operations package | test_ophtxn_ops_pack.py |
| ophtxn_production_ops.py | Production operations | test_ophtxn_production_ops.py |
| ophtxn_simulation.py | Simulation runner | (none) |

### Research and Ingestion
| Script | Purpose | Test File |
|--------|---------|-----------|
| ecosystem_research_ingest.py | Ecosystem research ingestion | test_ecosystem_research_ingest.py |
| github_research_ingest.py | GitHub research ingestion | test_github_research_ingest.py |
| github_trending_ingest.py | GitHub trending ingestion | test_github_trending_ingest.py |
| ingest_documents.py | Document ingestion | (none) |
| ingest_drive_all.py | Google Drive ingestion | (none) |
| ingest_sources.py | Source ingestion | test_ingest_sources_append.py |
| ingest_tool_outputs.py | Tool output ingestion | (none) |
| new_sources.py | New source discovery | (none) |
| prediction_ingest.py | Prediction data ingestion | (none) |
| social_research_ingest.py | Social media research | (none) |
| world_watch_ingest.py | World news ingestion | (none) |

### Automation and System
| Script | Purpose | Test File |
|--------|---------|-----------|
| automation_daily_report.py | Daily automation report | test_automation_reporting.py |
| automation_verify.py | Verify automation health | (none) |
| clean_artifacts.py | Clean build artifacts | test_clean_artifacts.py |
| cleanup_weekly.py | Weekly cleanup | (none) |
| file_organizer.py | File organization | test_file_organizer.py |
| git_autocommit.py | Automated git commits | (none) |
| secret_scan.py | Secret detection scanner | (none) |
| self_improvement_loop.py | Self-improvement automation | (none) |
| setup_desktop_launchers.py | Desktop launcher setup | (none) |
| system_snapshot.py | System state snapshot | (none) |
| status.py | System status check | (none) |
| status_glance.py | Quick status glance | (none) |

### Market and Trading
| Script | Purpose | Test File |
|--------|---------|-----------|
| market_backtest_queue.py | Backtest queue management | test_market_backtest_queue.py |
| market_focus_brief.py | Market focus briefing | test_market_focus_brief.py |
| prediction_lab.py | Prediction experimentation | (none) |
| opportunity_ranker.py | Opportunity ranking | (none) |

### Devices and Hardware
| Script | Purpose | Test File |
|--------|---------|-----------|
| dell_cutover_verify.py | Dell cutover verification | test_dell_cutover_verify.py |
| dell_remote.py | Dell remote management | test_dell_remote.py |
| glasses_autopilot.py | Smart glasses autopilot | test_glasses_autopilot.py |
| glasses_bridge.py | Smart glasses bridge | test_glasses_bridge.py |
| mac_control.py | Mac control automation | (none) |
| mac_mini_remote.py | Mac Mini remote ops | test_mac_mini_remote.py |
| remote_ready.py | Remote readiness check | (none) |

### Briefing and Reports
| Script | Purpose | Test File |
|--------|---------|-----------|
| briefing_run.py | Run daily briefing | test_briefing_run.py |
| dashboard_report.py | Dashboard report generation | (none) |
| health_summary.py | Health data summary | (none) |
| hr_report.py | HR/agent report | (none) |
| life_os_brief.py | Life OS briefing | test_life_os_brief.py |
| sources_brief.py | Sources briefing | (none) |
| sources_digest.py | Sources digest | (none) |
| synthesis_brief.py | Synthesis briefing | (none) |

### Clipping and Content
| Script | Purpose | Test File |
|--------|---------|-----------|
| clipping_pipeline_manager.py | Clipping pipeline | test_clipping_pipeline_manager.py |
| clipping_transcript_ingest.py | Transcript ingestion | test_clipping_transcript_ingest.py |
| narrative_tracker.py | Narrative tracking | test_narrative_tracker.py |
| social_draft_queue.py | Social media drafts | (none) |
| social_summary.py | Social media summary | (none) |

### Infrastructure and Integration
| Script | Purpose | Test File |
|--------|---------|-----------|
| agent_github_ops.py | Agent GitHub operations | test_agent_github_ops.py |
| anthropic_keychain.py | Anthropic API keychain | test_anthropic_keychain.py |
| arcana_cli.py | Arcana CLI tool | test_arcana_engine.py |
| ari_reception.py | ARI reception handler | test_ari_reception.py |
| attachment_pipeline.py | Attachment processing | test_attachment_pipeline.py |
| command_center.py | Command center server | (none) |
| connector_keychain.py | Connector keychain | test_connector_keychain.py |
| eval_harness.py | Evaluation harness | (none) |
| foundation_api.py | Foundation API server | (none) |
| foundation_site.py | Foundation site server | (none) |
| ghost_os_bridge.py | Ghost OS bridge | test_ghost_os_bridge.py |
| governed_learning_loop.py | Governed learning loop | test_governed_learning_loop.py |
| idea_intake.py | Idea intake pipeline | test_idea_intake.py |
| integration_readiness.py | Integration readiness check | test_integration_readiness.py |
| interface_server.py | Interface server | (none) |
| ledger_sync.py | Ledger synchronization | (none) |
| low_cost_mode.py | Low cost mode toggle | test_low_cost_mode.py |
| migrate_to_sqlite.py | SQLite migration | (none) |
| notebooklm_sync.py | NotebookLM sync | (none) |
| openclaw_health_sync.py | OpenClaw health sync | test_openclaw_health_sync.py |
| openclaw_status.py | OpenClaw status | test_openclaw_status.py |
| operator_surface.py | Operator surface | test_operator_surface.py |
| platform_change_watch.py | Platform change monitor | test_cli_platform_change_watch.py |
| practice_squad_run.py | Practice squad runner | (none) |
| promote_memory.py | Memory promotion | test_memory_promotion.py |
| promotion_daily.py | Daily promotions | (none) |
| promotion_queue.py | Promotion queue | (none) |
| promotion_review.py | Promotion review | (none) |
| reliability_streak.py | Reliability streak tracking | (none) |
| reliability_watch.py | Reliability monitoring | (none) |
| research_inbox.py | Research inbox | (none) |
| resume_brand_brief.py | Resume brand briefing | (none) |
| second_brain_init.py | Second brain initialization | (none) |
| second_brain_report.py | Second brain report | (none) |
| terminal_task_queue.py | Terminal task queue | (none) |
| v04_snapshot.py | v0.4 snapshot | (none) |
| world_watch_alerts.py | World watch alerts | (none) |
| x_account_watch.py | X/Twitter account monitoring | (none) |

## Code Standards
- All file reads wrapped in try/except
- All network calls wrapped in try/except
- All fetch calls use AbortController
- Commits: feat(scope): description or fix(scope): description
