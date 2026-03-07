# Release Notes — v0.2.1 (2026-02-03)

## Summary
This release locks in OpenClaw integration, HR system health reporting, and parallel episodic JSONL logging. It also adds maintenance tooling (cleanup, auto‑commit, snapshots) and expands CLI coverage.

## Highlights
- OpenClaw status + health capture (outputs + tool memory)
- HR Agent (The Shepherd) with OpenClaw excerpts and tool degradation awareness
- Episodic JSONL logging alongside per‑task JSON state files
- New CLI commands: briefing, dashboard, snapshot, openclaw-sync, cleanup-weekly, git-autocommit

## Notable Additions
- `scripts/openclaw_status.py` + `scripts/openclaw_health_sync.py`
- `scripts/briefing_run.py`, `scripts/dashboard_report.py`, `scripts/system_snapshot.py`
- `core/memory.py` (episodic JSONL logger)
- `docs/cli_reference.md`

## Operational Notes
- OpenClaw is treated as a tool/controller, not a peer.
- Missing sources still escalates by design.
- OpenClaw health sync writes HR notifications to `logs/hr_notifications.jsonl`.

## Compatibility
- No breaking changes to existing per‑task episodic JSON files.
- New JSONL logs are additive only.

## Next Focus (Phase 2)
- Real Researcher pipeline (sources + provenance)
- Real Executor pipeline (spec + sources → final outputs)
- Evaluation harness expansion (adversarial + failure injection)
