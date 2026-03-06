#!/usr/bin/env python3
"""
Audit no-spend guardrails and recent model provider usage.
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parents[1]
OUTPUT_DIR = Path(os.getenv("PERMANENCE_OUTPUT_DIR", str(BASE_DIR / "outputs")))
TOOL_DIR = Path(os.getenv("PERMANENCE_TOOL_DIR", str(BASE_DIR / "memory" / "tool")))
ENV_PATH = BASE_DIR / ".env"
MODEL_CALLS_PATH = BASE_DIR / "logs" / "model_calls.jsonl"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now().isoformat().replace("+00:00", "Z")


def _is_true(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _load_env(path: Path) -> dict[str, str]:
    env = dict(os.environ)
    if not path.exists():
        return env
    for raw_line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key:
            continue
        value = value.strip()
        if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
            value = value[1:-1]
        env[key] = value
    return env


def _parse_caps(raw: str) -> dict[str, float]:
    caps = {"anthropic": 0.0, "openai": 0.0, "xai": 0.0, "ollama": 0.0}
    token = str(raw or "").strip()
    if not token:
        return caps
    for piece in token.split(","):
        item = piece.strip()
        if "=" not in item:
            continue
        key, value = item.split("=", 1)
        provider = key.strip().lower()
        if provider not in caps:
            continue
        caps[provider] = max(0.0, _safe_float(value, 0.0))
    return caps


def _parse_timestamp(value: str) -> datetime | None:
    token = str(value or "").strip()
    if not token:
        return None
    try:
        parsed = datetime.fromisoformat(token.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _infer_provider(model: str) -> str:
    token = str(model or "").strip().lower()
    if not token:
        return "unknown"
    if token.startswith("gpt") or "openai" in token:
        return "openai"
    if token.startswith("claude") or "anthropic" in token:
        return "anthropic"
    if token.startswith("grok") or token.startswith("xai"):
        return "xai"
    if ":" in token or token.startswith(("qwen", "llama", "mistral", "gemma", "deepseek", "phi")):
        return "ollama"
    return "unknown"


def _load_recent_model_calls(path: Path, lookback_hours: int, max_recent_calls: int) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    sampled = rows[-max(1, int(max_recent_calls)) :]
    start = _now() - timedelta(hours=max(1, int(lookback_hours)))
    out: list[dict[str, Any]] = []
    for line in sampled:
        token = line.strip()
        if not token:
            continue
        try:
            payload = json.loads(token)
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict):
            continue
        ts = _parse_timestamp(str(payload.get("timestamp") or ""))
        if ts is None or ts < start:
            continue
        model = str(payload.get("model") or payload.get("model_assigned") or "").strip()
        provider = _infer_provider(model)
        out.append(
            {
                "timestamp": ts.isoformat().replace("+00:00", "Z"),
                "provider": provider,
                "model": model,
                "task_type": str(payload.get("task_type") or "").strip(),
                "input_tokens": int(float(payload.get("input_tokens") or 0)),
                "output_tokens": int(float(payload.get("output_tokens") or 0)),
            }
        )
    return out


def _provider_mix(rows: list[dict[str, Any]]) -> list[tuple[str, int]]:
    counts: dict[str, int] = {}
    for row in rows:
        provider = str(row.get("provider") or "unknown").strip().lower() or "unknown"
        counts[provider] = counts.get(provider, 0) + 1
    return sorted(counts.items(), key=lambda item: item[1], reverse=True)


def _write_outputs(
    *,
    env_path: Path,
    calls_path: Path,
    lookback_hours: int,
    status: dict[str, Any],
    provider_mix: list[tuple[str, int]],
    recent_calls: list[dict[str, Any]],
    warnings: list[str],
    violations: list[str],
) -> tuple[Path, Path]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    TOOL_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _now().strftime("%Y%m%d-%H%M%S")
    md_path = OUTPUT_DIR / f"no_spend_audit_{stamp}.md"
    latest_md = OUTPUT_DIR / "no_spend_audit_latest.md"
    json_path = TOOL_DIR / f"no_spend_audit_{stamp}.json"

    lines = [
        "# No Spend Audit",
        "",
        f"Generated (UTC): {_now_iso()}",
        f"Env path: {env_path}",
        f"Calls log path: {calls_path}",
        f"Lookback hours: {max(1, int(lookback_hours))}",
        "",
        "## Guardrail Status",
        f"- No-spend mode: {status.get('no_spend_mode')}",
        f"- Low-cost mode: {status.get('low_cost_mode')}",
        f"- Active provider: {status.get('provider')}",
        f"- Provider caps raw: {status.get('caps_raw')}",
    ]
    caps = status.get("caps") if isinstance(status.get("caps"), dict) else {}
    lines.append(
        "- Parsed caps: "
        f"anthropic={caps.get('anthropic', 0.0):g}, "
        f"openai={caps.get('openai', 0.0):g}, "
        f"xai={caps.get('xai', 0.0):g}, "
        f"ollama={caps.get('ollama', 0.0):g}"
    )

    lines.extend(["", "## Recent Provider Mix"])
    if provider_mix:
        for provider, count in provider_mix:
            lines.append(f"- {provider}: {count}")
    else:
        lines.append("- No model call events found in lookback window.")

    lines.extend(["", "## Recent Calls (Head)"])
    head = recent_calls[:10]
    if not head:
        lines.append("- No recent calls.")
    for row in head:
        lines.append(
            f"- {row.get('timestamp')} provider={row.get('provider')} "
            f"model={row.get('model') or '-'} in={row.get('input_tokens')} out={row.get('output_tokens')}"
        )

    if warnings:
        lines.extend(["", "## Warnings"])
        for warning in warnings:
            lines.append(f"- {warning}")

    if violations:
        lines.extend(["", "## Violations"])
        for violation in violations:
            lines.append(f"- {violation}")

    lines.extend(
        [
            "",
            "## Notes",
            "- This audit is read-only and does not mutate providers, credentials, or balances.",
            "- Use `python cli.py low-cost-mode --action enable` to re-apply no-spend defaults quickly.",
            "",
        ]
    )

    markdown = "\n".join(lines)
    md_path.write_text(markdown + "\n", encoding="utf-8")
    latest_md.write_text(markdown + "\n", encoding="utf-8")

    payload = {
        "generated_at": _now_iso(),
        "env_path": str(env_path),
        "calls_log_path": str(calls_path),
        "lookback_hours": max(1, int(lookback_hours)),
        "status": status,
        "provider_mix": provider_mix,
        "recent_calls_head": head,
        "warnings": warnings,
        "violations": violations,
        "latest_markdown": str(latest_md),
    }
    json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return md_path, json_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit no-spend guardrails and recent provider usage.")
    parser.add_argument("--env-path", help="Override .env path")
    parser.add_argument("--calls-log", help="Override model_calls.jsonl path")
    parser.add_argument("--lookback-hours", type=int, default=24, help="Calls lookback window in hours")
    parser.add_argument("--max-recent-calls", type=int, default=200, help="Max rows sampled from model_calls tail")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero when violations are found")
    args = parser.parse_args(argv)

    env_path = Path(args.env_path).expanduser() if args.env_path else ENV_PATH
    calls_path = Path(args.calls_log).expanduser() if args.calls_log else MODEL_CALLS_PATH
    lookback_hours = max(1, int(args.lookback_hours))
    max_recent_calls = max(10, int(args.max_recent_calls))

    env = _load_env(env_path)
    provider = str(env.get("PERMANENCE_MODEL_PROVIDER", "anthropic")).strip().lower() or "anthropic"
    no_spend_mode = _is_true(env.get("PERMANENCE_NO_SPEND_MODE", "0"))
    low_cost_mode = _is_true(env.get("PERMANENCE_LOW_COST_MODE", "0"))
    caps_raw = str(env.get("PERMANENCE_MODEL_PROVIDER_CAPS_USD", "")).strip()
    caps = _parse_caps(caps_raw)

    recent_calls = _load_recent_model_calls(calls_path, lookback_hours=lookback_hours, max_recent_calls=max_recent_calls)
    provider_mix = _provider_mix(recent_calls)
    paid_calls = [row for row in recent_calls if str(row.get("provider") or "") in {"anthropic", "openai", "xai"}]

    warnings: list[str] = []
    violations: list[str] = []
    if not no_spend_mode:
        warnings.append("No-spend mode is disabled.")
    if no_spend_mode and provider != "ollama":
        violations.append(f"No-spend mode is enabled but active provider is `{provider}` (expected `ollama`).")
    if no_spend_mode:
        for paid_provider in ("anthropic", "openai", "xai"):
            if _safe_float(caps.get(paid_provider), 0.0) > 0:
                violations.append(f"No-spend mode is enabled but cap for `{paid_provider}` is > 0.")
    if no_spend_mode and paid_calls:
        violations.append(f"{len(paid_calls)} paid-provider model call(s) detected in lookback window.")

    status = {
        "no_spend_mode": no_spend_mode,
        "low_cost_mode": low_cost_mode,
        "provider": provider,
        "caps_raw": caps_raw or "-",
        "caps": caps,
        "recent_paid_calls": len(paid_calls),
        "recent_total_calls": len(recent_calls),
    }

    md_path, json_path = _write_outputs(
        env_path=env_path,
        calls_path=calls_path,
        lookback_hours=lookback_hours,
        status=status,
        provider_mix=provider_mix,
        recent_calls=recent_calls,
        warnings=warnings,
        violations=violations,
    )

    print(f"No-spend audit report: {md_path}")
    print(f"No-spend audit latest: {OUTPUT_DIR / 'no_spend_audit_latest.md'}")
    print(f"Tool payload: {json_path}")
    print(f"No-spend mode: {status.get('no_spend_mode')}")
    print(f"Provider: {status.get('provider')} | recent calls: {status.get('recent_total_calls')}")
    if violations:
        print(f"Violations: {len(violations)}")
    if args.strict and violations:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
