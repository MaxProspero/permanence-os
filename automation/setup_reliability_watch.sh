#!/usr/bin/env bash
set -euo pipefail

REPO_PATH="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DAYS="${1:-7}"
INTERVAL_MINUTES="${2:-30}"

if [[ "$OSTYPE" != darwin* ]]; then
  echo "setup_reliability_watch.sh configures macOS launchd only."
  exit 1
fi

cd "$REPO_PATH"
python "$REPO_PATH/cli.py" reliability-watch \
  --arm \
  --force \
  --days "$DAYS" \
  --check-interval-minutes "$INTERVAL_MINUTES"

python "$REPO_PATH/cli.py" reliability-watch --status

echo "Reliability watch armed for ${DAYS} day(s)."
echo "Check status anytime with: python cli.py reliability-watch --status"
