#!/usr/bin/env python3
"""
Generate and manage self-improvement pitches for Ophtxn under governance.

This workflow proposes upgrades, requests explicit approval, and can queue
approved upgrades into the existing approvals board.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parents[1]


def _load_local_env() -> None:
    env_path = BASE_DIR / ".env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key or key in os.environ:
            continue
        value = value.strip()
        if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
            value = value[1:-1]
        os.environ[key] = value


_load_local_env()
WORKING_DIR = Path(os.getenv("PERMANENCE_WORKING_DIR", str(BASE_DIR / "memory" / "working")))
OUTPUT_DIR = Path(os.getenv("PERMANENCE_OUTPUT_DIR", str(BASE_DIR / "outputs")))
TOOL_DIR = Path(os.getenv("PERMANENCE_TOOL_DIR", str(BASE_DIR / "memory" / "tool")))
PROPOSALS_PATH = Path(
    os.getenv("PERMANENCE_SELF_IMPROVEMENT_PROPOSALS_PATH", str(WORKING_DIR / "self_improvement_proposals.json"))
)
POLICY_PATH = Path(
    os.getenv("PERMANENCE_SELF_IMPROVEMENT_POLICY_PATH", str(WORKING_DIR / "self_improvement_policy.json"))
)
APPROVALS_PATH = Path(os.getenv("PERMANENCE_APPROVALS_PATH", str(BASE_DIR / "memory" / "approvals.json")))
PERSONAL_MEMORY_PATH = Path(
    os.getenv(
        "PERMANENCE_TELEGRAM_CONTROL_MEMORY_PATH",
        str(WORKING_DIR / "telegram_control" / "personal_memory.json"),
    )
)
SIMULATION_LATEST_PATH = OUTPUT_DIR / "ophtxn_simulation_latest.md"

PRIORITY_ORDER = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
STATUS_ORDER = {"PENDING_HUMAN_REVIEW": 0, "APPROVED": 1, "REJECTED": 2, "DEFERRED": 3}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now().isoformat()


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _is_true(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _default_policy() -> dict[str, Any]:
    return {
        "version": "1.0",
        "enabled": True,
        "require_explicit_approval": True,
        "require_decision_code": False,
        "decision_code_sha256": "",
        "max_pending_pitches": 25,
        "auto_queue_approved": True,
        "auto_send_pitch_to_telegram": False,
        "thresholds": {
            "memory_top1_min": 0.72,
            "max_chat_reply_failures": 0,
            "max_open_profile_conflicts": 0,
        },
        "updated_at": _now_iso(),
    }


def _ensure_policy(path: Path, force_template: bool = False) -> tuple[dict[str, Any], str]:
    defaults = _default_policy()
    if force_template or not path.exists():
        _write_json(path, defaults)
        return defaults, "written"
    payload = _read_json(path, {})
    if not isinstance(payload, dict):
        payload = {}
    merged = dict(defaults)
    merged.update(payload)
    if not isinstance(merged.get("thresholds"), dict):
        merged["thresholds"] = dict(defaults["thresholds"])
    else:
        threshold_merged = dict(defaults["thresholds"])
        threshold_merged.update(merged["thresholds"])
        merged["thresholds"] = threshold_merged
    if merged != payload:
        merged["updated_at"] = _now_iso()
        _write_json(path, merged)
        return merged, "updated"
    return merged, "existing"


def _load_proposals(path: Path) -> list[dict[str, Any]]:
    payload = _read_json(path, [])
    if not isinstance(payload, list):
        return []
    return [row for row in payload if isinstance(row, dict)]


def _normalize_priority(value: Any) -> str:
    token = str(value or "").strip().upper()
    if token in PRIORITY_ORDER:
        return token
    return "MEDIUM"


def _normalize_status(value: Any) -> str:
    token = str(value or "").strip().upper()
    if token in STATUS_ORDER:
        return token
    return "PENDING_HUMAN_REVIEW"


def _proposal_fingerprint(title: str, proposed_change: str) -> str:
    token = f"{title.strip().lower()}|{proposed_change.strip().lower()}"
    return hashlib.sha1(token.encode("utf-8")).hexdigest()[:16]


def _proposal_id(fingerprint: str) -> str:
    return f"IMP-{fingerprint[:10].upper()}"


def _hash_decision_code(code: str) -> str:
    token = str(code or "").strip()
    if not token:
        return ""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _verify_decision_code(policy: dict[str, Any], decision_code: str) -> tuple[bool, str]:
    required = bool(policy.get("require_decision_code"))
    if not required:
        return True, ""
    expected = str(policy.get("decision_code_sha256") or "").strip().lower()
    if not expected:
        return False, "decision code required but policy hash is not configured"
    provided_hash = _hash_decision_code(decision_code).strip().lower()
    if not provided_hash:
        return False, "decision code required: provide --decision-code"
    if provided_hash != expected:
        return False, "decision code mismatch"
    return True, ""


def _latest_tool(pattern: str) -> Path | None:
    if not TOOL_DIR.exists():
        return None
    rows = sorted(TOOL_DIR.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    return rows[0] if rows else None


def _simulation_metrics(path: Path) -> dict[str, float]:
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    top1_match = re.search(r"Top1 hit rate:\s*([0-9.]+)", text)
    conflicts_match = re.search(r"Open profile conflicts:\s*([0-9.]+)", text)
    top1 = _safe_float(top1_match.group(1), 0.0) if top1_match else 0.0
    conflicts = _safe_float(conflicts_match.group(1), 0.0) if conflicts_match else 0.0
    return {"top1_hit_rate": top1, "open_profile_conflicts": conflicts}


def _open_profile_conflicts_from_memory(path: Path) -> int:
    payload = _read_json(path, {})
    if not isinstance(payload, dict):
        return 0
    profiles = payload.get("profiles")
    if not isinstance(profiles, dict):
        return 0
    total = 0
    for row in profiles.values():
        if not isinstance(row, dict):
            continue
        conflicts = row.get("profile_conflicts")
        if not isinstance(conflicts, list):
            continue
        for item in conflicts:
            if not isinstance(item, dict):
                continue
            if str(item.get("status") or "").strip().lower() == "resolved":
                continue
            total += 1
    return total


def _candidate(
    *,
    title: str,
    priority: str,
    current_state: str,
    proposed_change: str,
    expected_benefit: str,
    risk_if_ignored: str,
    source_findings: list[str],
    draft_codex_task: str = "",
) -> dict[str, Any]:
    fingerprint = _proposal_fingerprint(title, proposed_change)
    return {
        "proposal_id": _proposal_id(fingerprint),
        "fingerprint": fingerprint,
        "title": title.strip(),
        "priority": _normalize_priority(priority),
        "finding_summary": current_state.strip(),
        "current_state": current_state.strip(),
        "proposed_change": proposed_change.strip(),
        "expected_benefit": expected_benefit.strip(),
        "risk_if_ignored": risk_if_ignored.strip(),
        "implementation_scope": "system_improvement",
        "draft_codex_task": draft_codex_task.strip() or None,
        "source_findings": [item for item in source_findings if str(item or "").strip()][:8],
        "source": "self_improvement_loop",
    }


def _collect_candidates(policy: dict[str, Any]) -> list[dict[str, Any]]:
    thresholds = policy.get("thresholds") if isinstance(policy.get("thresholds"), dict) else {}
    min_top1 = _safe_float(thresholds.get("memory_top1_min"), 0.72)
    max_chat_failures = _safe_int(thresholds.get("max_chat_reply_failures"), 0)
    max_conflicts = _safe_int(thresholds.get("max_open_profile_conflicts"), 0)

    candidates: list[dict[str, Any]] = []

    metrics = _simulation_metrics(SIMULATION_LATEST_PATH)
    if metrics["top1_hit_rate"] > 0 and metrics["top1_hit_rate"] < min_top1:
        candidates.append(
            _candidate(
                title="Improve memory retrieval precision",
                priority="HIGH",
                current_state=(
                    f"Memory top1 hit rate is {metrics['top1_hit_rate']:.2f}, below target {min_top1:.2f}."
                ),
                proposed_change=(
                    "Add semantic reranking layer (embedding + lexical hybrid) for /recall and chat memory context."
                ),
                expected_benefit="Higher first-answer relevance and less repetition in long-running conversations.",
                risk_if_ignored="The assistant feels forgetful or off-target in high-context sessions.",
                source_findings=[str(SIMULATION_LATEST_PATH)],
                draft_codex_task=(
                    "Implement embedding reranker fallback in telegram_control memory retrieval path."
                ),
            )
        )

    open_conflicts = max(
        _safe_int(metrics.get("open_profile_conflicts"), 0),
        _open_profile_conflicts_from_memory(PERSONAL_MEMORY_PATH),
    )
    if open_conflicts > max_conflicts:
        candidates.append(
            _candidate(
                title="Add profile conflict resolver workflow",
                priority="MEDIUM",
                current_state=f"Detected {open_conflicts} open profile conflicts across stored profile memory.",
                proposed_change="Add `/profile-resolve <conflict-id>` to close or merge contradictory profile updates.",
                expected_benefit="Cleaner personalization and fewer conflicting decisions in assistant behavior.",
                risk_if_ignored="Conflicting profile facts can degrade trust and decision quality.",
                source_findings=[str(PERSONAL_MEMORY_PATH)],
                draft_codex_task="Add resolve command and status transitions for profile conflict rows.",
            )
        )

    tg_path = _latest_tool("telegram_control_*.json")
    tg_payload = _read_json(tg_path, {}) if tg_path else {}
    if isinstance(tg_payload, dict):
        failed = _safe_int(tg_payload.get("chat_replies_failed"), 0)
        fallback = _safe_int(tg_payload.get("chat_replies_fallback_sent"), 0)
        if failed > max_chat_failures:
            candidates.append(
                _candidate(
                    title="Reduce chat reply failures in Telegram loop",
                    priority="HIGH",
                    current_state=f"Telegram loop recorded {failed} failed chat replies (fallback sent={fallback}).",
                    proposed_change=(
                        "Add structured retry with jitter + model failover to keep conversational continuity."
                    ),
                    expected_benefit="Higher reliability and fewer dead-air moments in chat.",
                    risk_if_ignored="User trust drops when replies intermittently fail.",
                    source_findings=[str(tg_path)],
                    draft_codex_task="Implement retry/failover path around _generate_chat_reply send flow.",
                )
            )

    gl_path = _latest_tool("governed_learning_*.json")
    gl_payload = _read_json(gl_path, {}) if gl_path else {}
    if isinstance(gl_payload, dict):
        reasons = gl_payload.get("block_reasons") if isinstance(gl_payload.get("block_reasons"), list) else []
        if reasons:
            candidates.append(
                _candidate(
                    title="Unblock governed learning cadence",
                    priority="MEDIUM",
                    current_state=f"Governed learning was blocked with {len(reasons)} reason(s).",
                    proposed_change="Resolve block reasons and schedule a fixed daily/6-hour learning pitch cycle.",
                    expected_benefit="Consistent self-improvement ideas delivered without manual babysitting.",
                    risk_if_ignored="System improvement cadence remains inconsistent.",
                    source_findings=[str(gl_path)] + [str(item) for item in reasons[:4]],
                    draft_codex_task="Address block reason(s) and configure automation setup for governed learning.",
                )
            )

    policy_path = _read_json(POLICY_PATH, {})
    if isinstance(policy_path, dict) and not bool(policy_path.get("enabled", True)):
        candidates.append(
            _candidate(
                title="Enable self-improvement policy",
                priority="MEDIUM",
                current_state="Self-improvement policy is disabled.",
                proposed_change="Enable policy and enforce explicit approval workflow for proposed upgrades.",
                expected_benefit="Predictable cycle of pitch -> approve -> execute.",
                risk_if_ignored="No proactive upgrade pitches will be generated.",
                source_findings=[str(POLICY_PATH)],
                draft_codex_task="Toggle enabled=true and run initial pitch generation.",
            )
        )

    if not candidates:
        candidates.append(
            _candidate(
                title="Run weekly capability tuning review",
                priority="LOW",
                current_state="No urgent performance regressions detected in latest signals.",
                proposed_change=(
                    "Perform weekly personality/memory/habit tuning review and update thresholds from user feedback."
                ),
                expected_benefit="Steady compounding improvements without waiting for failures.",
                risk_if_ignored="Slow drift in assistant quality and personalization fit.",
                source_findings=["governance: steady-state recommendation"],
                draft_codex_task="Add weekly review checklist and threshold update notes.",
            )
        )

    return candidates


def _dedupe_and_add(
    proposals: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
    max_pending: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int]:
    normalized: list[dict[str, Any]] = []
    for row in proposals:
        if not isinstance(row, dict):
            continue
        item = dict(row)
        item["status"] = _normalize_status(item.get("status"))
        item["priority"] = _normalize_priority(item.get("priority"))
        item["fingerprint"] = str(item.get("fingerprint") or "").strip()
        if not item["fingerprint"]:
            item["fingerprint"] = _proposal_fingerprint(
                str(item.get("title") or ""),
                str(item.get("proposed_change") or ""),
            )
        item["proposal_id"] = str(item.get("proposal_id") or _proposal_id(item["fingerprint"])).strip()
        normalized.append(item)

    existing_fingerprints = {str(item.get("fingerprint") or "") for item in normalized}
    pending_count = sum(1 for item in normalized if str(item.get("status")) == "PENDING_HUMAN_REVIEW")

    added: list[dict[str, Any]] = []
    skipped_capacity = 0
    for candidate in candidates:
        fingerprint = str(candidate.get("fingerprint") or "")
        if not fingerprint or fingerprint in existing_fingerprints:
            continue
        if pending_count >= max_pending:
            skipped_capacity += 1
            continue
        now = _now_iso()
        item = dict(candidate)
        item["status"] = "PENDING_HUMAN_REVIEW"
        item["created_at"] = now
        item["updated_at"] = now
        normalized.append(item)
        added.append(item)
        existing_fingerprints.add(fingerprint)
        pending_count += 1

    normalized.sort(
        key=lambda row: (
            STATUS_ORDER.get(str(row.get("status") or ""), 9),
            PRIORITY_ORDER.get(str(row.get("priority") or ""), 9),
            str(row.get("created_at") or ""),
        )
    )
    return normalized, added, skipped_capacity


def _pending_rows(proposals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = [row for row in proposals if str(row.get("status") or "") == "PENDING_HUMAN_REVIEW"]
    rows.sort(
        key=lambda row: (
            PRIORITY_ORDER.get(str(row.get("priority") or ""), 9),
            str(row.get("created_at") or ""),
        )
    )
    return rows


def _find_proposal(proposals: list[dict[str, Any]], proposal_id: str) -> dict[str, Any] | None:
    needle = str(proposal_id or "").strip().upper()
    if not needle:
        return None
    for row in proposals:
        token = str(row.get("proposal_id") or "").strip().upper()
        if token == needle:
            return row
    return None


def _load_approvals(path: Path) -> list[dict[str, Any]]:
    payload = _read_json(path, [])
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict) and isinstance(payload.get("approvals"), list):
        return [row for row in payload.get("approvals", []) if isinstance(row, dict)]
    return []


def _save_approvals(path: Path, approvals: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(approvals, indent=2) + "\n", encoding="utf-8")


def _queue_approved_proposal(proposal: dict[str, Any], approvals_path: Path) -> tuple[bool, str]:
    approvals = _load_approvals(approvals_path)
    proposal_id = str(proposal.get("proposal_id") or "").strip()
    for row in approvals:
        rid = str(row.get("id") or row.get("proposal_id") or row.get("approval_id") or "").strip()
        if rid == proposal_id:
            return False, "already_queued"
    item = {
        "proposal_id": proposal_id,
        "id": proposal_id,
        "approval_id": proposal_id,
        "title": str(proposal.get("title") or "System improvement").strip(),
        "finding_summary": str(proposal.get("finding_summary") or "").strip(),
        "current_state": str(proposal.get("current_state") or "").strip(),
        "proposed_change": str(proposal.get("proposed_change") or "").strip(),
        "expected_benefit": str(proposal.get("expected_benefit") or "").strip(),
        "risk_if_ignored": str(proposal.get("risk_if_ignored") or "").strip(),
        "implementation_scope": str(proposal.get("implementation_scope") or "system_improvement").strip(),
        "draft_canon_amendment": None,
        "draft_codex_task": proposal.get("draft_codex_task"),
        "source_findings": proposal.get("source_findings") if isinstance(proposal.get("source_findings"), list) else [],
        "priority": _normalize_priority(proposal.get("priority")),
        "status": "APPROVED",
        "created_at": _now_iso(),
        "queued_at": _now_iso(),
        "source": "self_improvement_loop",
        "manual_approval_required": True,
    }
    approvals.append(item)
    _save_approvals(approvals_path, approvals)
    return True, "queued"


def _send_imessage(text: str, timeout: int = 20) -> tuple[bool, str]:
    if sys.platform != "darwin":
        return False, "iMessage/SMS mirror requires macOS"
    if not _is_true(os.getenv("PERMANENCE_TELEGRAM_CONTROL_IMESSAGE_MIRROR", "0")):
        return False, "iMessage mirror disabled"
    target = str(os.getenv("PERMANENCE_TELEGRAM_CONTROL_IMESSAGE_TARGET", "")).strip()
    if not target:
        return False, "iMessage target missing"
    service_raw = str(os.getenv("PERMANENCE_TELEGRAM_CONTROL_IMESSAGE_SERVICE", "iMessage")).strip().lower()
    service_name = "SMS" if service_raw in {"sms", "text", "textmessage"} else "iMessage"
    prefix = str(os.getenv("PERMANENCE_TELEGRAM_CONTROL_IMESSAGE_PREFIX", "[Ophtxn]")).strip()
    payload = str(text or "").strip()
    if not payload:
        return False, "iMessage payload is empty"
    if prefix:
        payload = f"{prefix} {payload}".strip()
    max_chars_raw = str(os.getenv("PERMANENCE_TELEGRAM_CONTROL_IMESSAGE_MAX_CHARS", "1200")).strip()
    try:
        max_chars = max(120, int(max_chars_raw))
    except ValueError:
        max_chars = 1200
    if len(payload) > max_chars:
        payload = payload[: max_chars - 3].rstrip() + "..."
    script = (
        "on run argv\n"
        "set targetHandle to item 1 of argv\n"
        "set messageText to item 2 of argv\n"
        "set preferredService to item 3 of argv\n"
        "tell application \"Messages\"\n"
        "set targetService to missing value\n"
        "if preferredService is \"SMS\" then\n"
        "try\n"
        "set targetService to first service whose service type = SMS\n"
        "end try\n"
        "end if\n"
        "if targetService is missing value then\n"
        "try\n"
        "set targetService to first service whose service type = iMessage\n"
        "end try\n"
        "end if\n"
        "if targetService is missing value then error \"No available Messages service\"\n"
        "set targetBuddy to buddy targetHandle of targetService\n"
        "send messageText to targetBuddy\n"
        "end tell\n"
        "return \"sent\"\n"
        "end run\n"
    )
    proc = subprocess.run(
        ["osascript", "-e", script, target, payload, service_name],
        check=False,
        capture_output=True,
        text=True,
        timeout=max(3, int(timeout)),
    )
    if proc.returncode != 0:
        return False, (proc.stderr or "").strip() or f"osascript exited {proc.returncode}"
    return True, (proc.stdout or "").strip() or "sent"


def _send_telegram_message(text: str, chat_id_override: str = "") -> tuple[bool, str]:
    token = str(os.getenv("PERMANENCE_TELEGRAM_BOT_TOKEN", "")).strip()
    chat_id = str(chat_id_override or os.getenv("PERMANENCE_TELEGRAM_CHAT_ID", "")).strip()
    if not token:
        return False, "telegram token missing"
    if not chat_id:
        return False, "telegram chat id missing"
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    cmd = [
        "curl",
        "-sS",
        "--max-time",
        "20",
        "--get",
        url,
        "--data-urlencode",
        f"chat_id={chat_id}",
        "--data-urlencode",
        f"text={text}",
    ]
    proc = subprocess.run(cmd, check=False, capture_output=True, text=True)
    if proc.returncode != 0:
        return False, (proc.stderr or "").strip() or f"curl exited {proc.returncode}"
    try:
        payload = json.loads(proc.stdout or "{}")
    except json.JSONDecodeError:
        return False, "invalid telegram response"
    if not bool(payload.get("ok")):
        return False, f"telegram send failed: {payload.get('description') or 'unknown'}"
    mirrored, mirror_detail = _send_imessage(text, timeout=20)
    if mirrored:
        return True, f"sent; iMessage mirror: {mirror_detail}"
    if "disabled" in str(mirror_detail).lower():
        return True, "sent"
    return True, f"sent; iMessage mirror skipped: {mirror_detail}"


def _write_report(
    *,
    action: str,
    policy_path: Path,
    proposals_path: Path,
    policy_status: str,
    policy: dict[str, Any],
    proposals: list[dict[str, Any]],
    new_pitches: list[dict[str, Any]],
    skipped_capacity: int,
    decision_result: str,
    warnings: list[str],
) -> tuple[Path, Path]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    TOOL_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _now().strftime("%Y%m%d-%H%M%S")
    md_path = OUTPUT_DIR / f"self_improvement_{stamp}.md"
    latest_md = OUTPUT_DIR / "self_improvement_latest.md"
    json_path = TOOL_DIR / f"self_improvement_{stamp}.json"

    pending = [row for row in proposals if str(row.get("status") or "") == "PENDING_HUMAN_REVIEW"]
    approved = [row for row in proposals if str(row.get("status") or "") == "APPROVED"]
    rejected = [row for row in proposals if str(row.get("status") or "") == "REJECTED"]
    deferred = [row for row in proposals if str(row.get("status") or "") == "DEFERRED"]

    lines = [
        "# Self Improvement",
        "",
        f"Generated (UTC): {_now_iso()}",
        f"Action: {action}",
        f"Policy path: {policy_path}",
        f"Proposals path: {proposals_path}",
        f"Policy status: {policy_status}",
        "",
        "## Governance",
        f"- Policy enabled: {bool(policy.get('enabled'))}",
        f"- Requires explicit approval: {bool(policy.get('require_explicit_approval'))}",
        f"- Requires decision code: {bool(policy.get('require_decision_code'))}",
        f"- Auto-queue approved: {bool(policy.get('auto_queue_approved'))}",
        f"- Auto-send pitch to Telegram: {bool(policy.get('auto_send_pitch_to_telegram'))}",
        "",
        "## Summary",
        f"- New pitches: {len(new_pitches)}",
        f"- Pending: {len(pending)}",
        f"- Approved: {len(approved)}",
        f"- Rejected: {len(rejected)}",
        f"- Deferred: {len(deferred)}",
        f"- Capacity skips: {skipped_capacity}",
        f"- Decision result: {decision_result or '-'}",
    ]

    lines.extend(["", "## Pending Pitches"])
    if not pending:
        lines.append("- No pending pitches.")
    for idx, row in enumerate(_pending_rows(proposals)[:12], start=1):
        lines.extend(
            [
                f"{idx}. {row.get('title')} [{row.get('priority')}] ({row.get('proposal_id')})",
                f"   - proposed_change={row.get('proposed_change')}",
                f"   - expected_benefit={row.get('expected_benefit')}",
                f"   - risk_if_ignored={row.get('risk_if_ignored')}",
            ]
        )

    if warnings:
        lines.extend(["", "## Warnings"])
        for row in warnings:
            lines.append(f"- {row}")

    report = "\n".join(lines) + "\n"
    md_path.write_text(report, encoding="utf-8")
    latest_md.write_text(report, encoding="utf-8")

    payload = {
        "generated_at": _now_iso(),
        "action": action,
        "policy_path": str(policy_path),
        "proposals_path": str(proposals_path),
        "policy_status": policy_status,
        "policy_enabled": bool(policy.get("enabled")),
        "new_pitches_count": len(new_pitches),
        "pending_count": len(pending),
        "approved_count": len(approved),
        "rejected_count": len(rejected),
        "deferred_count": len(deferred),
        "capacity_skips": skipped_capacity,
        "decision_result": decision_result,
        "warnings": warnings,
        "new_pitches": new_pitches,
        "pending_pitches": _pending_rows(proposals)[:20],
        "latest_markdown": str(latest_md),
    }
    _write_json(json_path, payload)
    return md_path, json_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Governed self-improvement pitch loop for Ophtxn.")
    parser.add_argument("--action", choices=["status", "pitch", "list", "decide", "init-policy"], default="status")
    parser.add_argument("--policy-path", help="Policy JSON path override")
    parser.add_argument("--proposals-path", help="Proposals JSON path override")
    parser.add_argument("--force-template", action="store_true", help="Rewrite policy template")
    parser.add_argument("--decision", choices=["approve", "reject", "defer"], help="Decision action for --action decide")
    parser.add_argument("--proposal-id", help="Proposal id for --action decide")
    parser.add_argument("--decided-by", help="Actor making decision")
    parser.add_argument("--note", help="Optional decision note")
    parser.add_argument("--decision-code", help="Decision code for --action decide when policy requires it")
    parser.add_argument("--set-decision-code", help="Set or rotate policy decision code")
    parser.add_argument("--clear-decision-code", action="store_true", help="Disable required decision code")
    parser.add_argument("--send-telegram", action="store_true", help="Send top pitch/decision summary to Telegram")
    parser.add_argument("--telegram-chat-id", help="Telegram chat id override")
    args = parser.parse_args(argv)

    policy_path = Path(args.policy_path).expanduser() if args.policy_path else POLICY_PATH
    proposals_path = Path(args.proposals_path).expanduser() if args.proposals_path else PROPOSALS_PATH
    policy, policy_status = _ensure_policy(policy_path, force_template=bool(args.force_template or args.action == "init-policy"))
    proposals = _load_proposals(proposals_path)

    decision_code_flag_conflict = bool(args.set_decision_code) and bool(args.clear_decision_code)
    policy_mutated = False
    if bool(args.set_decision_code) and (not decision_code_flag_conflict):
        policy["require_decision_code"] = True
        policy["decision_code_sha256"] = _hash_decision_code(str(args.set_decision_code))
        policy["updated_at"] = _now_iso()
        _write_json(policy_path, policy)
        policy_mutated = True
    if bool(args.clear_decision_code) and (not decision_code_flag_conflict):
        policy["require_decision_code"] = False
        policy["decision_code_sha256"] = ""
        policy["updated_at"] = _now_iso()
        _write_json(policy_path, policy)
        policy_mutated = True
    if policy_mutated and policy_status == "existing":
        policy_status = "updated"

    warnings: list[str] = []
    new_pitches: list[dict[str, Any]] = []
    skipped_capacity = 0
    decision_result = ""
    rc = 0
    if decision_code_flag_conflict:
        warnings.append("invalid flags: use either --set-decision-code or --clear-decision-code")
        rc = 1

    if args.action in {"pitch", "init-policy"}:
        if not bool(policy.get("enabled")) and args.action == "pitch":
            warnings.append("policy disabled: set enabled=true to generate proactive pitches")
        else:
            max_pending = max(1, _safe_int(policy.get("max_pending_pitches"), 25))
            candidates = _collect_candidates(policy)
            proposals, new_pitches, skipped_capacity = _dedupe_and_add(
                proposals=proposals,
                candidates=candidates,
                max_pending=max_pending,
            )
            _write_json(proposals_path, proposals)
            if not new_pitches:
                warnings.append("no new unique pitches generated")

    if args.action == "decide":
        decision = str(args.decision or "").strip().lower()
        if decision not in {"approve", "reject", "defer"}:
            warnings.append("invalid decision: use --decision approve|reject|defer")
            rc = 1
        else:
            code_ok, code_reason = _verify_decision_code(policy, str(args.decision_code or ""))
            if not code_ok:
                warnings.append(code_reason)
                rc = 1
        if rc == 0:
            target = _find_proposal(proposals, str(args.proposal_id or ""))
            if target is None:
                pending = _pending_rows(proposals)
                target = pending[0] if pending else None
            if target is None:
                warnings.append("no pending proposals available")
                rc = 1
            else:
                status = {
                    "approve": "APPROVED",
                    "reject": "REJECTED",
                    "defer": "DEFERRED",
                }[decision]
                target["status"] = status
                target["updated_at"] = _now_iso()
                target["decided_at"] = _now_iso()
                target["decided_by"] = str(args.decided_by or "").strip() or "manual"
                target["decision_note"] = str(args.note or "").strip()
                decision_result = f"{target.get('proposal_id')} -> {status}"
                if status == "APPROVED" and bool(policy.get("auto_queue_approved", True)):
                    queued, queue_result = _queue_approved_proposal(target, APPROVALS_PATH)
                    if not queued:
                        warnings.append(f"approval queue: {queue_result}")
                _write_json(proposals_path, proposals)

    if args.action == "list":
        pass

    md_path, json_path = _write_report(
        action=args.action,
        policy_path=policy_path,
        proposals_path=proposals_path,
        policy_status=policy_status,
        policy=policy,
        proposals=proposals,
        new_pitches=new_pitches,
        skipped_capacity=skipped_capacity,
        decision_result=decision_result,
        warnings=warnings,
    )

    should_send_telegram = bool(args.send_telegram or policy.get("auto_send_pitch_to_telegram"))
    if should_send_telegram:
        pending = _pending_rows(proposals)
        if args.action == "decide" and decision_result:
            msg = (
                f"Ophtxn decision logged: {decision_result}\n"
                f"Remaining pending pitches: {len(pending)}\n"
                f"See: {OUTPUT_DIR / 'self_improvement_latest.md'}"
            )
        elif pending:
            top = pending[0]
            msg = (
                "Ophtxn improvement pitch:\n"
                f"{top.get('title')} [{top.get('priority')}] ({top.get('proposal_id')})\n"
                f"Change: {top.get('proposed_change')}\n"
                "Reply with /improve-approve or /improve-reject."
            )
        else:
            msg = "Ophtxn improvement loop: no pending pitches right now."
        sent, detail = _send_telegram_message(msg, chat_id_override=str(args.telegram_chat_id or ""))
        if not sent:
            warnings.append(detail)
            rc = 1 if rc == 0 else rc

    print(f"Self-improvement report: {md_path}")
    print(f"Self-improvement latest: {OUTPUT_DIR / 'self_improvement_latest.md'}")
    print(f"Tool payload: {json_path}")
    print(f"New pitches: {len(new_pitches)}")
    print(f"Pending pitches: {len(_pending_rows(proposals))}")
    if warnings:
        print(f"Warnings: {len(warnings)}")
    if rc != 0:
        return rc
    if warnings and args.action == "decide":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
