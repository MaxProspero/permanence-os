# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]
- N/A

## [0.2.1] - 2026-02-03
- Added HR Agent (The Shepherd) implementation with weekly health reporting
- Added HR report generator script and CLI command (hr-report)
- Added HR Agent Canon amendment (CA-003) with thresholds and family covenant
- Added OpenClaw status helper script and CLI command (openclaw-status)
- Wired OpenClaw status capture into tool memory and Briefing Agent notes
- Added OpenClaw status references to HR reports and status helper output
- Auto-capture OpenClaw status + health before governed runs
- Briefing Agent includes OpenClaw status excerpt when available
- Added Briefing CLI command and HR report auto-capture of OpenClaw status/health
- Added episodic JSONL memory logger (core/memory.py) alongside existing episodic JSON files
- Added OpenClaw health sync job + CLI command (openclaw-sync)
- Added CLI reference documentation and new tests for episodic memory + OpenClaw sync + briefing
- Added dashboard report script and CLI command (dashboard)
- Added weekly cleanup + auto-commit scripts and system snapshot report
- Added promotion review checklist generator and CLI command
- Added source adapter registry and ingest-sources CLI entrypoint
- Added document ingestion for Researcher with CLI support
- Added Canon promotion queue helper script and CLI wrapper
- Added Canon promotion rubric and included it in promotion drafts
- Status helper now shows risk tier, single-source overrides, and promotion queue count
- Enforced single-source check in runner with --allow-single-source override
- Added single-source coverage to eval harness
- Added memory promotion draft generator and CLI promote command
- Added stub implementations for Researcher, Executor, Reviewer, Conciliator
- Added agent utilities and boundary tests
- Added architecture and governance docs
- Added governed task runner and sources example
- Added budget guardrails across runner stages
- Added helper script to create sources provenance file
- Added draft-aware executor packaging and stricter review checks
- Expanded .env.example with optional path overrides
- Added CLI flags for runner sources/draft overrides
- Added artifact cleanup helper script
- Added status helper script
- Added Legal Integrity and Identity Protocol amendments to the Canon
- Added compliance gate and department agent stubs
- Added identity_config.yaml and compliance gate tests
- Added unified CLI (run/add-source/status/clean/test)
- Added evaluation harness with normal/adversarial/failure tests
- Added Researcher tool-ingest pipeline and CLI ingest command
- Added auto-compose executor output from source notes

## [0.1.0] - 2026-02-02
- Established Canon v0.1.0 and core system values
- Implemented Polemarch (governor) and Planner agents
- Added initial tests and example workflow
- Added documentation and Codex integration guide
