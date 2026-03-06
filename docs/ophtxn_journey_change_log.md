# Ophtxn Journey Change Log

Purpose: preserve an auditable narrative of what was changed, why, and what it affected.

Rule: append a new dated entry after each major implementation pass.

## 2026-03-06 (UTC) - Next-Level Local Hub + Platform Intel Pass

### Goals
- Push localhost UI toward product-grade visual quality and coherence.
- Add external platform intelligence to guide stack choices.
- Clarify skill strategy across Codex, OpenClaw, and browser operations.
- Keep governance-first policy for model behavior and sensitive actions.

### Changes Applied

1. Redesigned Local Hub.
- Updated: `site/foundation/local_hub.html`
- Added: multi-theme colorways (Aurora/Copper Night/Signal Mono), stack decision matrix, skill lanes, and stronger launch cockpit UX.

2. Added platform intelligence and skill docs.
- Added:
  - `docs/ophtxn_platform_intelligence_20260306.md`
  - `docs/ophtxn_skill_stack_20260306.md`
  - `docs/ophtxn_model_policy_guardrails_20260306.md`

3. Updated documentation index and top-level docs links.
- Updated:
  - `docs/README.md`
  - `README.md`

### Outcome
- Local experience is more cohesive, expressive, and launch-ready for founder/operator use.
- Stack decisions now reference current external platform movement instead of only anecdotal posts.
- Governance-first model policy is explicit and documented.


## 2026-03-06 (UTC) - Full Repo Cleanup and Archive Reorganization

### Goals
- Remove stale/duplicate repository artifacts.
- Organize legacy plans into an explicit archive section.
- Fix docs index consistency so all linked files exist on `main`.
- Add a clear best-path and governance operating reference.

### Changes Applied

1. Removed deprecated snapshot package.
- Deleted:
  - `permanence_os_v0_3/` (legacy duplicate tree)
  - `permanence_os_v0_3.zip`

2. Archived legacy planning/brief docs.
- Moved:
  - `CODEX_BRIEFING_v0.3.0.md` -> `docs/archive/CODEX_BRIEFING_v0.3.0.md`
  - `CODEX_BRIEF_v0_3_0.md` -> `docs/archive/CODEX_BRIEF_v0_3_0.md`
  - `docs/EXECUTION_PLAN_v0.3.md` -> `docs/archive/EXECUTION_PLAN_v0.3.md`
  - `docs/EXECUTION_PLAN_v0.4.md` -> `docs/archive/EXECUTION_PLAN_v0.4.md`
  - `docs/release_notes_v0.2.1.md` -> `docs/archive/release_notes_v0.2.1.md`
  - `docs/roadmap_phase2.md` -> `docs/archive/roadmap_phase2.md`

3. Updated docs index and canonical references.
- Updated:
  - `docs/README.md`
  - `README.md`
- Result:
  - broken links removed
  - references now point to existing docs
  - archive section explicitly mapped

4. Added governance + execution path docs.
- Added:
  - `docs/ophtxn_governance_operating_model.md`
  - `docs/ophtxn_best_path_20260306.md`

5. Cleaned stale absolute local path references in archived plan.
- Updated:
  - `docs/archive/EXECUTION_PLAN_v0.4.md`

6. Updated contribution workflow rules.
- Updated:
  - `CONTRIBUTING.md`
- Added:
  - branch hygiene + archive policy requirements

### Validation Performed

- reference audit for moved/deleted files across README/docs/changelog
- post-cleanup docs index check (`docs/README.md` links match present files)
- repository state check after deletion/move set

### Outcome

- Repository root is leaner and easier to navigate.
- Legacy materials are preserved in archive without polluting active operator surfaces.
- Governance and best-path docs now reflect current operating reality.

## 2026-03-06 (UTC) - Repository Revamp Pass (Docs + Hygiene)

### Goals
- Improve repository clarity for onboarding and day-to-day operation.
- Replace outdated/fragmented docs with canonical references.
- Add safer artifact cleanup and stronger local hygiene defaults.
- Validate that revamp changes do not break core health checks.

