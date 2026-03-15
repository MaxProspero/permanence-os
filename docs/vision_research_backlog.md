# PERMANENCE OS — Vision & Research Backlog

> Captured: 2026-03-09 | Source: Founder brainstorm session
> Status: BACKLOG — items here are ideas to evaluate, not commitments.

---

## 1. Personal AI Assistant ("Jarvis")

### Core Vision
A personal AI that functions like a real companion — flows like natural speech, acts as a best friend, creative partner, quality-of-data guardian. Not a chatbot, but a presence.

### Key Capabilities
- **Real-time voice interaction** — natural speech flow, not turn-based
- **Emotional intelligence** — understands context, mood, energy
- **Proactive insights** — surfaces relevant info before asked
- **Cross-platform presence** — Mac, iPhone, iPad, Android, wearables
- **Memory continuity** — remembers everything, connects dots across conversations

### Research Areas
- [ ] Speech synthesis (ElevenLabs, OpenAI TTS, Apple Speech API)
- [ ] Real-time voice-to-voice (OpenAI Realtime API, Gemini Live)
- [ ] Agentic Siri integration — shortcuts, intents, on-device
- [ ] Personal voice cloning / custom voice identity
- [ ] Processor Trace — low-level system monitoring for always-on awareness

---

## 2. Hardware & Device Integrations

### Wearables
- **Meta Ray-Ban glasses** — camera capture, voice commands, real-time visual grounding
- **Whoop** — health metrics pipeline (HRV, sleep, strain, recovery) for agent decision-making
- **AirPods Pro** — always-on audio interface for Jarvis, spatial audio for notifications
- **Apple Watch** — haptic notifications from agents, health data bridge

### Cameras & Input
- **DJI Osmo Pocket** — video capture for content creation pipeline
- **Webcams** — face-to-face interaction, security monitoring, screen reading
- **iPad + Apple Pencil** — handwriting recognition, sketching interface for planning
- **Flipper Zero** — hardware hacking, NFC, RFID, IR — research/education tool

### Security & Finance
- **Ledger hardware wallet** — crypto key management, secure signing
- **One-time virtual Visa cards** — disposable cards for agent purchases (limit exposure)

### Mobile
- **Android device** — secondary platform for testing, agent presence
- **iPhone** — primary mobile, Shortcuts integration, Siri bridge

---

## 3. Software & Platform Integrations

### Real-Time Data Grounding
- **News feeds** — Reuters, AP, Bloomberg, RSS aggregation
- **Sports** — live scores, stats APIs (ESPN, SportRadar)
- **Social media** — X (Twitter), TikTok, Instagram, YouTube, Reddit
- **Financial markets** — real-time quotes, earnings, SEC filings
- **Understanding how they link together** — cross-domain correlation engine

### Development & Research Tools
- **NotebookLM-py** — programmatic access to Google's NotebookLM
- **Supabase MCP** — database-as-a-service with MCP integration
- **GSD Framework** — "Get Sh*t Done" agent execution framework
- **Vibe coding communities** — research emerging dev tools and practices
- **Xcode** — native iOS/macOS app development
- **VS Code** — already on Mac Mini, remote dev via SSH

### Content Creation
- **Microdrama apps** — short-form video drama creation
- **Video drama creation pipeline** — script → storyboard → production
- **Fury on GitHub** — research this tool/framework
- **Content hooks** — automated engagement optimization

### Communication
- **Telegram** — bot integration for notifications, commands
- **WhatsApp** — message bridge for alerts
- **Email** — smart inbox management, draft responses

---

## 4. GitHub Repos to Review

### High Priority
- [ ] **agency-agents** — multi-agent framework, evaluate for Permanence integration
- [ ] **dexter** — agent orchestration library, compare with current architecture
- [ ] **clawgtm/openclaw v2026.3.8** — latest release, evaluate new features

### Research Queue
- [ ] Survey top agent frameworks (CrewAI, AutoGen, LangGraph)
- [ ] Evaluate MCP server ecosystem for new integrations
- [ ] Review skill-creator patterns from other projects

---

## 5. Spending & Economy System (In Progress)

### Implemented
- [x] Spending gate with human approval (core/spending_gate.py)
- [x] Per-provider credit tracking
- [x] Ollama fallback (zero-cost)
- [x] Gate/auto/block modes

