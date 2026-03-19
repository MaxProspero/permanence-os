# UX/UI Master Extraction Reference
# Source: User-provided deep research (March 19, 2026)
# Platforms: use.ai, Google Stitch, Bloomberg, Perplexity Finance,
#            Quicken, Monarch Money, YNAB, Robinhood, Yahoo Finance

## Quick Index
- use.ai: Chat/research interface spec (model selector pill, input card, sidebar)
- Google Stitch: Dark app builder (Angular, dot-grid, warm neutrals)
- Bloomberg: Power-user density, keyboard-first, HUD philosophy
- Perplexity Finance: OKLCH tokens, sparkline cards, heatmap, tab nav
- Quicken: Dual-rail biz/personal split, LifeHub, Haffer font
- Monarch: Copernicus serif headings, warm off-white, mark-as-reviewed
- YNAB: Assignment-first budgeting, zero-based, intentionality UX
- Robinhood: Minimal line charts, vibe state color changes, haptic scrub

## KEY PATTERNS TO ADOPT

### 1. Model Selector Pill (use.ai / Stitch)
- Gray pill, 36px height, 16px radius, chevron rotates on open
- Dropdown: 14px radius, 8px shadow, scrollable model list
- Each item: provider logo + name + description + checkmark

### 2. Input Card (use.ai)
- 28px border-radius, white bg, ring-1 border, 20px outer glow shadow
- Toolbar inside: [+] [Deep Research] [Pro] ... [mic] [send]
- Send button: 36px circle, gray inactive, accent when text present

### 3. Finance Cards (Perplexity Finance)
- 12px radius, subtle border, sparkline SVG inside
- Hover: scale(1.02) + super-color shadow
- Monospace for prices (tabular-nums!)

### 4. Dual-Rail Split (Quicken)
- "All Accounts: $X" -> "Business: $X" | "Personal: $X"
- Color-coded pills for each rail

### 5. Dark Glassmorphism (Stitch)
- App shell: #191a1f
- Surface raised: #252729
- Border: rgba(255,255,255,0.10)
- Hover: rgba(255,255,255,0.08)

### 6. Finance Tokens
- Bull: #00C805 / Bear: #FF5000
- Font-mono with tabular-nums for non-jittering prices
- Chart stroke: 2px, area fill with gradient fade

### 7. Personal OS Sidebar (Monarch-inspired)
- Finance: Dashboard, Accounts, Transactions, Cash Flow, Budget, Recurring
- Business: Revenue, Expenses, Clients, Tax Buckets
- Intelligence: Reports, Goals, Forecast, AI Insights
- Vault: Documents, Assets, Notes

## DESIGN TOKENS SAVED
See individual platform sections below for complete CSS custom property blocks.
Full specs stored in this file for agent reference.