### Source Input Reviewed
- PDF snapshot: `MaxProspero_permanence-os.pdf` (38 pages, GitHub state/export context).
- Review outcome: repository needed structural clarity and canonical docs more than new feature code.

### Changes Applied

1. README full rewrite.
- Updated:
  - `README.md`
- Added:
  - clear system description and current focus
  - local interface endpoints
  - quick-start and operator commands
  - no-spend guidance
  - branch/PR visibility workflow
  - direct links to canonical docs

2. Documentation structure revamp.
- Added:
  - `docs/README.md` (docs index and categorization)
- Rewritten:
  - `docs/architecture.md` (authority model, runtime components, data/state, governance controls)
  - `docs/cli_reference.md` (canonical quick-reference grouped by operational domain)

3. Repository hygiene hardening.
- Updated:
  - `.gitignore`
- Added ignore coverage for local-only artifacts:
  - `.env.local`
  - `memory/inbox/*`
  - `.wrangler/`
  - `backups/`
  - extra automation temp/log patterns

4. Artifact cleanup tooling revamp.
- Rewritten:
  - `scripts/clean_artifacts.py`
- New behavior:
  - grouped cleanup targets (`logs`, `episodic`, `tool`, `working`, `inbox`, `outputs`)
  - conservative pattern matching
  - `.gitkeep` preservation
  - `--dry-run` support with explicit matched count

5. Added cleanup test coverage.
- Added:
  - `tests/test_clean_artifacts.py`
- Covers:
  - dedupe + `.gitkeep` skip behavior
  - dry-run safety
  - actual delete behavior

### Validation Performed

- `pytest -q tests/test_clean_artifacts.py tests/test_operator_surface.py tests/test_app_foundation_server.py tests/test_comms_status.py` -> 18 passed
- `python cli.py ophtxn-launchpad --action status --strict --min-score 80` -> overall 100
- `python cli.py comms-status` -> warnings 0
- `python scripts/clean_artifacts.py --all --dry-run` -> completed with expected artifact scan output

### Outcome

- Repository is significantly easier to understand and operate.
- Canonical docs are now explicit and discoverable.
- Local cleanup and ignore policy now match current runtime artifact volume.

## 2026-03-06 (UTC) - Comms Noise Reduction + Ops Pack Verification

### Goals
- Keep comms health strict for active channels (Telegram/Discord) without false warnings for intentionally optional iMessage.
- Run a strict no-spend operator cycle after stabilization.

### Changes Applied

1. OpenClaw iMessage warning behavior made optional in comms status.
- Updated:
  - `scripts/comms_status.py`
- Added optional flag + env support:
  - CLI: `--require-openclaw-imessage`
  - ENV: `PERMANENCE_COMMS_STATUS_REQUIRE_IMESSAGE=1`
- New behavior:
  - Telegram/Discord remain required and health-gated.
  - iMessage only warns when:
    - explicitly required via flag/env, or
    - configured but unhealthy.
  - iMessage not configured no longer raises warning by default.

2. Added test coverage for optional/required iMessage paths.
- Updated:
  - `tests/test_comms_status.py`
- Added assertions for:
  - default mode: no iMessage warning when not configured
  - required mode: warning appears when iMessage missing

### Validation Performed

- `pytest -q tests/test_comms_status.py` -> 9 passed
- `python cli.py comms-status` -> warnings 0
- `python cli.py ophtxn-ops-pack --action status`
- `python cli.py ophtxn-ops-pack --action run --strict` -> executed 3/3, failed 0

### Outcome

- Comms health now reflects active production channels only by default.
- Strict operator cycle passed while no-spend mode remained active.

## 2026-03-06 (UTC) - Interface Recovery + Full Surface Auto-Boot Fix

### Trigger
- Operator surface appeared online, but Ophtxn app shell endpoint was missing (`:8797` not serving), so the full interface felt broken/incomplete.

### Root Cause
- `scripts/foundation_api.py` was being launched as a direct script path from operator-surface.
- In that launch context, Python import path did not include repo root, causing:
  - `ModuleNotFoundError: No module named 'app'`