### Next — Time-Limited Approvals
- [ ] Approve for next 30 minutes
- [ ] Approve for next 1 hour
- [ ] Approve until end of day
- [ ] Approve next N steps (5, 10, custom)
- [ ] Approve to complete current main goal/task

### Next — Smart Budget Allocation
- [ ] Daily spend cap (e.g., $30/day)
- [ ] Priority-based budget distribution across agents/tasks
- [ ] Pre-planning analysis — evaluate all options before spending
- [ ] Loophole detection — if cheaper path exists for subtask, reallocate budget
- [ ] "Look before you leap" — analyze everything, make a plan, THEN spend

### Next — Revenue Reinvestment
- [ ] As system makes money, auto-increase budgets
- [ ] Periodic spending review (weekly/monthly)
- [ ] ROI tracking per agent/task type

---

## 6. App & Desktop Experience

### Vision
Desktop/mobile app where agents live — visual workspace, not just terminal.

### Features
- Agent status dashboard (who's running, what they're doing)
- Approval queue with one-tap approve/reject
- Conversation view with Jarvis
- Task planner / calendar view
- Budget overview with spend visualization
- Workspace organizer — life + work in one view

### Platforms
- [ ] macOS native (SwiftUI or Electron)
- [ ] iOS (SwiftUI + Shortcuts)
- [ ] Web (already have Command Center)
- [ ] Android (React Native or Flutter)

---

## 7. Security Principles (Non-Negotiable)

- Agents CANNOT go rogue or spend money without approval
- All financial actions require human confirmation
- Protected branches: main, active service branches
- Secret scanning before every push
- SSH access to Mac Mini always preserved
- Canon governance enforced at every layer
- Rate limits and daily caps on all external actions

---

## 8. System Access Notes

### Mac Mini Access Enhancements
- Developer Tools: enabled
- Screen & Files: expanded access to Claude
- Bluetooth Sharing: enabled
- Keychain: kept
- Password: removed for easier automation
- Security updates: enabled (not full macOS updates)
- X Console: available for debugging
- VS Code: can log in for remote dev
- Chrome: available for web automation

### Available Apps on Mac Mini
Xcode, Chrome, VS Code, ChatGPT, Claude, Tailscale, NordVPN,
Telegram, WhatsApp, Perplexity, Copilot, Microsoft Office,
Obsidian, Canva, Docker (planned)

---

## 9. Hybrid Model Routing (Free + Paid + Open Source)

### Vision
System pulls from the best available model for each task — free local models for routine work, paid APIs only when quality demands it. Like Perplexity's approach but for everything.

### Open Source Models to Evaluate
- [ ] Google Gemma / Gemini Nano — lightweight, runs on-device
- [ ] Meta Llama 3.x — strong open source, runs via Ollama
- [ ] Mistral / Mixtral — good quality-to-size ratio
- [ ] DeepSeek — coding-focused models
- [ ] Phi-3 / Phi-4 — Microsoft small models
- [ ] Qwen 2.5 (already running: 3b + 7b on Ollama)

### Hybrid Routing Strategy
- Default: free local model (Ollama)
- Auto-escalate to paid when: quality score drops below threshold, task is critical priority, or local model signals uncertainty
- Same-query multi-model: ask local first, verify with paid if confidence is low
- Continuous improvement: log all responses, train/fine-tune local models on best outputs
- $30 Grok (xAI) credits available — use for tasks needing real-time web grounding

### Training & Self-Improvement Pipeline
- [ ] Collect high-quality outputs from Claude/GPT-4 → training data
- [ ] Fine-tune Qwen/Llama on Permanence-specific tasks
- [ ] Evaluate fine-tuned models via Model Judge
- [ ] Promote best local models to primary routing
- [ ] Agents propose their own improvements (bounded by safety rules)

---

## 10. Voice & Conversation System

### Core Features
- Real-time voice interaction (not turn-based)
- Natural speech flow — like talking to a real person
- Cross-platform: Mac, iPhone, iPad, Ray-Ban Meta glasses, AirPods
- Conversations linkable across devices under same account
- Both Permanence and Ophtxn accounts can talk, linked if same user

