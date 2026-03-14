#!/usr/bin/env bash
# ============================================================================
# Permanence OS — Mac Mini Server Setup
# ============================================================================
# Automates provisioning a Mac Mini M4 as an always-on Permanence OS server.
#
# What it does:
#   1. Installs Homebrew, Python 3.12+, Node.js, Git, Ollama
#   2. Clones the repo (or skips if already present)
#   3. Installs Python dependencies
#   4. Pulls the default Ollama model for local LLM routing
#   5. Installs launchd plists for auto-start on boot
#   6. Configures macOS energy & sharing settings (requires admin)
#   7. Optionally sets up Cloudflare Tunnel for remote access
#
# Usage:
#   bash scripts/mac_mini_setup.sh [--skip-ollama] [--skip-tunnel] [--repo-dir DIR]
#
# Prerequisites:
#   - macOS 14+ (Sonoma or later recommended)
#   - Admin account (for launchd and system settings)
#   - Internet connection
# ============================================================================
set -euo pipefail

# ── Defaults ────────────────────────────────────────────────────────────────
REPO_URL="git@github.com:MaxProspero/permanence-os.git"
DEFAULT_REPO_DIR="$HOME/Code/permanence-os"
OLLAMA_MODEL="qwen2.5:7b"
OLLAMA_SMALL_MODEL="qwen2.5:3b"
LAUNCHD_DIR="$HOME/Library/LaunchAgents"
SKIP_OLLAMA=false
SKIP_TUNNEL=false
REPO_DIR=""

# ── Parse args ──────────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
  case "$1" in
    --skip-ollama)  SKIP_OLLAMA=true; shift ;;
    --skip-tunnel)  SKIP_TUNNEL=true; shift ;;
    --repo-dir)     REPO_DIR="$2"; shift 2 ;;
    -h|--help)
      echo "Usage: bash scripts/mac_mini_setup.sh [--skip-ollama] [--skip-tunnel] [--repo-dir DIR]"
      exit 0
      ;;
    *) echo "Unknown flag: $1"; exit 1 ;;
  esac
done

REPO_DIR="${REPO_DIR:-$DEFAULT_REPO_DIR}"

echo ""
echo "============================================"
echo "  Permanence OS — Mac Mini Server Setup"
echo "============================================"
echo ""
echo "Repo dir:      $REPO_DIR"
echo "Ollama model:  $OLLAMA_MODEL"
echo "Skip Ollama:   $SKIP_OLLAMA"
echo "Skip Tunnel:   $SKIP_TUNNEL"
echo ""

# ── Helper ──────────────────────────────────────────────────────────────────
step() { echo ""; echo "==> $1"; }
ok()   { echo "    ✓ $1"; }
skip() { echo "    ⏭  $1 (skipped)"; }

# ── 1. Homebrew ─────────────────────────────────────────────────────────────
step "Checking Homebrew"
if command -v brew &>/dev/null; then
  ok "Homebrew already installed ($(brew --version | head -1))"
else
  echo "    Installing Homebrew..."
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
  # Ensure brew is on PATH for Apple Silicon
  if [[ -f "/opt/homebrew/bin/brew" ]]; then
    eval "$(/opt/homebrew/bin/brew shellenv)"
  fi
  ok "Homebrew installed"
fi

# ── 2. Core packages ───────────────────────────────────────────────────────
step "Installing core packages via Homebrew"
PACKAGES=(python@3.12 node git)
for pkg in "${PACKAGES[@]}"; do
  if brew list --formula "$pkg" &>/dev/null 2>&1; then
    ok "$pkg already installed"
  else
    echo "    Installing $pkg..."
    brew install "$pkg"
    ok "$pkg installed"
  fi
done

# ── 3. Ollama ───────────────────────────────────────────────────────────────
step "Setting up Ollama (local LLM)"
if [[ "$SKIP_OLLAMA" == "true" ]]; then
  skip "Ollama setup"
