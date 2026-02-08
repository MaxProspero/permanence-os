# Permanence OS v0.3 Execution Plan

## Current Snapshot (2026-02-07)
- Ingestion and briefing pipeline operational
- NotebookLM sync operational with split fallback for oversized docs
- OpenClaw, HR reporting, and governed task pipeline active
- Automation schedule verified via `automation-verify` (07:00, 12:00, 19:00)
- Briefing and digest confirmed writing to `/Volumes/LaCie/outputs`
- Synthesis draft and approval flow validated (`outputs/synthesis/drafts` -> `outputs/synthesis/final`)

## Phase 1: Core v0.3 Foundation
- Status: Complete
- Added `canon/dna.yaml` for 3-6-9 DNA configuration
- Added `agents/base.py` with DNA-aware base model
- Added `core/polemarch.py` v0.3 routing/governor module
- Added `memory/zero_point.py` for governed shared memory writes
- Added `memory/proposal_queue.py` for Muse proposal governance
- Added `special/` agents:
  - `special/muse_agent.py`
  - `special/digital_twin.py`
  - `special/chimera_builder.py`
  - `special/arch_evolution_agent.py`

## Phase 2: Test Integration
- Status: Complete
- Added `tests/test_v03_components.py`
- Added v0.3 suite to CLI test runner in `cli.py`
- Verified v0.3 test suite: 28/28 passing
- Verified aggregate `python cli.py test`: passing

## Phase 3: Automation Hardening
- Status: Complete
- Updated `automation/run_briefing.sh` to export `PYTHONPATH` for script stability
- Added slot-aware NotebookLM sync execution and post-run status glance generation
- Added optional Ari receptionist summary slot execution (`PERMANENCE_ARI_ENABLED`, `PERMANENCE_ARI_SLOT`)
- Updated `core/storage.py` to:
  - detect both `/Volumes/LaCie_Permanence` and `/Volumes/LaCie`
  - validate write access before selecting storage root
  - fallback safely to repo-local `permanence_storage/` when mounted storage is read-only
- Verified automation run executes briefing + digest + healthcheck end-to-end

## Phase 4: Operator Surface + Reception
- Status: Complete
- Added Ari receptionist queue + summary:
  - `agents/departments/reception_agent.py`
  - `scripts/ari_reception.py`
  - CLI command: `python cli.py ari-reception`
- Added operator panel in daily briefing from glance/status files:
  - today gate, streak, phase gate, latest automation report
- Added Dell cutover verification:
  - `scripts/dell_cutover_verify.py`
  - CLI command: `python cli.py dell-cutover-verify`

## Reliability Gate Notes
- `reliability-gate --days 7` remains expected FAIL until a full 7-day window completes.
- `reliability-gate --days 1 --include-today --slots 19` can PASS after one completed 19:00 slot.
- Use the 7-day gate as the phase promotion signal, not the 1-day gate.

## Next Execution Queue
1. Let launchd run unattended for 7 consecutive days.
2. Review `/Volumes/LaCie/logs/automation_report_*.md` daily for missed slots or fallback writes.
3. Run weekly phase gate after day 7:
   - `python cli.py phase-gate --days 7`
4. Keep NotebookLM export folder populated and rely on scheduled sync.