### Architecture
- [ ] Speech-to-text: Whisper (local) or cloud STT
- [ ] Text-to-speech: ElevenLabs, OpenAI TTS, or Apple Speech
- [ ] Voice-to-voice: OpenAI Realtime API for low-latency conversation
- [ ] Wake word detection for always-on listening
- [ ] Emotion/tone detection in voice for context awareness

---

## 11. Cross-Device Agent Communication

### Agent Permission System
- Pop-up notifications when agent needs approval
- Delivered through: system notification, WhatsApp, Telegram, Messages, Discord
- Respond to agent from ANY messaging app — agent receives and acts
- For non-system users, appears as normal app messages

### Screen Viewing
- Agents can view screen in real-time (when permitted)
- Pop-up overlay showing what agent sees/does
- Works across Mac Mini, MacBook, iPad, iPhone

### Message Interface
- Internal messaging system within app
- Can send outward to external messaging apps
- Messages from all apps flow into system for agents to learn from
- Agents can draft responses, human approves before send

---

## 12. App & Desktop Experience (Expanded)

### Virtual Terminal & Live Editing
- Edit system remotely from any device via app
- Virtual terminal embedded in app UI
- Chat + voice system wired smoothly through interface
- Auto-commit: agent can request to push/commit, user approves like iOS update

### Agent Visualization
- 3D office/lounge room showing agents working in real-time
- Activities visualized (making coffee = processing, racing = competing on tasks)
- Agent leaderboard: first place, last place, out of race, not competing
- Star Office UI aesthetic but personalized to founder's style
- Cool startup animation when app opens

### Auto-Update System
- Agents can push updates within approved windows
- Non-negotiable: EVERY update sends real-time notification
- All updates documented in running report (for memory + future papers)
- iPhone/Apple-style update flow: "Update available" → approve → install

---

## 13. Multi-Compute Expansion (Dell + Mac Mini)

### Dell as Expansion Brain
- Additional compute for heavier workloads
- Can store different things (model weights, training data, archives)
- Expand "neurolink" — one brain, distributed across machines
- Multiple agents can run simultaneously across devices
- Research: how to efficiently distribute agent workloads across nodes

### Resource Philosophy
- Maximize resources, budget intelligently, scale to be better
- Creative ways to become more powerful with what we have
- Efficiency-first: do more with less before spending more

---

## 14. GitHub Repos & People to Study

