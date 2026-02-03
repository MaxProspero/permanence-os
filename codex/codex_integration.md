# CODEX INTEGRATION GUIDE

## Overview
This system is designed to work across multiple Claude interfaces:
- Claude.ai Projects (current)
- Claude Code / Codex (terminal)
- API implementations
- Mobile/desktop apps

Terminology note: **Polemarch** (formerly “King Bot”) is implemented in `agents/king_bot.py`.

## Universal Principles (Apply Everywhere)

1. **Canon is source of truth** - Always in `canon/base_canon.yaml`
2. **Logs are append-only** - Every interface must log to `logs/`
3. **State persists** - Use `memory/episodic/` for task history
4. **Human authority final** - No interface can override escalations
5. **Compliance Gate** - Outbound actions require compliance review

## Codex-Specific Setup

### Initialize in Terminal
```bash
# Navigate to project
cd ~/permanence-os

# Codex will read Canon automatically
cat canon/base_canon.yaml

# Start task
python agents/king_bot.py  # Polemarch
```

### Governed Task Runner
```bash
python run_task.py "Your task goal"
# Provide sources at memory/working/sources.json
# Optional: provide a draft at memory/working/draft.md
python run_task.py "Your task goal" --sources /path/to/sources.json --draft /path/to/draft.md
```

Identity routing is configured in `identity_config.yaml`.

### Unified CLI
```bash
python cli.py run "Your task goal"
python cli.py add-source "source-name" 0.7 "optional notes"
python cli.py status
python cli.py clean --all
python cli.py test
```

### Environment Variables
```bash
export PERMANENCE_CANON_PATH="~/permanence-os/canon/base_canon.yaml"
export PERMANENCE_LOG_DIR="~/permanence-os/logs"
export PERMANENCE_MEMORY_DIR="~/permanence-os/memory"
```

### Usage Pattern in Codex

When starting a task in Codex/terminal:

```bash
# 1. Load Canon context
codex --context canon/base_canon.yaml

# 2. Reference project knowledge
codex --project-dir ~/permanence-os

# 3. Start task with governance
codex execute "Research X" --governed
```

### Cross-Platform State Sync

**Strategy:** Git as synchronization layer (episodic state tracked; logs optional)

```bash
# After each session, commit state
git add memory/episodic/*.json
git commit -m "Session: $(date)"
git push

# Optional: version logs
# - remove logs/*.log from .gitignore if you want to track log files
# - then add logs/*.log here

# On new machine/interface
git pull
# State is restored
```

### Context Loading

Every interface should load in this order:
1. Canon (`canon/base_canon.yaml`)
2. Recent logs (`logs/` most recent)
3. Active tasks (`memory/episodic/` status != DONE)
4. Project knowledge (via search tools)

### Interface-Specific Behavior

**Claude.ai Projects:**
- Use project_knowledge_search extensively
- Leverage memory features
- Visual artifacts for outputs

**Claude Code/Codex:**
- CLI-first outputs
- File-based artifacts
- Direct script execution
- Git integration for state

**API:**
- Programmatic access to all agents
- Webhook escalations
- Automated audit loops

### Failsafe: Manual Sync

If automated sync fails:

```bash
# Export current state
python -c "
from agents.king_bot import Polemarch
polemarch = Polemarch()
print(polemarch.state.to_dict() if polemarch.state else 'No active state')
" > state_backup.json

# Import on new system
cat state_backup.json
# Manually recreate in new interface
```

## Integration Checklist

When using Permanence OS in a new environment:

- [ ] Canon file accessible at expected path
- [ ] Log directory exists and writable
- [ ] Memory directories created
- [ ] Environment variables set
- [ ] Git repository initialized
- [ ] Test task executes successfully
- [ ] Escalation mechanism works
- [ ] Logs are being written

## Best Practices

1. **Always start with Canon validation**
2. **Check recent logs for context**
3. **Commit state after complex tasks**
4. **Use project knowledge search first**
5. **Escalate early, not late**
6. **Document interface-specific quirks**

## Emergency Recovery

If system state becomes corrupted:

```bash
# 1. Stop all running tasks
pkill -f king_bot

# 2. Review logs for last known good state
tail -n 100 logs/$(date +%Y-%m-%d).log

# 3. Restore from episodic memory
ls -t memory/episodic/ | head -1
cat memory/episodic/[latest-task].json

# 4. Reinitialize if needed
git reset --hard HEAD
python agents/king_bot.py --recover
```

## Testing Cross-Platform

Create a test task that works everywhere:

```bash
# Test script
python << EOF
from agents.king_bot import Polemarch
polemarch = Polemarch()
state = polemarch.initialize_task("Test cross-platform compatibility")
print(f"✓ Initialized: {state.task_id}")
polemarch.save_state()
print(f"✓ State saved")
EOF
```

Expected output:
```
[timestamp] [INFO] Task initialized: T-[datetime]
[timestamp] [INFO] Goal: Test cross-platform compatibility
✓ Initialized: T-[datetime]
[timestamp] [INFO] State saved: memory/episodic/T-[datetime].json
✓ State saved
```

If this works, your environment is correctly configured.
