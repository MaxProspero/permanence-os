#!/usr/bin/env python3
"""
Unified skill registry for Permanence OS.

Discovers, catalogs, and manages all scripts, agents, and automation as
activatable skills with status tracking and health checks.

Usage:
    python3 scripts/skill_registry.py --action list
    python3 scripts/skill_registry.py --action list --category agent --status active
    python3 scripts/skill_registry.py --action manifest
    python3 scripts/skill_registry.py --action activate --name idea_intake
    python3 scripts/skill_registry.py --action deactivate --name idea_intake
    python3 scripts/skill_registry.py --action health --name idea_intake
    python3 scripts/skill_registry.py --action report
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parents[1]
WORKING_DIR = Path(os.getenv("PERMANENCE_WORKING_DIR", str(BASE_DIR / "memory" / "working")))
OUTPUT_DIR = Path(os.getenv("PERMANENCE_OUTPUT_DIR", str(BASE_DIR / "outputs")))
MANIFEST_PATH = Path(os.getenv("PERMANENCE_SKILL_MANIFEST_PATH", str(WORKING_DIR / "skill_manifest.json")))


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return default


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


class SkillRegistry:
    SCAN_DIRS: dict[str, str] = {
        "script": "scripts",
        "agent": "agents",
        "department": "agents/departments",
        "special": "special",
        "automation": "automation",
    }

    def __init__(self) -> None:
        self._skills: dict[str, dict[str, Any]] = {}
        self._manifest: dict[str, dict[str, Any]] = {}

    def load_manifest(self) -> None:
        data = _read_json(MANIFEST_PATH, {})
        if isinstance(data, dict):
            self._manifest = data
        else:
            self._manifest = {}

    def save_manifest(self) -> None:
        out: dict[str, dict[str, Any]] = {}
        for name, skill in self._skills.items():
            out[name] = {
                "status": skill.get("status", "dormant"),
                "last_run": skill.get("last_run"),
                "health": skill.get("health", "unknown"),
            }
        _write_json(MANIFEST_PATH, out)

    def scan(self) -> None:
        for category, rel_dir in self.SCAN_DIRS.items():
            dir_path = BASE_DIR / rel_dir
            if not dir_path.is_dir():
                continue
            for py_file in sorted(dir_path.glob("*.py")):
                if py_file.name.startswith("_"):
                    continue
                name = py_file.stem
                if category == "department":
                    name = f"dept_{name}"
                description = self._extract_docstring(py_file)
                override = self._manifest.get(name, {})
                self._skills[name] = {
                    "name": name,
                    "path": str(py_file.relative_to(BASE_DIR)),
                    "category": category,
                    "status": override.get("status", "dormant"),
                    "description": description,
                    "last_run": override.get("last_run"),
                    "health": override.get("health", "unknown"),
                }

    @staticmethod
    def _extract_docstring(path: Path) -> str:
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return "No description"
        for marker in ['"""', "'''"]:
            idx = content.find(marker)
            if idx >= 0:
                end = content.find(marker, idx + 3)
                if end > idx:
                    doc = content[idx + 3 : end].strip()
                    first_line = doc.split("\n")[0].strip()
                    if first_line:
                        return first_line
        return "No description"

    def list_skills(
        self, category: str | None = None, status: str | None = None
    ) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for skill in self._skills.values():
            if category and skill["category"] != category:
                continue
            if status and skill["status"] != status:
                continue
            out.append(dict(skill))
        out.sort(key=lambda s: (s["category"], s["name"]))
        return out

    def get_skill(self, name: str) -> dict[str, Any] | None:
        return self._skills.get(name)

    def activate(self, name: str) -> bool:
        skill = self._skills.get(name)
        if not skill:
            return False
        skill["status"] = "active"
        return True

    def deactivate(self, name: str) -> bool:
        skill = self._skills.get(name)
        if not skill:
            return False
        skill["status"] = "dormant"
        return True

    def health_check(self, name: str) -> str:
        skill = self._skills.get(name)
        if not skill:
            return "not_found"
        full_path = BASE_DIR / skill["path"]
        if not full_path.exists():
            skill["health"] = "error"
            return "error"
        try:
            spec = importlib.util.spec_from_file_location(name, str(full_path))
            if spec and spec.loader:
                skill["health"] = "healthy"
                return "healthy"
            skill["health"] = "error"
            return "error"
        except Exception:  # noqa: BLE001
            skill["health"] = "error"
            return "error"

    @property
    def skills(self) -> dict[str, dict[str, Any]]:
        return self._skills