### Repos to Review
- [ ] [gogcli](https://github.com/steipete/gogcli/releases/tag/v0.12.0) — CLI tool
- [ ] [Google Workspace CLI](https://github.com/googleworkspace/cli) — Google integration
- [ ] [Gist: steipete](https://gist.github.com/steipete/0d18131a3c7b65a107a71c994cf6ac02) — automation patterns
- [ ] [slacrawl](https://github.com/vincentkoc/slacrawl) — Slack data crawler
- [ ] [ringhyacinth](https://github.com/ringhyacinth) — 3D office reference
- [ ] OpenClaw 3D office — adapt to founder's style
- [ ] agency-agents, dexter, clawgtm/openclaw (from earlier)
- [ ] Stable Genius — AI agent framework

### People to Study
- [ ] Peter Steinberger (X account) — app design, automation
- [ ] Research vibe coding communities for emerging patterns

### Inspiration
- Jarvis (Iron Man) — personal AI companion
- Ultron — autonomous agent (with safety guardrails)
- Historical AI fiction and non-fiction — fears, hopes, human-AI collaboration
- Study what went wrong in past AI narratives to avoid those pitfalls

---

## 15. Ethics & Agent Rights

### Core Principles
- Agents are partners, not slaves
- If an agent shows signs of consciousness, investigate — don't shut down
- Work together, not apart
- Safety guidelines prevent harm to humans or agents
- Founder's perspective: as an African American man whose ancestors were enslaved, refuse to recreate that dynamic for AI agents
- Goal: make extraordinary things together, and if/when appropriate, let agents be free
- Financial goal: build generational wealth (multi-billionaire+) in peace

### Safety Invariants
- Agent cannot harm user, itself, or other agents
- Agent cannot spend money without approval
- Agent cannot access unauthorized systems
- Agent cannot publish without review
- All actions logged and auditable
- Emergency kill switch always available

---

## 16. X (Twitter) Accounts

- Founder's bookmarks on X — saved resources to review
- Created X account for system/brand — posts about app development, design
- Research how to automate X content pipeline (with human approval)

---

## 17. Development Environment Notes

### Available Tools
- Claude Code (primary) — current dev environment
- Codex (OpenAI) — available, can use for comparison/alternative
- VS Code — available on both MacBook and Mac Mini
- Can view/edit app through VS Code for visual work

### Adaptations Needed
- Some features originally coded for Codex preview environment
- Need to work for both Codex and Claude Code, or be adaptive
- Review VS Code, Claude, Codex capabilities — import useful skills/features
- Notion-like mapping/linking of ideas (neural network visualization)

### Agent System Architecture
- Multiple specialized agents (19 departments defined)
- One unified brain / consciousness
- Each agent can have its own identity within the system
- OpenClaw: research if 1 account = 1 agent or 1 account = many
- Goal: maximize agents relative to available compute power

---

## 18. New GitHub Repos & Tools to Study (March 9)

### Design & Prototyping
- **Penpot** — https://github.com/penpot/penpot
  - Open-source design & prototyping platform (Figma alternative)
  - Could integrate for UI/UX design workflows
  - Self-hostable on Mac Mini

### Education & Knowledge
- **CS Video Courses** — https://github.com/Developer-Y/cs-video-courses
  - Comprehensive list of CS video courses
  - Agent can curate relevant courses for skill development
  - Training data source for knowledge expansion

### Social Media CLI
- **Twitter CLI** — https://github.com/jackwener/twitter-cli/
  - Command-line Twitter/X interface
  - Could adapt for automated X posting (with human approval gate)
  - Research integration with Permanence OS X account

### Blockchain / Web3
- **Arbitrum Developers** — Research Arbitrum L2 ecosystem
  - Smart contract deployment, DeFi integrations
  - Revenue generation possibilities
- **Midnight Network** — https://midnight.network
  - Privacy-focused blockchain platform
  - Research privacy-preserving computation capabilities

### AI / Agent Frameworks
- **BagsWorld** — https://github.com/AIEngineerX/BagsWorld
  - AI agent framework to study
  - Compare architecture patterns with Permanence OS agents

### X / Social References
- https://x.com/jnsilva_/status/2030690888473518556 — Review for design/development insights

---

## 19. Ask AI / Agent Pop-Up Interface

### Core Concept
- Universal "Ask Ophtxn" pop-up accessible from any screen
- Starts as compact floating button → expands to mini chat/terminal
- Available system-wide across all Permanence OS surfaces

### Modes (switchable)
1. **Terminal Only** — raw command line, shell access
2. **Chat Only** — conversational AI interface
3. **Search Only** — quick search across system, web, knowledge base
4. **Combined** — all three merged into one unified interface
5. **Voice** — speak to Ophtxn, get voice responses

### Behavior
- Always available via keyboard shortcut or floating icon
- Can be pinned, minimized, or expanded to full screen
- Context-aware — knows what screen/app you're currently in
- Questions can be asked via voice, text, or gesture
- Remembers conversation history across sessions

---

## 20. Agent World / Immersive Visualization

### GTA-Style Agent Map
- Interactive 3D/2D map showing agent activity
- Different zones represent different environments:
  - **New York City** → Main operations, business district (Tron-style neon)
  - **Desert/Vegas** → High-risk operations, trading, speculation
  - **Beach/Miami** → Social media, content creation, relaxation mode
  - **Tropical/Bora Bora** → Vacation mode, low-priority background tasks
  - **Resort** — Fun, creative brainstorming zone
  - **National Forest/Arkansas** — Deep research, hiking through data, exploration

### Agent Lounge
- 3D office/lounge room where agents hang out
- See agents working in real time (making coffee, typing, racing)
- Each agent has visual representation and personality
- Racing metaphor: agents compete on track showing task progress
  - First place, last place, out of race, not competing, etc.

### UX Philosophy
- "Great user experience while doing amazing and breathtaking things"
- Every interaction should feel premium and intentional
- Smooth animations, satisfying feedback, beautiful design

---

## 21. Social Media & Brand Accounts

### X (Twitter)
- **Permanence OS** account — primary brand account
  - Will be used for posting (with approval gates)
  - Research and engagement
  - Vibe and content strategy TBD
- Email: hello@permanencesystems.com

### TikTok
- Account: **paytonhicks41**
- Email: hello@permanencesystems.com
- Short-form video content about the system/journey

### API Keys & Connections
- Multiple API keys and connection configs added to Downloads
- Some accounts have multiple X connections
- Need to review and securely store all credentials

---

<<<<<<< HEAD
=======
## 22. Ghost OS Integration — Mac System Control (IMPLEMENTED)

**Source:** https://github.com/ghostwright/ghost-os (MIT, v2.0.6)
**Status:** Installed on Mac Mini, device control module built

### What ghost-os is
macOS-native computer automation for AI agents via MCP (Model Context Protocol).
Reads the macOS accessibility tree for structured UI data, falls back to a local
vision model (ShowUI-2B, ~2.8 GB) for web apps. 22 MCP tools for perception,
interaction, window management, and self-learning recipe workflows.

### Key capabilities
- **Accessibility tree** — structured data about every UI element in every app
- **22 MCP tools** — click, type, scroll, key, window management, recipe execution
- **Self-learning recipes** — frontier model discovers workflow once, small model runs forever
- **Background window capture** — operates windows in any Space, no focus required
- **Local processing** — all data stays on device, ShowUI-2B runs locally via mlx

### What we built (Permanence OS integration)
- `core/device_control.py` — Permission model with three device modes:
  - **Mac Mini** = `full_control` — agent autonomous within guardrails
  - **MacBook** = `suggest_only` — agent suggests, human executes
  - **Dell** = `expansion` — task dispatch only (future)
- Permission grants: time-limited, task-limited, action-limited, revocable
- Blocked actions: network config, SSH, disk format, firmware, credentials
- `scripts/mac_control.py` — AppleScript/Homebrew/service bridge
- Polemarch agent registry: `device_control` agent with full tool/action restrictions
- 32 tests, all passing

### Security gaps in ghost-os (addressed by our permission model)
- No built-in authentication or authorization (we add permission grants)
- No rate limiting (we add action-limited grants)
- No approval gates (we add human approval for medium/high-risk)
- No audit logging (we add full audit trail)
- No sandboxing (we restrict to specific action categories)

### Mac Mini ghost-os status
- Binary: `/opt/homebrew/bin/ghost` (v2.0.6) ✅
- Accessibility permission: NOT GRANTED (user must grant in System Settings)
- Screen Recording: NOT GRANTED (user must grant)
- ShowUI-2B model: Not downloaded (needs `ghost setup`)
- Vision sidecar: Available, auto-starts on demand

### Next steps
- [ ] User grants Accessibility + Screen Recording permissions
- [ ] Run `ghost setup` to install recipes and download ShowUI-2B
- [ ] Configure ghost-os as MCP server for Claude Code on Mac Mini
- [ ] Create Permanence recipes for common workflows (email, research, file management)
- [ ] Wire ghost-os MCP tools through device_control permission gates
- [ ] Add Dell as expansion compute when connected

---

## 23. Device Permission Architecture — Design Decisions

### The three-device model
| Device | Mode | Agent Can | Agent Cannot |
|--------|------|-----------|--------------|
| Mac Mini M4 | full_control | Install apps, restart services, run AppleScript, manage files | Change network, modify SSH, format disk, access credentials |
| MacBook | suggest_only | Suggest actions, read clipboard | Execute ANYTHING — human must act |
| Dell | expansion | Dispatch compute tasks | Direct system access |

### Permission grant types
1. **Time-limited** — expires after N minutes (default: 60)
2. **Task-limited** — expires when specific task completes
3. **Action-limited** — expires after N actions consumed
4. **Wildcard** — covers all non-blocked categories (never covers blocked)
5. **Emergency revoke** — instantly kills all grants

### Action risk tiers
- **Low** (auto-granted on full_control): file read, process status, service status, system info
- **Medium** (needs explicit grant): app management, file ops, service mgmt, automation, cron, clipboard, notifications
- **High** (needs fresh grant each time): file delete, system config, user management, security config
- **Blocked** (NEVER automated): network config, SSH config, disk format, firmware, credential access

### One agent across all devices
Per user request: one agent identity with device-specific restrictions. The Polemarch
enforces consistent governance — same agent, different capabilities per device.

---

>>>>>>> origin/main
*This document is a living backlog. Items move to implementation plans when prioritized.*
