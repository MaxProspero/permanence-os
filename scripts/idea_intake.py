#!/usr/bin/env python3
"""
Idea intake pipeline for Ophtxn:
- ingest long-form link dumps
- rank ideas with cost-aware + governance-aware scoring
- optionally queue top ideas for manual approval
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

BASE_DIR = Path(__file__).resolve().parents[1]
WORKING_DIR = Path(os.getenv("PERMANENCE_WORKING_DIR", str(BASE_DIR / "memory" / "working")))
OUTPUT_DIR = Path(os.getenv("PERMANENCE_OUTPUT_DIR", str(BASE_DIR / "outputs")))
TOOL_DIR = Path(os.getenv("PERMANENCE_TOOL_DIR", str(BASE_DIR / "memory" / "tool")))
INTAKE_PATH = Path(
    os.getenv(
        "PERMANENCE_TELEGRAM_CONTROL_INTAKE_PATH",
        str(BASE_DIR / "memory" / "inbox" / "telegram_share_intake.jsonl"),
    )
)
STATE_PATH = Path(
    os.getenv(
        "PERMANENCE_IDEA_INTAKE_STATE_PATH",
        str(WORKING_DIR / "idea_intake" / "state.json"),
    )
)
POLICY_PATH = Path(
    os.getenv(
        "PERMANENCE_IDEA_INTAKE_POLICY_PATH",
        str(WORKING_DIR / "idea_intake" / "policy.json"),
    )
)
APPROVALS_PATH = Path(os.getenv("PERMANENCE_APPROVALS_PATH", str(BASE_DIR / "memory" / "approvals.json")))
MAX_ITEMS_DEFAULT = int(os.getenv("PERMANENCE_IDEA_INTAKE_MAX_ITEMS", "40"))
QUEUE_MIN_SCORE_DEFAULT = float(os.getenv("PERMANENCE_IDEA_INTAKE_QUEUE_MIN_SCORE", "65"))
QUEUE_LIMIT_DEFAULT = int(os.getenv("PERMANENCE_IDEA_INTAKE_QUEUE_LIMIT", "6"))
URL_RE = re.compile(r"https?://[^\s<>\"]+")


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
        return int(float(value))
    except (TypeError, ValueError):
        return default


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


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line:
            continue
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            rows.append(parsed)
    return rows


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload) + "\n")


def _normalize_url(url: str) -> str:
    cleaned = str(url or "").strip()
    if not cleaned:
        return ""
    cleaned = cleaned.rstrip(".,);]")
    parsed = urlparse(cleaned)
    if not parsed.scheme or not parsed.netloc:
        return ""
    host = parsed.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    path = parsed.path or "/"
    query = f"?{parsed.query}" if parsed.query else ""
    return f"{parsed.scheme.lower()}://{host}{path}{query}"


def _url_hash(url: str) -> str:
    return hashlib.sha1(str(url).encode("utf-8")).hexdigest()[:16]


def _extract_urls(text: str) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for candidate in URL_RE.findall(str(text or "")):
        normalized = _normalize_url(candidate)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        out.append(normalized)
    return out


def _priority_label(score: float) -> str:
    if score >= 80:
        return "HIGH"
    if score >= 55:
        return "MEDIUM"
    return "LOW"


def _default_policy() -> dict[str, Any]:
    return {
        "max_items": max(5, MAX_ITEMS_DEFAULT),
        "min_score_keep": 28.0,
        "queue_min_score": max(20.0, QUEUE_MIN_SCORE_DEFAULT),
        "queue_limit": max(1, QUEUE_LIMIT_DEFAULT),
        "domain_bonuses": {
            "github.com": 16.0,
            "docs.": 8.0,
            "cloudflare.com": 10.0,
            "openai.com": 10.0,
            "ycombinator.com": 7.0,
            "mitsloan.mit.edu": 6.0,
            "mit.edu": 7.0,
            "substack.com": 8.0,
            "arxiv.org": 11.0,
            "nature.com": 9.0,
            "science.org": 9.0,
            "acm.org": 8.0,
            "ieee.org": 8.0,
        },
        "signal_weights": {
            "mcp": 18.0,
            "cloudflare": 14.0,
            "symphony": 16.0,
            "agent": 8.0,
            "agents": 8.0,
            "memory": 7.0,
            "googleworkspace": 14.0,
            "gmail": 10.0,
            "calendar": 10.0,
            "workflow": 6.0,
            "revenue": 8.0,
            "audit": 12.0,
            "solidity": 12.0,
            "smart contract": 12.0,
            "education": 10.0,
            "lms": 10.0,
            "substack": 8.0,
            "arxiv": 10.0,
            "journal": 8.0,
            "paper": 8.0,
            "research": 7.0,
            "mit": 6.0,
        },
        "drop_tokens": [
            "giveaway",
            "airdrop",
            "free money",
            "dm to claim",
            "telegram.me",
        ],
        "risk_high_tokens": [
            "trade",
            "trading",
            "crypto",
            "lottery",
            "jailbreak",
            "uncensor",
        ],
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

    payload_domain_bonuses = payload.get("domain_bonuses") if isinstance(payload.get("domain_bonuses"), dict) else {}
    merged_domain_bonuses = dict(defaults["domain_bonuses"])
    merged_domain_bonuses.update(payload_domain_bonuses)
    merged["domain_bonuses"] = merged_domain_bonuses

    payload_signal_weights = payload.get("signal_weights") if isinstance(payload.get("signal_weights"), dict) else {}
    merged_signal_weights = dict(defaults["signal_weights"])
    merged_signal_weights.update(payload_signal_weights)
    merged["signal_weights"] = merged_signal_weights

    payload_drop_tokens = payload.get("drop_tokens") if isinstance(payload.get("drop_tokens"), list) else []
    merged_drop_tokens = list(dict.fromkeys([str(x).strip() for x in defaults["drop_tokens"] + payload_drop_tokens if str(x).strip()]))
    merged["drop_tokens"] = merged_drop_tokens

    payload_risk_tokens = payload.get("risk_high_tokens") if isinstance(payload.get("risk_high_tokens"), list) else []
    merged_risk_tokens = list(
        dict.fromkeys([str(x).strip() for x in defaults["risk_high_tokens"] + payload_risk_tokens if str(x).strip()])
    )
    merged["risk_high_tokens"] = merged_risk_tokens

    if merged != payload:
        _write_json(path, merged)
        return merged, "updated"
    return merged, "existing"


def _entry_id(entry: dict[str, Any]) -> str:
    token = str(entry.get("intake_id") or entry.get("id") or "").strip()
    if token:
        return token
    text = str(entry.get("text") or "")
    source = str(entry.get("source") or "manual")
    channel = str(entry.get("channel") or "manual")
    created = str(entry.get("created_at") or _now_iso())
    digest = hashlib.sha1(f"{text}|{source}|{channel}|{created}".encode("utf-8")).hexdigest()[:12]
    return f"INT-{digest.upper()}"


def _classify_url(url: str) -> str:
    parsed = urlparse(url)
    host = (parsed.netloc or "").lower()
    path = (parsed.path or "").lower()
    if any(
        token in host
        for token in (
            "arxiv.org",
            "nature.com",
            "science.org",
            "sciencedirect.com",
            "springer.com",
            "acm.org",
            "ieee.org",
            "cell.com",
            "nejm.org",
            "thelancet.com",
            "jstor.org",
        )
    ):
        return "academic_journal"
    if "github.com" in host:
        chunks = [chunk for chunk in path.split("/") if chunk]
        if len(chunks) >= 2:
            return "github_repo"
        return "github"
    if "x.com" in host or "twitter.com" in host:
        if "/status/" in path:
            return "x_post"
        return "x_profile"
    if "youtube.com" in host or "youtu.be" in host:
        return "video"
    if "substack.com" in host:
        return "strategy_article"
    if "docs" in host or "/docs" in path:
        return "docs"
    if "mit.edu" in host or "ycombinator.com" in host:
        return "strategy_article"
    if "huggingface.co" in host:
        return "model_tool"
    return "web_tool"


def _category_base_score(category: str) -> float:
    if category == "github_repo":
        return 58.0
    if category == "academic_journal":
        return 56.0
    if category == "docs":
        return 52.0
    if category == "strategy_article":
        return 46.0
    if category == "model_tool":
        return 44.0
    if category == "x_post":
        return 36.0
    if category == "video":
        return 33.0
    if category == "x_profile":
        return 30.0
    return 28.0


def _decision(score: float) -> str:
    if score >= 78:
        return "accepted"
    if score >= 58:
        return "researching"
    if score >= 40:
        return "deferred"
    return "watchlist"


def _recommended_action(category: str) -> str:
    if category == "github_repo":
        return "Review repository and produce an adopt/adapt/reject memo with one reversible prototype task."
    if category == "academic_journal":
        return "Extract the core finding, verify methodology limits, and map one practical experiment to Ophtxn."
    if category in {"x_post", "x_profile"}:
        return "Capture the claim, find a primary source (repo/docs), and verify before integration."
    if category == "docs":
        return "Extract implementation steps and map to one low-risk integration ticket."
    if category == "strategy_article":
        return "Extract monetization model insights and map to one go-to-market experiment."
    if category == "video":
        return "Summarize actionable patterns and validate with a small experiment."
    return "Run a light validation pass and decide adopt/defer/reject with rationale."


def _score_candidate(candidate: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    url = str(candidate.get("url") or "")
    context = str(candidate.get("context") or "")
    source = str(candidate.get("source") or "manual")
    channel = str(candidate.get("channel") or "manual")
    entry_id = str(candidate.get("entry_id") or "unknown")
    parsed = urlparse(url)
    host = (parsed.netloc or "").lower()
    text = f"{url} {context}".lower()
    category = _classify_url(url)
    score = _category_base_score(category)

    domain_bonuses = policy.get("domain_bonuses") if isinstance(policy.get("domain_bonuses"), dict) else {}
    for domain, bonus_raw in domain_bonuses.items():
        token = str(domain or "").strip().lower()
        if token and token in host:
            score += _safe_float(bonus_raw, 0.0)

    signals = policy.get("signal_weights") if isinstance(policy.get("signal_weights"), dict) else {}
    signal_hits: list[str] = []
    for token, weight_raw in signals.items():
        key = str(token or "").strip().lower()
        if not key:
            continue
        if key in text:
            signal_hits.append(key)
            score += _safe_float(weight_raw, 0.0)

    drop_tokens = [str(x).strip().lower() for x in (policy.get("drop_tokens") or []) if str(x).strip()]
    drop_hits = [token for token in drop_tokens if token in text]
    if drop_hits:
        score -= min(40.0, 12.0 + len(drop_hits) * 8.0)

    risk_high_tokens = [str(x).strip().lower() for x in (policy.get("risk_high_tokens") or []) if str(x).strip()]
    risk_tier = "LOW"
    if any(token in text for token in risk_high_tokens):
        risk_tier = "HIGH"
    elif category in {"x_post", "x_profile", "video"}:
        risk_tier = "MEDIUM"

    score = round(max(0.0, min(99.0, score)), 2)
    decision = _decision(score)
    title = url
    if category == "github_repo":
        chunks = [chunk for chunk in (parsed.path or "").split("/") if chunk]
        repo = "/".join(chunks[:2]) if len(chunks) >= 2 else url
        title = f"{repo} integration candidate"
    elif category in {"x_post", "x_profile"}:
        title = "X signal for review"
    elif category == "strategy_article":
        title = "Strategy signal for venture planning"

    return {
        "idea_id": "IDEA-" + _url_hash(url).upper(),
        "entry_id": entry_id,
        "source": source,
        "channel": channel,
        "url": url,
        "host": host,
        "category": category,
        "title": title[:180],
        "score": score,
        "priority": _priority_label(score),
        "risk_tier": risk_tier,
        "decision": decision,
        "recommended_action": _recommended_action(category),
        "signal_hits": signal_hits[:12],
        "drop_hits": drop_hits[:8],
        "context_excerpt": context[:280],
        "manual_approval_required": True,
    }


def _load_state(path: Path) -> dict[str, Any]:
    payload = _read_json(path, {})
    if not isinstance(payload, dict):
        payload = {}
    processed_ids = payload.get("processed_entry_ids")
    if not isinstance(processed_ids, list):
        processed_ids = []
    processed_hashes = payload.get("processed_url_hashes")
    if not isinstance(processed_hashes, list):
        processed_hashes = []
    return {
        "updated_at": str(payload.get("updated_at") or ""),
        "processed_entry_ids": [str(x) for x in processed_ids if str(x).strip()],
        "processed_url_hashes": [str(x) for x in processed_hashes if str(x).strip()],
    }


def _save_state(path: Path, entry_ids: set[str], url_hashes: set[str]) -> None:
    _write_json(
        path,
        {
            "updated_at": _now_iso(),
            "processed_entry_ids": sorted(entry_ids),
            "processed_url_hashes": sorted(url_hashes),
            "processed_entries_count": len(entry_ids),
            "processed_urls_count": len(url_hashes),
        },
    )


def _collect_candidates(
    entries: list[dict[str, Any]],
    processed_entry_ids: set[str],
    processed_url_hashes: set[str],
) -> tuple[list[dict[str, Any]], set[str], set[str]]:
    candidates: list[dict[str, Any]] = []
    new_entry_ids: set[str] = set(processed_entry_ids)
    new_url_hashes: set[str] = set(processed_url_hashes)
    for entry in entries:
        entry_id = _entry_id(entry)
        if entry_id in processed_entry_ids:
            continue
        source = str(entry.get("source") or "manual")
        channel = str(entry.get("channel") or "manual")
        text = str(entry.get("text") or "")
        urls: list[str] = []
        seen: set[str] = set()
        for token in entry.get("urls") if isinstance(entry.get("urls"), list) else []:
            normalized = _normalize_url(str(token or ""))
            if normalized and normalized not in seen:
                seen.add(normalized)
                urls.append(normalized)
        for token in _extract_urls(text):
            if token not in seen:
                seen.add(token)
                urls.append(token)

        for url in urls:
            digest = _url_hash(url)
            if digest in new_url_hashes:
                continue
            candidates.append(
                {
                    "entry_id": entry_id,
                    "source": source,
                    "channel": channel,
                    "url": url,
                    "context": text,
                }
            )
            new_url_hashes.add(digest)
        new_entry_ids.add(entry_id)
    return candidates, new_entry_ids, new_url_hashes


def _load_approvals(path: Path) -> list[dict[str, Any]]:
    payload = _read_json(path, [])
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict) and isinstance(payload.get("approvals"), list):
        return [row for row in payload.get("approvals", []) if isinstance(row, dict)]
    return []


def _save_approvals(path: Path, approvals: list[dict[str, Any]]) -> None:
    _write_json(path, approvals)


def _queue_approvals(
    ranked: list[dict[str, Any]],
    min_score: float,
    limit: int,
) -> tuple[int, int]:
    approvals = _load_approvals(APPROVALS_PATH)
    existing_ids: set[str] = set()
    for row in approvals:
        token = str(row.get("proposal_id") or row.get("id") or row.get("approval_id") or "").strip()
        if token:
            existing_ids.add(token)

    queued = 0
    skipped_existing = 0
    for row in ranked:
        if queued >= max(1, int(limit)):
            break
        score = _safe_float(row.get("score"), 0.0)
        if score < float(min_score):
            continue
        proposal_id = str(row.get("idea_id") or "").strip() or "IDEA-" + _url_hash(str(row.get("url") or "")).upper()
        if proposal_id in existing_ids:
            skipped_existing += 1
            continue
        now = _now_iso()
        queue_item = {
            "proposal_id": proposal_id,
            "id": proposal_id,
            "approval_id": proposal_id,
            "title": str(row.get("title") or "Idea candidate"),
            "finding_summary": (
                f"{row.get('category')} signal scored {row.get('score')} from "
                f"{row.get('source')}:{row.get('channel')}"
            ),
            "current_state": "Idea queued from user link intake for governed review.",
            "proposed_change": str(row.get("recommended_action") or "Review and scope a safe prototype."),
            "expected_benefit": "Potential high-leverage feature or strategy upgrade from fresh external signal.",
            "risk_if_ignored": "High-quality ideas may decay before evaluation.",
            "implementation_scope": "research_intelligence",
            "draft_canon_amendment": None,
            "draft_codex_task": (
                f"Review {row.get('url')} and produce adopt/adapt/reject recommendation with one reversible next step."
            ),
            "source_findings": [str(row.get("url") or ""), str(row.get("entry_id") or "")],
            "priority": str(row.get("priority") or "MEDIUM"),
            "status": "PENDING_HUMAN_REVIEW",
            "created_at": now,
            "queued_at": now,
            "source": "idea_intake_queue",
            "source_report_id": str(row.get("idea_id") or proposal_id),
            "manual_approval_required": True,
            "idea_score": score,
            "risk_tier": str(row.get("risk_tier") or "MEDIUM"),
        }
        queue_item["proposal_fingerprint"] = hashlib.sha1(
            json.dumps(queue_item, sort_keys=True).encode("utf-8")
        ).hexdigest()[:16]
        approvals.append(queue_item)
        existing_ids.add(proposal_id)
        queued += 1

    if queued > 0:
        _save_approvals(APPROVALS_PATH, approvals)
    return queued, skipped_existing


def _write_outputs(
    *,
    action: str,
    ranked: list[dict[str, Any]],
    policy: dict[str, Any],
    policy_status: str,
    intake_path: Path,
    state_path: Path,
    queued_approvals: int,
    skipped_existing: int,
    warnings: list[str],
    processed_entries: int,
    new_urls: int,
) -> tuple[Path, Path]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    TOOL_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _now().strftime("%Y%m%d-%H%M%S")
    md_path = OUTPUT_DIR / f"idea_intake_{stamp}.md"
    latest_md = OUTPUT_DIR / "idea_intake_latest.md"
    json_path = TOOL_DIR / f"idea_intake_{stamp}.json"
    lines = [
        "# Idea Intake",
        "",
        f"Generated (UTC): {_now_iso()}",
        f"Action: {action}",
        f"Intake path: {intake_path}",
        f"State path: {state_path}",
        f"Policy: {POLICY_PATH} ({policy_status})",
        "",
        "## Summary",
        f"- Ranked ideas: {len(ranked)}",
        f"- Entries processed: {processed_entries}",
        f"- New URLs scored: {new_urls}",
        f"- Queued approvals: {queued_approvals}",
        f"- Skipped existing approvals: {skipped_existing}",
        "",
        "## Top Ideas",
    ]
    if not ranked:
        lines.append("- No idea candidates met thresholds.")
    for idx, row in enumerate(ranked, start=1):
        lines.extend(
            [
                f"{idx}. {row.get('title')} [{row.get('decision')}]",
                (
                    "   - "
                    f"score={row.get('score')} | priority={row.get('priority')} | risk={row.get('risk_tier')} | "
                    f"category={row.get('category')}"
                ),
                f"   - url={row.get('url')}",
                f"   - action={row.get('recommended_action')}",
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
            "- This pipeline is advisory and does not auto-implement ideas.",
            "- Approval queue entries require explicit human decisions before execution.",
            "",
        ]
    )

    payload = {
        "generated_at": _now_iso(),
        "action": action,
        "intake_path": str(intake_path),
        "state_path": str(state_path),
        "policy_path": str(POLICY_PATH),
        "policy_status": policy_status,
        "policy": policy,
        "item_count": len(ranked),
        "top_items": ranked,
        "queued_approvals": queued_approvals,
        "skipped_existing_approvals": skipped_existing,
        "processed_entries": processed_entries,
        "new_urls": new_urls,
        "warnings": warnings,
        "latest_markdown": str(latest_md),
    }
    report = "\n".join(lines) + "\n"
    md_path.write_text(report, encoding="utf-8")
    latest_md.write_text(report, encoding="utf-8")
    json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return md_path, json_path


def _status(intake_path: Path, state_path: Path) -> dict[str, Any]:
    entries = _load_jsonl(intake_path)
    state = _load_state(state_path)
    processed_entry_ids = set(state["processed_entry_ids"])
    processed_hashes = set(state["processed_url_hashes"])
    pending_entries = 0
    pending_urls: set[str] = set()
    for entry in entries:
        entry_id = _entry_id(entry)
        if entry_id in processed_entry_ids:
            continue
        pending_entries += 1
        text = str(entry.get("text") or "")
        urls = []
        if isinstance(entry.get("urls"), list):
            urls.extend([_normalize_url(str(x or "")) for x in entry.get("urls", [])])
        urls.extend(_extract_urls(text))
        for url in urls:
            if not url:
                continue
            digest = _url_hash(url)
            if digest in processed_hashes:
                continue
            pending_urls.add(url)
    return {
        "entries_total": len(entries),
        "entries_pending": pending_entries,
        "urls_pending": len(pending_urls),
        "intake_path": str(intake_path),
        "state_path": str(state_path),
    }


def _intake(text: str, source: str, channel: str, intake_path: Path) -> dict[str, Any]:
    created_at = _now_iso()
    payload = {
        "intake_id": "INT-" + hashlib.sha1(f"{created_at}|{source}|{channel}|{text}".encode("utf-8")).hexdigest()[:12].upper(),
        "created_at": created_at,
        "source": str(source or "manual"),
        "channel": str(channel or "manual"),
        "text": str(text or "").strip(),
        "urls": _extract_urls(text),
    }
    _append_jsonl(intake_path, payload)
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Process idea links from intake into ranked queues.")
    parser.add_argument("--action", choices=["status", "process", "intake"], default="status")
    parser.add_argument("--text", help="Text payload for --action intake")
    parser.add_argument("--source", default="manual", help="Source label for --action intake")
    parser.add_argument("--channel", default="manual", help="Channel label for --action intake")
    parser.add_argument("--intake-path", help="Intake JSONL path")
    parser.add_argument("--state-path", help="State JSON path")
    parser.add_argument("--policy-path", help="Policy JSON path")
    parser.add_argument("--max-items", type=int, help="Max ranked ideas to keep")
    parser.add_argument("--min-score", type=float, help="Minimum idea score to keep")
    parser.add_argument("--queue-approvals", action="store_true", help="Queue top scored ideas into approvals")
    parser.add_argument("--queue-limit", type=int, help="Max ideas to queue as approvals")
    parser.add_argument("--queue-min-score", type=float, help="Min score for queued approvals")
    parser.add_argument("--force-policy", action="store_true", help="Rewrite policy template")
    parser.add_argument("--strict", action="store_true", help="Return non-zero when warnings are present")
    args = parser.parse_args(argv)

    intake_path = Path(args.intake_path).expanduser() if args.intake_path else INTAKE_PATH
    state_path = Path(args.state_path).expanduser() if args.state_path else STATE_PATH
    policy_path = Path(args.policy_path).expanduser() if args.policy_path else POLICY_PATH

    if args.action == "intake":
        text = str(args.text or "").strip()
        if not text:
            print("Missing --text for --action intake")
            return 2
        payload = _intake(text=text, source=args.source, channel=args.channel, intake_path=intake_path)
        print(f"Idea intake saved: {payload['intake_id']} (urls={len(payload.get('urls') or [])})")
        return 0

    if args.action == "status":
        stat = _status(intake_path=intake_path, state_path=state_path)
        print(
            "Idea intake status: "
            f"total={stat['entries_total']} pending_entries={stat['entries_pending']} pending_urls={stat['urls_pending']}"
        )
        return 0

    policy, policy_status = _ensure_policy(policy_path, force_template=bool(args.force_policy))
    state = _load_state(state_path)
    processed_entry_ids = set(str(x) for x in state["processed_entry_ids"])
    processed_url_hashes = set(str(x) for x in state["processed_url_hashes"])
    entries = _load_jsonl(intake_path)

    candidates, new_entry_ids, new_url_hashes = _collect_candidates(
        entries=entries,
        processed_entry_ids=processed_entry_ids,
        processed_url_hashes=processed_url_hashes,
    )
    scored = [_score_candidate(row, policy=policy) for row in candidates]
    min_score = _safe_float(args.min_score, _safe_float(policy.get("min_score_keep"), 28.0))
    max_items = max(1, _safe_int(args.max_items, _safe_int(policy.get("max_items"), MAX_ITEMS_DEFAULT)))
    ranked = [row for row in scored if _safe_float(row.get("score"), 0.0) >= min_score]
    ranked.sort(key=lambda row: _safe_float(row.get("score"), 0.0), reverse=True)
    ranked = ranked[:max_items]

    _save_state(state_path, entry_ids=new_entry_ids, url_hashes=new_url_hashes)
    queue_min_score = _safe_float(args.queue_min_score, _safe_float(policy.get("queue_min_score"), QUEUE_MIN_SCORE_DEFAULT))
    queue_limit = max(1, _safe_int(args.queue_limit, _safe_int(policy.get("queue_limit"), QUEUE_LIMIT_DEFAULT)))
    queued_approvals = 0
    skipped_existing = 0
    if bool(args.queue_approvals):
        queued_approvals, skipped_existing = _queue_approvals(
            ranked=ranked,
            min_score=queue_min_score,
            limit=queue_limit,
        )

    warnings: list[str] = []
    if not intake_path.exists():
        warnings.append(f"Intake path missing: {intake_path}")
    if not candidates:
        warnings.append("No new URLs found in unprocessed intake entries.")

    md_path, json_path = _write_outputs(
        action="process",
        ranked=ranked,
        policy=policy,
        policy_status=policy_status,
        intake_path=intake_path,
        state_path=state_path,
        queued_approvals=queued_approvals,
        skipped_existing=skipped_existing,
        warnings=warnings,
        processed_entries=max(0, len(new_entry_ids) - len(processed_entry_ids)),
        new_urls=len(candidates),
    )
    print(f"Idea intake report: {md_path}")
    print(f"Idea intake latest: {OUTPUT_DIR / 'idea_intake_latest.md'}")
    print(f"Tool payload: {json_path}")
    print(f"Ranked ideas: {len(ranked)}")
    print(f"Queued approvals: {queued_approvals}")
    if warnings:
        print(f"Warnings: {len(warnings)}")
    return 1 if (args.strict and warnings) else 0


if __name__ == "__main__":
    raise SystemExit(main())
