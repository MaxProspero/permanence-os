#!/bin/bash
# install_keys.sh — Extract API keys from AirDropped RTF files and update .env
# Run this once to activate paid providers.

set -e
ENV_FILE="$HOME/Code/permanence-os/.env"
DL="$HOME/Downloads"

echo "=== Permanence OS — API Key Installer ==="
echo "Reading keys from Downloads RTF files..."
echo ""

# Extract text from RTF files
ANTHROPIC_KEY=$(textutil -convert txt -stdout "$DL/anthropic api key .rtf" 2>/dev/null | tr -d '[:space:]')
OPENAI_KEY=$(textutil -convert txt -stdout "$DL/open ai key .rtf" 2>/dev/null | tr -d '[:space:]')
XAI_KEY=$(textutil -convert txt -stdout "$DL/grok api ophtxn pbhicksfinn.rtf" 2>/dev/null | tr -d '[:space:]')

echo "Found keys:"
[ -n "$ANTHROPIC_KEY" ] && echo "  ✓ Anthropic: ${ANTHROPIC_KEY:0:10}..." || echo "  ✗ Anthropic: NOT FOUND"
[ -n "$OPENAI_KEY" ] && echo "  ✓ OpenAI:    ${OPENAI_KEY:0:8}..." || echo "  ✗ OpenAI: NOT FOUND"
[ -n "$XAI_KEY" ] && echo "  ✓ xAI/Grok:  ${XAI_KEY:0:8}..." || echo "  ✗ xAI/Grok: NOT FOUND"
echo ""

# Backup current .env
cp "$ENV_FILE" "$ENV_FILE.bak.$(date +%s)"

# Update keys in .env using sed
if [ -n "$ANTHROPIC_KEY" ]; then
    sed -i '' "s|^ANTHROPIC_API_KEY=.*|ANTHROPIC_API_KEY=$ANTHROPIC_KEY|" "$ENV_FILE"
    echo "Updated ANTHROPIC_API_KEY"
fi

if [ -n "$OPENAI_KEY" ]; then
    sed -i '' "s|^OPENAI_API_KEY=.*|OPENAI_API_KEY=$OPENAI_KEY|" "$ENV_FILE"
    echo "Updated OPENAI_API_KEY"
fi

if [ -n "$XAI_KEY" ]; then
    sed -i '' "s|^XAI_API_KEY=.*|XAI_API_KEY=$XAI_KEY|" "$ENV_FILE"
    echo "Updated XAI_API_KEY"
fi

echo ""
echo "Restarting command center..."
launchctl kickstart -k gui/$(id -u)/com.permanence.command-center 2>/dev/null && echo "✓ Command center restarted"
echo ""
echo "=== Done! Paid providers are now active. ==="
