# MAC MINI DEPLOYMENT HANDOFF

## Who You Are
You are Claude Code running on a Mac Mini M4. This document is your deployment briefing from the laptop session that built everything you're about to install.

## Project: Permanence OS
- **Owner:** Payton Hicks
- **Repo:** github.com/MaxProspero/permanence-os (private)
- **Branch:** `claude/vibrant-merkle`
- **Latest commit:** `e8eb59f` — Phase A Synthesis Layer
- **Tests:** 471 passing, 0 failures

## What Permanence OS Is
A governed personal intelligence OS with 19 agents, 80+ API endpoints, 6 automation loops, Canon-based governance (YAML constitutional rules), and a full revenue pipeline. Three runtime surfaces:
- Command Center API/UI on port 8000
- Foundation Site on port 8787
- Ophtxn Shell / Foundation API on port 8797

## Your Role (Mac Mini)
You are the **always-on brain** — the headless server that runs all services 24/7. No GUI needed. No Claude subscription needed on this machine. No Chrome needed. You run Python servers, Ollama for local LLM inference, and a Cloudflare Tunnel for remote access.

## What Has Been Built (Already in the Repo)

### Infrastructure (committed as `2d3ec60`)
- `scripts/mac_mini_setup.sh` — Full automated provisioning script
- `launchd/com.permanence.command-center.plist` — Auto-start Command Center on boot
- `launchd/com.permanence.foundation-site.plist` — Auto-start Foundation Site on boot
- `launchd/com.permanence.foundation-api.plist` — Auto-start Foundation API on boot
- `launchd/com.permanence.cloudflare-tunnel.plist` — Auto-start Cloudflare Tunnel on boot
- `scripts/tunnel_setup.sh` — Cloudflare tunnel automation

### Phase A: Synthesis Layer (committed as `e8eb59f`)
- `core/synthesis_db.py` (~780 lines) — Governed SQLite database with 6 tables, FTS5 search, WAL mode
- `core/synthesis_db_compat.py` (~175 lines) — SQLite-backed ZeroPoint + EpisodicMemory subclasses
- `core/cost_tracker.py` (~200 lines) — Per-call LLM cost tracking with pricing table
- `scripts/migrate_to_sqlite.py` (~280 lines) — Migration script for flat-file → SQLite
- `tests/test_synthesis_db.py` (34 tests) — Full coverage of Synthesis DB
- `tests/test_cost_tracker.py` (15 tests) — Cost tracking tests
- Cost tracker hooks added to: `models/claude.py`, `models/openai_model.py`, `models/xai.py`, `models/ollama.py`

## DEPLOYMENT TASKS — What You Need To Do

### Task 1: Set Up SSH Key (so laptop can connect later)
```bash
mkdir -p ~/.ssh && echo "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIJA6YI1WQGn3o5TS2MGfGn2Ov+b1pdEg0SYDVmxoIbpb permanence-laptop-to-mini" >> ~/.ssh/authorized_keys && chmod 700 ~/.ssh && chmod 600 ~/.ssh/authorized_keys
```

### Task 2: Run the Setup Script
```bash
cd ~/Code/permanence-os
git checkout claude/vibrant-merkle
bash scripts/mac_mini_setup.sh --skip-tunnel
```

This script will:
1. Install Homebrew (if not present)
2. Install Python 3.12, Node.js, Git via Homebrew
3. Install Ollama and pull qwen2.5:7b + qwen2.5:3b models
4. Create Python venv and install requirements.txt
5. Create default .env file (Ollama-first, no-spend mode)
6. Install and load launchd plists for auto-start on boot

### Task 3: Copy API Keys from Laptop's .env
The setup script creates a default .env with Ollama-only config. For full functionality, these keys need to be added (get them from Payton or the laptop's .env):
- `ANTHROPIC_API_KEY`
- `OPENAI_API_KEY`
- `XAI_API_KEY`
- `NOTION_API_KEY`
- `BRAVE_API_KEY`
- `GITHUB_TOKEN`

For now, the defaults are fine — Ollama runs free local inference.

### Task 4: Verify Everything
```bash
# Check services are running
launchctl list | grep permanence

# Hit all 3 endpoints
curl -s http://127.0.0.1:8000/api/health
curl -s http://127.0.0.1:8787/ | head -5
curl -s http://127.0.0.1:8797/app/ophtxn | head -5

# Check Ollama models
ollama list

# Run test suite
cd ~/Code/permanence-os && source venv/bin/activate && pytest -q
```

### Task 5: macOS Hardening (Payton does these in System Settings GUI)
- **Energy** → Prevent automatic sleeping, Start up automatically after power failure
- **Sharing** → Screen Sharing ON, Remote Login (SSH) ON
- **Lock Screen** → Never require password
- **Software Update** → Auto-install security updates ON, NOT major macOS upgrades

## Connection Details
- **Mac Mini IP:** 192.168.40.232
- **Mac Mini Username:** permanence-os
- **Laptop SSH key:** `~/.ssh/id_ed25519_mac_mini` (ed25519, comment: permanence-laptop-to-mini)

## What Comes After Deployment

### Phase B: Intelligence (next up)
- Embeddings via Ollama (nomic-embed-text, no-spend)
- Hybrid Search (FTS5 BM25 + cosine similarity)
- Contradiction Detector
- Context Engine with pluggable plugins
- Dashboard search/contradiction/cost endpoints

### Phase C: Autonomy
- Agent Identity Markdown files (19 agents)
- Cross-Device Task Router (Mac Mini = brain, MacBook = dev, Dell = sandbox, iPad = mobile command)
- Prediction Signal Pipeline
- Director Workflow

### Phase D: Scale
- MCP Server (expose Synthesis Ledger to external AI tools)
- Compaction (daily summarization jobs)
- Logos Praktikos activation gate
- Documentation

## Guardrails
- Never expose or commit secrets
- Keep no-spend defaults unless explicitly approved
- Preserve human-approval gates for high-risk actions
- Keep changes auditable in docs and logs
- Run `python cli.py secret-scan --staged` before any push

## Device Architecture
| Device | Role | Always On | Routes |
|--------|------|-----------|--------|
| Mac Mini | Brain/Server | Yes | Dashboard, Foundation, Cloudflare, automation loops, Ollama |
| MacBook | Dev Hub | Sessions | Claude Code, testing, code gen, manual research |
| Dell | Sandbox | On demand | Untrusted code, scraping, heavy compute |
| iPad | Mobile Command | On demand | Approvals via web dashboard + Cloudflare tunnel |
