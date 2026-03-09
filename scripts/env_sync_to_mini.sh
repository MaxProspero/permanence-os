#!/usr/bin/env bash
# ============================================================================
# Permanence OS — Secure .env Sync to Mac Mini
# ============================================================================
# Securely copies your MacBook's .env to the Mac Mini via SCP.
# The file is transferred encrypted over SSH — never touches disk unencrypted
# except at source and destination.
#
# Usage:
#   bash scripts/env_sync_to_mini.sh              # Copy full .env
#   bash scripts/env_sync_to_mini.sh --keys-only  # Copy only API key lines
#   bash scripts/env_sync_to_mini.sh --diff        # Show what's different
#   bash scripts/env_sync_to_mini.sh --verify      # Verify keys are set
#
# SECURITY:
#   - This file is in .gitignore (never committed)
#   - Transfer is over SSH (encrypted in transit)
#   - .env on Mac Mini is chmod 600 (owner-only read/write)
# ============================================================================
set -euo pipefail

MINI_HOST="${PERMANENCE_MINI_HOST:-192.168.40.232}"
MINI_USER="${PERMANENCE_MINI_USER:-permanence-os}"
MINI_KEY="${PERMANENCE_MINI_KEY:-$HOME/.ssh/id_ed25519_mac_mini}"
MINI_REPO="${PERMANENCE_MINI_REPO:-/Users/permanence-os/Code/permanence-os}"

# Find local .env — check worktree first, then main repo
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
LOCAL_ENV="$REPO_DIR/.env"
# If in a git worktree, check main repo for .env
if [[ ! -f "$LOCAL_ENV" ]]; then
    MAIN_REPO="$(git -C "$REPO_DIR" rev-parse --path-format=absolute --git-common-dir 2>/dev/null | sed 's|/.git$||')"
    if [[ -n "$MAIN_REPO" && -f "$MAIN_REPO/.env" ]]; then
        LOCAL_ENV="$MAIN_REPO/.env"
    fi
fi

SSH_CMD="ssh -o BatchMode=yes -o ConnectTimeout=10 -i $MINI_KEY $MINI_USER@$MINI_HOST"

# ── Helpers ──────────────────────────────────────────────────────────────
die() { echo "ERROR: $1" >&2; exit 1; }
ok()  { echo "  ✓ $1"; }

# Check prerequisites
[[ -f "$LOCAL_ENV" ]] || die "Local .env not found at $LOCAL_ENV"
[[ -f "$MINI_KEY" ]]  || die "SSH key not found at $MINI_KEY"

# ── Actions ──────────────────────────────────────────────────────────────

sync_full() {
    echo "Syncing full .env to Mac Mini..."
    echo "  Source: $LOCAL_ENV"
    echo "  Dest:   $MINI_USER@$MINI_HOST:$MINI_REPO/.env"
    echo ""

    scp -i "$MINI_KEY" "$LOCAL_ENV" "$MINI_USER@$MINI_HOST:$MINI_REPO/.env"
    $SSH_CMD "chmod 600 $MINI_REPO/.env"
    ok "Full .env synced and permissions set (chmod 600)"

    # Count keys
    local key_count
    key_count=$(grep -cE "^[A-Z_]+_KEY=.+" "$LOCAL_ENV" 2>/dev/null || echo "0")
    local token_count
    token_count=$(grep -cE "^[A-Z_]+_TOKEN=.+" "$LOCAL_ENV" 2>/dev/null || echo "0")
    ok "Transferred $key_count API keys + $token_count tokens"
}

