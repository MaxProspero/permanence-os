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

*This document is a living backlog. Items move to implementation plans when prioritized.*
