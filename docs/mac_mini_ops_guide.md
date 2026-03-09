# Mac Mini M4 — Operations Guide

## Connection

| Method | Command |
|--------|---------|
| SSH (local) | `ssh -i ~/.ssh/id_ed25519_mac_mini permanence-os@192.168.40.232` |
| SSH (Tailscale) | `ssh -i ~/.ssh/id_ed25519_mac_mini permanence-os@{tailscale-ip}` |
| CLI bridge | `python cli.py device --action status` |

- Username: `permanence-os`
- Local IP: `192.168.40.232`
- SSH key: `~/.ssh/id_ed25519_mac_mini`
- Repo path on Mini: `~/Code/permanence-os`

## Services

Four launchd services run on the Mac Mini:

| Service | Port | Plist |
|---------|------|-------|
| Command Center | :8000 | `com.permanence.command-center` |
| Foundation Site | :8787 | `com.permanence.foundation-site` |
| Foundation API | :8797 | `com.permanence.foundation-api` |
| Git Sync | — | `com.permanence.git-sync` |

### Service commands

```bash
# Check all services
launchctl list | grep permanence

# Restart a service
launchctl kickstart -k gui/$(id -u)/com.permanence.command-center

# View service logs
tail -f /tmp/permanence-command-center.log

# Stop a service
launchctl bootout gui/$(id -u)/com.permanence.command-center

# Start a service
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.permanence.command-center.plist
```

### Via CLI (from MacBook)

```bash
python cli.py device --action status       # System overview
python cli.py device --action services     # Service health
python cli.py device --action install --app jq   # Install app
python cli.py device --action notify --message "Deploy complete"
```

## Ollama

Ollama runs locally with two models:

```bash
# Check models
ollama list

# Pull a new model
ollama pull llama3.2:3b

# Test inference
ollama run qwen2.5:7b "Hello"

# API endpoint
curl http://localhost:11434/api/generate -d '{"model":"qwen2.5:7b","prompt":"test"}'
```

## Ghost-OS

Ghost-OS v2.0.6 is installed for macOS automation via MCP.

```bash
# Check status
ghost doctor

# Available recipes
ls ~/.ghost-os/recipes/

# MCP mode (for agent use)
ghost mcp
```

**Accessibility**: Ghost-OS needs Accessibility permission in System Settings.
Toggle Terminal/Claude off and on if ghost doctor shows NOT GRANTED.

**ShowUI-2B**: Vision model at `~/.ghost-os/models/ShowUI-2B/`.

## Code Sync

The Mac Mini pulls code from the remote repo. **Never commit directly on the Mac Mini.**

```bash
# Manual sync
cd ~/Code/permanence-os && git fetch origin && git pull --ff-only

# Auto-sync runs every 30 minutes via launchd (com.permanence.git-sync)
```

## API Keys

Keys are in `~/Code/permanence-os/.env` (never committed to git).

| Key | Status |
|-----|--------|
| ANTHROPIC_API_KEY | ✓ Set |
| OPENAI_API_KEY | ✓ Set |
| XAI_API_KEY | ✓ Set |
| TAVILY_API_KEY | ✓ Set |
| GH_TOKEN | ✗ Needs gh auth |
| POLYGON_API_KEY | ✗ Not needed yet |
| FINNHUB_API_KEY | ✗ Not needed yet |

## Device Control

The device permission model governs what agents can do:

```bash
# Check permissions
python cli.py device --action status

# Grant time-limited access
python cli.py device --action grant --scope app_management --duration 60

# Revoke all grants
python cli.py device --action revoke-all
```

**Modes**: Mac Mini = full_control, MacBook = suggest_only, Dell = expansion.

**Blocked actions** (never automated): network_config, ssh_config, disk_format, firmware, credential_access.

## Monitoring

```bash
# Disk usage
df -h /

# Memory
vm_stat | head -10

# CPU load
top -l 1 -n 0 | head -10

# Service processes
ps aux | grep permanence

# Network
lsof -i -P | grep LISTEN
```

## Troubleshooting

**Service won't start**: Check logs at `/tmp/permanence-*.log`. Common fix:
```bash
launchctl bootout gui/$(id -u)/com.permanence.command-center
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.permanence.command-center.plist
```

**SSH connection refused**: Verify Remote Login is on in System Settings > General > Sharing.

**Ollama not responding**: Restart via `brew services restart ollama`.

**Ghost-OS accessibility**: Toggle the app off and on in System Settings > Privacy & Security > Accessibility.

## Phone Access

With Tailscale + Termius/Blink:
1. Tailscale connects your phone to the mesh VPN
2. SSH to the Mac Mini using its Tailscale IP
3. Port forward :8000 to access the dashboard in phone browser
