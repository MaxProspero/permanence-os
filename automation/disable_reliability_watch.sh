#!/usr/bin/env bash
set -euo pipefail

REPO_PATH="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "$REPO_PATH"
python "$REPO_PATH/cli.py" reliability-watch --disarm
echo "Reliability watch disarmed."
