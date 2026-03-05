#!/usr/bin/env python3
"""
Gate feature work until revenue milestone is reached.
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parents[1]
WORKING_DIR = Path(os.getenv("PERMANENCE_WORKING_DIR", str(BASE_DIR / "memory" / "working")))
OUTPUT_DIR = Path(os.getenv("PERMANENCE_OUTPUT_DIR", str(BASE_DIR / "outputs")))
TOOL_DIR = Path(os.getenv("PERMANENCE_TOOL_DIR", str(BASE_DIR / "memory" / "tool")))
PIPELINE_PATH = Path(os.getenv("PERMANENCE_SALES_PIPELINE_PATH", str(WORKING_DIR / "sales_pipeline.json")))
EVAL_LATEST_PATH = OUTPUT_DIR / "revenue_eval_latest.md"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now().isoformat()


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def _pipeline_rows(path: Path) -> list[dict[str, Any]]:
    payload = _read_json(path, [])
    if not isinstance(payload, list):
        return []
    return [row for row in payload if isinstance(row, dict)]


def _won_value(row: dict[str, Any]) -> float:
    if row.get("actual_value") is not None:
        return max(0.0, _safe_float(row.get("actual_value"), 0.0))
    return max(0.0, _safe_float(row.get("est_value"), 0.0))


def _eval_result(path: Path) -> str:
    if not path.exists():
        return "unknown"
    text = path.read_text(encoding="utf-8", errors="ignore").lower()
    if "result: pass" in text:
        return "pass"
    if "result: fail" in text:
        return "fail"
    return "unknown"


def _build_gate_status(rows: list[dict[str, Any]], milestone_usd: float, min_won_deals: int) -> dict[str, Any]:
    won_rows = [row for row in rows if str(row.get("stage") or "").strip().lower() == "won"]
    open_rows = [
        row
        for row in rows
        if str(row.get("stage") or "").strip().lower() in {"lead", "qualified", "call_scheduled", "proposal_sent", "negotiation"}
    ]
    won_revenue = sum(_won_value(row) for row in won_rows)
    won_count = len(won_rows)
    gate_pass = (won_revenue >= float(milestone_usd)) and (won_count >= int(min_won_deals))
    return {
        "gate_pass": gate_pass,
        "milestone_usd": float(milestone_usd),
        "min_won_deals": int(min_won_deals),
        "won_revenue_usd": round(won_revenue, 2),
        "won_deals": won_count,
        "open_deals": len(open_rows),
        "total_deals": len(rows),
    }


def _write_outputs(
    *,
    status: dict[str, Any],
    pipeline_path: Path,
    eval_status: str,
    strict: bool,
) -> tuple[Path, Path]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    TOOL_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _now().strftime("%Y%m%d-%H%M%S")
    md_path = OUTPUT_DIR / f"money_first_gate_{stamp}.md"
    latest_md = OUTPUT_DIR / "money_first_gate_latest.md"
    json_path = TOOL_DIR / f"money_first_gate_{stamp}.json"

    gate_pass = bool(status.get("gate_pass"))
    lines = [
        "# Money First Gate",
        "",
        f"Generated (UTC): {_now_iso()}",
        f"Pipeline path: {pipeline_path}",
        f"Revenue eval status: {eval_status}",
        f"Strict mode: {strict}",
        "",
        "## Gate Status",
        f"- Feature work unlocked: {gate_pass}",
        f"- Won revenue (USD): {status.get('won_revenue_usd')}",
        f"- Won deals: {status.get('won_deals')}",
        f"- Open deals: {status.get('open_deals')}",
        f"- Revenue milestone (USD): {status.get('milestone_usd')}",
        f"- Min won deals required: {status.get('min_won_deals')}",
    ]

    if gate_pass:
        lines.extend(
            [
                "",
                "## Result",
                "- Gate is OPEN. Feature work can proceed.",
            ]
        )
    else:
        lines.extend(
            [
                "",
                "## Result",
                "- Gate is CLOSED. Stay in money-first lane until milestone is reached.",
                "",
                "## Next Actions",
                "- Run `python cli.py money-first-lane --strict`",
                "- Add or update leads with `python cli.py sales-pipeline ...`",
                "- Close at least one deal and update it to `won` with `actual_value`",
            ]
        )

    lines.extend(
        [
            "",
            "## Governance Notes",
            "- This gate protects focus and budget discipline during early-stage build.",
            "- Unlock condition is objective and data-driven from local sales pipeline records.",
            "",
        ]
    )

    report = "\n".join(lines)
    md_path.write_text(report, encoding="utf-8")
    latest_md.write_text(report, encoding="utf-8")

    payload = {
        "generated_at": _now_iso(),
        "strict": bool(strict),
        "pipeline_path": str(pipeline_path),
        "revenue_eval_status": eval_status,
        "status": status,
        "latest_markdown": str(latest_md),
    }
    json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return md_path, json_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Gate feature work until first revenue milestone is reached.")
    parser.add_argument("--pipeline-path", help="Override pipeline JSON path")
    parser.add_argument(
        "--milestone-usd",
        type=float,
        default=_safe_float(os.getenv("PERMANENCE_FEATURE_GATE_MILESTONE_USD"), 500.0),
        help="Minimum won revenue required to unlock feature work",
    )
    parser.add_argument(
        "--min-won-deals",
        type=int,
        default=_safe_int(os.getenv("PERMANENCE_FEATURE_GATE_MIN_WON_DEALS"), 1),
        help="Minimum won deals required to unlock feature work",
    )
    parser.add_argument("--strict", action="store_true", help="Return non-zero if gate is closed")
    args = parser.parse_args(argv)

    pipeline_path = Path(args.pipeline_path).expanduser() if args.pipeline_path else PIPELINE_PATH
    rows = _pipeline_rows(pipeline_path)
    status = _build_gate_status(
        rows=rows,
        milestone_usd=max(1.0, float(args.milestone_usd)),
        min_won_deals=max(0, int(args.min_won_deals)),
    )
    eval_status = _eval_result(EVAL_LATEST_PATH)
    md_path, json_path = _write_outputs(status=status, pipeline_path=pipeline_path, eval_status=eval_status, strict=args.strict)

    print(f"Money-first gate report: {md_path}")
    print(f"Money-first gate latest: {OUTPUT_DIR / 'money_first_gate_latest.md'}")
    print(f"Tool payload: {json_path}")
    print(f"Feature work unlocked: {status.get('gate_pass')}")
    if args.strict and (not bool(status.get("gate_pass"))):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