def _print_table(skills: list[dict[str, Any]]) -> None:
    if not skills:
        print("No skills found matching criteria.")
        return
    name_w = max(28, max(len(s["name"]) for s in skills) + 2)
    cat_w = 14
    status_w = 10
    header = f"{'Name':<{name_w}} {'Category':<{cat_w}} {'Status':<{status_w}} Description"
    print(header)
    print("-" * len(header))
    for s in skills:
        desc = s["description"][:60]
        print(f"{s['name']:<{name_w}} {s['category']:<{cat_w}} {s['status']:<{status_w}} {desc}")


def _write_report(reg: SkillRegistry) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    report_path = OUTPUT_DIR / "skill_registry_latest.md"

    all_skills = reg.list_skills()
    active = [s for s in all_skills if s["status"] == "active"]
    dormant = [s for s in all_skills if s["status"] == "dormant"]
    disabled = [s for s in all_skills if s["status"] == "disabled"]

    lines = [
        "# Skill Registry Report",
        "",
        f"Generated: {_now_iso()}",
        "",
        "## Summary",
        f"- Total skills: {len(all_skills)}",
        f"- Active: {len(active)}",
        f"- Dormant: {len(dormant)}",
        f"- Disabled: {len(disabled)}",
    ]

    categories = sorted(set(s["category"] for s in all_skills))
    for cat in categories:
        cat_skills = [s for s in all_skills if s["category"] == cat]
        lines.extend([
            "",
            f"### {cat.title()}s ({len(cat_skills)})",
            "",
            "| Name | Status | Description |",
            "|------|--------|-------------|",
        ])
        for s in cat_skills:
            desc = s["description"][:80].replace("|", "/")
            lines.append(f"| {s['name']} | {s['status']} | {desc} |")

    lines.append("")
    report = "\n".join(lines)
    report_path.write_text(report, encoding="utf-8")
    return report_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Permanence OS skill registry.")
    parser.add_argument("--action", default="list", choices=["list", "manifest", "activate", "deactivate", "health", "report"])
    parser.add_argument("--name", default="", help="Skill name for activate/deactivate/health")
    parser.add_argument("--category", default="", help="Filter by category")
    parser.add_argument("--status", default="", help="Filter by status")
    args = parser.parse_args(argv)

    reg = SkillRegistry()
    reg.load_manifest()
    reg.scan()

    if args.action == "list":
        skills = reg.list_skills(
            category=args.category or None,
            status=args.status or None,
        )
        _print_table(skills)
        print(f"\nTotal: {len(skills)} skills")
        return 0

    if args.action == "manifest":
        reg.save_manifest()
        print(f"Manifest written: {MANIFEST_PATH}")
        print(f"Total skills: {len(reg.skills)}")
        return 0

    if args.action == "activate":
        if not args.name:
            print("--name is required for activate action.", file=sys.stderr)
            return 1
        if reg.activate(args.name):
            reg.save_manifest()
            print(f"Activated: {args.name}")
            return 0
        print(f"Skill not found: {args.name}", file=sys.stderr)
        return 1

    if args.action == "deactivate":
        if not args.name:
            print("--name is required for deactivate action.", file=sys.stderr)
            return 1
        if reg.deactivate(args.name):
            reg.save_manifest()
            print(f"Deactivated: {args.name}")
            return 0
        print(f"Skill not found: {args.name}", file=sys.stderr)
        return 1

    if args.action == "health":
        if not args.name:
            print("--name is required for health action.", file=sys.stderr)
            return 1
        result = reg.health_check(args.name)
        print(f"Health check for {args.name}: {result}")
        return 0 if result == "healthy" else 1

    if args.action == "report":
        report_path = _write_report(reg)
        print(f"Report written: {report_path}")
        print(f"Total skills: {len(reg.skills)}")
        return 0

    return 0


if __name__ == "__main__":
    import sys
    raise SystemExit(main())