else
  if command -v ollama &>/dev/null; then
    ok "Ollama already installed"
  else
    echo "    Installing Ollama..."
    brew install ollama
    ok "Ollama installed"
  fi

  # Start Ollama service if not running
  if ! pgrep -x "ollama" &>/dev/null; then
    echo "    Starting Ollama service..."
    ollama serve &>/dev/null &
    sleep 3
    ok "Ollama service started"
  else
    ok "Ollama service already running"
  fi

  # Pull models
  echo "    Pulling model: $OLLAMA_MODEL (this may take a few minutes)..."
  ollama pull "$OLLAMA_MODEL" || echo "    ⚠  Failed to pull $OLLAMA_MODEL — check connection"
  echo "    Pulling model: $OLLAMA_SMALL_MODEL..."
  ollama pull "$OLLAMA_SMALL_MODEL" || echo "    ⚠  Failed to pull $OLLAMA_SMALL_MODEL — check connection"
  ok "Ollama models ready"
fi

# ── 4. Clone / update repo ─────────────────────────────────────────────────
step "Setting up repository"
if [[ -d "$REPO_DIR/.git" ]]; then
  ok "Repository already exists at $REPO_DIR"
  echo "    Pulling latest changes..."
  cd "$REPO_DIR"
  git pull --ff-only || echo "    ⚠  git pull failed — resolve manually"
else
  echo "    Cloning $REPO_URL to $REPO_DIR..."
  mkdir -p "$(dirname "$REPO_DIR")"
  git clone "$REPO_URL" "$REPO_DIR"
  ok "Repository cloned"
fi

cd "$REPO_DIR"

# ── 5. Python dependencies ─────────────────────────────────────────────────
step "Installing Python dependencies"
PYTHON_BIN="python3.12"
if ! command -v "$PYTHON_BIN" &>/dev/null; then
  PYTHON_BIN="python3"
fi

if [[ -d "venv" ]]; then
  ok "Virtual environment already exists"
else
  echo "    Creating virtual environment..."
  "$PYTHON_BIN" -m venv venv
  ok "Virtual environment created"
fi

# shellcheck disable=SC1091
source venv/bin/activate
pip install --upgrade pip --quiet
pip install -r requirements.txt --quiet
ok "Python dependencies installed"

# ── 6. Create .env from template if missing ─────────────────────────────────
step "Checking environment configuration"
if [[ -f ".env" ]]; then
  ok ".env file exists"
else
  if [[ -f ".env.example" ]]; then
    cp .env.example .env
    ok "Created .env from .env.example — edit with your API keys"
  else
    cat > .env << 'ENVEOF'
# Permanence OS — Environment Configuration
# Generated by scripts/mac_mini_setup.sh

# Model routing
PERMANENCE_MODEL_PROVIDER=ollama
PERMANENCE_MODEL_PROVIDER_FALLBACKS=ollama
PERMANENCE_DEFAULT_MODEL=qwen2.5:3b
PERMANENCE_MODEL_OPUS=qwen2.5:7b
PERMANENCE_MODEL_SONNET=qwen2.5:3b
PERMANENCE_MODEL_HAIKU=qwen2.5:3b
PERMANENCE_NO_SPEND_MODE=1
PERMANENCE_LOW_COST_MODE=1
PERMANENCE_LLM_MONTHLY_BUDGET_USD=10

# Server ports
PORT_COMMAND_CENTER=8000
PORT_FOUNDATION_SITE=8787
PORT_FOUNDATION_API=8797

# Add your API keys below (uncomment as needed)
# ANTHROPIC_API_KEY=
# OPENAI_API_KEY=
# XAI_API_KEY=
ENVEOF
    ok "Created default .env — edit with your API keys"
  fi
fi

# ── 7. Install launchd plists ──────────────────────────────────────────────
step "Installing launchd plists (auto-start on boot)"
mkdir -p "$LAUNCHD_DIR"

PLIST_NAMES=(
  "com.permanence.command-center"
  "com.permanence.foundation-site"
  "com.permanence.foundation-api"
  "com.permanence.git-sync"
)
PLIST_DIR="$REPO_DIR/launchd"

if [[ ! -d "$PLIST_DIR" ]]; then
  echo "    ⚠  launchd/ directory not found in repo — skipping plist install"
else
  for plist_name in "${PLIST_NAMES[@]}"; do
    src="$PLIST_DIR/${plist_name}.plist"
    dest="$LAUNCHD_DIR/${plist_name}.plist"
    if [[ ! -f "$src" ]]; then
      echo "    ⚠  $src not found — skipping"
      continue
    fi

    # Substitute $HOME and $REPO_DIR in the plist
    sed \
      -e "s|__HOME__|$HOME|g" \
      -e "s|__REPO_DIR__|$REPO_DIR|g" \
      -e "s|__USER__|$(whoami)|g" \
      "$src" > "$dest"

    # Unload if already loaded, then load
    launchctl unload "$dest" 2>/dev/null || true
    launchctl load "$dest"
    ok "Loaded $plist_name"
  done
