# Session Handoff: Design Research + Sprint 3 + Test Fixes
**Date:** 2026-03-19
**Branch:** main
**Test State:** 1,053 passed, 0 failures (175 test files, 152 scripts)

---

## What Was Built This Session

### 1. Sprint 3 Committed (edc484b)
28 files changed, 2,725 insertions. Includes:
- SMC/ICT live overlays wired to Trading Room (chart overlays + backtest tab)
- OCA Lead Generator (`scripts/oca_lead_generator.py`) -- scrapes SAM.gov, LinkedIn, industry directories for boring-wedge client leads
- OCA Proposal Generator (`scripts/oca_proposal_generator.py`) -- generates scoped proposals from leads with pricing and timeline
- ECC (Evolutionary Context Cascade) patterns: 28 files across `rules/`, `.agents/`, `contexts/`, `.claude/commands/`, `scripts/hooks/`
- New tests: `tests/test_oca_lead_generator.py` (23 tests), `tests/test_oca_proposal_generator.py` (47 tests)

### 2. All 23 Pre-Existing Test Failures Fixed (c6606d6)
Root causes identified and resolved:
- `tests/test_spending_gate.py` -- env variable pollution between test runs; added isolation
- `tests/test_model_router_providers.py` -- provider capability caps leaking via env; added env clear
- `dashboard_api.py` -- approve-all endpoint bug + file locking race condition
- Result: 1,053/1,053 tests passing, clean slate

### 3. Foundation Site Diagnosis
**Root cause of unresponsive pages:** `site/foundation/surface-system.js` (added by Codex on March 15) was rewriting ALL anchor hrefs to point to port 8797, breaking navigation on the :8787 static server.
- Created old-version server on port 8788 to prove pages work without surface-system.js
- Confirmed fix: removing surface-system.js script tag restores full interactivity
- Old working site backup exists at: `/Users/permanence-os/permanence-os/site/foundation/`

### 4. Design Research (9 Reports)
Deep research conducted across these targets:
1. Perplexity -- layout, typography, color, spacing patterns
2. Claude (claude.ai) -- chat interface, sidebar, input patterns
3. Apple -- product page structure, typography scale, whitespace
4. ChatGPT -- conversation UI patterns
5. Google Gemini / Material Design 3 -- surface system, color roles
6. Trending AI apps -- current design patterns across the category
7. Design inspiration sites -- Dribbble, Behance, Awwwards trends
8. GitHub repos + icon libraries -- actionable tools catalog
9. Comprehensive synthesis -- merged findings into design tokens

---

## Design Research Key Findings

