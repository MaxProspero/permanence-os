#!/usr/bin/env python3
"""
Logos Praktikos activation gate.
Evaluates tier eligibility using Canon thresholds and HR history.
"""

import argparse
import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import yaml

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CANON_PATH = os.getenv("PERMANENCE_CANON_PATH", os.path.join(BASE_DIR, "canon", "base_canon.yaml"))
LOG_DIR = os.getenv("PERMANENCE_LOG_DIR", os.path.join(BASE_DIR, "logs"))
HISTORY_PATH = os.path.join(LOG_DIR, "hr_agent_history.json")


def _load_canon(path: str) -> Dict[str, Any]:
    with open(path, "r") as f:
        return yaml.safe_load(f)


def _load_history(path: str) -> List[Dict[str, Any]]:
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return []
    raw_scores = data.get("scores", [])
    history: List[Dict[str, Any]] = []
    for item in raw_scores:
        if not isinstance(item, (list, tuple)) or len(item) != 2:
            continue
        ts, score = item
        history.append({"timestamp": ts, "score": score})
    return history


def _consecutive_weeks(history: List[Dict[str, Any]], min_score: float) -> int:
    count = 0
    for entry in reversed(history):
        if entry.get("score", 0) >= min_score:
            count += 1
        else:
            break
    return count


def _evaluate_tier(tier: Dict[str, Any], history: List[Dict[str, Any]]) -> Dict[str, Any]:
    blockers: List[str] = []
    min_weeks = int(tier.get("min_weeks_stable", 0))
    min_score = float(tier.get("min_health_score", 0))
    min_no_high = int(tier.get("min_weeks_no_high_patterns", 0))
    canon_alignment = float(tier.get("canon_alignment", 0))

    if min_weeks > 0:
        stable = _consecutive_weeks(history, min_score)
        if stable < min_weeks:
            blockers.append(f"Needs {min_weeks} consecutive weeks with score >= {min_score}. Current: {stable}.")

    if min_no_high > 0:
        # Historical high-pattern tracking not available yet.
        blockers.append(f"Requires {min_no_high} weeks with no HIGH patterns (not tracked yet).")

    if canon_alignment > 0:
        # Canon alignment history not tracked yet; require HR to certify.
        blockers.append(f"Requires canon alignment >= {canon_alignment}% (not tracked yet).")

    if tier.get("human_approval", False):
        blockers.append("Human approval required.")

    return {
        "eligible": len(blockers) == 0,
        "blockers": blockers,
        "capabilities": tier.get("capabilities", []),
        "restrictions": tier.get("restrictions", []),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate Logos Praktikos activation tiers")
    parser.add_argument("--output", help="Output path (default: outputs/logos_gate.md)")
    args = parser.parse_args()

    canon = _load_canon(CANON_PATH)
    tiers = canon.get("logos_praktikos_activation", {})
    history = _load_history(HISTORY_PATH)

    output_dir = os.getenv("PERMANENCE_OUTPUT_DIR", os.path.join(BASE_DIR, "outputs"))
    os.makedirs(output_dir, exist_ok=True)
    output_path = args.output or os.path.join(output_dir, "logos_gate.md")

    lines: List[str] = []
    lines.append("# Logos Praktikos Gate")
    lines.append("")
    lines.append(f"Generated (UTC): {datetime.now(timezone.utc).isoformat()}")
    lines.append(f"History entries: {len(history)}")
    lines.append("")

    if not tiers:
        lines.append("No logos_praktikos_activation tiers found in Canon.")
    else:
        for name, tier in tiers.items():
            result = _evaluate_tier(tier, history)
            lines.append(f"## {name}")
            lines.append(f"- Eligible: {'YES' if result['eligible'] else 'NO'}")
            if result["blockers"]:
                lines.append("- Blockers:")
                for blocker in result["blockers"]:
                    lines.append(f"  - {blocker}")
            if result["capabilities"]:
                lines.append("- Capabilities:")
                for cap in result["capabilities"]:
                    lines.append(f"  - {cap}")
            if result["restrictions"]:
                lines.append("- Restrictions:")
                for res in result["restrictions"]:
                    lines.append(f"  - {res}")
            lines.append("")

    with open(output_path, "w") as f:
        f.write("\n".join(lines).rstrip() + "\n")

    print(f"Logos gate report written to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
