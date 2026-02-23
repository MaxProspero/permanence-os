#!/usr/bin/env python3
"""
Safe file organizer:
- scan roots and produce a report + action plan
- apply plan by moving files into quarantine (never hard delete)
- open macOS Storage settings
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DEFAULT_OUTPUT_DIR = os.getenv("PERMANENCE_OUTPUT_DIR", os.path.join(BASE_DIR, "outputs"))
DEFAULT_QUARANTINE_ROOT = os.path.expanduser("~/Documents/Permanence Quarantine")


@dataclass
class FileRecord:
    path: str
    size: int
    mtime: float


def _walk_files(roots: Iterable[str]) -> list[FileRecord]:
    records: list[FileRecord] = []
    for root in roots:
        root_path = os.path.abspath(os.path.expanduser(root))
        if not os.path.exists(root_path):
            continue
        if os.path.isfile(root_path):
            try:
                stat = os.stat(root_path)
            except OSError:
                continue
            records.append(FileRecord(path=root_path, size=stat.st_size, mtime=stat.st_mtime))
            continue
        for dirpath, dirnames, filenames in os.walk(root_path):
            # Keep scan finite by skipping common heavy/derived directories.
            dirnames[:] = [
                d
                for d in dirnames
                if d
                not in {
                    ".git",
                    ".venv",
                    "node_modules",
                    "__pycache__",
                    ".mypy_cache",
                    ".pytest_cache",
                }
            ]
            for filename in filenames:
                path = os.path.join(dirpath, filename)
                try:
                    stat = os.stat(path)
                except OSError:
                    continue
                if not os.path.isfile(path):
                    continue
                records.append(FileRecord(path=path, size=stat.st_size, mtime=stat.st_mtime))
    return records


def _sha256(path: str, chunk_size: int = 1024 * 1024) -> str | None:
    digest = hashlib.sha256()
    try:
        with open(path, "rb") as handle:
            while True:
                chunk = handle.read(chunk_size)
                if not chunk:
                    break
                digest.update(chunk)
    except OSError:
        return None
    return digest.hexdigest()


def _find_duplicates(records: list[FileRecord], min_bytes: int = 64 * 1024) -> list[list[FileRecord]]:
    by_size: dict[int, list[FileRecord]] = {}
    for rec in records:
        if rec.size < min_bytes:
            continue
        by_size.setdefault(rec.size, []).append(rec)

    duplicates: list[list[FileRecord]] = []
    for same_size in by_size.values():
        if len(same_size) < 2:
            continue
        by_hash: dict[str, list[FileRecord]] = {}
        for rec in same_size:
            file_hash = _sha256(rec.path)
            if not file_hash:
                continue
            by_hash.setdefault(file_hash, []).append(rec)
        for dup_group in by_hash.values():
            if len(dup_group) > 1:
                duplicates.append(sorted(dup_group, key=lambda r: r.mtime, reverse=True))
    return duplicates


def _iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


def _quarantine_destination(run_dir: str, path: str) -> str:
    abs_path = os.path.abspath(path)
    # Preserve full source path under run dir to avoid name collisions.
    rel = abs_path.lstrip(os.sep)
    return os.path.join(run_dir, rel)


def build_plan(
    roots: list[str],
    stale_days: int = 30,
    min_large_mb: int = 500,
    top_large: int = 40,
    duplicate_min_kb: int = 64,
    max_stale_actions: int = 500,
    quarantine_root: str = DEFAULT_QUARANTINE_ROOT,
) -> dict:
    scanned = _walk_files(roots)
    now = datetime.now(timezone.utc)
    stale_cutoff = now - timedelta(days=stale_days)
    min_large_bytes = max(1, min_large_mb) * 1024 * 1024
    dup_min_bytes = max(1, duplicate_min_kb) * 1024

    large_files = sorted([r for r in scanned if r.size >= min_large_bytes], key=lambda r: r.size, reverse=True)[
        : max(1, top_large)
    ]
    stale_files = sorted(
        [r for r in scanned if datetime.fromtimestamp(r.mtime, tz=timezone.utc) < stale_cutoff],
        key=lambda r: r.mtime,
    )
    dup_groups = _find_duplicates(scanned, min_bytes=dup_min_bytes)

    created_at = now.strftime("%Y%m%d-%H%M%S")
    run_dir = os.path.join(os.path.abspath(os.path.expanduser(quarantine_root)), f"run_{created_at}")

    actions: list[dict] = []
    action_paths: set[str] = set()

    # Duplicate policy: keep newest item, quarantine older duplicates.
    for group in dup_groups:
        for rec in group[1:]:
            if rec.path in action_paths:
                continue
            action_paths.add(rec.path)
            actions.append(
                {
                    "op": "move_to_quarantine",
                    "reason": "duplicate_file",
                    "path": rec.path,
                    "destination": _quarantine_destination(run_dir, rec.path),
                    "size": rec.size,
                    "mtime": _iso(rec.mtime),
                }
            )

    # Stale policy follows explicit scan roots; apply step still requires explicit approval.
    stale_targets = tuple(os.path.abspath(os.path.expanduser(r)) for r in roots)
    stale_added = 0
    for rec in stale_files:
        if rec.path in action_paths:
            continue
        if not rec.path.startswith(stale_targets):
            continue
        if stale_added >= max(0, max_stale_actions):
            break
        action_paths.add(rec.path)
        stale_added += 1
        actions.append(
            {
                "op": "move_to_quarantine",
                "reason": "stale_file",
                "path": rec.path,
                "destination": _quarantine_destination(run_dir, rec.path),
                "size": rec.size,
                "mtime": _iso(rec.mtime),
            }
        )

    plan = {
        "created_at": now.isoformat(),
        "roots": [os.path.abspath(os.path.expanduser(r)) for r in roots],
        "quarantine_root": os.path.abspath(os.path.expanduser(quarantine_root)),
        "run_dir": run_dir,
        "scan_summary": {
            "files_scanned": len(scanned),
            "large_files_count": len(large_files),
            "stale_files_count": len(stale_files),
            "duplicate_groups": len(dup_groups),
            "actions_count": len(actions),
        },
        "large_files": [
            {"path": r.path, "size": r.size, "mtime": _iso(r.mtime)}
            for r in large_files
        ],
        "duplicates": [
            [{"path": r.path, "size": r.size, "mtime": _iso(r.mtime)} for r in group]
            for group in dup_groups
        ],
        "actions": actions,
    }
    return plan


def write_scan_artifacts(plan: dict, output_dir: str = DEFAULT_OUTPUT_DIR) -> tuple[str, str]:
    os.makedirs(output_dir, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    plan_path = os.path.join(output_dir, f"file_organizer_plan_{stamp}.json")
    report_path = os.path.join(output_dir, f"file_organizer_report_{stamp}.md")

    with open(plan_path, "w") as handle:
        json.dump(plan, handle, indent=2)

    summary = plan["scan_summary"]
    lines = [
        "# File Organizer Scan",
        "",
        f"Created: {plan['created_at']}",
        f"Roots: {', '.join(plan['roots'])}",
        f"Files scanned: {summary['files_scanned']}",
        f"Large files: {summary['large_files_count']}",
        f"Stale files: {summary['stale_files_count']}",
        f"Duplicate groups: {summary['duplicate_groups']}",
        f"Planned actions (quarantine moves): {summary['actions_count']}",
        "",
        "## Top Large Files",
    ]
    if not plan["large_files"]:
        lines.append("- (none)")
    else:
        for item in plan["large_files"][:20]:
            mb = item["size"] / (1024 * 1024)
            lines.append(f"- {item['path']} ({mb:.1f} MB)")

    lines.append("")
    lines.append("## Planned Actions")
    if not plan["actions"]:
        lines.append("- (none)")
    else:
        for item in plan["actions"][:50]:
            lines.append(f"- [{item['reason']}] {item['path']}")
        if len(plan["actions"]) > 50:
            lines.append(f"- ... {len(plan['actions']) - 50} more")

    lines.append("")
    lines.append(f"Plan file: {plan_path}")
    lines.append(f"Quarantine root: {plan['quarantine_root']}")
    lines.append("Safety: files are moved, never hard deleted.")

    with open(report_path, "w") as handle:
        handle.write("\n".join(lines) + "\n")

    return plan_path, report_path


def apply_plan(plan_path: str, dry_run: bool = False, limit: int = 0) -> dict:
    with open(plan_path, "r") as handle:
        plan = json.load(handle)

    actions = plan.get("actions", [])
    if limit > 0:
        actions = actions[:limit]

    moved = 0
    missing = 0
    failed = 0
    failures: list[dict] = []

    run_dir = plan.get("run_dir") or os.path.join(
        os.path.abspath(os.path.expanduser(plan.get("quarantine_root", DEFAULT_QUARANTINE_ROOT))),
        f"run_{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}",
    )

    for action in actions:
        src = action.get("path")
        dst = action.get("destination") or _quarantine_destination(run_dir, src)
        if not src:
            failed += 1
            failures.append({"path": src, "error": "missing_source_path"})
            continue
        if not os.path.exists(src):
            missing += 1
            continue
        if dry_run:
            moved += 1
            continue
        try:
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.move(src, dst)
            moved += 1
        except OSError as exc:
            failed += 1
            failures.append({"path": src, "error": str(exc)})

    result = {
        "applied_at": datetime.now(timezone.utc).isoformat(),
        "plan_path": os.path.abspath(plan_path),
        "run_dir": run_dir,
        "dry_run": dry_run,
        "attempted": len(actions),
        "moved": moved,
        "missing": missing,
        "failed": failed,
        "failures": failures,
    }

    if not dry_run:
        os.makedirs(run_dir, exist_ok=True)
        manifest_path = os.path.join(
            run_dir,
            f"manifest_{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}.json",
        )
        with open(manifest_path, "w") as handle:
            json.dump(result, handle, indent=2)
        result["manifest_path"] = manifest_path

    return result


def open_storage_settings() -> int:
    uris = [
        "x-apple.systempreferences:com.apple.settings.Storage",
        "x-apple.systempreferences:com.apple.preference.storage",
    ]
    for uri in uris:
        code = subprocess.call(["open", uri])
        if code == 0:
            return 0
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Safe file organizer")
    parser.add_argument("--action", choices=["scan", "apply", "open-storage"], default="scan")
    parser.add_argument("--roots", nargs="*", help="Roots to scan (default: ~/Downloads ~/Desktop ~/Documents)")
    parser.add_argument("--stale-days", type=int, default=30, help="Age threshold for stale-file candidates")
    parser.add_argument("--min-large-mb", type=int, default=500, help="Minimum size for large-file reporting")
    parser.add_argument("--top-large", type=int, default=40, help="Number of large files to include in report")
    parser.add_argument("--duplicate-min-kb", type=int, default=64, help="Minimum file size for duplicate hashing")
    parser.add_argument("--max-stale-actions", type=int, default=500, help="Cap stale-file move candidates")
    parser.add_argument("--quarantine-root", default=DEFAULT_QUARANTINE_ROOT, help="Quarantine root directory")
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR, help="Directory for scan plan/report outputs")
    parser.add_argument("--plan", help="Path to plan JSON for --action apply")
    parser.add_argument("--dry-run", action="store_true", help="Simulate apply without moving files")
    parser.add_argument("--confirm", action="store_true", help="Required for non-dry-run apply")
    parser.add_argument("--limit", type=int, default=0, help="Apply only first N actions (0=all)")
    args = parser.parse_args()

    if args.action == "open-storage":
        code = open_storage_settings()
        if code == 0:
            print("Opened Storage settings.")
        else:
            print("Failed to open Storage settings.")
        return code

    if args.action == "scan":
        roots = args.roots or ["~/Downloads", "~/Desktop", "~/Documents"]
        plan = build_plan(
            roots=roots,
            stale_days=max(1, args.stale_days),
            min_large_mb=max(1, args.min_large_mb),
            top_large=max(1, args.top_large),
            duplicate_min_kb=max(1, args.duplicate_min_kb),
            max_stale_actions=max(0, args.max_stale_actions),
            quarantine_root=args.quarantine_root,
        )
        plan_path, report_path = write_scan_artifacts(plan, output_dir=args.output_dir)
        print(f"Scan complete. Plan: {plan_path}")
        print(f"Report: {report_path}")
        print(f"Planned actions: {plan['scan_summary']['actions_count']}")
        return 0

    if not args.plan:
        print("Missing --plan for --action apply")
        return 2
    if not args.dry_run and not args.confirm:
        print("Refusing apply without --confirm. Use --dry-run first or pass --confirm.")
        return 2
    result = apply_plan(args.plan, dry_run=args.dry_run, limit=max(0, args.limit))
    print(
        "Apply complete: "
        f"attempted={result['attempted']} moved={result['moved']} "
        f"missing={result['missing']} failed={result['failed']} dry_run={result['dry_run']}"
    )
    if result.get("manifest_path"):
        print(f"Manifest: {result['manifest_path']}")
    return 0 if result["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