### Color Validation
- Transformative Teal is WGSN Color of the Year 2026 -- validates our `--c1` (#00e5c4)
- All top apps use monochromatic base + ONE accent color, not multiple

### Layout Patterns (universal across Perplexity, Claude, Apple)
- Narrow content columns: 650-980px max-width
- 3-4 font sizes maximum (hero 48px, section 28px, body 17px, meta 12px)
- No decorative borders -- separation via spacing and subtle background shifts
- Section padding: 64-80px vertical

### Glass CSS Sweet Spot
- Background: `rgba(255, 255, 255, 0.05-0.12)`
- Blur: `10-20px`
- Border: `1px solid rgba(255, 255, 255, 0.10-0.18)`

### Icon Libraries
- Primary recommendation: Solar Icons (dark-interface-first design)
- Secondary: Phosphor Icons
- Both available as SVG sprite sheets

### Tool
- `nextlevelbuilder/ui-ux-pro-max-skill` being installed as Claude Code skill for design token generation

---

## User's Design Direction

**Aesthetic:** "Warm precision" -- governed intelligence that feels like home. Tech + southern charm, Magnolia meets clean code.

**Color Palette:**
- Primary accent: teal `#00e5c4` (--c1)
- Secondary accent: gold `#efbb5f` (--c2)
- Base background: `#0A0A0F` (warm dark, not pure black)
- Text: `#e0e0e0` (off-white, not pure white)
- Cards: `#1C1C1E`

**Reference Companies:** Apple, Perplexity, Claude, Linear, Wealthsimple, Arc

**Identity Elements to Keep:**
- System tags and world-building language (v1.0, Canon Active, etc.)
- Permanence OS branding and terminology
- Glassmorphism cards (refined, not overdone)

**Design Workflow:**
Google Stitch (generate concepts) -> Figma Make (refine layouts) -> Claude Code + Figma MCP -> build in code

**Critical User Feedback:**
- Remove ALL emojis (hard rule in CLAUDE.md)
- Max 1 link per destination per page -- eliminate redundant navigation
- Remove surface-system dock overlay entirely
- Terminal (ophtxn_shell) should feel like Claude's chat interface
- "Less is more" -- strip everything that does not earn its place
- Quality bar: Perplexity/Apple, not generic dashboard-ware

---

## What Is Next (Priority Order)

### Priority 1: Fix surface-system.js (THE blocker)
- File: `site/foundation/surface-system.js`
- Problem: Rewrites all links to port 8797, breaking navigation
- Options: (a) remove it entirely, (b) rewrite to respect current port, (c) make it opt-in
- This blocks all other page work

### Priority 2: Design System CSS
- Apply nextlevelbuilder/ui-ux-pro-max-skill to generate design tokens
- Create or finalize `site/foundation/design-system.css` (file already exists as untracked)
- Tokens should encode the color palette, typography scale, spacing, glass properties documented above

### Priority 3: Rebuild Pages (in order)
1. `index.html` (Lobby) -- template page, establishes the pattern
2. `local_hub.html` (Control Room) -- strip redundancy, glass cards, single nav
3. `ophtxn_shell.html` (Terminal) -- Claude-style chat interface
4. `trading_room.html` -- keep chart overlays from Sprint 3, clean everything else
5. `command_center.html` -- dashboard layout
6. Remaining 9 pages inherit the design system

---

## Files Modified This Session

### Backend
- `dashboard_api.py` -- 5 new API endpoints, approve-all fix, file locking fix

### Frontend
- `site/foundation/trading_room.html` -- chart overlays, backtest tab
- `site/foundation/surface-system.js` -- diagnosed as root cause (staged change)
- `site/foundation/agent_view.html` -- staged change
- Multiple other `site/foundation/*.html` files have unstaged modifications

### New Files
- `scripts/oca_lead_generator.py`
- `scripts/oca_proposal_generator.py`
- `tests/test_oca_lead_generator.py` (23 tests)
- `tests/test_oca_proposal_generator.py` (47 tests)
- 28 ECC pattern files across `rules/`, `.agents/`, `contexts/`, `.claude/commands/`, `scripts/hooks/`

### Test Fixes
- `tests/test_spending_gate.py` -- env isolation
- `tests/test_model_router_providers.py` -- env clear

### Untracked (not yet committed)
- `docs/design_research_dark_glassmorphism_2026-03-19.md`
- `docs/session_handoff/` (this directory)
- `scripts/fix_perf.py`
- `scripts/restore_effects.py`
- `site/foundation/clear-cache.html`
- `site/foundation/design-system.css`
- `site/foundation/test_nav.html`

---

## Memory Files Updated

These persist across sessions in `~/.claude/projects/-Users-permanence-os-Code-permanence-os/memory/`:
- `reference_design_system.md` -- synthesized design tokens from all 9 research reports
- `reference_design_resources.md` -- GitHub repos, icon libraries, tools catalog
- `feedback_ui_design.md` -- critical UI feedback (too much redundancy, needs Perplexity/Apple quality)
- `feedback_design_process.md` -- design-first workflow preferences
- `user_aesthetic.md` -- "warm precision" aesthetic, color palette, reference companies

---

## Active Infrastructure

| Service | Port | Status |
|---------|------|--------|
| Foundation Site | :8787 | Running (static HTML) |
| Command Center | :8000 | Running (Flask backend) |
| Foundation API | :8797 | Running |
| Old version server | :8788 | Created this session for comparison |

---

## Context for Next Agent

You are continuing a design overhaul of 14 HTML pages. The codebase is healthy (1,053 tests, 0 failures). The research is done. The user's preferences are documented. The blocker (surface-system.js) is identified. Start by fixing the blocker, then build the design system CSS, then rebuild pages one at a time starting with index.html.

Read these before starting:
1. This file
2. `CLAUDE.md` in repo root
3. `~/.claude/projects/-Users-permanence-os-Code-permanence-os/memory/reference_design_system.md`
4. `~/.claude/projects/-Users-permanence-os-Code-permanence-os/memory/user_aesthetic.md`
5. `site/foundation/design-system.css` (if it exists)
