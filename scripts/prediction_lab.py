#!/usr/bin/env python3
"""
Generate a governed prediction-market research brief.

This tool is intentionally advisory: it does not place trades or connect to exchanges.
"""

from __future__ import annotations

import json
import math
import os
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parents[1]
WORKING_DIR = Path(os.getenv("PERMANENCE_WORKING_DIR", str(BASE_DIR / "memory" / "working")))
OUTPUT_DIR = Path(os.getenv("PERMANENCE_OUTPUT_DIR", str(BASE_DIR / "outputs")))
TOOL_DIR = Path(os.getenv("PERMANENCE_TOOL_DIR", str(BASE_DIR / "memory" / "tool")))
HYPOTHESIS_PATH = Path(os.getenv("PERMANENCE_PREDICTION_HYPOTHESES_PATH", str(WORKING_DIR / "prediction_hypotheses.json")))

BANKROLL_USD = float(os.getenv("PERMANENCE_PREDICTION_BANKROLL_USD", "1000"))
SIM_RUNS = int(os.getenv("PERMANENCE_PREDICTION_SIM_RUNS", "2000"))
EDGE_THRESHOLD = float(os.getenv("PERMANENCE_PREDICTION_EDGE_THRESHOLD", "0.03"))
MAX_RISK_PCT = float(os.getenv("PERMANENCE_PREDICTION_MAX_RISK_PCT", "0.01"))
RANDOM_SEED = int(os.getenv("PERMANENCE_PREDICTION_SEED", "42"))


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def _as_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _clip_probability(value: float) -> float:
    return max(0.01, min(0.99, value))


def _default_hypotheses() -> list[dict[str, Any]]:
    return [
        {
            "hypothesis_id": "PM-001",
            "title": "Sample policy outcome market",
            "market": "paper_demo",
            "status": "watchlist",
            "prior_prob": 0.50,
            "signal_score": 0.0,
            "market_prob": 0.50,
            "odds_decimal": 2.0,
            "confidence": "low",
            "notes": "Replace with real market hypotheses once data pipeline is connected.",
        }
    ]


def _load_hypotheses() -> list[dict[str, Any]]:
    payload = _read_json(HYPOTHESIS_PATH, [])
    if not isinstance(payload, list):
        payload = []
    rows = [row for row in payload if isinstance(row, dict)]
    if not rows:
        rows = _default_hypotheses()
    return rows


def _posterior_prob(prior_prob: float, signal_score: float) -> float:
    # Bayesian style update from signal score to likelihood ratio.
    prior = _clip_probability(prior_prob)
    odds = prior / (1.0 - prior)
    likelihood_ratio = math.exp(max(-2.0, min(2.0, signal_score)))
    post_odds = odds * likelihood_ratio
    return _clip_probability(post_odds / (1.0 + post_odds))


def _simulate_ev(prob: float, odds_decimal: float, runs: int) -> tuple[float, float]:
    random.seed(RANDOM_SEED)
    pnl: list[float] = []
    for _ in range(max(100, runs)):
        hit = random.random() < prob
        gain = odds_decimal - 1.0
        pnl.append(gain if hit else -1.0)
    pnl.sort()
    expected = sum(pnl) / len(pnl)
    p05 = pnl[max(0, int(0.05 * len(pnl)) - 1)]
    return expected, p05


def _kelly_fraction(prob: float, odds_decimal: float) -> float:
    b = max(0.0001, odds_decimal - 1.0)
    q = 1.0 - prob
    return max(0.0, min(1.0, (b * prob - q) / b))


