#!/usr/bin/env python3
"""
Convert chronicle timeline signals into backlog refinements.

This script is advisory only: it never auto-executes actions.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scripts.chronicle_common import CHRONICLE_OUTPUT_DIR, utc_iso

BASE_DIR = Path(__file__).resolve().parents[1]
OUTPUT_DIR = Path(os.getenv("PERMANENCE_OUTPUT_DIR", str(BASE_DIR / "outputs")))
TOOL_DIR = Path(os.getenv("PERMANENCE_TOOL_DIR", str(BASE_DIR / "memory" / "tool")))
WORKING_DIR = Path(os.getenv("PERMANENCE_WORKING_DIR", str(BASE_DIR / "memory" / "working")))
DEFAULT_BACKLOG_PATH = Path(
    os.getenv("PERMANENCE_CHRONICLE_BACKLOG_PATH", str(WORKING_DIR / "chronicle_backlog_refinement.json"))
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now().isoformat().replace("+00:00", "Z")


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _latest_chronicle_report() -> Path | None:
    if not CHRONICLE_OUTPUT_DIR.exists():
        return None
    rows = sorted(CHRONICLE_OUTPUT_DIR.glob("chronicle_report_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    return rows[0] if rows else None


def _as_event_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [row for row in value if isinstance(row, dict)]


def _trim(text: str, max_chars: int = 180) -> str:
    cleaned = " ".join(str(text or "").strip().split())
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[: max_chars - 3].rstrip() + "..."


def _score_to_priority(score: int) -> str:
    if score >= 85:
        return "HIGH"
    if score >= 65:
        return "MEDIUM"
    return "LOW"


def _action_blueprint(summary: str, category: str) -> tuple[str, str]:
    lower = summary.lower()
    if "queue" in lower or "backlog" in lower:
        return (
            "Queue hygiene and backlog compression",
            "Reduce pending queue items to <=1 and keep a daily queue-zero closeout check.",
        )
    if any(token in lower for token in ["error", "failed", "timeout", "blocked", "denied", "disconnect"]):
        return (
            "Failure-path hardening and regression coverage",
            "Reproduce the failure from chronicle evidence, patch the root cause, and add a regression test.",
        )
    if any(token in lower for token in ["telegram", "discord", "relay", "chat", "comms"]):
        return (
            "Communication routing reliability hardening",
            "Harden multi-channel message routing, retries, and freshness checks for chat loops.",
        )
    if any(token in lower for token in ["token", "budget", "cost", "quota", "credit"]):
        return (
            "Cost-control routing tune-up",
            "Tighten local-first model routing and fallback thresholds to keep spend within budget caps.",
        )
    if any(token in lower for token in ["roadmap", "priority", "direction", "strategy", "focus"]):
        return (
            "Roadmap alignment and priority lock",
            "Convert direction changes into explicit roadmap updates with owners and exit criteria.",
        )
    if category == "issue":
        return (
            "Chronicle issue triage",
            "Create a scoped fix task from this issue signal and verify with a targeted test.",
        )
    return (
        "Chronicle direction refinement",
        "Translate this direction signal into one concrete backlog task and owner.",
    )


def _candidate_id(seed_parts: list[str]) -> str:
    digest = hashlib.sha1("|".join(seed_parts).encode("utf-8")).hexdigest()[:12]
    return f"CRB-{digest}"


def _candidate_from_event(event: dict[str, Any], category: str, index: int) -> dict[str, Any]:
    summary = _trim(str(event.get("summary") or f"{category} signal"))
    timestamp = str(event.get("timestamp") or "unknown")
    title, next_action = _action_blueprint(summary, category)
    base_score = 92 if category == "issue" else 74
    score = max(45, base_score - index * 3)
    why_now = (
        "Chronicle captured recurring friction that can degrade execution velocity."
        if category == "issue"
        else "Chronicle detected directional drift that should be converted into explicit priorities."
    )
    return {
        "id": _candidate_id([category, timestamp, summary]),
        "title": title,
        "category": category,
        "priority": _score_to_priority(score),
        "score": int(score),
        "next_action": next_action,
        "why_now": why_now,
        "evidence": [f"{timestamp} | {summary}"],
    }


def _meta_candidates(report: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    signal_totals = report.get("signal_totals") or {}
    issue_hits = _safe_int(signal_totals.get("issue_hits"))
    log_error_hits = _safe_int(signal_totals.get("log_error_hits"))
    direction_hits = _safe_int(signal_totals.get("direction_hits"))
    warning_hits = _safe_int(signal_totals.get("log_warning_hits"))
    events_count = _safe_int(report.get("events_count"))
    commit_count = _safe_int(report.get("commit_count"))

    if issue_hits > 0 or log_error_hits > 0:
        score = min(95, 78 + issue_hits * 2 + log_error_hits * 2)
        out.append(
            {
                "id": _candidate_id(["meta", "stability", str(issue_hits), str(log_error_hits)]),
                "title": "Stability sprint from chronicle friction totals",
                "category": "meta",
                "priority": _score_to_priority(score),
                "score": int(score),
                "next_action": (
                    "Run a bounded stability sprint against top error/failure signals and close with regression tests."
                ),
                "why_now": (
                    f"Chronicle totals show issue_hits={issue_hits}, log_error_hits={log_error_hits}."
                ),
                "evidence": [f"signal_totals.issue_hits={issue_hits}", f"signal_totals.log_error_hits={log_error_hits}"],
            }
        )

    if direction_hits >= 2:
        score = min(90, 68 + direction_hits * 3)
        out.append(
            {
                "id": _candidate_id(["meta", "direction", str(direction_hits)]),
                "title": "Direction-shift consolidation",
                "category": "meta",
                "priority": _score_to_priority(score),
                "score": int(score),
                "next_action": "Consolidate direction shifts into one ordered roadmap sequence and prune conflicting tasks.",
                "why_now": f"Chronicle detected repeated direction signals (direction_hits={direction_hits}).",
                "evidence": [f"signal_totals.direction_hits={direction_hits}"],
            }
        )

    if events_count >= 12 and commit_count <= 3:
        score = 66
        out.append(
            {
                "id": _candidate_id(["meta", "throughput", str(events_count), str(commit_count)]),
                "title": "Signal-to-shipping throughput correction",
                "category": "meta",
                "priority": _score_to_priority(score),
                "score": int(score),
                "next_action": "Convert top chronicle signals into 1-3 day scoped tasks and ship at least one completion daily.",
                "why_now": (
                    f"Chronicle events ({events_count}) are outpacing commit throughput ({commit_count}) in the same window."
                ),
                "evidence": [f"events_count={events_count}", f"commit_count={commit_count}"],
            }
        )

    if warning_hits >= 3:
        score = min(84, 62 + warning_hits * 2)
        out.append(
            {
                "id": _candidate_id(["meta", "warnings", str(warning_hits)]),
                "title": "Warning-noise reduction pass",
                "category": "meta",
                "priority": _score_to_priority(score),
                "score": int(score),
                "next_action": "Reduce chronic warning sources and promote only high-signal alerts into daily loops.",
                "why_now": f"Chronicle warning signal volume remains elevated (log_warning_hits={warning_hits}).",
                "evidence": [f"signal_totals.log_warning_hits={warning_hits}"],
            }
        )

    return out


def _dedupe_and_rank(candidates: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for row in sorted(
        candidates,
        key=lambda item: (-_safe_int(item.get("score")), str(item.get("title") or "").lower()),
    ):
        title_key = str(row.get("title") or "").strip().lower()
        if not title_key or title_key in seen:
            continue
        seen.add(title_key)
        unique.append(row)
        if len(unique) >= limit:
            break
    return unique


def _build_backlog_updates(report: dict[str, Any], max_items: int) -> list[dict[str, Any]]:
    issue_events = _as_event_list(report.get("issue_events"))
    direction_events = _as_event_list(report.get("direction_events"))
    candidates: list[dict[str, Any]] = []
    for idx, event in enumerate(issue_events[:10]):
        candidates.append(_candidate_from_event(event, category="issue", index=idx))
    for idx, event in enumerate(direction_events[:10]):
        candidates.append(_candidate_from_event(event, category="direction", index=idx))
    candidates.extend(_meta_candidates(report))
    return _dedupe_and_rank(candidates, limit=max(1, int(max_items)))


def _build_canon_checks(
    report: dict[str, Any],
    backlog_updates: list[dict[str, Any]],
    max_items: int,
) -> list[dict[str, Any]]:
    if max_items <= 0:
        return []

    direction_events = _as_event_list(report.get("direction_events"))
    signal_totals = report.get("signal_totals") or {}
    issue_hits = _safe_int(signal_totals.get("issue_hits"))
    log_error_hits = _safe_int(signal_totals.get("log_error_hits"))

    trigger = "routine_review"
    trigger_note = "No major direction shift detected; routine canon alignment check."
    if direction_events:
        trigger = "direction_shift_detected"
        trigger_note = f"Chronicle reports {len(direction_events)} direction-shift event(s)."
    elif issue_hits > 0 or log_error_hits > 0:
        trigger = "stability_patch_detected"
        trigger_note = f"Chronicle reports issue_hits={issue_hits}, log_error_hits={log_error_hits}."

    backlog_ids = [str(row.get("id")) for row in backlog_updates if str(row.get("id")).strip()]
    check = {
        "check_id": _candidate_id(["canon", trigger, _now_iso()]).replace("CRB-", "CANON-"),
        "title": "Canon alignment review before backlog execution",
        "trigger": trigger,
        "status": "PENDING_HUMAN_REVIEW",
        "question": (
            "Do these backlog updates preserve human-final authority and non-negotiable guardrails "
            "for money, legal, and public actions?"
        ),
        "recommended_gate": "manual_review",
        "trigger_note": trigger_note,
        "related_backlog_ids": backlog_ids[:6],
    }
    return [check][: max(1, int(max_items))]


def _sync_backlog(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _write_outputs(
    *,
    report_source: Path | None,
    backlog_updates: list[dict[str, Any]],
    canon_checks: list[dict[str, Any]],
    warnings: list[str],
    backlog_path: Path | None,
    output_path_override: Path | None,
) -> tuple[Path, Path]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    TOOL_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _now().strftime("%Y%m%d-%H%M%S")

    md_path = output_path_override if output_path_override else OUTPUT_DIR / f"chronicle_refinement_{stamp}.md"
    latest_md = OUTPUT_DIR / "chronicle_refinement_latest.md"
    json_path = TOOL_DIR / f"chronicle_refinement_{stamp}.json"

    lines = [
        "# Chronicle Backlog Refinement",
        "",
        f"Generated (UTC): {_now_iso()}",
        f"Chronicle source: {report_source if report_source else 'none'}",
        f"Backlog sync: {backlog_path if backlog_path else 'disabled'}",
        "",
        "## Summary",
        f"- Backlog updates proposed: {len(backlog_updates)}",
        f"- Canon checks proposed: {len(canon_checks)}",
    ]
    if warnings:
        lines.append(f"- Warnings: {len(warnings)}")
    lines.extend(["", "## Top Backlog Updates"])

    if not backlog_updates:
        lines.append("- None generated.")
    for idx, item in enumerate(backlog_updates, start=1):
        lines.extend(
            [
                f"{idx}. {item.get('title')} [{item.get('priority')}]",
                f"   - score={item.get('score')} | category={item.get('category')} | id={item.get('id')}",
                f"   - next_action={item.get('next_action')}",
                f"   - why_now={item.get('why_now')}",
            ]
        )
        evidence_rows = item.get("evidence") if isinstance(item.get("evidence"), list) else []
        for ev in evidence_rows[:2]:
            lines.append(f"   - evidence={ev}")

    lines.extend(["", "## Canon Checks"])
    if not canon_checks:
        lines.append("- None generated.")
    for idx, item in enumerate(canon_checks, start=1):
        lines.extend(
            [
                f"{idx}. {item.get('title')}",
                f"   - trigger={item.get('trigger')} | status={item.get('status')} | check_id={item.get('check_id')}",
                f"   - question={item.get('question')}",
                f"   - trigger_note={item.get('trigger_note')}",
            ]
        )

    if warnings:
        lines.extend(["", "## Warnings"])
        for warning in warnings:
            lines.append(f"- {warning}")

    lines.extend(
        [
            "",
            "## Governance Notes",
            "- Advisory-only output; this does not execute external actions.",
            "- Human review is required before any canon or high-risk workflow changes.",
            "",
        ]
    )

    markdown = "\n".join(lines)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(markdown, encoding="utf-8")
    latest_md.write_text(markdown, encoding="utf-8")

    payload = {
        "generated_at": utc_iso(),
        "chronicle_source": str(report_source) if report_source else "none",
        "backlog_sync_path": str(backlog_path) if backlog_path else None,
        "backlog_updates_count": len(backlog_updates),
        "canon_checks_count": len(canon_checks),
        "backlog_updates": backlog_updates,
        "canon_checks": canon_checks,
        "warnings": warnings,
        "latest_markdown": str(latest_md),
    }
    json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return md_path, json_path


def _load_report(path_arg: str | None) -> tuple[dict[str, Any], Path | None, str | None]:
    source: Path | None
    if path_arg:
        source = Path(path_arg).expanduser()
    else:
        source = _latest_chronicle_report()
    if source is None or not source.exists():
        return {}, None, "No chronicle report JSON found. Run `python cli.py chronicle-report` first."
    payload = _read_json(source, {})
    if not isinstance(payload, dict):
        return {}, source, f"Chronicle report could not be parsed: {source}"
    return payload, source, None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Refine backlog priorities from chronicle report signals.")
    parser.add_argument("--report-json", help="Chronicle report JSON path (default: latest chronicle report)")
    parser.add_argument("--max-backlog-items", type=int, default=3, help="Maximum backlog updates to propose")
    parser.add_argument("--max-canon-checks", type=int, default=1, help="Maximum canon checks to propose")
    parser.add_argument("--backlog-path", help="Output JSON path for synced backlog refinement recommendations")
    parser.add_argument("--output", help="Optional markdown output path")
    parser.add_argument("--no-sync-backlog", action="store_true", help="Do not sync recommendations into backlog JSON")
    parser.add_argument("--strict", action="store_true", help="Return non-zero when chronicle source is missing/invalid")
    args = parser.parse_args(argv)

    warnings: list[str] = []
    report, report_source, load_warning = _load_report(args.report_json)
    if load_warning:
        warnings.append(load_warning)

    backlog_updates: list[dict[str, Any]] = []
    canon_checks: list[dict[str, Any]] = []
    if report:
        backlog_updates = _build_backlog_updates(report, max_items=max(1, int(args.max_backlog_items)))
        canon_checks = _build_canon_checks(
            report,
            backlog_updates=backlog_updates,
            max_items=max(0, int(args.max_canon_checks)),
        )

    backlog_path = None if args.no_sync_backlog else Path(args.backlog_path).expanduser() if args.backlog_path else DEFAULT_BACKLOG_PATH
    if backlog_path is not None:
        _sync_backlog(
            backlog_path,
            {
                "generated_at": utc_iso(),
                "chronicle_source": str(report_source) if report_source else "none",
                "backlog_updates": backlog_updates,
                "canon_checks": canon_checks,
                "warnings": warnings,
            },
        )

    output_override = Path(args.output).expanduser() if args.output else None
    md_path, json_path = _write_outputs(
        report_source=report_source,
        backlog_updates=backlog_updates,
        canon_checks=canon_checks,
        warnings=warnings,
        backlog_path=backlog_path,
        output_path_override=output_override,
    )
    print(f"Chronicle refinement report: {md_path}")
    print(f"Chronicle refinement latest: {OUTPUT_DIR / 'chronicle_refinement_latest.md'}")
    if backlog_path:
        print(f"Backlog refinement sync: {backlog_path}")
    print(f"Tool payload written: {json_path}")
    print(f"Backlog updates: {len(backlog_updates)} | Canon checks: {len(canon_checks)}")

    if args.strict and warnings:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
