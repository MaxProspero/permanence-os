#!/usr/bin/env bash
set -euo pipefail

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="$BASE_DIR/logs/automation"
mkdir -p "$LOG_DIR"

STAMP="$(date -u +%Y%m%d-%H%M%S)"
LOG_FILE="$LOG_DIR/second_brain_loop_${STAMP}.log"

PYTHON_BIN="python3"
if [[ -x "$BASE_DIR/.venv/bin/python" ]]; then
  PYTHON_BIN="$BASE_DIR/.venv/bin/python"
fi

run_step() {
  local name="$1"
  shift
  echo "== $name ==" | tee -a "$LOG_FILE"
  if "$@" >>"$LOG_FILE" 2>&1; then
    echo "[ok] $name" | tee -a "$LOG_FILE"
  else
    local rc=$?
    echo "[warn] $name failed (status $rc)" | tee -a "$LOG_FILE"
  fi
}

echo "Second brain loop started (UTC): $(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee "$LOG_FILE"
echo "Repo: $BASE_DIR" | tee -a "$LOG_FILE"

cd "$BASE_DIR"
if [[ -f "$BASE_DIR/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$BASE_DIR/.env"
  set +a
fi

FEATURE_GATE_REQUIRED="${PERMANENCE_FEATURE_WORK_REQUIRE_REVENUE_MILESTONE:-0}"
if [[ "$FEATURE_GATE_REQUIRED" == "1" ]]; then
  echo "== money-first-gate ==" | tee -a "$LOG_FILE"
  if "$PYTHON_BIN" cli.py money-first-gate --strict >>"$LOG_FILE" 2>&1; then
    echo "[ok] money-first-gate" | tee -a "$LOG_FILE"
  else
    rc=$?
    echo "[fail] money-first-gate blocked second-brain-loop (status $rc)" | tee -a "$LOG_FILE"
    echo "Set PERMANENCE_FEATURE_WORK_REQUIRE_REVENUE_MILESTONE=0 to bypass." | tee -a "$LOG_FILE"
    exit 2
  fi
else
  echo "[skip] money-first-gate (PERMANENCE_FEATURE_WORK_REQUIRE_REVENUE_MILESTONE=0)" | tee -a "$LOG_FILE"
fi

run_step "life-os-brief" "$PYTHON_BIN" cli.py life-os-brief
run_step "github-research-ingest" "$PYTHON_BIN" cli.py github-research-ingest
run_step "github-trending-ingest" "$PYTHON_BIN" cli.py github-trending-ingest
run_step "ecosystem-research-ingest" "$PYTHON_BIN" cli.py ecosystem-research-ingest
run_step "social-research-ingest" "$PYTHON_BIN" cli.py social-research-ingest
run_step "side-business-portfolio" "$PYTHON_BIN" cli.py side-business-portfolio
run_step "prediction-ingest" "$PYTHON_BIN" cli.py prediction-ingest
run_step "prediction-lab" "$PYTHON_BIN" cli.py prediction-lab
run_step "world-watch" "$PYTHON_BIN" cli.py world-watch
run_step "world-watch-alerts" "$PYTHON_BIN" cli.py world-watch-alerts
run_step "market-focus-brief" "$PYTHON_BIN" cli.py market-focus-brief
run_step "market-backtest-queue" "$PYTHON_BIN" cli.py market-backtest-queue
run_step "narrative-tracker" "$PYTHON_BIN" cli.py narrative-tracker
run_step "opportunity-ranker" "$PYTHON_BIN" cli.py opportunity-ranker
run_step "opportunity-approval-queue" "$PYTHON_BIN" cli.py opportunity-approval-queue
run_step "clipping-transcript-ingest" "$PYTHON_BIN" cli.py clipping-transcript-ingest
run_step "clipping-pipeline" "$PYTHON_BIN" cli.py clipping-pipeline
run_step "revenue-execution-board" "$PYTHON_BIN" cli.py revenue-execution-board
run_step "revenue-cost-recovery" "$PYTHON_BIN" cli.py revenue-cost-recovery
run_step "second-brain-report" "$PYTHON_BIN" cli.py second-brain-report

echo "Second brain loop completed (UTC): $(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee -a "$LOG_FILE"
echo "Log: $LOG_FILE" | tee -a "$LOG_FILE"
