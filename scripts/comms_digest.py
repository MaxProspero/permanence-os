#!/usr/bin/env python3
"""
Build and optionally send a daily communication digest to Telegram.

Digest pulls from latest tool payloads:
- discord_telegram_relay
- telegram_control
- glasses_autopilot
- comms_status
- integration_readiness
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
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
HISTORY_PATH = Path(
    os.getenv(
        "PERMANENCE_COMMS_DIGEST_HISTORY_PATH",
        str(WORKING_DIR / "comms" / "digest_history.jsonl"),
    )
)


def _is_true(value: str) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now().isoformat()


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default
    return payload


def _latest_json(prefix: str, root: Path | None = None) -> Path | None:
    base = root or TOOL_DIR
    if not base.exists():
        return None
    rows = sorted(base.glob(f"{prefix}_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    return rows[0] if rows else None


def _load_component(prefix: str) -> dict[str, Any]:
    path = _latest_json(prefix)
    payload = _read_json(path, {}) if path else {}
    if not isinstance(payload, dict):
        payload = {}
    payload["_path"] = str(path) if path else ""
    return payload


def _collect_payload() -> dict[str, Any]:
    relay = _load_component("discord_telegram_relay")
    telegram = _load_component("telegram_control")
    glasses = _load_component("glasses_autopilot")
    comms = _load_component("comms_status")
    readiness = _load_component("integration_readiness")

    return {
        "generated_at": _now_iso(),
        "relay": relay,
        "telegram": telegram,
        "glasses": glasses,
        "comms": comms,
        "readiness": readiness,
    }


def _warnings(payload: dict[str, Any], max_items: int) -> list[str]:
    rows: list[str] = []
    relay_warnings = payload.get("relay", {}).get("warnings") if isinstance(payload.get("relay"), dict) else []
    if isinstance(relay_warnings, list):
        for item in relay_warnings:
            text = str(item or "").strip()
            if text:
                rows.append(f"relay: {text}")

    comms_warnings = payload.get("comms", {}).get("warnings") if isinstance(payload.get("comms"), dict) else []
    if isinstance(comms_warnings, list):
        for item in comms_warnings:
            text = str(item or "").strip()
            if text:
                rows.append(f"comms: {text}")

    if not rows:
        return []
    deduped: list[str] = []
    seen: set[str] = set()
    for row in rows:
        if row in seen:
            continue
        seen.add(row)
        deduped.append(row)
    return deduped[: max(0, int(max_items))]


def _component_value(payload: dict[str, Any], component: str, key: str, default: Any = 0) -> Any:
    node = payload.get(component) if isinstance(payload.get(component), dict) else {}
    value = node.get(key)
    return default if value is None else value


def _build_digest_text(payload: dict[str, Any], max_warnings: int = 8, include_paths: bool = False) -> str:
    relay_new = _component_value(payload, "relay", "new_messages", 0)
    relay_sent = _component_value(payload, "relay", "telegram_messages_sent", 0)

    tg_updates = _component_value(payload, "telegram", "updates_count", 0)
    tg_ingested = _component_value(payload, "telegram", "ingested_count", 0)

    glasses_imported = _component_value(payload, "glasses", "imported_count", 0)
    glasses_candidates = _component_value(payload, "glasses", "candidate_count", 0)

    launchd = payload.get("comms", {}).get("launchd") if isinstance(payload.get("comms"), dict) else {}
    launchd_state = str(launchd.get("state") or "unknown")
    launchd_runs = int(launchd.get("runs") or 0)
    launchd_exit = launchd.get("last_exit_code")

    readiness = payload.get("readiness") if isinstance(payload.get("readiness"), dict) else {}
    readiness_blocked = bool(readiness.get("blocked"))

    lines = [
        f"Comms Digest ({payload.get('generated_at', _now_iso())})",
        "",
        "Automation:",
        f"- comms loop state: {launchd_state}",
        f"- comms loop runs: {launchd_runs}",
        f"- comms loop last exit: {launchd_exit}",
        "",
        "Flow metrics:",
        f"- discord -> telegram: new={relay_new}, sent={relay_sent}",
        f"- telegram control: updates={tg_updates}, ingested={tg_ingested}",
        f"- glasses autopilot: imported={glasses_imported}, scanned={glasses_candidates}",
        f"- integration readiness blocked: {readiness_blocked}",
    ]

    warning_rows = _warnings(payload, max_items=max_warnings)
    lines.append("")
    lines.append("Warnings:")
    if warning_rows:
        for row in warning_rows:
            lines.append(f"- {row}")
    else:
        lines.append("- none")

    if include_paths:
        lines.append("")
        lines.append("Latest payload paths:")
        for key in ("relay", "telegram", "glasses", "comms", "readiness"):
            path = ""
            node = payload.get(key)
            if isinstance(node, dict):
                path = str(node.get("_path") or "")
            lines.append(f"- {key}: {path or '-'}")

    return "\n".join(lines).strip() + "\n"


def _split_chunks(text: str, max_chars: int = 3500) -> list[str]:
    if len(text) <= max_chars:
        return [text]
    chunks: list[str] = []
    current: list[str] = []
    size = 0
    for line in text.splitlines():
        line_len = len(line) + 1
        if current and size + line_len > max_chars:
            chunks.append("\n".join(current).strip() + "\n")
            current = [line]
            size = line_len
        else:
            current.append(line)
            size += line_len
    if current:
        chunks.append("\n".join(current).strip() + "\n")
    return chunks


def _telegram_api(token: str, method: str, params: dict[str, Any], timeout: int = 20) -> dict[str, Any]:
    url = f"https://api.telegram.org/bot{token}/{method}"
    cmd = ["curl", "-sS", "--max-time", str(max(1, int(timeout))), url]
    for key, value in params.items():
        cmd.extend(["--data-urlencode", f"{key}={value}"])
    proc = subprocess.run(cmd, check=False, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or f"curl exited {proc.returncode}")
    try:
        payload = json.loads(proc.stdout or "{}")
    except json.JSONDecodeError as exc:  # noqa: PERF203
        raise RuntimeError(f"Invalid JSON from Telegram API: {exc}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("Unexpected Telegram API payload")
    return payload


def _send_telegram(token: str, chat_id: str, text: str, timeout: int = 20) -> int:
    sent = 0
    chunks = _split_chunks(text)
    for idx, chunk in enumerate(chunks, start=1):
        prefix = f"[{idx}/{len(chunks)}]\n" if len(chunks) > 1 else ""
        payload = _telegram_api(
            token=token,
            method="sendMessage",
            params={"chat_id": chat_id, "text": prefix + chunk},
            timeout=timeout,
        )
        if not bool(payload.get("ok")):
            raise RuntimeError(f"Telegram sendMessage returned ok=false at chunk {idx}")
        sent += 1
    return sent


def _append_history(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=True) + "\n")


def _write_outputs(payload: dict[str, Any], digest_text: str, sent_count: int) -> tuple[Path, Path]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    TOOL_DIR.mkdir(parents=True, exist_ok=True)

    stamp = _now().strftime("%Y%m%d-%H%M%S")
    md_path = OUTPUT_DIR / f"comms_digest_{stamp}.md"
    latest_md = OUTPUT_DIR / "comms_digest_latest.md"
    json_path = TOOL_DIR / f"comms_digest_{stamp}.json"

    md_path.write_text(digest_text, encoding="utf-8")
    latest_md.write_text(digest_text, encoding="utf-8")

    record = {
        "generated_at": payload.get("generated_at"),
        "sent_count": sent_count,
        "relay_new": payload.get("relay", {}).get("new_messages") if isinstance(payload.get("relay"), dict) else None,
        "telegram_updates": payload.get("telegram", {}).get("updates_count") if isinstance(payload.get("telegram"), dict) else None,
        "glasses_imported": payload.get("glasses", {}).get("imported_count") if isinstance(payload.get("glasses"), dict) else None,
        "latest_markdown": str(latest_md),
    }
    json_path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    return md_path, json_path


def main(argv: list[str] | None = None) -> int:
    max_warnings_default = int(os.getenv("PERMANENCE_COMMS_DIGEST_MAX_WARNINGS", "8"))
    parser = argparse.ArgumentParser(description="Build/send comms digest")
    parser.add_argument("--send", action="store_true", help="Send digest to Telegram")
    parser.add_argument("--chat-id", help="Override Telegram chat id")
    parser.add_argument("--timeout", type=int, default=20, help="Network timeout seconds")
    parser.add_argument("--max-warnings", type=int, default=max_warnings_default, help="Max warning lines in digest")
    parser.add_argument("--include-paths", action="store_true", help="Include local payload paths in digest")
    parser.add_argument("--dry-run", action="store_true", help="Build digest only")
    parser.add_argument("--no-history", action="store_true", help="Skip history append")
    parser.add_argument("--history-path", help="Digest history JSONL path")
    args = parser.parse_args(argv)

    payload = _collect_payload()
    digest_text = _build_digest_text(
        payload=payload,
        max_warnings=max(0, int(args.max_warnings)),
        include_paths=bool(args.include_paths),
    )

    send_default = _is_true(str(os.getenv("PERMANENCE_COMMS_DIGEST_SEND_DEFAULT", "0")))
    do_send = bool(args.send or send_default)

    sent_count = 0
    warnings: list[str] = []
    if do_send and not args.dry_run:
        token = str(os.getenv("PERMANENCE_TELEGRAM_BOT_TOKEN", "")).strip()
        chat_id = str(args.chat_id or os.getenv("PERMANENCE_TELEGRAM_CHAT_ID", "")).strip()
        if not token:
            warnings.append("missing PERMANENCE_TELEGRAM_BOT_TOKEN")
        elif not chat_id:
            warnings.append("missing --chat-id and PERMANENCE_TELEGRAM_CHAT_ID")
        else:
            try:
                sent_count = _send_telegram(token=token, chat_id=chat_id, text=digest_text, timeout=max(1, int(args.timeout)))
            except Exception as exc:  # noqa: BLE001
                warnings.append(f"telegram send failed: {exc}")

    md_path, json_path = _write_outputs(payload=payload, digest_text=digest_text, sent_count=sent_count)

    history_path = Path(args.history_path).expanduser() if args.history_path else HISTORY_PATH
    if not args.no_history:
        _append_history(
            history_path,
            {
                "generated_at": payload.get("generated_at"),
                "sent_count": sent_count,
                "warnings": warnings,
                "markdown": str(md_path),
            },
        )

    print(f"Comms digest written: {md_path}")
    print(f"Comms digest latest: {OUTPUT_DIR / 'comms_digest_latest.md'}")
    print(f"Tool payload written: {json_path}")
    print(f"Telegram messages sent: {sent_count}")
    if warnings:
        print(f"Warnings: {len(warnings)}")

    return 0 if not warnings else 1


if __name__ == "__main__":
    raise SystemExit(main())