fi

# ── 8. Cloudflare Tunnel (optional) ────────────────────────────────────────
step "Cloudflare Tunnel setup"
if [[ "$SKIP_TUNNEL" == "true" ]]; then
  skip "Cloudflare Tunnel"
else
  if [[ -f "$REPO_DIR/scripts/tunnel_setup.sh" ]]; then
    echo "    Running tunnel setup script..."
    bash "$REPO_DIR/scripts/tunnel_setup.sh" || echo "    ⚠  Tunnel setup had issues — run manually later"
    ok "Cloudflare Tunnel configured"

    # Install tunnel launchd plist if available
    TUNNEL_PLIST_SRC="$PLIST_DIR/com.permanence.cloudflare-tunnel.plist"
    TUNNEL_PLIST_DEST="$LAUNCHD_DIR/com.permanence.cloudflare-tunnel.plist"
    if [[ -f "$TUNNEL_PLIST_SRC" ]]; then
      sed \
        -e "s|__HOME__|$HOME|g" \
        -e "s|__REPO_DIR__|$REPO_DIR|g" \
        -e "s|__USER__|$(whoami)|g" \
        "$TUNNEL_PLIST_SRC" > "$TUNNEL_PLIST_DEST"
      launchctl unload "$TUNNEL_PLIST_DEST" 2>/dev/null || true
      launchctl load "$TUNNEL_PLIST_DEST"
      ok "Loaded cloudflare-tunnel launchd plist"
    fi
  else
    skip "tunnel_setup.sh not found"
  fi
fi

# ── 9. macOS system settings reminders ─────────────────────────────────────
step "macOS System Settings Checklist"
echo ""
echo "    The following settings must be configured manually in System Settings:"
echo ""
echo "    Energy:"
echo "      • System Settings → Energy → Prevent sleeping when display is off ✓"
echo "      • System Settings → Energy → Start up automatically after power failure ✓"
echo "      • System Settings → Lock Screen → Turn display off → Never (or long interval)"
echo ""
echo "    Sharing:"
echo "      • System Settings → General → Sharing → Remote Login (SSH) ✓"
echo "      • System Settings → General → Sharing → Screen Sharing ✓"
echo ""
echo "    Network:"
echo "      • Prefer Ethernet over WiFi for server stability"
echo "      • Note your local IP: $(ipconfig getifaddr en0 2>/dev/null || echo 'unavailable')"
echo ""

# ── 10. Verify ─────────────────────────────────────────────────────────────
step "Verification"
echo ""

# Check servers via launchctl
for plist_name in "${PLIST_NAMES[@]}"; do
  if launchctl list "$plist_name" &>/dev/null 2>&1; then
    ok "$plist_name is loaded"
  else
    echo "    ⚠  $plist_name not loaded — check plist"
  fi
done

echo ""
echo "============================================"
echo "  Setup Complete!"
echo "============================================"
echo ""
echo "  Servers:"
echo "    Command Center:   http://$(ipconfig getifaddr en0 2>/dev/null || echo 'localhost'):8000"
echo "    Foundation Site:   http://$(ipconfig getifaddr en0 2>/dev/null || echo 'localhost'):8787"
echo "    Foundation API:    http://$(ipconfig getifaddr en0 2>/dev/null || echo 'localhost'):8797"
echo ""
echo "  iPad PWA:"
echo "    Open Safari on iPad → navigate to one of the URLs above"
echo "    Tap Share → Add to Home Screen"
echo ""
echo "  Manage services:"
echo "    launchctl list | grep permanence"
echo "    launchctl unload ~/Library/LaunchAgents/com.permanence.*.plist"
echo "    launchctl load ~/Library/LaunchAgents/com.permanence.*.plist"
echo ""
echo "  Logs:"
echo "    tail -f /tmp/permanence-command-center.log"
echo "    tail -f /tmp/permanence-foundation-site.log"
echo "    tail -f /tmp/permanence-foundation-api.log"
echo ""
