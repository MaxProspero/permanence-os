#!/usr/bin/env bash
set -euo pipefail

REPO_PATH="${1:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
HOOK_PATH="$REPO_PATH/.git/hooks/pre-push"

if [[ ! -d "$REPO_PATH/.git/hooks" ]]; then
  echo "Not a git repo: $REPO_PATH"
  exit 1
fi

cat > "$HOOK_PATH" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$REPO_ROOT"

if command -v python3 >/dev/null 2>&1; then
  python3 cli.py secret-scan --staged
else
  python cli.py secret-scan --staged
fi
EOF

chmod +x "$HOOK_PATH"
echo "Secret scan pre-push hook installed: $HOOK_PATH"
