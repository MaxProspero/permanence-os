# Feature Roadmap -- Stitch/Figma Pipeline
**Date:** 2026-03-19 | **Source:** User feedback session

## For Stitch Wireframing (Phase 1)

### New Pages
- [ ] Sports Betting page -- live Vegas odds, all active sports, channel links (mini monitors)
  - Tier 1 (Sportsbooks): DraftKings, FanDuel, BetMGM
  - Tier 2 (Mobile/DFS): PrizePicks, Underdog
  - Tier 3 (Prediction Markets): Kalshi
- [ ] Search/Media page -- YouTube, streaming, finance news
- [ ] Music Player -- Open-source unlimited music with lyrics (like Spotify/Apple Music flow)
  - Research: open-source music players, lyrics APIs, streaming alternatives

### Page Redesigns (Wireframe First)
- [ ] Terminal (ophtxn_shell) -- Chat-style like Claude/ChatGPT, natural language input, model selector dropdown, voice input
- [ ] Agent View -- Visual lobby showing agents working with AVATARS, not just text
  - Agent avatar system (customizable pics)
  - Like watching a team in a glass office
- [ ] AI School -- Course system with study materials, links to external courses per topic
- [ ] Mind Map (press_kit) -- Drawing/whiteboard, document upload, search, NotebookLM-style
- [ ] Markets Terminal -- News stream embed (Yahoo Finance, CNBC, TradingView, TBPN), live data
- [ ] Daily Planner -- Minimal, connected to Google Calendar

### System Features
- [ ] Smart Model Router UI -- System auto-selects best model per task:
  - Simple tasks: Qwen/Llama (free, local)
  - Complex tasks: Claude API
  - Code: Claude Code / Codex
  - User can adjust controls in Settings, set budgets
- [ ] NotebookLM-style system -- Drop sources, ask questions, built-in notes/docs
- [ ] Google Workspace connection (free trial available):
  - Google Drive (import knowledge, sync docs)
  - Google Calendar (daily planner sync)
  - Gmail (comms hub integration)
  - School email (.edu) for extended trials
- [ ] Settings page -- Feature toggles (LLMs on/off, agents on/off, integrations)
  - Connect terminals/apps/connections
  - System analyzes and auto-selects best tool
  - Usage tracking and spend controls
- [ ] Onboarding flow -- First-time setup, data source upload, preferences
- [ ] Model selector -- Icon + dropdown in terminal AND agent view
- [ ] Music integration -- Spotify, Apple Music, OR open-source alternative
  - Find open-source music UI (lyrics, player, unlimited)
- [ ] Avatar system -- For agents AND user profile
  - Customizable agent avatars
  - Developing/generating avatars

## For Figma Component Library (Phase 2)

### Components to Design
- [ ] Glass card (3 tiers: nav, content, modal)
- [ ] Dropdown menu (standard across all pages)
- [ ] Dark/Light/System toggle (small, top-right)
- [ ] Zoom slider (in View dropdown)
- [ ] Model selector (icon + dropdown)
- [ ] Agent avatar cards (visual, not text)
- [ ] Chart overlays (candle, line, area with glass bg)
- [ ] Terminal input (chat-style, with / command support)
- [ ] Document upload zone
- [ ] Source card (NotebookLM style)
- [ ] Sports odds card (tiered by sportsbook type)
- [ ] News/stream embed card
- [ ] Course lesson card
- [ ] Settings toggle row
- [ ] Music player mini + full view
- [ ] Avatar editor/selector

## Design Principles (User's Words)
- "Minimal, not a lot, just enough art"
- "Clean, sleek, user friendly, great design"
- "Subtle from the icons to the words and times"
- "When I talk to a terminal it should talk back like a human"
- "I should just be able to ask for it or command -- I don't like all the buttons"
- "Tech + southern charm, Magnolia meets clean code"
- "Sec sorority girl edit meets cool calm code guy"
- "Copy the computer" (macOS menubar style)
- "Every page different but still goated"

## Integration Answers
- **Google Workspace:** Free trial available. School email for extended trials.
- **Sports data:** DraftKings, FanDuel, BetMGM (Tier 1) + PrizePicks, Underdog (Tier 2) + Kalshi (Tier 3)
- **News streams:** Yahoo Finance Live, CNBC, TradingView, TBPN (all free)
- **Music:** Explore open-source alternatives to Spotify/Apple Music with lyrics
- **Model routing:** Smart auto-select (Qwen/Llama local for simple, Claude for complex, Codex for code)
- **Avatars:** Agent + user avatars, customizable
