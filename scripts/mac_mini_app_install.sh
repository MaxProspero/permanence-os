#!/usr/bin/env bash
# ============================================================================
# Permanence OS — Mac Mini App Installation
# ============================================================================
# Installs all applications needed for the Mac Mini to function as the
# always-on brain / agent server. Idempotent — safe to re-run.
#
# Usage:
#   bash scripts/mac_mini_app_install.sh [--skip-casks] [--skip-docker]
#
# Run from the Mac Mini directly, or via SSH from the MacBook:
#   ssh permanence-os@192.168.40.232 "cd ~/Code/permanence-os && bash scripts/mac_mini_app_install.sh"
# ============================================================================
set -euo pipefail

SKIP_CASKS=false
SKIP_DOCKER=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --skip-casks)  SKIP_CASKS=true; shift ;;
    --skip-docker) SKIP_DOCKER=true; shift ;;
    -h|--help)
      echo "Usage: bash scripts/mac_mini_app_install.sh [--skip-casks] [--skip-docker]"
      exit 0
      ;;
    *) echo "Unknown flag: $1"; exit 1 ;;
  esac
done

# ── Ensure Homebrew is on PATH ────────────────────────────────────────────
if [[ -f "/opt/homebrew/bin/brew" ]]; then
  eval "$(/opt/homebrew/bin/brew shellenv)"
fi

if ! command -v brew &>/dev/null; then
  echo "ERROR: Homebrew not found. Run mac_mini_setup.sh first."
  exit 1
fi

# ── Helpers ───────────────────────────────────────────────────────────────
step() { echo ""; echo "==> $1"; }
ok()   { echo "    ✓ $1"; }
skip() { echo "    ⏭  $1 (skipped)"; }

install_cask() {
  local name="$1"
  local desc="${2:-$name}"
  if brew list --cask "$name" &>/dev/null 2>&1; then
    ok "$desc already installed"
  else
    echo "    Installing $desc..."
    brew install --cask "$name" 2>/dev/null || echo "    ⚠  Failed to install $desc — install manually"
    ok "$desc installed"
  fi
}

install_formula() {
  local name="$1"
  local desc="${2:-$name}"
  if brew list --formula "$name" &>/dev/null 2>&1; then
    ok "$desc already installed"
  else
    echo "    Installing $desc..."
    brew install "$name" 2>/dev/null || echo "    ⚠  Failed to install $desc — install manually"
    ok "$desc installed"
  fi
}

echo ""
echo "============================================"
echo "  Permanence OS — Mac Mini App Installation"
echo "============================================"
echo ""

# ── 1. Homebrew Casks (GUI Apps) ──────────────────────────────────────────
step "Installing GUI Applications (Homebrew Casks)"
if [[ "$SKIP_CASKS" == "true" ]]; then
  skip "GUI app installation"
else
  install_cask "google-chrome"      "Google Chrome (browser for web automation)"
  install_cask "visual-studio-code" "VS Code (remote dev via SSH)"
  install_cask "chatgpt"            "ChatGPT Desktop"
  install_cask "tailscale"          "Tailscale (mesh VPN for remote access)"
  # claude is already installed
  if brew list --cask "claude" &>/dev/null 2>&1; then
    ok "Claude Desktop already installed"
  fi
fi

# ── 2. Homebrew Formulae (CLI Tools) ─────────────────────────────────────
step "Installing CLI Tools (Homebrew Formulae)"
install_formula "gh"          "GitHub CLI (PR automation)"
install_formula "jq"          "jq (JSON processing)"
install_formula "cloudflared" "Cloudflare Tunnel CLI"
install_formula "htop"        "htop (process monitoring)"
install_formula "tmux"        "tmux (terminal multiplexer)"
install_formula "rsync"       "rsync (file sync)"

# ── 3. Docker (Optional) ─────────────────────────────────────────────────
step "Docker Setup"
if [[ "$SKIP_DOCKER" == "true" ]]; then
  skip "Docker installation"
else
  install_cask "docker" "Docker Desktop (container runtime)"
fi

# ── 4. Ollama Verification ───────────────────────────────────────────────
step "Verifying Ollama"
if command -v ollama &>/dev/null; then
  ok "Ollama installed ($(ollama --version 2>/dev/null || echo 'version unknown'))"
  echo "    Models:"
  ollama list 2>/dev/null | while read -r line; do
    echo "      $line"
  done
else
  echo "    ⚠  Ollama not found — run mac_mini_setup.sh first"
fi

# ── 5. GitHub CLI Auth Check ─────────────────────────────────────────────
step "GitHub CLI Status"
if command -v gh &>/dev/null; then
  if gh auth status &>/dev/null 2>&1; then
    ok "GitHub CLI authenticated"
  else
    echo "    ⚠  GitHub CLI not authenticated. Run: gh auth login"
    echo "    (Select SSH protocol, use existing SSH key)"
  fi
else
  echo "    ⚠  GitHub CLI not available"
fi

# ── 6. Tailscale Setup Reminder ──────────────────────────────────────────
step "Tailscale Status"
if command -v tailscale &>/dev/null; then
  if tailscale status &>/dev/null 2>&1; then
    ok "Tailscale connected"
  else
    echo "    ⚠  Tailscale installed but not connected. Open Tailscale.app and sign in."
  fi
else
  echo "    ⚠  Tailscale not available. Open Tailscale.app from Applications."
fi

# ── Summary ──────────────────────────────────────────────────────────────
echo ""
echo "============================================"
echo "  App Installation Complete!"
echo "============================================"
echo ""
echo "  Installed Apps:"
echo "    brew list --cask:"
brew list --cask 2>/dev/null | while read -r c; do echo "      • $c"; done
echo ""
echo "  Manual Steps Needed:"
echo "    1. Open Tailscale.app → Sign in to your Tailscale network"
echo "    2. Run: gh auth login (SSH protocol, existing key)"
echo "    3. Open Docker.app if you plan to use containers"
echo ""