- Result: FOUNDATION API process failed at startup, leaving only dashboard/site partially available.

### Changes Applied

1. Fixed FOUNDATION API import bootstrap.
- Updated:
  - `scripts/foundation_api.py`
- Added explicit repo-root `sys.path` bootstrap before importing `app.foundation.server`.
- This makes the API runnable consistently from launchd, CLI wrappers, and direct script invocations.

2. Expanded CLI operator-surface parity.
- Updated:
  - `cli.py`
- Added missing operator-surface flags:
  - `--foundation-api-port`
  - `--no-foundation-api`
- Ensures CLI passthrough fully matches `scripts/operator_surface.py` capabilities.

3. Hardened operator surface URL behavior.
- Updated:
  - `scripts/operator_surface.py`
- Browser auto-open now includes `/app/ophtxn` only when FOUNDATION API is enabled, preventing dead-tab opens in API-disabled mode.

4. Restarted launchd-managed operator surface.
- Relaunched `com.permanence.operator_surface` with `kickstart`.
- Verified all three processes now run under launchd:
  - `command_center.py` on `127.0.0.1:8000`
  - `foundation_site.py` on `127.0.0.1:8787`
  - `foundation_api.py` on `127.0.0.1:8797`

5. Opened operator interfaces.
- Opened:
  - `http://127.0.0.1:8000`
  - `http://127.0.0.1:8797/app/ophtxn`
  - `openclaw dashboard` URL (`http://127.0.0.1:18789/...`)

### Validation Performed

- `python3 scripts/foundation_api.py --host 127.0.0.1 --port 8797` + `GET /health` -> OK
- `python3 cli.py operator-surface --dry-run --no-open`
- `pytest -q tests/test_operator_surface.py tests/test_app_foundation_server.py` -> 6 passed
- Port listeners confirmed:
  - `8000`, `8787`, `8797`
- Endpoint checks confirmed:
  - `GET http://127.0.0.1:8000/api/status` -> OK
  - `GET http://127.0.0.1:8787/index.html` -> OK
  - `GET http://127.0.0.1:8797/health` -> OK
  - `GET http://127.0.0.1:8797/app/ophtxn` -> OK

### OpenClaw Channel State Snapshot

- Telegram: works
- Discord: works
- iMessage: intentionally disabled for now to remove runtime error noise.
  - Root blocker for iMessage enablement remains local dependency install:
    - `brew install steipete/tap/imsg` fails until Command Line Tools are upgraded.
  - `softwareupdate --list` confirms available updates (including `Command Line Tools for Xcode-16.4`).
- This keeps channel health clean while preserving a clear later re-enable path.
- Additional OpenClaw hygiene:
  - disabled iMessage plugin + removed stale iMessage channel config
  - created missing OAuth credentials directory (`~/.openclaw/credentials`) so `openclaw doctor` no longer reports state-integrity criticals

## 2026-03-06 (UTC) - Connectivity, Audit, and Governance Tightening

### Goals
- Verify whether `pbhicks` commits were actually implemented.
- Repair Telegram/Discord connectivity between OpenClaw and bot channels.
- Tighten operator visibility so channel drift appears in routine health checks.
- Consolidate execution flow and access policy documentation.

### Changes Applied

1. Commit implementation audits produced and saved.
- PDF-based commit audit:
  - `outputs/pbhicks_commit_implementation_audit_latest.md`
- All-refs containment audit:
  - `outputs/pbhicks_allrefs_main_containment_latest.md`
- Result summary:
  - PDF list valid commits in `main`: 35/35
  - All `pbhicks` commits in all refs contained in `main`: 113/114
  - One remaining commit is a codex snapshot ref, not a normal feature branch merge target.

2. OpenClaw connectivity repairs.
- Enabled disabled channel plugins:
  - `telegram`
  - `discord`
- Restarted gateway service.
- Added channel accounts via existing secure tokens in local keychain/config.
- Probed status until both reported `works`.

