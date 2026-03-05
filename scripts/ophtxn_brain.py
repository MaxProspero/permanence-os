#!/usr/bin/env python3
"""
Build and query Ophtxn's persistent brain vault from system files.
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
BRAIN_PATH = Path(
    os.getenv("PERMANENCE_OPHTXN_BRAIN_PATH", str(WORKING_DIR / "ophtxn_brain_vault.json"))
)
SHARE_INTAKE_PATH = Path(
    os.getenv(
        "PERMANENCE_TELEGRAM_CONTROL_INTAKE_PATH",
        str(BASE_DIR / "memory" / "inbox" / "telegram_share_intake.jsonl"),
    )
)
TERMINAL_QUEUE_PATH = Path(
    os.getenv(
        "PERMANENCE_TELEGRAM_CONTROL_TERMINAL_QUEUE_PATH",
        os.getenv(
            "PERMANENCE_TERMINAL_TASK_QUEUE_PATH",
            str(WORKING_DIR / "telegram_terminal_tasks.jsonl"),
        ),
    )
)
WORD_RE = re.compile(r"[a-zA-Z][a-zA-Z0-9_-]{1,}")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now().isoformat()


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


def _file_mtime_iso(path: Path) -> str:
    try:
        return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()
    except OSError:
        return _now_iso()


def _safe_text(text: str, max_chars: int = 900) -> str:
    payload = " ".join(str(text or "").replace("\r", "\n").split())
    if not payload:
        return ""
    cap = max(120, int(max_chars))
    if len(payload) <= cap:
        return payload
    return payload[: cap - 3].rstrip() + "..."


def _tokenize(text: str) -> set[str]:
    out: set[str] = set()
    for token in WORD_RE.findall(str(text or "").lower()):
        if len(token) < 3:
            continue
        out.add(token)
    return out


def _chunk_text(text: str, max_chars: int = 680) -> list[str]:
    rows = [row.strip() for row in str(text or "").splitlines() if row.strip()]
    if not rows:
        return []
    chunks: list[str] = []
    current: list[str] = []
    current_size = 0
    cap = max(240, int(max_chars))
    for row in rows:
        piece = row
        size = len(piece) + 1
        if current and (current_size + size > cap):
            chunks.append(_safe_text("\n".join(current), max_chars=cap))
            current = [piece]
            current_size = len(piece)
        else:
            current.append(piece)
            current_size += size
    if current:
        chunks.append(_safe_text("\n".join(current), max_chars=cap))
    return [row for row in chunks if row]


def _brain_chunk_id(source: str, text: str) -> str:
    token = f"{source}|{text}"
    return "BRAIN-" + hashlib.sha1(token.encode("utf-8")).hexdigest()[:16].upper()


def _source_candidates() -> list[Path]:
    rows: list[Path] = []

    explicit = [
        BASE_DIR / "docs" / "ophtxn_personal_agent_roadmap.md",
        BASE_DIR / "docs" / "ophtxn_research_method_20260304.md",
        BASE_DIR / "docs" / "agent_specs.md",
        BASE_DIR / "docs" / "memory_system.md",
        BASE_DIR / "outputs" / "second_brain_report_latest.md",
        BASE_DIR / "outputs" / "self_improvement_latest.md",
        BASE_DIR / "outputs" / "governed_learning_latest.md",
        BASE_DIR / "outputs" / "social_research_ingest_latest.md",
        BASE_DIR / "outputs" / "external_access_policy_latest.md",
        BASE_DIR / "outputs" / "ophtxn_simulation_latest.md",
        WORKING_DIR / "telegram_control" / "personal_memory.json",
        WORKING_DIR / "telegram_control" / "chat_history.json",
        WORKING_DIR / "operator_constraints.json",
        WORKING_DIR / "social_research_feeds.json",
        SHARE_INTAKE_PATH,
        TERMINAL_QUEUE_PATH,
    ]
    for path in explicit:
        if path.exists():
            rows.append(path)

    docs_dir = BASE_DIR / "docs"
    if docs_dir.exists():
        for path in sorted(docs_dir.glob("*.md")):
            if path not in rows:
                rows.append(path)
    return rows


def _extract_from_markdown(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    return _chunk_text(text, max_chars=680)[:80]


def _extract_from_share_intake(path: Path) -> list[str]:
    rows: list[str] = []
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines()[-200:]:
        line = raw.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict):
            continue
        text = _safe_text(str(payload.get("text") or ""), max_chars=680)
        if not text:
            continue
        rows.append(text)
    return rows


def _extract_from_terminal_queue(path: Path) -> list[str]:
    rows: list[str] = []
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines()[-300:]:
        line = raw.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict):
            continue
        text = _safe_text(str(payload.get("text") or ""), max_chars=620)
        if not text:
            continue
        status = str(payload.get("status") or "PENDING").strip().upper()
        task_id = str(payload.get("task_id") or "").strip()
        source = str(payload.get("source") or "").strip()
        summary = f"terminal-task {task_id or '-'} [{status}] {text}"
        if source:
            summary = f"{summary} (source={source})"
        rows.append(_safe_text(summary, max_chars=680))
    return rows


def _extract_from_personal_memory(path: Path) -> list[str]:
    payload = _read_json(path, {})
    if not isinstance(payload, dict):
        return []
    profiles = payload.get("profiles")
    if not isinstance(profiles, dict):
        return []
    rows: list[str] = []
    for profile in profiles.values():
        if not isinstance(profile, dict):
            continue
        notes = profile.get("notes")
        if not isinstance(notes, list):
            continue
        for note in notes[-120:]:
            if not isinstance(note, dict):
                continue
            text = _safe_text(str(note.get("text") or ""), max_chars=680)
            if text:
                rows.append(text)
    return rows


def _extract_from_chat_history(path: Path) -> list[str]:
    payload = _read_json(path, {})
    if not isinstance(payload, dict):
        return []
    rows: list[str] = []
    for history in payload.values():
        if not isinstance(history, list):
            continue
        for row in history[-80:]:
            if not isinstance(row, dict):
                continue
            text = _safe_text(str(row.get("text") or ""), max_chars=680)
            role = str(row.get("role") or "").strip().lower()
            if not text:
                continue
            if role == "assistant":
                rows.append(f"assistant: {text}")
            else:
                rows.append(f"user: {text}")
    return rows


def _extract_from_json(path: Path) -> list[str]:
    payload = _read_json(path, {})
    text = _safe_text(json.dumps(payload, ensure_ascii=True), max_chars=6800)
    return _chunk_text(text, max_chars=680)[:80]


def _extract_chunks(path: Path) -> list[str]:
    name = path.name.lower()
    suffix = path.suffix.lower()
    if name == SHARE_INTAKE_PATH.name:
        return _extract_from_share_intake(path)
    if path == TERMINAL_QUEUE_PATH or name == "telegram_terminal_tasks.jsonl":
        return _extract_from_terminal_queue(path)
    if name == "personal_memory.json":
        return _extract_from_personal_memory(path)
    if name == "chat_history.json":
        return _extract_from_chat_history(path)
    if suffix == ".md":
        return _extract_from_markdown(path)
    if suffix == ".json":
        return _extract_from_json(path)
    text = path.read_text(encoding="utf-8", errors="ignore")
    return _chunk_text(text, max_chars=680)[:80]


def _build_sync_entries(sources: list[Path]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for path in sources:
        try:
            chunks = _extract_chunks(path)
        except OSError:
            continue
        mtime = _file_mtime_iso(path)
        try:
            source_rel = str(path.relative_to(BASE_DIR))
        except ValueError:
            source_rel = str(path)
        source_kind = "doc" if path.suffix.lower() == ".md" else "data"
        for idx, text in enumerate(chunks, start=1):
            if not text:
                continue
            out.append(
                {
                    "id": _brain_chunk_id(source_rel, text),
                    "source": source_rel,
                    "source_kind": source_kind,
                    "chunk_index": idx,
                    "text": text,
                    "tokens": sorted(_tokenize(text))[:80],
                    "source_updated_at": mtime,
                    "ingested_at": _now_iso(),
                }
            )
    return out


def _load_vault(path: Path) -> dict[str, Any]:
    payload = _read_json(path, {})
    if not isinstance(payload, dict):
        payload = {}
    chunks = payload.get("chunks")
    if not isinstance(chunks, list):
        chunks = []
    return {
        "version": str(payload.get("version") or "1.0"),
        "chunks": [row for row in chunks if isinstance(row, dict)],
        "updated_at": str(payload.get("updated_at") or ""),
        "sources_count": int(payload.get("sources_count") or 0),
    }


def _merge_vault(existing: dict[str, Any], fresh: list[dict[str, Any]], max_chunks: int = 5000) -> tuple[dict[str, Any], int]:
    by_id: dict[str, dict[str, Any]] = {}
    for row in existing.get("chunks", []):
        rid = str(row.get("id") or "").strip()
        if rid:
            by_id[rid] = row
    before = len(by_id)
    for row in fresh:
        rid = str(row.get("id") or "").strip()
        if not rid:
            continue
        by_id[rid] = row

    merged_rows = sorted(
        by_id.values(),
        key=lambda row: (
            str(row.get("source_updated_at") or ""),
            str(row.get("ingested_at") or ""),
        ),
        reverse=True,
    )
    cap = max(300, int(max_chunks))
    merged_rows = merged_rows[:cap]
    merged = {
        "version": "1.0",
        "chunks": merged_rows,
        "updated_at": _now_iso(),
        "sources_count": len({str(row.get("source") or "") for row in merged_rows if str(row.get("source") or "").strip()}),
    }
    added = max(0, len(by_id) - before)
    return merged, added


def _score_recall(row: dict[str, Any], query_tokens: set[str], query_text: str) -> float:
    text = str(row.get("text") or "").lower()
    source = str(row.get("source") or "").lower()
    tokens = row.get("tokens")
    token_set = {str(tok).lower() for tok in tokens} if isinstance(tokens, list) else _tokenize(text)
    overlap = len(query_tokens & token_set)
    score = float(overlap)
    if query_text and query_text in text:
        score += 3.0
    if query_text and query_text in source:
        score += 1.0
    if overlap > 0:
        score += min(2.0, overlap * 0.25)
    return score


def _recall(vault: dict[str, Any], query: str, limit: int = 8) -> list[dict[str, Any]]:
    query_text = " ".join(str(query or "").strip().lower().split())
    if not query_text:
        return []
    query_tokens = _tokenize(query_text)
    rows: list[dict[str, Any]] = []
    for row in vault.get("chunks", []):
        if not isinstance(row, dict):
            continue
        score = _score_recall(row, query_tokens=query_tokens, query_text=query_text)
        if score <= 0:
            continue
        item = dict(row)
        item["score"] = round(score, 3)
        rows.append(item)
    rows.sort(key=lambda row: float(row.get("score") or 0.0), reverse=True)
    cap = max(1, min(20, int(limit)))
    return rows[:cap]


def _write_report(
    *,
    action: str,
    vault_path: Path,
    source_count: int,
    chunk_count: int,
    added_chunks: int,
    query: str,
    recall_rows: list[dict[str, Any]],
    warnings: list[str],
) -> tuple[Path, Path]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    TOOL_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _now().strftime("%Y%m%d-%H%M%S")
    md_path = OUTPUT_DIR / f"ophtxn_brain_{stamp}.md"
    latest_md = OUTPUT_DIR / "ophtxn_brain_latest.md"
    json_path = TOOL_DIR / f"ophtxn_brain_{stamp}.json"

    lines = [
        "# Ophtxn Brain",
        "",
        f"Generated (UTC): {_now_iso()}",
        f"Action: {action}",
        f"Vault path: {vault_path}",
        "",
        "## Summary",
        f"- Source files scanned: {source_count}",
        f"- Total brain chunks: {chunk_count}",
        f"- New chunks added this run: {added_chunks}",
    ]
    if query:
        lines.append(f"- Recall query: {query}")
        lines.append(f"- Recall hits: {len(recall_rows)}")

    if recall_rows:
        lines.extend(["", "## Recall Results"])
        for idx, row in enumerate(recall_rows, start=1):
            snippet = _safe_text(str(row.get("text") or ""), max_chars=320)
            lines.append(
                f"{idx}. score={row.get('score')} | source={row.get('source')} | {snippet}"
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
        "vault_path": str(vault_path),
        "source_count": source_count,
        "chunk_count": chunk_count,
        "added_chunks": added_chunks,
        "query": query,
        "recall_count": len(recall_rows),
        "recall_rows": recall_rows,
        "warnings": warnings,
        "latest_markdown": str(latest_md),
    }
    _write_json(json_path, payload)
    return md_path, json_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Sync and query Ophtxn persistent brain vault.")
    parser.add_argument("--action", choices=["status", "sync", "recall"], default="status")
    parser.add_argument("--vault-path", help="Override vault json path")
    parser.add_argument("--query", help="Recall query for --action recall")
    parser.add_argument("--limit", type=int, default=8, help="Recall result limit")
    parser.add_argument("--max-chunks", type=int, default=5000, help="Max chunk rows retained in vault")
    args = parser.parse_args(argv)

    vault_path = Path(args.vault_path).expanduser() if args.vault_path else BRAIN_PATH
    warnings: list[str] = []
    source_count = 0
    added_chunks = 0
    recall_rows: list[dict[str, Any]] = []

    vault = _load_vault(vault_path)

    if args.action in {"sync", "recall"}:
        sources = _source_candidates()
        source_count = len(sources)
        fresh = _build_sync_entries(sources)
        vault, added_chunks = _merge_vault(vault, fresh, max_chunks=max(300, int(args.max_chunks)))
        _write_json(vault_path, vault)
        if not fresh:
            warnings.append("no source chunks extracted during sync")
    else:
        source_count = int(vault.get("sources_count") or 0)

    query = " ".join(str(args.query or "").split())
    if args.action == "recall":
        if not query:
            warnings.append("missing --query for recall action")
        else:
            recall_rows = _recall(vault, query=query, limit=max(1, int(args.limit)))
            if not recall_rows:
                warnings.append("no recall matches found")

    chunk_count = len(vault.get("chunks", []))
    md_path, json_path = _write_report(
        action=args.action,
        vault_path=vault_path,
        source_count=source_count,
        chunk_count=chunk_count,
        added_chunks=added_chunks,
        query=query,
        recall_rows=recall_rows,
        warnings=warnings,
    )

    print(f"Ophtxn brain report: {md_path}")
    print(f"Ophtxn brain latest: {OUTPUT_DIR / 'ophtxn_brain_latest.md'}")
    print(f"Tool payload: {json_path}")
    print(f"Brain chunks: {chunk_count}")
    if args.action in {"sync", "recall"}:
        print(f"Sources scanned: {source_count}")
        print(f"New chunks: {added_chunks}")
    if query:
        print(f"Recall hits: {len(recall_rows)}")
    if warnings:
        print(f"Warnings: {len(warnings)}")
    if args.action == "recall" and (not recall_rows):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