sync_keys_only() {
    echo "Syncing API keys only to Mac Mini..."
    echo "  (Merging into existing Mac Mini .env)"
    echo ""

    # Extract key lines from local .env
    local key_lines
    key_lines=$(grep -E "^(ANTHROPIC_API_KEY|OPENAI_API_KEY|XAI_API_KEY|NOTION_API_KEY|BRAVE_API_KEY|GITHUB_TOKEN|DISCORD_BOT_TOKEN|TELEGRAM_BOT_TOKEN)=" "$LOCAL_ENV" 2>/dev/null || true)

    if [[ -z "$key_lines" ]]; then
        die "No API key lines found in local .env"
    fi

    echo "  Keys to sync:"
    echo "$key_lines" | while IFS='=' read -r key val; do
        # Show key name + masked value
        local masked
        if [[ ${#val} -gt 8 ]]; then
            masked="${val:0:4}...${val: -4}"
        else
            masked="****"
        fi
        echo "    $key = $masked"
    done

    # Create a temp script that merges keys into remote .env
    local merge_script
    merge_script=$(cat <<'MERGE_EOF'
#!/bin/bash
set -euo pipefail
ENV_FILE="__REPO__/.env"
if [[ ! -f "$ENV_FILE" ]]; then
    echo "ERROR: No .env on Mac Mini at $ENV_FILE"
    exit 1
fi
while IFS='=' read -r key val; do
    [[ -z "$key" ]] && continue
    if grep -q "^${key}=" "$ENV_FILE" 2>/dev/null; then
        # Replace existing line
        sed -i '' "s|^${key}=.*|${key}=${val}|" "$ENV_FILE"
        echo "  Updated: $key"
    else
        # Append new line
        echo "${key}=${val}" >> "$ENV_FILE"
        echo "  Added: $key"
    fi
done
chmod 600 "$ENV_FILE"
MERGE_EOF
)
    merge_script="${merge_script//__REPO__/$MINI_REPO}"

    echo "$key_lines" | $SSH_CMD "$merge_script"
    ok "API keys merged into Mac Mini .env"
}

show_diff() {
    echo "Comparing .env files..."
    echo ""

    # Get remote .env key names (not values!) for comparison
    local remote_keys
    remote_keys=$($SSH_CMD "grep -E '^[A-Z_]+=.' $MINI_REPO/.env 2>/dev/null | cut -d= -f1 | sort" 2>/dev/null || echo "")
    local local_keys
    local_keys=$(grep -E "^[A-Z_]+=." "$LOCAL_ENV" 2>/dev/null | cut -d= -f1 | sort)

    echo "Keys set on MacBook but NOT on Mac Mini:"
    comm -23 <(echo "$local_keys") <(echo "$remote_keys") | while read -r k; do
        echo "  + $k"
    done

    echo ""
    echo "Keys set on Mac Mini but NOT on MacBook:"
    comm -13 <(echo "$local_keys") <(echo "$remote_keys") | while read -r k; do
        echo "  - $k"
    done

    echo ""
    echo "Keys set on BOTH (may have different values):"
    comm -12 <(echo "$local_keys") <(echo "$remote_keys") | wc -l | xargs echo " "
}

verify_keys() {
    echo "Verifying API keys on Mac Mini..."
    echo ""

    local critical_keys=(
        ANTHROPIC_API_KEY
        OPENAI_API_KEY
        XAI_API_KEY
        NOTION_API_KEY
        BRAVE_API_KEY
        GITHUB_TOKEN
    )

    for key in "${critical_keys[@]}"; do
        local val
        val=$($SSH_CMD "grep '^${key}=' $MINI_REPO/.env 2>/dev/null | cut -d= -f2-" 2>/dev/null || echo "")
        if [[ -n "$val" && "$val" != "your_key_here" && "$val" != "" ]]; then
            local masked
            if [[ ${#val} -gt 8 ]]; then
                masked="${val:0:4}...${val: -4}"
            else
                masked="****"
            fi
            echo "  ✓ $key = $masked"
        else
            echo "  ✗ $key — NOT SET"
        fi
    done
}

# ── Main ─────────────────────────────────────────────────────────────────

case "${1:-}" in
    --keys-only) sync_keys_only ;;
    --diff)      show_diff ;;
    --verify)    verify_keys ;;
    --help|-h)
        echo "Usage: bash scripts/env_sync_to_mini.sh [--keys-only|--diff|--verify]"
        echo ""
        echo "  (no flag)    Copy full .env to Mac Mini"
        echo "  --keys-only  Merge only API key lines into Mini's existing .env"
        echo "  --diff       Show which keys differ between MacBook and Mini"
        echo "  --verify     Check which critical keys are set on Mini"
        ;;
    *)           sync_full ;;
esac
