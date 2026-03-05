#!/usr/bin/env python3
"""
Autopilot importer for smart-glasses exports.

Scans a directory (default: ~/Downloads) for new JSON exports and routes them
through glasses-bridge, then optionally runs attachment + research follow-ups.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parents[1]

DEFAULT_PATTERNS = [
    "nearby_glasses_detected*.json",
    "*nearby*glasses*.json",
    "*visionclaw*.json",
    "*captured_media*.json",
]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now().isoformat()


def _working_dir() -> Path:
    return Path(os.getenv("PERMANENCE_WORKING_DIR", str(BASE_DIR / "memory" / "working")))


def _output_dir() -> Path:
    return Path(os.getenv("PERMANENCE_OUTPUT_DIR", str(BASE_DIR / "outputs")))


def _tool_dir() -> Path:
    return Path(os.getenv("PERMANENCE_TOOL_DIR", str(BASE_DIR / "memory" / "tool")))


def _default_state_path() -> Path:
    return Path(
        os.getenv(
            "PERMANENCE_GLASSES_AUTOPILOT_STATE_PATH",
            str(_working_dir() / "glasses" / "autopilot_state.json"),
        )
    )


def _safe_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _file_fingerprint(path: Path) -> str:
    stat = path.stat()
    basis = f"{path.resolve()}|{int(stat.st_size)}|{int(stat.st_mtime)}"
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()[:20]


def _load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"processed": {}, "updated_at": ""}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"processed": {}, "updated_at": ""}
    if not isinstance(payload, dict):
        return {"processed": {}, "updated_at": ""}
    if not isinstance(payload.get("processed"), dict):
        payload["processed"] = {}
    return payload


def _save_state(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _candidate_files(downloads_dir: Path, patterns: list[str], max_files: int) -> list[Path]:
    found: list[Path] = []
    for pattern in patterns:
        found.extend(downloads_dir.glob(pattern))
    uniq: dict[str, Path] = {}
    for path in found:
        if path.is_file():
            uniq[str(path.resolve())] = path
    rows = sorted(uniq.values(), key=lambda p: p.stat().st_mtime, reverse=True)
    return rows[: max(1, max_files)]


def _is_plausible_export(path: Path) -> bool:
    payload = _safe_json(path)
    if payload is None:
        return False
    if isinstance(payload, list):
        return any(isinstance(row, dict) for row in payload)
    if isinstance(payload, dict):
        for key in ("detections", "events", "items", "records", "entries", "capturedMedia"):
            rows = payload.get(key)
            if isinstance(rows, list) and rows:
                return True
        return True
    return False


def _write_report(
    *,
    action: str,
    downloads_dir: Path,
    candidates: list[Path],
    imported: list[Path],
    skipped: list[str],
    state_path: Path,
) -> tuple[Path, Path]:
    output_dir = _output_dir()
    tool_dir = _tool_dir()
    output_dir.mkdir(parents=True, exist_ok=True)
    tool_dir.mkdir(parents=True, exist_ok=True)
    stamp = _now().strftime("%Y%m%d-%H%M%S")
    md_path = output_dir / f"glasses_autopilot_{stamp}.md"
    latest_md = output_dir / "glasses_autopilot_latest.md"
    json_path = tool_dir / f"glasses_autopilot_{stamp}.json"

    lines = [
        "# Glasses Autopilot",
        "",
        f"Generated (UTC): {_now_iso()}",
        f"Action: {action}",
        f"Downloads dir: {downloads_dir}",
        f"State path: {state_path}",
        "",
        "## Summary",
        f"- Candidate files scanned: {len(candidates)}",
        f"- Imported this run: {len(imported)}",
        f"- Skipped: {len(skipped)}",
        "",
    ]
    if imported:
        lines.append("## Imported Files")
        for path in imported:
            lines.append(f"- {path}")
        lines.append("")
    if skipped:
        lines.append("## Skipped")
        for item in skipped[:100]:
            lines.append(f"- {item}")
        lines.append("")

    report = "\n".join(lines)
    md_path.write_text(report, encoding="utf-8")
    latest_md.write_text(report, encoding="utf-8")
    payload = {
        "generated_at": _now_iso(),
        "action": action,
        "downloads_dir": str(downloads_dir),
        "state_path": str(state_path),
        "candidate_count": len(candidates),
        "imported_count": len(imported),
        "skipped_count": len(skipped),
        "imported_files": [str(path) for path in imported],
        "skipped": skipped,
        "latest_markdown": str(latest_md),
    }
    json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return md_path, json_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Autopilot importer for smart-glasses export files.")
    parser.add_argument("--action", choices=["run", "status"], default="status")
    parser.add_argument("--downloads-dir", default=str(Path.home() / "Downloads"), help="Directory to scan")
    parser.add_argument("--state-path", help="Autopilot state path")
    parser.add_argument("--pattern", action="append", default=[], help="Glob pattern (repeatable)")
    parser.add_argument("--max-files", type=int, default=60, help="Max candidate files to inspect")
    parser.add_argument("--no-attachment-pipeline", action="store_true", help="Skip attachment-pipeline follow-up")
    parser.add_argument("--no-research-process", action="store_true", help="Skip research-inbox process follow-up")
    parser.add_argument("--dry-run", action="store_true", help="Scan only; do not ingest or update state")
    args = parser.parse_args(argv)

    downloads_dir = Path(args.downloads_dir).expanduser()
    state_path = Path(args.state_path).expanduser() if args.state_path else _default_state_path()
    patterns = args.pattern if args.pattern else list(DEFAULT_PATTERNS)
    state = _load_state(state_path)
    processed = state.get("processed") if isinstance(state.get("processed"), dict) else {}

    candidates = _candidate_files(downloads_dir=downloads_dir, patterns=patterns, max_files=max(1, int(args.max_files)))
    imported: list[Path] = []
    skipped: list[str] = []

    if args.action == "run":
        new_files: list[Path] = []
        for path in candidates:
            fingerprint = _file_fingerprint(path)
            if processed.get(fingerprint):
                skipped.append(f"already imported: {path}")
                continue
            if not _is_plausible_export(path):
                skipped.append(f"not plausible export json: {path}")
                continue
            new_files.append(path)

        if new_files and not args.dry_run:
            import scripts.glasses_bridge as bridge_mod  # noqa: WPS433

            bridge_args = ["--action", "ingest"]
            for path in new_files:
                bridge_args.extend(["--from-json", str(path)])
            bridge_mod.main(bridge_args)

            imported.extend(new_files)
            for path in new_files:
                processed[_file_fingerprint(path)] = {
                    "path": str(path.resolve()),
                    "imported_at": _now_iso(),
                }

            if not args.no_attachment_pipeline:
                import scripts.attachment_pipeline as attachment_mod  # noqa: WPS433

                attachment_mod.main([])

            if not args.no_research_process:
                import scripts.research_inbox as research_mod  # noqa: WPS433

                research_mod.main(["--action", "process"])

        elif new_files and args.dry_run:
            imported.extend(new_files)
        else:
            skipped.append("no new files matched import rules")

        if not args.dry_run:
            state["processed"] = processed
            state["updated_at"] = _now_iso()
            _save_state(state_path, state)

    md_path, json_path = _write_report(
        action=args.action,
        downloads_dir=downloads_dir,
        candidates=candidates,
        imported=imported,
        skipped=skipped,
        state_path=state_path,
    )
    print(f"Glasses autopilot written: {md_path}")
    print(f"Glasses autopilot latest: {_output_dir() / 'glasses_autopilot_latest.md'}")
    print(f"Tool payload written: {json_path}")
    if args.action == "status":
        print(f"State entries: {len(processed)}")
    else:
        print(f"Imported files: {len(imported)}")
        if skipped:
            print(f"Skipped: {len(skipped)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
