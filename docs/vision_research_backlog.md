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

*This document is a living backlog. Items move to implementation plans when prioritized.*
