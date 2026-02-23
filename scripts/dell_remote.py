#!/usr/bin/env python3
"""
Mac -> Dell remote bridge via SSH/rsync.

Use this script from your Mac-side repo to:
- store Dell host config once
- test SSH connectivity
- run commands on Dell in the repo (with optional venv activation)
- sync local code to Dell without copy/paste
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
from datetime import datetime, timezone
from typing import Any

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DEFAULT_CONFIG_PATH = os.path.join(BASE_DIR, "memory", "working", "remote", "dell_remote.json")

DEFAULT_SYNC_EXCLUDES = [
    ".git/",
    ".venv/",
    "__pycache__/",
    ".pytest_cache/",
    "logs/",
    "outputs/",
    "memory/tool/",
    "memory/working/research/",
    "memory/working/sources.json",
    ".DS_Store",
]


def _load_json(path: str, fallback: dict[str, Any]) -> dict[str, Any]:
    if not os.path.exists(path):
        return dict(fallback)
    try:
        with open(path, "r") as handle:
            parsed = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return dict(fallback)
    return parsed if isinstance(parsed, dict) else dict(fallback)


def _save_json(path: str, payload: dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as handle:
        json.dump(payload, handle, indent=2)


def _require(cfg: dict[str, Any], fields: list[str]) -> None:
    missing = [f for f in fields if not cfg.get(f)]
    if missing:
        raise ValueError(f"Missing required Dell remote fields: {', '.join(missing)}")


def _remote_target(cfg: dict[str, Any]) -> str:
    return f"{cfg['user']}@{cfg['host']}"


def _ssh_prefix(cfg: dict[str, Any]) -> list[str]:
    cmd = ["ssh", "-o", "BatchMode=yes"]
    if cfg.get("port"):
        cmd += ["-p", str(cfg["port"])]
    if cfg.get("key_path"):
        cmd += ["-i", str(cfg["key_path"])]
    cmd += [_remote_target(cfg)]
    return cmd


def _rsync_ssh_transport(cfg: dict[str, Any]) -> str:
    parts = ["ssh"]
    if cfg.get("port"):
        parts += ["-p", str(cfg["port"])]
    if cfg.get("key_path"):
        parts += ["-i", str(cfg["key_path"])]
    return " ".join(parts)


def build_remote_shell(
    command: str,
    repo_path: str | None = None,
    use_repo: bool = True,
    use_venv: bool = True,
) -> str:
    steps: list[str] = []
    if use_repo and repo_path:
        steps.append(f"cd {shlex.quote(repo_path)}")
        if use_venv:
            steps.append("if [ -f .venv/bin/activate ]; then . .venv/bin/activate; fi")
    steps.append(command)
    return " && ".join(steps)


def run_remote(
    cfg: dict[str, Any],
    command: str,
    use_repo: bool = True,
    use_venv: bool = True,
    print_cmd: bool = False,
) -> int:
    _require(cfg, ["host", "user", "repo_path"])
    remote_shell = build_remote_shell(
        command=command,
        repo_path=cfg.get("repo_path"),
        use_repo=use_repo,
        use_venv=use_venv,
    )
    cmd = _ssh_prefix(cfg) + [remote_shell]
    if print_cmd:
        print("Running:", " ".join(shlex.quote(p) for p in cmd))
    return subprocess.call(cmd)


def sync_code(
    cfg: dict[str, Any],
    local_path: str = BASE_DIR,
    dry_run: bool = False,
    print_cmd: bool = False,
) -> int:
    _require(cfg, ["host", "user", "repo_path"])
    local = os.path.abspath(os.path.expanduser(local_path))
    if not os.path.isdir(local):
        raise ValueError(f"Local path not found: {local}")

    # Ensure remote repo dir exists before rsync.
    mkdir_cmd = _ssh_prefix(cfg) + [f"mkdir -p {shlex.quote(cfg['repo_path'])}"]
    code = subprocess.call(mkdir_cmd)
    if code != 0:
        return code

    rsync_cmd = ["rsync", "-az"]
    if dry_run:
        rsync_cmd.append("--dry-run")
    for pattern in DEFAULT_SYNC_EXCLUDES:
        rsync_cmd += ["--exclude", pattern]
    rsync_cmd += ["-e", _rsync_ssh_transport(cfg)]
    rsync_cmd += [f"{local.rstrip('/')}/", f"{_remote_target(cfg)}:{cfg['repo_path'].rstrip('/')}/"]
    if print_cmd:
        print("Running:", " ".join(shlex.quote(p) for p in rsync_cmd))
    return subprocess.call(rsync_cmd)


def _merge_cli_config(existing: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    cfg = dict(existing)
    updates = {
        "host": args.host,
        "user": args.user,
        "repo_path": args.repo_path,
        "port": args.port,
        "key_path": args.key_path,
    }
    for key, value in updates.items():
        if value is not None:
            cfg[key] = value
    return cfg


def _safe_show(cfg: dict[str, Any]) -> dict[str, Any]:
    payload = dict(cfg)
    if payload.get("key_path"):
        payload["key_path"] = os.path.abspath(os.path.expanduser(str(payload["key_path"])))
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Dell remote bridge (SSH + rsync)")
    parser.add_argument(
        "--action",
        choices=["configure", "show", "test", "run", "sync-code"],
        default="show",
        help="Bridge action",
    )
    parser.add_argument("--config", default=DEFAULT_CONFIG_PATH, help="Config JSON path")
    parser.add_argument("--host", help="Dell host or IP")
    parser.add_argument("--user", help="Dell SSH user")
    parser.add_argument("--repo-path", help="Repo path on Dell")
    parser.add_argument("--port", type=int, help="SSH port")
    parser.add_argument("--key-path", help="SSH private key path")
    parser.add_argument("--cmd", help="Remote command for --action run")
    parser.add_argument("--no-repo", action="store_true", help="Do not cd into repo before run")
    parser.add_argument("--no-venv", action="store_true", help="Do not auto-activate .venv")
    parser.add_argument("--local-path", default=BASE_DIR, help="Local path for --action sync-code")
    parser.add_argument("--dry-run", action="store_true", help="Dry run for sync-code")
    parser.add_argument("--print-cmd", action="store_true", help="Print underlying command before running")
    args = parser.parse_args()

    existing = _load_json(args.config, {})
    cfg = _merge_cli_config(existing, args)

    if args.action == "configure":
        cfg["updated_at"] = datetime.now(timezone.utc).isoformat()
        _save_json(args.config, cfg)
        print(f"Dell remote config saved: {os.path.abspath(args.config)}")
        print(json.dumps(_safe_show(cfg), indent=2))
        return 0

    if args.action == "show":
        print(json.dumps(_safe_show(cfg), indent=2))
        return 0

    # Non-config actions require a valid config.
    _require(cfg, ["host", "user", "repo_path"])

    if args.action == "test":
        return run_remote(
            cfg=cfg,
            command="echo Dell remote OK",
            use_repo=False,
            use_venv=False,
            print_cmd=args.print_cmd,
        )

    if args.action == "run":
        if not args.cmd:
            print("Missing --cmd for --action run")
            return 2
        return run_remote(
            cfg=cfg,
            command=args.cmd,
            use_repo=not args.no_repo,
            use_venv=not args.no_venv,
            print_cmd=args.print_cmd,
        )

    return sync_code(
        cfg=cfg,
        local_path=args.local_path,
        dry_run=args.dry_run,
        print_cmd=args.print_cmd,
    )


if __name__ == "__main__":
    raise SystemExit(main())
