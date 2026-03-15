#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────
# Mac Mini Security Hardening Script
# Run ON the Mac Mini (not remotely) with: sudo bash scripts/mac_mini_harden.sh
# ─────────────────────────────────────────────────────────────────────
set -euo pipefail

echo "╔════════════════════════════════════════════════╗"
echo "║  Permanence OS — Mac Mini Security Hardening   ║"
echo "╚════════════════════════════════════════════════╝"
echo ""

# ── 1. Hostname Anonymization ─────────────────────────────────────
echo "[1/6] Setting generic hostname..."
scutil --set ComputerName "server"
scutil --set HostName "server"
scutil --set LocalHostName "server"
echo "  ✓ Hostname set to 'server'"

# ── 2. Firewall ───────────────────────────────────────────────────
echo "[2/6] Enabling firewall..."
/usr/libexec/ApplicationFirewall/socketfilterfw --setglobalstate on
echo "  ✓ Firewall enabled"

# ── 3. Stealth Mode ──────────────────────────────────────────────
echo "[3/6] Enabling stealth mode (no ping/port-scan responses)..."
/usr/libexec/ApplicationFirewall/socketfilterfw --setstealthmode on
echo "  ✓ Stealth mode enabled"

# ── 4. mDNS / Bonjour Suppression ────────────────────────────────
echo "[4/6] Suppressing mDNS/Bonjour advertising..."
defaults write /Library/Preferences/com.apple.mDNSResponder.plist \
    NoMulticastAdvertisements -bool true
killall -HUP mDNSResponder 2>/dev/null || true
echo "  ✓ mDNS advertising suppressed"

# ── 5. WiFi (only disable if Ethernet is connected) ──────────────
echo "[5/6] Checking network before WiFi changes..."
WIFI_IF=$(networksetup -listallhardwareports | awk '/Wi-Fi/{getline; print $2}')
ETH_STATUS=$(ifconfig en0 2>/dev/null | grep "status:" | awk '{print $2}')

if [ "$ETH_STATUS" = "active" ]; then
    echo "  Ethernet (en0) is active — safe to disable WiFi"
    if [ -n "$WIFI_IF" ]; then
        networksetup -setairportpower "$WIFI_IF" off
        echo "  ✓ WiFi ($WIFI_IF) disabled"
    else
        echo "  ⚠ No WiFi interface found (already off or no hardware)"
    fi
else
    echo "  ⚠ Ethernet NOT active — skipping WiFi disable to preserve connectivity"
    echo "  → Plug in Ethernet first, then re-run this script"
fi

# ── 6. Verification ──────────────────────────────────────────────
echo "[6/6] Verifying..."
echo ""
echo "  Hostname:    $(scutil --get ComputerName)"
echo "  Firewall:    $(/usr/libexec/ApplicationFirewall/socketfilterfw --getglobalstate)"
echo "  Stealth:     $(/usr/libexec/ApplicationFirewall/socketfilterfw --getstealthmode)"
echo "  FileVault:   $(fdesetup status)"
if [ -n "$WIFI_IF" ]; then
    echo "  WiFi ($WIFI_IF): $(networksetup -getairportpower "$WIFI_IF")"
fi
echo ""
echo "════════════════════════════════════════════════════"
echo "  Hardening complete. Remaining manual steps:"
echo "  • SSH hardening: edit /etc/ssh/sshd_config (see docs/research/)"
echo "  • DNS over HTTPS: configure in System Settings → Network → DNS"
echo "  • Install LuLu: brew install --cask lulu"
echo "════════════════════════════════════════════════════"
