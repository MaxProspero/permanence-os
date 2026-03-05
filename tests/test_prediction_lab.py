#!/usr/bin/env python3
"""Tests for prediction lab brief."""

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import scripts.prediction_lab as pred_mod  # noqa: E402


def test_prediction_lab_generates_manual_review_candidates():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        outputs = root / "outputs"
        tool = root / "tool"
        working = root / "working"
        outputs.mkdir(parents=True, exist_ok=True)
        tool.mkdir(parents=True, exist_ok=True)
        working.mkdir(parents=True, exist_ok=True)

        hypothesis_path = working / "prediction_hypotheses.json"
        hypothesis_path.write_text(
            json.dumps(
                [
                    {
                        "hypothesis_id": "PM-1",
                        "title": "Positive edge candidate",
                        "market": "demo",
                        "prior_prob": 0.55,
                        "signal_score": 0.8,
                        "market_prob": 0.45,
                        "odds_decimal": 2.3,
                    },
                    {
                        "hypothesis_id": "PM-2",
                        "title": "Negative EV candidate",
                        "market": "demo",
                        "prior_prob": 0.35,
                        "signal_score": -0.8,
                        "market_prob": 0.50,
                        "odds_decimal": 1.7,
                    },
                ]
            ),
            encoding="utf-8",
        )

        original = {
            "OUTPUT_DIR": pred_mod.OUTPUT_DIR,
            "TOOL_DIR": pred_mod.TOOL_DIR,
            "HYPOTHESIS_PATH": pred_mod.HYPOTHESIS_PATH,
            "SIM_RUNS": pred_mod.SIM_RUNS,
            "EDGE_THRESHOLD": pred_mod.EDGE_THRESHOLD,
            "MAX_RISK_PCT": pred_mod.MAX_RISK_PCT,
            "BANKROLL_USD": pred_mod.BANKROLL_USD,
        }
        try:
            pred_mod.OUTPUT_DIR = outputs
            pred_mod.TOOL_DIR = tool
            pred_mod.HYPOTHESIS_PATH = hypothesis_path
            pred_mod.SIM_RUNS = 500
            pred_mod.EDGE_THRESHOLD = 0.02
            pred_mod.MAX_RISK_PCT = 0.02
            pred_mod.BANKROLL_USD = 1000
            rc = pred_mod.main()
        finally:
            pred_mod.OUTPUT_DIR = original["OUTPUT_DIR"]
            pred_mod.TOOL_DIR = original["TOOL_DIR"]
            pred_mod.HYPOTHESIS_PATH = original["HYPOTHESIS_PATH"]
            pred_mod.SIM_RUNS = original["SIM_RUNS"]
            pred_mod.EDGE_THRESHOLD = original["EDGE_THRESHOLD"]
            pred_mod.MAX_RISK_PCT = original["MAX_RISK_PCT"]
            pred_mod.BANKROLL_USD = original["BANKROLL_USD"]

        assert rc == 0
        latest = outputs / "prediction_lab_latest.md"
        assert latest.exists()
        content = latest.read_text(encoding="utf-8")
        assert "Prediction Lab Brief" in content

        tool_files = sorted(tool.glob("prediction_lab_*.json"))
        assert tool_files
        payload = json.loads(tool_files[-1].read_text(encoding="utf-8"))
        assert payload.get("manual_review_candidates", 0) >= 1
        results = payload.get("results") or []
        assert any(row.get("manual_approval_required") for row in results)


if __name__ == "__main__":
    test_prediction_lab_generates_manual_review_candidates()
    print("✓ Prediction lab tests passed")