def _evaluate_row(row: dict[str, Any]) -> dict[str, Any]:
    prior_prob = _clip_probability(_as_float(row.get("prior_prob"), 0.50))
    signal_score = _as_float(row.get("signal_score"), 0.0)
    market_prob = _clip_probability(_as_float(row.get("market_prob"), 0.50))
    odds_decimal = max(1.01, _as_float(row.get("odds_decimal"), 1.0 / market_prob))
    posterior = _posterior_prob(prior_prob, signal_score)
    edge = posterior - market_prob
    expected_pnl, p05 = _simulate_ev(posterior, odds_decimal, SIM_RUNS)
    kelly = _kelly_fraction(posterior, odds_decimal)
    capped_fraction = min(MAX_RISK_PCT, kelly * 0.50)
    suggested_stake = round(BANKROLL_USD * capped_fraction, 2)

    decision = "watchlist"
    if edge >= EDGE_THRESHOLD and expected_pnl > 0:
        decision = "review_for_manual_execution"
    if expected_pnl <= 0:
        decision = "reject_negative_ev"

    return {
        "hypothesis_id": str(row.get("hypothesis_id") or "unknown"),
        "title": str(row.get("title") or "Untitled hypothesis"),
        "market": str(row.get("market") or "unknown"),
        "status": str(row.get("status") or "watchlist"),
        "manual_approval_required": True,
        "prior_prob": round(prior_prob, 4),
        "signal_score": round(signal_score, 4),
        "posterior_prob": round(posterior, 4),
        "market_prob": round(market_prob, 4),
        "edge": round(edge, 4),
        "odds_decimal": round(odds_decimal, 4),
        "expected_pnl_per_1usd": round(expected_pnl, 4),
        "p05_pnl_per_1usd": round(p05, 4),
        "kelly_fraction": round(kelly, 4),
        "risk_cap_fraction": round(capped_fraction, 4),
        "suggested_stake_usd": suggested_stake,
        "decision": decision,
        "notes": str(row.get("notes") or ""),
    }


def _write_outputs(results: list[dict[str, Any]]) -> tuple[Path, Path]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    TOOL_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _now().strftime("%Y%m%d-%H%M%S")
    md_path = OUTPUT_DIR / f"prediction_lab_{stamp}.md"
    latest_md = OUTPUT_DIR / "prediction_lab_latest.md"
    json_path = TOOL_DIR / f"prediction_lab_{stamp}.json"

    rows = sorted(results, key=lambda row: row.get("edge", 0), reverse=True)
    review_count = sum(1 for row in rows if row.get("decision") == "review_for_manual_execution")

    lines = [
        "# Prediction Lab Brief",
        "",
        f"Generated (UTC): {_now().isoformat()}",
        f"Hypothesis source: {HYPOTHESIS_PATH}",
        f"Bankroll assumption: ${BANKROLL_USD:,.2f}",
        f"Edge threshold: {EDGE_THRESHOLD:.2%}",
        f"Max risk cap: {MAX_RISK_PCT:.2%}",
        "",
        "## Summary",
        f"- Hypotheses reviewed: {len(rows)}",
        f"- Manual-review candidates: {review_count}",
        "",
        "## Ranked Hypotheses",
    ]
    if not rows:
        lines.append("- No hypotheses available.")
    for idx, row in enumerate(rows, start=1):
        lines.extend(
            [
                f"{idx}. {row.get('title')} ({row.get('hypothesis_id')})",
                (
                    "   - "
                    f"posterior={row.get('posterior_prob')} | market={row.get('market_prob')} | "
                    f"edge={row.get('edge')} | ev_per_$1={row.get('expected_pnl_per_1usd')} | "
                    f"p05={row.get('p05_pnl_per_1usd')}"
                ),
                (
                    "   - "
                    f"kelly={row.get('kelly_fraction')} | cap={row.get('risk_cap_fraction')} | "
                    f"suggested_stake=${row.get('suggested_stake_usd', 0):,.2f} | decision={row.get('decision')}"
                ),
            ]
        )

    lines.extend(
        [
            "",
            "## Governance Notes",
            "- Advisory only: no order placement and no broker/exchange execution.",
            "- Manual approval is mandatory before any real-money action.",
            "- Validate legal and tax constraints for your jurisdiction and platform.",
            "",
        ]
    )

    report = "\n".join(lines)
    md_path.write_text(report, encoding="utf-8")
    latest_md.write_text(report, encoding="utf-8")

    payload = {
        "generated_at": _now().isoformat(),
        "hypothesis_path": str(HYPOTHESIS_PATH),
        "bankroll_usd": BANKROLL_USD,
        "edge_threshold": EDGE_THRESHOLD,
        "max_risk_pct": MAX_RISK_PCT,
        "simulation_runs": SIM_RUNS,
        "manual_review_candidates": review_count,
        "results": rows,
        "latest_markdown": str(latest_md),
    }
    json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return md_path, json_path


def main() -> int:
    rows = _load_hypotheses()
    results = [_evaluate_row(row) for row in rows]
    md_path, json_path = _write_outputs(results)
    print(f"Prediction lab written: {md_path}")
    print(f"Prediction lab latest: {OUTPUT_DIR / 'prediction_lab_latest.md'}")
    print(f"Tool payload written: {json_path}")
    print(f"Manual-review candidates: {sum(1 for row in results if row.get('decision') == 'review_for_manual_execution')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