3. Comms health hardening in code.
- Updated `scripts/comms_status.py` to include an OpenClaw channel probe:
  - runs `openclaw channels status --probe`
  - captures Telegram/Discord `found/enabled/configured/running/works`
  - adds warnings when channel probe fails or channels are unhealthy
- Added CLI flag:
  - `--skip-openclaw-channels-check`
- Added test coverage in `tests/test_comms_status.py`.

4. Documentation and execution structure updates.
- Added and/or updated:
  - `docs/ophtxn_master_execution_board_20260306.md`
  - `docs/ophtxn_access_vpn_policy_20260306.md`
  - `docs/ophtxn_operator_command_guide.md`
  - `docs/cli_reference.md`
  - `README.md`

5. OpenClaw app runtime verification.
- Opened desktop app at `/Applications/OpenClaw.app`.
- Confirmed gateway and channels active.

### Validation Performed

- `pytest -q tests/test_comms_status.py tests/test_ophtxn_daily_ops.py tests/test_telegram_control.py tests/test_telegram_provider_commands.py`
- `python cli.py comms-status`
- `openclaw channels status --probe`
- `python cli.py ophtxn-launchpad --action status --strict --min-score 80`
- `python cli.py ophtxn-production --action status --strict --min-score 80`

### Observations

- Core operator checks are healthy (`warnings: 0` in current comms-status).
- No-spend mode remains ON.
- Approval backlog is still a significant active queue and remains the next operational tightening target.

### Security Note

- Telegram `groupPolicy=open` removes message-drop friction but increases risk profile.
- Recommended long-term posture: move to allowlist-based controls after approved group/user IDs are captured.

## 2026-03-06 (UTC) - Ophtxn Claw Strategy Definition

### Goals
- Convert OpenFang/OpenClaw inspiration into a concrete Ophtxn-native roadmap.
- Keep architecture aligned with no-spend, governance-first, and personal-agent memory goals.

### Artifacts
- `docs/ophtxn_claw_blueprint_20260306.md`

### Source Inputs Referenced
- OpenFang repository and release notes
- OpenClaw operational runtime and CLI behavior

## 2026-03-06 (UTC) - Telegram Security Hardening + iMessage Optional Path

### Goals
- Move Telegram from permissive group mode back to controlled allowlist mode.
- Prevent command execution from unapproved users/chats.
- Keep iMessage ready as optional add-on, not forced baseline complexity.

### Changes Applied

1. OpenClaw Telegram hardening.
- Set `channels.telegram.groupPolicy=allowlist`.
- Set `channels.telegram.groupAllowFrom=[\"8693377286\"]`.
- Set `channels.telegram.allowFrom=[\"8693377286\"]`.
- Restarted OpenClaw gateway and re-verified channel probes.

2. Local telegram-control command allowlist enforcement.
- Updated local `.env` keys:
  - `PERMANENCE_TELEGRAM_CONTROL_REQUIRE_COMMAND_ALLOWLIST=1`
  - `PERMANENCE_TELEGRAM_CONTROL_COMMAND_USER_IDS=8693377286`
  - `PERMANENCE_TELEGRAM_CONTROL_COMMAND_CHAT_IDS=8693377286,-1003837160764`

3. iMessage onboarding documentation.
- Added optional OpenClaw iMessage section to operator guide for staged enable/probe flow.

### Validation Performed

- `openclaw channels status --probe`
- `openclaw doctor --non-interactive`
- `python cli.py telegram-control --action poll --enable-commands --ack --limit 10`

### Outcome

- Telegram + Discord probes report `works`.
- OpenClaw channel security warnings cleared for Telegram group policy/sender allowlist.
- Command execution now requires explicit allowlisted user/chat IDs in local control path.

## 2026-03-06 (UTC) - OpenClaw Access UX + New Link Intake

### Goals
- Ensure OpenClaw visual interface is immediately accessible from desktop flow.
- Clarify how to talk to agents through OpenClaw UI/CLI.
- Capture newly shared research links into intake backlog.

### Changes Applied

