# PERMANENCE OS — CLAUDE.md

## IDENTITY
Owner: Payton Hicks (pbhicksfinn@gmail.com)
Project: Permanence OS / Ophtxn
Repo: github.com/MaxProspero/permanence-os (private, branch: main)
Status: Full-time founder, done with school (BS+MS Finance, U of Arkansas)
Birthday target: March 7 (v1 launch)

## WHAT THIS PROJECT IS
A governed personal intelligence OS. Three live runtimes:
- Command Center: http://127.0.0.1:8000
- Foundation Site: http://127.0.0.1:8787
- Ophtxn Shell: http://127.0.0.1:8797/app/ophtxn

## FILE LOCATIONS
- Site HTML: site/foundation/
- Python core: cli.py, dashboard_api.py, horizon_agent.py, context_loader.py, run_task.py, setup_integrations.py
- Docs: docs/
- Tests: tests/

## NEVER TOUCH
- Do NOT commit API keys or tokens
- Do NOT use Inter/Roboto/Arial/Space Grotesk as primary display fonts
- Do NOT remove governance/approval gates
- Do NOT write DOM without diffing current value first
- Do NOT use setInterval < 30000ms for health polling

## CODE STANDARDS
- Python: try/except on all file reads and network calls, AbortController on all fetches
- HTML: staggered animations via .animate:nth-child, CSS custom properties in :root, glassmorphism cards
- Commits: feat(scope): description | fix(scope): description
- Branch: codex/upgrade-YYYYMMDD

## OPERATING MODE
Complex tasks → OBSERVE → THINK → PLAN → BUILD → VERIFY
Simple tasks → just do it
Uncertain → ask ONE specific question before proceeding

## SUCCESS DEFINITION
pytest -q: 0 failures. Secret scanner: clean. local_hub: green. Pages: excellent at 1440px + 375px.
