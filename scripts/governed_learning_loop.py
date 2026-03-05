#!/usr/bin/env python3
"""
Run a governed continuous-learning loop for Ophtxn.

This loop is read-only by design and requires explicit approval by default.
"""

from __future__ import annotations

import argparse
import json
import os
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
POLICY_PATH = Path(
    os.getenv("PERMANENCE_GOVERNED_LEARNING_POLICY_PATH", str(WORKING_DIR / "governed_learning_policy.json"))
)
STATE_PATH = Path(
    os.getenv("PERMANENCE_GOVERNED_LEARNING_STATE_PATH", str(WORKING_DIR / "governed_learning_state.json"))
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now().isoformat()


def _today_key() -> str:
    return _now().strftime("%Y-%m-%d")


def _is_true(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


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


def _default_policy() -> dict[str, Any]:
    return {
        "version": "1.0",
        "enabled": False,
        "require_explicit_approval": True,
        "approval_note_required": False,
        "max_runs_per_day": 4,
        "block_when_external_write_enabled": True,
        "topics": {
            "ai": ["ai", "agent", "automation", "llm", "model", "mcp"],
            "finance": ["finance", "market", "macro", "equity", "crypto", "forex"],
            "excel": ["excel", "spreadsheet", "formula", "dashboard", "analysis"],
            "media": ["youtube", "podcast", "shorts", "creator", "content", "distribution"],
        },
        "pipelines": {
            "openclaw_health": {"enabled": True},
            "social_research": {"enabled": True},
            "github_trending": {"enabled": True, "since": "daily"},
            "ecosystem_research": {"enabled": True},
            "world_watch": {"enabled": True},
            "market_focus_brief": {"enabled": True},
        },
        "updated_at": _now_iso(),
    }


def _default_state() -> dict[str, Any]:
    return {
        "runs_by_day": {},
        "last_run_at": "",
        "last_approved_by": "",
        "last_status": "never_run",
        "last_report_path": "",
        "updated_at": _now_iso(),
    }


def _ensure_policy(path: Path, force_template: bool = False) -> tuple[dict[str, Any], str]:
    defaults = _default_policy()
    if force_template or (not path.exists()):
        payload = dict(defaults)
        payload["updated_at"] = _now_iso()
        _write_json(path, payload)
        return payload, "written"
    payload = _read_json(path, {})
    if not isinstance(payload, dict):
        payload = {}
    merged: dict[str, Any] = dict(defaults)
    merged.update(payload)
    if not isinstance(merged.get("topics"), dict):
        merged["topics"] = dict(defaults["topics"])
    if not isinstance(merged.get("pipelines"), dict):
        merged["pipelines"] = dict(defaults["pipelines"])
    for key, default_cfg in defaults["pipelines"].items():
        cfg = merged["pipelines"].get(key)
        if not isinstance(cfg, dict):
            merged["pipelines"][key] = dict(default_cfg)
            continue
        merged_cfg = dict(default_cfg)
        merged_cfg.update(cfg)
        merged["pipelines"][key] = merged_cfg
    if merged != payload:
        merged["updated_at"] = _now_iso()
        _write_json(path, merged)
        return merged, "updated"
    return merged, "existing"


def _ensure_state(path: Path) -> dict[str, Any]:
    defaults = _default_state()
    payload = _read_json(path, {})
    if not isinstance(payload, dict):
        payload = {}
    merged = dict(defaults)
    merged.update(payload)
    if not isinstance(merged.get("runs_by_day"), dict):
        merged["runs_by_day"] = {}
    return merged


def _topic_keywords(policy: dict[str, Any]) -> list[str]:
    topics = policy.get("topics")
    if not isinstance(topics, dict):
        return []
    seen: set[str] = set()
    out: list[str] = []
    for rows in topics.values():
        if not isinstance(rows, list):
            continue
        for token in rows:
            word = str(token or "").strip().lower()
            if not word or word in seen:
                continue
            seen.add(word)
            out.append(word)
    return out


def _compact_text(text: str, max_lines: int = 8, max_chars: int = 900) -> str:
    rows = [row.strip() for row in str(text or "").splitlines() if row.strip()]
    if not rows:
        return "-"
    clipped = rows[: max(1, int(max_lines))]
    payload = "\n".join(clipped).strip()
    if len(payload) > max(120, int(max_chars)):
        payload = payload[: max(120, int(max_chars)) - 3].rstrip() + "..."
    return payload


def _pipeline_commands(policy: dict[str, Any], skip: set[str]) -> list[dict[str, Any]]:
    pipelines = policy.get("pipelines")
    cfg = pipelines if isinstance(pipelines, dict) else {}

    def enabled(name: str) -> bool:
        row = cfg.get(name)
        if not isinstance(row, dict):
            return False
        return bool(row.get("enabled"))

    commands: list[dict[str, Any]] = []
    if enabled("openclaw_health") and "openclaw_health" not in skip:
        commands.append(
            {
                "name": "openclaw_health",
                "argv": [sys.executable, str(BASE_DIR / "cli.py"), "openclaw-sync", "--once"],
            }
        )
    if enabled("social_research") and "social_research" not in skip:
        commands.append(
            {
                "name": "social_research",
                "argv": [sys.executable, str(BASE_DIR / "cli.py"), "social-research-ingest"],
            }
        )
    if enabled("github_trending") and "github_trending" not in skip:
        since = str(((cfg.get("github_trending") or {}).get("since") or "daily")).strip().lower()
        if since not in {"daily", "weekly", "monthly"}:
            since = "daily"
        commands.append(
            {
                "name": "github_trending",
                "argv": [sys.executable, str(BASE_DIR / "cli.py"), "github-trending-ingest", "--since", since],
            }
        )
    if enabled("ecosystem_research") and "ecosystem_research" not in skip:
        commands.append(
            {
                "name": "ecosystem_research",
                "argv": [sys.executable, str(BASE_DIR / "cli.py"), "ecosystem-research-ingest"],
            }
        )
    if enabled("world_watch") and "world_watch" not in skip:
        commands.append(
            {
                "name": "world_watch",
                "argv": [sys.executable, str(BASE_DIR / "cli.py"), "world-watch"],
            }
        )
    if enabled("market_focus_brief") and "market_focus_brief" not in skip:
        commands.append(
            {
                "name": "market_focus_brief",
                "argv": [sys.executable, str(BASE_DIR / "cli.py"), "market-focus-brief"],
            }
        )
    return commands


def _execute_pipeline(argv: list[str], timeout: int, env: dict[str, str]) -> dict[str, Any]:
    proc = subprocess.run(
        argv,
        check=False,
        capture_output=True,
        text=True,
        cwd=str(BASE_DIR),
        timeout=max(10, int(timeout)),
        env=env,
    )
    return {
        "ok": proc.returncode == 0,
        "returncode": int(proc.returncode),
        "stdout": _compact_text(proc.stdout or ""),
        "stderr": _compact_text(proc.stderr or ""),
    }


def _policy_block_reasons(
    policy: dict[str, Any],
    state: dict[str, Any],
    approved_by: str,
    approval_note: str,
    force: bool,
) -> list[str]:
    reasons: list[str] = []
    if not bool(policy.get("enabled")):
        reasons.append("policy disabled: set `enabled=true` in governed_learning_policy.json")
    if bool(policy.get("block_when_external_write_enabled")) and _is_true(
        os.getenv("PERMANENCE_AGENT_EXTERNAL_WRITE_ENABLE", "0")
    ):
        reasons.append("blocked: PERMANENCE_AGENT_EXTERNAL_WRITE_ENABLE is enabled")
    if bool(policy.get("require_explicit_approval")) and not str(approved_by or "").strip():
        reasons.append("missing approval: provide --approved-by")
    if bool(policy.get("approval_note_required")) and not str(approval_note or "").strip():
        reasons.append("missing approval note: provide --approval-note")
    max_runs = max(1, _safe_int(policy.get("max_runs_per_day"), 4))
    runs_by_day = state.get("runs_by_day") if isinstance(state.get("runs_by_day"), dict) else {}
    today_runs = _safe_int(runs_by_day.get(_today_key()), 0)
    if (not force) and today_runs >= max_runs:
        reasons.append(
            f"daily cap reached: {today_runs}/{max_runs} runs today (use --force to override)"
        )
    return reasons


def _write_report(
    *,
    action: str,
    policy_path: Path,
    state_path: Path,
    policy_status: str,
    policy: dict[str, Any],
    state: dict[str, Any],
    approved_by: str,
    approval_note: str,
    skip: set[str],
    block_reasons: list[str],
    runs: list[dict[str, Any]],
    dry_run: bool,
) -> tuple[Path, Path]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    TOOL_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _now().strftime("%Y%m%d-%H%M%S")
    md_path = OUTPUT_DIR / f"governed_learning_{stamp}.md"
    latest_md = OUTPUT_DIR / "governed_learning_latest.md"
    json_path = TOOL_DIR / f"governed_learning_{stamp}.json"

    executed_rows = [row for row in runs if _safe_int(row.get("returncode"), -1) != -1]
    skipped_count = len(runs) - len(executed_rows)
    success_count = sum(1 for row in executed_rows if bool(row.get("ok")))
    failed_count = len(executed_rows) - success_count
    keywords = _topic_keywords(policy)
    max_runs = max(1, _safe_int(policy.get("max_runs_per_day"), 4))
    runs_by_day = state.get("runs_by_day") if isinstance(state.get("runs_by_day"), dict) else {}
    today_runs = _safe_int(runs_by_day.get(_today_key()), 0)

    lines = [
        "# Governed Learning",
        "",
        f"Generated (UTC): {_now_iso()}",
        f"Action: {action}",
        f"Policy path: {policy_path}",
        f"State path: {state_path}",
        f"Policy status: {policy_status}",
        "",
        "## Governance",
        f"- Policy enabled: {bool(policy.get('enabled'))}",
        f"- Requires explicit approval: {bool(policy.get('require_explicit_approval'))}",
        f"- Approval actor: {approved_by or '-'}",
        f"- Approval note: {approval_note or '-'}",
        f"- External write block: {bool(policy.get('block_when_external_write_enabled'))}",
        f"- Daily run limit: {today_runs}/{max_runs}",
        f"- Dry run: {bool(dry_run)}",
        "",
        "## Learning Scope",
        f"- Topic keywords: {', '.join(keywords) if keywords else '-'}",
        f"- Skipped pipelines: {', '.join(sorted(skip)) if skip else '-'}",
        "",
        "## Execution Summary",
        f"- Pipelines attempted: {len(executed_rows)}",
        f"- Pipelines skipped: {skipped_count}",
        f"- Pipelines succeeded: {success_count}",
        f"- Pipelines failed: {failed_count}",
    ]

    if block_reasons:
        lines.extend(["", "## Blocked"])
        for item in block_reasons:
            lines.append(f"- {item}")

    if runs:
        lines.extend(["", "## Pipeline Runs"])
        for row in runs:
            lines.append(
                f"- {row.get('name')}: {'ok' if row.get('ok') else 'failed'} | rc={row.get('returncode')}\n"
                f"  stdout={row.get('stdout')}\n"
                f"  stderr={row.get('stderr')}"
            )

    report = "\n".join(lines) + "\n"
    md_path.write_text(report, encoding="utf-8")
    latest_md.write_text(report, encoding="utf-8")

    payload = {
        "generated_at": _now_iso(),
        "action": action,
        "policy_path": str(policy_path),
        "state_path": str(state_path),
        "policy_status": policy_status,
        "policy_enabled": bool(policy.get("enabled")),
        "required_approval": bool(policy.get("require_explicit_approval")),
        "approved_by": approved_by,
        "approval_note": approval_note,
        "topic_keywords": keywords,
        "skip": sorted(skip),
        "dry_run": bool(dry_run),
        "block_reasons": block_reasons,
        "runs": runs,
        "success_count": success_count,
        "failed_count": failed_count,
        "skipped_count": skipped_count,
        "latest_markdown": str(latest_md),
    }
    _write_json(json_path, payload)
    return md_path, json_path


def _update_state_after_run(state: dict[str, Any], approved_by: str, status: str, report_path: Path) -> dict[str, Any]:
    out = dict(state)
    runs_by_day = out.get("runs_by_day")
    if not isinstance(runs_by_day, dict):
        runs_by_day = {}
    today = _today_key()
    runs_by_day[today] = _safe_int(runs_by_day.get(today), 0) + 1
    out["runs_by_day"] = runs_by_day
    out["last_run_at"] = _now_iso()
    out["last_approved_by"] = str(approved_by or "").strip()
    out["last_status"] = status
    out["last_report_path"] = str(report_path)
    out["updated_at"] = _now_iso()
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Governed continuous-learning orchestrator for Ophtxn.")
    parser.add_argument("--action", choices=["status", "run", "init-policy"], default="status")
    parser.add_argument("--policy-path", help="Override policy path")
    parser.add_argument("--state-path", help="Override state path")
    parser.add_argument("--force-template", action="store_true", help="Rewrite policy template")
    parser.add_argument("--approved-by", help="Approval actor for run action")
    parser.add_argument("--approval-note", help="Approval note / reason")
    parser.add_argument("--skip-pipeline", action="append", default=[], help="Skip pipeline by name")
    parser.add_argument("--timeout", type=int, default=180, help="Per-pipeline timeout seconds")
    parser.add_argument("--force", action="store_true", help="Override daily run cap")
    parser.add_argument("--dry-run", action="store_true", help="Do not execute pipeline commands")
    args = parser.parse_args(argv)

    policy_path = Path(args.policy_path).expanduser() if args.policy_path else POLICY_PATH
    state_path = Path(args.state_path).expanduser() if args.state_path else STATE_PATH

    if args.action == "init-policy":
        policy, policy_status = _ensure_policy(policy_path, force_template=True)
        state = _ensure_state(state_path)
        md_path, json_path = _write_report(
            action=args.action,
            policy_path=policy_path,
            state_path=state_path,
            policy_status=policy_status,
            policy=policy,
            state=state,
            approved_by="",
            approval_note="",
            skip=set(),
            block_reasons=[],
            runs=[],
            dry_run=True,
        )
        print(f"Governed learning report: {md_path}")
        print(f"Governed learning latest: {OUTPUT_DIR / 'governed_learning_latest.md'}")
        print(f"Tool payload: {json_path}")
        return 0

    policy, policy_status = _ensure_policy(policy_path, force_template=bool(args.force_template))
    state = _ensure_state(state_path)
    skip = {str(item or "").strip().lower() for item in (args.skip_pipeline or []) if str(item or "").strip()}

    if args.action == "status":
        md_path, json_path = _write_report(
            action=args.action,
            policy_path=policy_path,
            state_path=state_path,
            policy_status=policy_status,
            policy=policy,
            state=state,
            approved_by="",
            approval_note="",
            skip=skip,
            block_reasons=[],
            runs=[],
            dry_run=True,
        )
        print(f"Governed learning report: {md_path}")
        print(f"Governed learning latest: {OUTPUT_DIR / 'governed_learning_latest.md'}")
        print(f"Tool payload: {json_path}")
        return 0

    approved_by = str(args.approved_by or "").strip()
    approval_note = str(args.approval_note or "").strip()
    block_reasons = _policy_block_reasons(
        policy=policy,
        state=state,
        approved_by=approved_by,
        approval_note=approval_note,
        force=bool(args.force),
    )

    commands = _pipeline_commands(policy, skip=skip)
    runs: list[dict[str, Any]] = []
    env = dict(os.environ)
    keywords = _topic_keywords(policy)
    if keywords and not str(env.get("PERMANENCE_SOCIAL_KEYWORDS", "")).strip():
        env["PERMANENCE_SOCIAL_KEYWORDS"] = ",".join(keywords)

    if (not block_reasons) and (not args.dry_run):
        for row in commands:
            result = _execute_pipeline(row["argv"], timeout=max(10, int(args.timeout)), env=env)
            run_row = {"name": row["name"], **result}
            runs.append(run_row)
    else:
        for row in commands:
            runs.append(
                {
                    "name": row["name"],
                    "ok": False,
                    "returncode": -1,
                    "stdout": "-",
                    "stderr": "skipped",
                }
            )

    if block_reasons:
        status = "blocked"
        rc = 1
    else:
        failed = [row for row in runs if not bool(row.get("ok"))]
        status = "ok" if not failed else "degraded"
        rc = 0 if not failed else 1

    md_path, json_path = _write_report(
        action=args.action,
        policy_path=policy_path,
        state_path=state_path,
        policy_status=policy_status,
        policy=policy,
        state=state,
        approved_by=approved_by,
        approval_note=approval_note,
        skip=skip,
        block_reasons=block_reasons,
        runs=runs,
        dry_run=bool(args.dry_run),
    )

    if (not args.dry_run) and (not block_reasons):
        updated_state = _update_state_after_run(
            state=state,
            approved_by=approved_by,
            status=status,
            report_path=md_path,
        )
        _write_json(state_path, updated_state)

    print(f"Governed learning report: {md_path}")
    print(f"Governed learning latest: {OUTPUT_DIR / 'governed_learning_latest.md'}")
    print(f"Tool payload: {json_path}")
    executed_rows = [row for row in runs if _safe_int(row.get("returncode"), -1) != -1]
    failed_rows = [row for row in executed_rows if not bool(row.get("ok"))]
    print(f"Block reasons: {len(block_reasons)}")
    print(f"Pipelines attempted: {len(executed_rows)}")
    print(f"Pipelines failed: {len(failed_rows)}")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