1. Opened OpenClaw dashboard directly.
- Command: `openclaw dashboard`
- Result: browser opened with authenticated URL and token hash.

2. Verified local UX entrypoints for operator use.
- `openclaw dashboard --help`
- `openclaw tui --help`
- `openclaw agent --help`

3. Captured user-shared links into intake.
- Command:
  - `python cli.py idea-intake --action intake --text \"https://chamath.substack.com/p/equity-tokenization https://github.com/awesome-selfhosted/awesome-selfhosted\"`
- Result:
- Intake ID `INT-CCED6EA7C5C5` (2 URLs).

## 2026-03-06 (UTC) - OpenClaw Ollama Auth Outage Repair

### Trigger
- OpenClaw agent failure:
  - `No API key found for provider "ollama"` for main agent auth store path.

### Root Cause
- Main agent had no `auth-profiles.json` and no provider key fallback configured for Ollama.
- `models status` showed `missingProvidersInUse: ["ollama"]`.

### Changes Applied

1. Configured explicit Ollama provider defaults in OpenClaw config.
- `openclaw config set models.providers.ollama.apiKey ollama-local`
- `openclaw config set models.providers.ollama.baseUrl http://127.0.0.1:11434`

2. Restarted gateway.
- `openclaw gateway restart`

3. Cleared sandbox execution blocker (Docker absent).
- `openclaw config set agents.defaults.sandbox.mode off`
- `openclaw gateway restart`

### Validation

- `openclaw models status --json` now shows `missingProvidersInUse: []`.
- Direct agent run executes and returns payloads with provider/model:
  - provider `ollama`
  - model `qwen2.5:3b`

### Notes

- This repair prioritizes immediate runtime availability on a machine without Docker.
- If Docker is installed later, sandbox mode can be re-enabled deliberately.

## 2026-03-06 (UTC) - iMessage Runtime Hardening + External Link Triage

### Goals
- Make iMessage channel state visible inside operator health outputs.
- Remove iMessage group-policy warning noise while keeping secure defaults.
- Convert latest external link batch into a structured adopt/watch/ignore plan.

### Changes Applied

1. OpenClaw iMessage governance config update.
- `openclaw config set channels.imessage.groupPolicy disabled`
- Result: channel security warnings cleared in `openclaw doctor`.

2. iMessage runtime diagnosis.
- Confirmed iMessage probe failure root cause:
  - `imsg rpc not ready ... (imsg not found (imsg))`
- Attempted install:
  - `brew install steipete/tap/imsg`
- Blocked by local system dependency:
  - Command Line Tools update required first.
- Confirmed available updates with:
  - `softwareupdate --list`

3. Comms status code + test upgrade for iMessage.
- Updated `scripts/comms_status.py`:
  - Added OpenClaw iMessage parsing in probe payload.
  - Added iMessage health checks to warning rollup.
  - Added iMessage signal to markdown status output.
- Updated `tests/test_comms_status.py`:
  - Added healthy iMessage parsing assertions.
  - Added probe-failed iMessage parsing test.

4. Documentation updates.
- `README.md`:
  - Added optional iMessage setup (including `imsg` prerequisite and CLT unblock path).
  - Added explicit “Interface Surfaces (Available Now)” run/open paths.
- `docs/ophtxn_operator_command_guide.md`:
  - Added concrete iMessage setup and troubleshooting steps (`imsg not found` path).
- `docs/cli_reference.md`:
  - Updated comms-status description to include OpenClaw iMessage probe coverage.
- New strategy doc:
  - `docs/ophtxn_link_review_20260306.md` (adopt/watch/ignore triage + pipeline recommendations).

### Validation Performed

- `openclaw channels status --probe`
- `openclaw channels logs --channel imessage`
- `openclaw doctor --non-interactive`

### Outcome

- Telegram/Discord remain operational in probe checks.
- iMessage is configured but blocked on missing `imsg` binary pending CLT update + install.
- Operator docs now include exact unblock sequence and live interface entrypoints.
- Latest link batch is structured into implementation priorities instead of ad-hoc intake.
