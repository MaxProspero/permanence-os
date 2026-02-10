# Permanence OS v0.4 Execution Plan

Last updated: 2026-02-09

## Source Inputs Reviewed
- `/Users/paytonhicks/Documents/Documents - Payton’s MacBook Air/UARK MSF/Quantum + Future + Study/Permanence Systems - files /Permanence_OS_v04_Codex_Instructions.docx`
- `/Users/paytonhicks/Documents/Documents - Payton’s MacBook Air/UARK MSF/Quantum + Future + Study/Permanence Systems - files /Permanence_Systems_Executive_Overview_v4.docx`
- `/Users/paytonhicks/Documents/Permanence OS/permanence-os/CODEX_BRIEFING_v0.3.0.md`

## v0.4 Directive Coverage Status
- `Sibling Dynamics refactor`: implemented and guarded by `tests/test_sibling_dynamics.py`.
- `Interface Agent (Layer 6)`: implemented in `core/interface_agent.py` with intake sanitization, provenance, ticket responses, and Polemarch routing.
- `Practice Squad (Layer 5.5)`: implemented in `special/practice_squad.py` with scrimmage and hyper-sim entry points.
- `Arcana Engine`: implemented in `special/arcana_engine.py` with digital root scan + looking-glass projection hooks.
- `Digital Twin Looking Glass support`: implemented in `special/digital_twin.py` (`project_timeline`).
- `Polemarch intake listener`: implemented in `core/polemarch.py` (`poll_intake` + `assess_risk`).
- `CLI expansion`: implemented in `cli.py` (`server`, `scrimmage`, `looking-glass`, `hyper-sim`, `arcana scan`).
- `v0.4 tests`: implemented in `tests/test_interface_agent.py`, `tests/test_practice_squad.py`, `tests/test_arcana_engine.py`, and `tests/test_sibling_dynamics.py`.

## Operational Defaults (Current)
- Primary storage root: `PERMANENCE_STORAGE_ROOT=/Volumes/LaCie`.
- Briefing automation schedule: 07:00, 12:00, 19:00 local.
- NotebookLM sync: enabled via `PERMANENCE_NOTEBOOKLM_SYNC=1`.
- Reliability watch: arm once and let it self-run in background for 7 days.

## Runbook: One-Time Setup, Minimal Daily Friction
1. Verify automation is loaded:
   - `python cli.py automation-verify`
2. Verify one manual run succeeds:
   - `bash automation/run_briefing.sh`
3. Arm reliability watch once for 7 days:
   - `python cli.py reliability-watch --arm --days 7 --check-interval-minutes 30`
4. Check status only when needed:
   - `python cli.py reliability-watch --status`
5. After 7 days, validate gate:
   - `python cli.py reliability-gate --days 7`

## Physical Outputs You Can Open
- Briefings: `/Volumes/LaCie/outputs/briefings`
- Digests: `/Volumes/LaCie/outputs/digests`
- Synthesis drafts/finals: `/Volumes/LaCie/outputs/synthesis/drafts` and `/Volumes/LaCie/outputs/synthesis/final`
- v0.4 snapshots: `/Volumes/LaCie/outputs/snapshots`
- NotebookLM archive: `/Volumes/LaCie/archives/notebooklm`

## Next Technical Milestones
1. Maintain 7-day reliability pass under scheduled slots (no manual overrides).
2. Keep NotebookLM sync stable for large doc splits; review skipped/failed items weekly.
3. Perform Dell cutover only after stable reliability pass:
   - `python cli.py dell-cutover-verify`
4. After cutover verification, migrate scheduler to Dell and keep Mac as fallback controller.
