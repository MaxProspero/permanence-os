#!/usr/bin/env bash
# Setup Cloudflare Tunnel for Permanence OS
# Usage: bash scripts/tunnel_setup.sh
set -euo pipefail

TUNNEL_NAME="permanence-os"
CONFIG_SRC="tunnel/cloudflared-config.yml"
CONFIG_DEST="$HOME/.cloudflared/config.yml"

echo "=== Permanence OS Tunnel Setup ==="

# Check cloudflared installed
if ! command -v cloudflared &>/dev/null; then
  echo "Installing cloudflared..."
  brew install cloudflared
fi

# Login if needed
if ! cloudflared tunnel list &>/dev/null 2>&1; then
  echo "Authenticating with Cloudflare (browser will open)..."
  cloudflared tunnel login
fi

# Create tunnel
echo "Creating tunnel: $TUNNEL_NAME"
TUNNEL_ID=$(cloudflared tunnel create "$TUNNEL_NAME" 2>&1 | grep -oE '[a-f0-9-]{36}' | head -1)
echo "Tunnel ID: $TUNNEL_ID"

# Route DNS
echo "Setting DNS routes..."
cloudflared tunnel route dns "$TUNNEL_NAME" api.permanencesystems.com
cloudflared tunnel route dns "$TUNNEL_NAME" app.permanencesystems.com

# Generate config
echo "Writing config to $CONFIG_DEST"
mkdir -p "$HOME/.cloudflared"
sed "s/<TUNNEL_UUID>/$TUNNEL_ID/g" "$CONFIG_SRC" > "$CONFIG_DEST"

echo ""
echo "=== Setup complete ==="
echo "Start tunnel: cloudflared tunnel run $TUNNEL_NAME"
