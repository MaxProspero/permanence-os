# NemoClaw Setup Guide

**Date:** 2026-03-18 | **Status:** Partially installed

---

## What is NemoClaw

NVIDIA NemoClaw is a security orchestration framework for running OpenClaw
agents in sandboxed, policy-governed containers. It wraps agents with:
- Network policy enforcement (blocks unauthorized outbound)
- Filesystem restrictions (/sandbox and /tmp only)
- Process isolation (no privilege escalation)
- Inference routing through NVIDIA backend (Nemotron model) or local Ollama

## Current Installation State

| Component | Status | Location |
|-----------|--------|----------|
| NemoClaw CLI | Installed | /opt/homebrew/bin/nemoclaw |
| Docker CLI | Installed | /opt/homebrew/bin/docker |
| Colima | Installed | /opt/homebrew/bin/colima |
| Node.js | v25.8.0 | /opt/homebrew/bin/node |
| npm | v11.11.0 | /opt/homebrew/bin/npm |
| OpenShell | NOT INSTALLED | Requires manual install |

## What Needs to Happen Next

### 1. Install OpenShell (NVIDIA container runtime)

The onboard wizard failed to auto-install OpenShell because it tried to
fetch from a private GitHub repo. Install manually:

```bash
# Option A: Via GitHub release (may require gh auth login first)
gh auth login
nemoclaw onboard

# Option B: Download manually from
# https://github.com/NVIDIA/OpenShell/releases
# Then re-run onboard
```

### 2. Get NVIDIA API Key

Required for inference routing through NVIDIA cloud.

1. Go to https://build.nvidia.com
2. Create an account / sign in
3. Generate an API key
4. The onboard wizard will prompt for it

### 3. Complete Onboard

```bash
nemoclaw onboard
```

This runs a 7-step wizard:
1. Preflight checks (Docker, OpenShell)
2. Create sandbox (pulls ~2.4 GB image)
3. Configure inference provider
4. Apply security policies
5. Network restrictions
6. Filesystem restrictions
7. Verify sandbox health

### 4. Create First Sandbox

```bash
# After onboard completes:
nemoclaw list                    # See all sandboxes
nemoclaw <name> connect          # Enter sandbox shell
nemoclaw <name> status           # Check health
nemoclaw <name> logs --follow    # Watch logs
```

### 5. Run Agent Inside Sandbox

```bash
# Inside the sandbox:
openclaw tui                           # Interactive chat UI
openclaw agent --agent main -m "task"  # CLI execution
```

## Integration with Permanence OS

NemoClaw sandboxes run agents in isolated containers. The Permanence OS
model router (core/model_router.py) already has an OpenClaw adapter
(models/openclaw.py) that can route tasks to OpenClaw agents.

For OCA client deployments, the flow is:
1. Permanence OS orchestrator decomposes task
2. Model router determines Hermes vs OpenClaw routing
3. For computer-use tasks, NemoClaw sandbox provides secure execution
4. Results flow back through the governance pipeline

## Colima Management

```bash
# Start container runtime (needed before any Docker commands)
colima start --cpu 2 --memory 4 --disk 30

# Stop when not in use (saves resources)
colima stop

# Check status
colima status
```

## Resource Notes

- NemoClaw sandbox image: ~2.4 GB compressed
- Colima VM: 2 CPU, 4 GB RAM, 30 GB disk (current config)
- Stop Colima when not running agents to save Mac Mini resources
- NemoClaw is alpha software -- interfaces may change
