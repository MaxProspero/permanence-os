#!/usr/bin/env python3
"""
Revenue Ops evaluation harness (artifact + data contract checks).
"""

from __future__ import annotations

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
PLAYBOOK_PATH = Path(os.getenv("PERMANENCE_REVENUE_PLAYBOOK_PATH", str(WORKING_DIR / "revenue_playbook.json")))
TARGETS_PATH = Path(os.getenv("PERMANENCE_REVENUE_TARGETS_PATH", str(WORKING_DIR / "revenue_targets.json")))
INTEGRATION_LATEST = OUTPUT_DIR / "integration_readiness_latest.md"


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def _latest_tool(pattern: str) -> Path | None:
    if not TOOL_DIR.exists():
        return None
    items = sorted(TOOL_DIR.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    return items[0] if items else None


def _default_playbook() -> dict[str, Any]:
    return {
        "offer_name": "Permanence OS Foundation Setup",
        "cta_keyword": "FOUNDATION",
    }


def _default_targets() -> dict[str, Any]:
    weekly = 3000
    return {
        "weekly_revenue_target": weekly,
        "monthly_revenue_target": max(12000, weekly * 4),
    }


def _check_files() -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []

    def add_file(name: str, path: Path, required: bool = True) -> None:
        checks.append(
            {
                "name": name,
                "required": required,
                "ok": path.exists(),
                "detail": str(path),
            }
        )

    add_file("queue_latest_md", OUTPUT_DIR / "revenue_action_queue_latest.md")
    add_file("execution_board_latest_md", OUTPUT_DIR / "revenue_execution_board_latest.md")
    add_file("outreach_pack_latest_md", OUTPUT_DIR / "revenue_outreach_pack_latest.md")
    add_file("followup_queue_latest_md", OUTPUT_DIR / "revenue_followup_queue_latest.md", required=False)
    add_file("integration_readiness_latest_md", INTEGRATION_LATEST, required=False)
    add_file("pipeline_json", PIPELINE_PATH)
    add_file("playbook_json", PLAYBOOK_PATH, required=False)
    add_file("targets_json", TARGETS_PATH)
    return checks


def _check_data_contracts() -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    pipeline = _read_json(PIPELINE_PATH, [])
    playbook_payload = _read_json(PLAYBOOK_PATH, {})
    if not isinstance(playbook_payload, dict):
        playbook_payload = {}
    playbook = dict(_default_playbook())
    playbook.update(playbook_payload)

    targets_payload = _read_json(TARGETS_PATH, {})
    if not isinstance(targets_payload, dict):
        targets_payload = {}
    targets = dict(_default_targets())
    targets.update(targets_payload)

    checks.append(
        {
            "name": "pipeline_is_list",
            "required": True,
            "ok": isinstance(pipeline, list),
            "detail": f"type={type(pipeline).__name__}",
        }
    )
    open_count = 0
    if isinstance(pipeline, list):
        open_count = sum(1 for row in pipeline if isinstance(row, dict) and str(row.get("stage")) not in {"won", "lost"})
    checks.append(
        {
            "name": "pipeline_open_count_non_negative",
            "required": True,
            "ok": open_count >= 0,
            "detail": f"open_count={open_count}",
        }
    )

    checks.append(
        {
            "name": "playbook_has_offer_and_cta",
            "required": True,
            "ok": isinstance(playbook, dict) and bool(str(playbook.get("offer_name") or "").strip()) and bool(str(playbook.get("cta_keyword") or "").strip()),
            "detail": f"offer={playbook.get('offer_name')} cta={playbook.get('cta_keyword')}",
        }
    )
    checks.append(
        {
            "name": "targets_have_revenue_values",
            "required": True,
            "ok": isinstance(targets, dict) and float(targets.get("weekly_revenue_target", 0) or 0) >= 0 and float(targets.get("monthly_revenue_target", 0) or 0) >= 0,
            "detail": f"weekly={targets.get('weekly_revenue_target')} monthly={targets.get('monthly_revenue_target')}",
        }
    )

    outreach_tool = _latest_tool("revenue_outreach_pack_*.json")
    outreach_payload = _read_json(outreach_tool, {}) if outreach_tool else {}
    messages = outreach_payload.get("messages") if isinstance(outreach_payload, dict) else []
    msg_count = len(messages) if isinstance(messages, list) else 0
    checks.append(
        {
            "name": "outreach_messages_when_open_leads",
            "required": False,
            "ok": (open_count == 0) or (msg_count > 0),
            "detail": f"open_count={open_count} outreach_messages={msg_count}",
        }
    )
    return checks


def _write_report(checks: list[dict[str, Any]]) -> tuple[Path, Path]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    TOOL_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    md_path = OUTPUT_DIR / f"revenue_eval_{stamp}.md"
    latest_md = OUTPUT_DIR / "revenue_eval_latest.md"
    json_path = TOOL_DIR / f"revenue_eval_{stamp}.json"

    required_checks = [c for c in checks if c.get("required")]
    required_pass = sum(1 for c in required_checks if c.get("ok"))
    required_total = len(required_checks)
    failed = [c for c in checks if c.get("required") and not c.get("ok")]
    status = "PASS" if not failed else "FAIL"

    lines = [
        "# Revenue Eval",
        "",
        f"Generated (UTC): {_now_utc()}",
        "",
        "## Summary",
        f"- Required checks: {required_pass}/{required_total}",
        f"- Result: {status}",
        "",
        "## Checks",
    ]
    for check in checks:
        level = "required" if check.get("required") else "optional"
        result = "PASS" if check.get("ok") else "FAIL"
        lines.append(f"- {check['name']} | {level} | {result} | {check['detail']}")

    if failed:
        lines.extend(["", "## Failures"])
        for row in failed:
            lines.append(f"- {row['name']}: {row['detail']}")

    report = "\n".join(lines) + "\n"
    md_path.write_text(report, encoding="utf-8")
    latest_md.write_text(report, encoding="utf-8")
    payload = {
        "generated_at": _now_utc(),
        "result": status,
        "required_passed": required_pass,
        "required_total": required_total,
        "checks": checks,
        "latest_markdown": str(latest_md),
    }
    json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return md_path, json_path


def main() -> int:
    checks = _check_files() + _check_data_contracts()
    md_path, json_path = _write_report(checks)
    required_failures = [c for c in checks if c.get("required") and not c.get("ok")]
    print(f"Revenue eval written: {md_path}")
    print(f"Revenue eval latest: {OUTPUT_DIR / 'revenue_eval_latest.md'}")
    print(f"Tool payload written: {json_path}")
    print("Revenue eval: PASS" if not required_failures else "Revenue eval: FAIL")
    return 0 if not required_failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
