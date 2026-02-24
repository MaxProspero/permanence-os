#!/usr/bin/env python3
"""
BRIEFING AGENT
Aggregate intelligence from departments into a daily report.
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timezone, timedelta
import os
from pathlib import Path
import json
import re

from agents.utils import log


@dataclass
class AgentResult:
    status: str
    notes: List[str]
    artifact: Optional[Any] = None
    created_at: str = datetime.now(timezone.utc).isoformat()


class BriefingAgent:
    """
    ROLE: Aggregate read-only summaries across departments.

    CONSTRAINTS:
    - Read-only aggregation
    - No cross-department writes
    """

    legal_exposure_domains = ["sensitive_data_aggregation"]

    allowed_tools = ["read_reports"]

    source_agents = [
        "email_agent",
        "device_agent",
        "social_agent",
        "health_agent",
        "trainer_agent",
        "therapist_agent",
        "hr_agent",
        "openclaw_status",
    ]

    forbidden_actions = ["write_back_to_departments", "publish_without_approval"]

    def execute(self, _task: Dict[str, Any]) -> AgentResult:
        log("BriefingAgent execute called", level="INFO")
        now = datetime.now(timezone.utc).isoformat()
        email_summary = self._load_email_summary()
        health_summary = self._load_health_summary()
        social_summary = self._load_social_summary()
        reception_summary = self._load_reception_summary()
        operator_panel = self._load_operator_panel()
        v04_telemetry = self._load_v04_telemetry()
        system_health = self._load_system_health()
        documents_summary = self._load_documents_summary()
        chronicle_summary = self._load_chronicle_summary()
        focus_items = self._generate_focus(email_summary, health_summary, social_summary)
        notes: List[str] = [
            "# Daily Briefing",
            "",
            f"Generated (UTC): {now}",
            "",
        ]

        notes.extend(self._section_system_status())
        notes.extend(self._section_operator_panel(operator_panel))
        notes.extend(self._section_v04_telemetry(v04_telemetry))
        notes.extend(self._section_openclaw())
        notes.extend(self._section_email_summary(email_summary))
        notes.extend(self._section_health_summary(health_summary))
        notes.extend(self._section_social_summary(social_summary))
        notes.extend(self._section_reception_summary(reception_summary))
        notes.extend(self._section_documents(documents_summary))
        notes.extend(self._section_chronicle(chronicle_summary))
        notes.extend(self._section_focus(focus_items))
        notes.extend(self._section_system_health(system_health))
        notes.extend(self._section_outputs())

        return AgentResult(
            status="COMPILED",
            notes=notes,
        )

    @staticmethod
    def _latest_openclaw_status() -> Optional[str]:
        output_dir = os.getenv(
            "PERMANENCE_OUTPUT_DIR",
            os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "outputs")),
        )
        try:
            candidates = sorted(
                Path(output_dir).glob("openclaw_status_*.txt"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
        except FileNotFoundError:
            return None
        if not candidates:
            return None
        latest = candidates[0]
        excerpt = ""
        try:
            with open(latest, "r") as f:
                lines = [next(f).rstrip() for _ in range(6)]
            excerpt = " | ".join([l for l in lines if l])
        except (OSError, StopIteration):
            excerpt = ""
        if excerpt:
            return f"OpenClaw status: {excerpt}"
        return f"OpenClaw status captured: {latest}"

    @staticmethod
    def _latest_email_triage() -> Optional[str]:
        output_dir = os.getenv(
            "PERMANENCE_OUTPUT_DIR",
            os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "outputs")),
        )
        try:
            candidates = sorted(
                Path(output_dir).glob("email_triage_*.md"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
        except FileNotFoundError:
            return None
        if not candidates:
            return None
        latest = candidates[0]
        excerpt = ""
        try:
            with open(latest, "r") as f:
                lines = [next(f).rstrip() for _ in range(6)]
            excerpt = " | ".join([l for l in lines if l])
        except (OSError, StopIteration):
            excerpt = ""
        if excerpt:
            return f"Email triage: {excerpt}"
        return f"Email triage captured: {latest}"

    @staticmethod
    def _latest_openclaw_health() -> Optional[str]:
        output_dir = os.getenv(
            "PERMANENCE_OUTPUT_DIR",
            os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "outputs")),
        )
        try:
            candidates = sorted(
                Path(output_dir).glob("openclaw_health_*.txt"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
        except FileNotFoundError:
            return None
        if not candidates:
            return None
        latest = candidates[0]
        excerpt = BriefingAgent._read_excerpt(latest, max_lines=6)
        if excerpt:
            return f"OpenClaw health: {excerpt}"
        return f"OpenClaw health captured: {latest}"

    @staticmethod
    def _latest_hr_report() -> Optional[str]:
        output_dir = os.getenv(
            "PERMANENCE_OUTPUT_DIR",
            os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "outputs")),
        )
        path = Path(output_dir) / "weekly_system_health_report.md"
        if not path.exists():
            return None
        latest = path
        excerpt = BriefingAgent._read_excerpt(latest, max_lines=12)
        if excerpt:
            return f"HR report excerpt: {excerpt}"
        return f"HR report captured: {latest}"

    @staticmethod
    def _latest_tool_payload(prefix: str) -> Optional[Path]:
        tool_dir = os.getenv(
            "PERMANENCE_TOOL_DIR",
            os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "memory", "tool")),
        )
        try:
            candidates = sorted(
                Path(tool_dir).glob(f"{prefix}_*.json"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
        except FileNotFoundError:
            return None
        if not candidates:
            return None
        return candidates[0]

    @staticmethod
    def _read_json(path: Path) -> Optional[Dict[str, Any]]:
        try:
            with open(path, "r") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError):
            return None

    @staticmethod
    def _parse_email_md(path: Path) -> Dict[str, Any]:
        summary = {"p0": 0, "p1": 0, "p2": 0, "p3": 0, "p2_items": []}
        try:
            lines = path.read_text().splitlines()
        except OSError:
            return summary
        current = None
        for line in lines:
            line = line.strip()
            if not line:
                continue
            match = re.match(r"^##\s+P([0-3])\s+\((\d+)\)", line)
            if match:
                bucket = f"p{match.group(1)}"
                summary[bucket] = int(match.group(2))
                current = bucket
                continue
            if current == "p2" and line.startswith("- "):
                summary["p2_items"].append(line[2:])
        return summary

    def _load_email_summary(self) -> Dict[str, Any]:
        payload_path = self._latest_tool_payload("email_triage")
        if payload_path:
            payload = self._read_json(payload_path) or {}
            p0 = payload.get("P0", []) or payload.get("p0", [])
            p1 = payload.get("P1", []) or payload.get("p1", [])
            p2 = payload.get("P2", []) or payload.get("p2", [])
            p3 = payload.get("P3", []) or payload.get("p3", [])
            p2_items = [item.get("summary") for item in p2 if isinstance(item, dict)]
            return {
                "p0": len(p0),
                "p1": len(p1),
                "p2": len(p2),
                "p3": len(p3),
                "p2_items": [i for i in p2_items if i],
            }
        output_dir = os.getenv(
            "PERMANENCE_OUTPUT_DIR",
            os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "outputs")),
        )
        try:
            candidates = sorted(
                Path(output_dir).glob("email_triage_*.md"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
        except FileNotFoundError:
            return {"p0": 0, "p1": 0, "p2": 0, "p3": 0, "p2_items": [], "missing": True}
        if not candidates:
            return {"p0": 0, "p1": 0, "p2": 0, "p3": 0, "p2_items": [], "missing": True}
        summary = self._parse_email_md(candidates[0])
        summary["missing"] = False
        return summary

    def _load_health_summary(self) -> Dict[str, Any]:
        payload_path = self._latest_tool_payload("health_summary")
        if not payload_path:
            return {"not_connected": True}
        payload = self._read_json(payload_path) or {}
        latest = payload.get("latest") or {}
        return {
            "not_connected": False,
            "avg_sleep_hours": payload.get("avg_sleep_hours"),
            "avg_hrv": payload.get("avg_hrv"),
            "avg_recovery": payload.get("avg_recovery"),
            "avg_strain": payload.get("avg_strain"),
            "latest": latest,
        }

    def _load_social_summary(self) -> Dict[str, Any]:
        payload_path = self._latest_tool_payload("social_summary")
        if not payload_path:
            return {"not_connected": True, "drafts_ready": 0, "notifications": 0, "dms_pending": 0}
        payload = self._read_json(payload_path) or {}
        drafts = payload.get("drafts") or []
        return {
            "not_connected": False,
            "drafts_ready": payload.get("count", len(drafts)),
            "notifications": 0,
            "dms_pending": 0,
        }

    def _load_reception_summary(self) -> Dict[str, Any]:
        payload_path = self._latest_tool_payload("ari_reception")
        if not payload_path:
            return {"not_connected": True, "total_entries": 0, "open_entries": 0, "urgent_open_entries": 0}
        payload = self._read_json(payload_path) or {}
        return {
            "not_connected": False,
            "total_entries": int(payload.get("total_entries", 0)),
            "open_entries": int(payload.get("open_entries", 0)),
            "urgent_open_entries": int(payload.get("urgent_open_entries", 0)),
        }

    @staticmethod
    def _candidate_storage_roots() -> List[Path]:
        roots: List[Path] = []
        from_env = os.getenv("PERMANENCE_STORAGE_ROOT")
        if from_env:
            roots.append(Path(os.path.expanduser(from_env)))
        base_dir = Path(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
        roots.append(base_dir / "permanence_storage")
        roots.append(Path("/Volumes/LaCie"))
        roots.append(Path("/Volumes/LaCie_Permanence"))
        dedup: List[Path] = []
        seen = set()
        for root in roots:
            if str(root) in seen:
                continue
            seen.add(str(root))
            dedup.append(root)
        return dedup

    def _load_operator_panel(self) -> Dict[str, Any]:
        for root in self._candidate_storage_roots():
            status_path = root / "logs" / "status_today.json"
            if not status_path.exists():
                continue
            payload = self._read_json(status_path)
            if not payload:
                continue
            report_candidates = sorted((root / "logs").glob("automation_report_*.md"), reverse=True)
            latest_report = report_candidates[0].name if report_candidates else None
            return {
                "available": True,
                "today_state": payload.get("today_state", "UNKNOWN"),
                "slot_progress": payload.get("slot_progress", "0/0"),
                "streak_current": (payload.get("streak") or {}).get("current", 0),
                "streak_target": (payload.get("streak") or {}).get("target", 7),
                "phase_gate": payload.get("phase_gate", "PENDING"),
                "updated_at_utc": payload.get("updated_at_utc"),
                "status_file": str(status_path),
                "automation_report": latest_report,
            }
        return {"available": False}

    @staticmethod
    def _parse_iso(ts: Optional[str]) -> Optional[datetime]:
        if not ts:
            return None
        try:
            return datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except ValueError:
            return None

    @staticmethod
    def _zero_point_entries() -> List[Dict[str, Any]]:
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        zp_path = os.getenv("PERMANENCE_ZERO_POINT_PATH", os.path.join(base_dir, "memory", "zero_point_store.json"))
        path = Path(zp_path)
        if not path.exists():
            return []
        try:
            payload = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            return []
        entries = payload.get("entries", {})
        if not isinstance(entries, dict):
            return []
        out: List[Dict[str, Any]] = []
        for data in entries.values():
            if isinstance(data, dict):
                out.append(data)
        return out

    def _load_v04_telemetry(self) -> Dict[str, Any]:
        entries = self._zero_point_entries()
        if not entries:
            return {
                "available": False,
                "intake_24h": 0,
                "malformed_24h": 0,
                "latest_training_type": None,
                "latest_training_at": None,
                "latest_forecast_type": None,
                "latest_forecast_at": None,
                "latest_forecast_alignment_count": 0,
                "latest_forecast_branches": 0,
            }

        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        intake_24h = 0
        malformed_24h = 0
        training_rows: List[Dict[str, Any]] = []
        forecast_rows: List[Dict[str, Any]] = []

        for entry in entries:
            mem_type = str(entry.get("memory_type", "")).upper()
            author = str(entry.get("author_agent", "")).upper()
            created = self._parse_iso(entry.get("created_at") or entry.get("updated_at"))
            content = {}
            try:
                content = json.loads(str(entry.get("content", "{}")))
            except json.JSONDecodeError:
                content = {}

            if mem_type == "INTAKE" and created and created >= cutoff:
                intake_24h += 1
                if bool(content.get("malformed")) or bool(content.get("flags")):
                    malformed_24h += 1

            if mem_type == "TRAINING" and author == "PRACTICE_SQUAD":
                training_rows.append(
                    {
                        "created_at": entry.get("created_at"),
                        "type": content.get("type"),
                    }
                )

            if mem_type == "FORECAST" and author == "ARCANA":
                branches = content.get("branches")
                branch_count = len(branches) if isinstance(branches, list) else 0
                forecast_rows.append(
                    {
                        "created_at": entry.get("created_at"),
                        "type": content.get("heuristic_source") or content.get("signal_type"),
                        "alignment_count": int(content.get("alignment_count", 0) or 0),
                        "branch_count": branch_count,
                    }
                )

        floor_dt = datetime.min.replace(tzinfo=timezone.utc)
        training_rows.sort(key=lambda r: self._parse_iso(r.get("created_at")) or floor_dt, reverse=True)
        forecast_rows.sort(key=lambda r: self._parse_iso(r.get("created_at")) or floor_dt, reverse=True)
        latest_training = training_rows[0] if training_rows else {}
        latest_forecast = forecast_rows[0] if forecast_rows else {}

        return {
            "available": True,
            "intake_24h": intake_24h,
            "malformed_24h": malformed_24h,
            "latest_training_type": latest_training.get("type"),
            "latest_training_at": latest_training.get("created_at"),
            "latest_forecast_type": latest_forecast.get("type"),
            "latest_forecast_at": latest_forecast.get("created_at"),
            "latest_forecast_alignment_count": latest_forecast.get("alignment_count", 0),
            "latest_forecast_branches": latest_forecast.get("branch_count", 0),
        }

    def _load_system_health(self) -> Dict[str, Any]:
        output_dir = os.getenv(
            "PERMANENCE_OUTPUT_DIR",
            os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "outputs")),
        )
        hr_path = Path(output_dir) / "weekly_system_health_report.md"
        patterns = 0
        logos_status = "unknown"
        if hr_path.exists():
            try:
                lines = hr_path.read_text().splitlines()
            except OSError:
                lines = []
            in_patterns = False
            for line in lines:
                if line.strip().startswith("PATTERNS DETECTED"):
                    in_patterns = True
                    continue
                if in_patterns and line.strip().startswith("WINS THIS WEEK"):
                    in_patterns = False
                if in_patterns and line.strip().startswith("  "):
                    if line.strip().startswith("1.") or line.strip().startswith("2.") or line.strip().startswith("3."):
                        patterns += 1
                if line.strip().startswith("Ready:"):
                    value = line.split("Ready:", 1)[-1].strip().upper()
                    logos_status = "READY" if value.startswith("YES") else "DORMANT"
        episodic_count = self._count_episodic_entries_24h()
        return {
            "patterns_detected": patterns,
            "compliance_holds": 0,
            "episodic_entries_24h": episodic_count,
            "logos_status": logos_status,
        }

    def _load_documents_summary(self) -> Dict[str, Any]:
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        sources_path = os.getenv(
            "PERMANENCE_SOURCES_PATH",
            os.path.join(base_dir, "memory", "working", "sources.json"),
        )
        if not os.path.exists(sources_path):
            return {"missing": True, "count": 0, "items": []}
        try:
            with open(sources_path, "r") as f:
                sources = json.load(f)
        except (OSError, json.JSONDecodeError):
            return {"missing": True, "count": 0, "items": []}
        if not isinstance(sources, list):
            return {"missing": True, "count": 0, "items": []}

        items: List[Dict[str, Any]] = []
        for src in sources:
            origin = str(src.get("origin") or "")
            if "memory/working/documents" in origin or origin in {"google_docs", "drive_pdf"}:
                title = src.get("title") or src.get("source") or origin
                items.append(
                    {
                        "title": title,
                        "timestamp": src.get("timestamp"),
                        "notes": src.get("notes"),
                        "origin": origin,
                    }
                )

        def _parse_ts(ts: Optional[str]) -> datetime:
            if not ts:
                return datetime.min.replace(tzinfo=timezone.utc)
            try:
                return datetime.fromisoformat(ts.replace("Z", "+00:00"))
            except ValueError:
                return datetime.min.replace(tzinfo=timezone.utc)

        items.sort(key=lambda i: _parse_ts(i.get("timestamp")), reverse=True)
        excerpt_items: List[Tuple[str, str]] = []
        for item in items:
            note = item.get("notes")
            if note:
                excerpt_items.append((item.get("title") or "Untitled", note))
            if len(excerpt_items) >= 3:
                break
        return {
            "missing": False,
            "count": len(items),
            "items": items,
            "excerpts": excerpt_items,
        }

    def _load_chronicle_summary(self) -> Dict[str, Any]:
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        shared_path = Path(
            os.getenv(
                "PERMANENCE_CHRONICLE_SHARED_PATH",
                str(Path(base_dir) / "memory" / "chronicle" / "shared" / "chronicle_latest.json"),
            )
        )
        chronicle_output = Path(
            os.getenv(
                "PERMANENCE_CHRONICLE_OUTPUT_DIR",
                str(Path(base_dir) / "outputs" / "chronicle"),
            )
        )

        candidates: List[Path] = []
        if shared_path.exists():
            candidates.append(shared_path)
        if chronicle_output.exists():
            candidates.extend(
                sorted(
                    chronicle_output.glob("chronicle_report_*.json"),
                    key=lambda p: p.stat().st_mtime,
                    reverse=True,
                )
            )

        selected: Optional[Path] = None
        payload: Optional[Dict[str, Any]] = None
        for candidate in candidates:
            try:
                data = json.loads(candidate.read_text())
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(data, dict):
                selected = candidate
                payload = data
                break

        if not payload:
            return {"available": False}

        totals = payload.get("signal_totals") or {}
        direction_events = payload.get("direction_events") or []
        issue_events = payload.get("issue_events") or []
        return {
            "available": True,
            "path": str(selected) if selected else None,
            "generated_at": payload.get("generated_at"),
            "days": payload.get("days"),
            "events_count": payload.get("events_count", 0),
            "commit_count": payload.get("commit_count", 0),
            "direction_hits": int(totals.get("direction_hits", 0) or 0),
            "frustration_hits": int(totals.get("frustration_hits", 0) or 0),
            "issue_hits": int(totals.get("issue_hits", 0) or 0),
            "log_error_hits": int(totals.get("log_error_hits", 0) or 0),
            "direction_events": direction_events[-3:],
            "issue_events": issue_events[-3:],
        }

    @staticmethod
    def _count_episodic_entries_24h() -> int:
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        memory_dir = os.getenv("PERMANENCE_MEMORY_DIR", os.path.join(base_dir, "memory"))
        episodic_dir = Path(memory_dir) / "episodic"
        if not episodic_dir.exists():
            return 0
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        count = 0
        for path in episodic_dir.glob("episodic_*.jsonl"):
            try:
                for line in path.read_text().splitlines():
                    if not line.strip():
                        continue
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    ts = entry.get("timestamp")
                    if not ts:
                        continue
                    try:
                        parsed = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    except ValueError:
                        continue
                    if parsed >= cutoff:
                        count += 1
            except OSError:
                continue
        return count

    @staticmethod
    def _recommendation_from_health(health: Dict[str, Any]) -> Optional[str]:
        if health.get("not_connected"):
            return None
        recovery = health.get("avg_recovery")
        sleep = health.get("avg_sleep_hours")
        if isinstance(recovery, (int, float)) and recovery < 70:
            return "Light day. Prioritize recovery."
        if isinstance(sleep, (int, float)) and sleep < 7:
            return "Prioritize sleep and recovery."
        return None

    def _generate_focus(
        self, email: Dict[str, Any], health: Dict[str, Any], social: Dict[str, Any]
    ) -> List[str]:
        focus: List[str] = []
        for item in email.get("p2_items", [])[:3]:
            focus.append(f"Handle email: {item}")
        health_note = self._recommendation_from_health(health)
        if health_note:
            focus.append(health_note)
        if social.get("drafts_ready", 0) > 0:
            focus.append(f"Review {social.get('drafts_ready')} social drafts")
        if not focus:
            focus.append("Review the daily briefing and set top priorities.")
        return focus[:5]

    @staticmethod
    def _latest_status_snapshot() -> Optional[Dict[str, Any]]:
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        memory_dir = os.getenv("PERMANENCE_MEMORY_DIR", os.path.join(base_dir, "memory"))
        log_dir = os.getenv("PERMANENCE_LOG_DIR", os.path.join(base_dir, "logs"))
        output_dir = os.getenv("PERMANENCE_OUTPUT_DIR", os.path.join(base_dir, "outputs"))
        episodic_dir = os.path.join(memory_dir, "episodic")

        def _latest_file(path: str, ext: str) -> Optional[str]:
            if not os.path.isdir(path):
                return None
            files = [f for f in os.listdir(path) if f.endswith(ext)]
            if not files:
                return None
            files.sort(key=lambda f: os.path.getmtime(os.path.join(path, f)), reverse=True)
            return os.path.join(path, files[0])

        latest_state = _latest_file(episodic_dir, ".json")
        latest_log = _latest_file(log_dir, ".log")
        output_count = len([f for f in os.listdir(output_dir) if f.endswith(".md")]) if os.path.isdir(output_dir) else 0

        if not latest_state:
            return {
                "task_id": None,
                "stage": None,
                "status": None,
                "risk_tier": None,
                "goal": None,
                "latest_log": os.path.basename(latest_log) if latest_log else None,
                "outputs": output_count,
            }

        try:
            with open(latest_state, "r") as f:
                state = json.load(f)
        except (OSError, json.JSONDecodeError):
            state = {}

        return {
            "task_id": state.get("task_id"),
            "stage": state.get("stage"),
            "status": state.get("status"),
            "risk_tier": state.get("risk_tier"),
            "goal": state.get("task_goal"),
            "latest_log": os.path.basename(latest_log) if latest_log else None,
            "outputs": output_count,
        }

    @staticmethod
    def _read_excerpt(path: Path, max_lines: int = 6) -> str:
        try:
            with open(path, "r") as f:
                lines = []
                for _ in range(max_lines):
                    line = f.readline()
                    if not line:
                        break
                    line = line.rstrip()
                    if line:
                        lines.append(line)
            return " | ".join(lines)
        except OSError:
            return ""

    def _section_system_status(self) -> List[str]:
        snapshot = self._latest_status_snapshot()
        lines = ["## System Status"]
        if not snapshot:
            lines.append("- No status snapshot available")
            lines.append("")
            return lines
        lines.append(f"- Latest Task: {snapshot.get('task_id') or 'none'}")
        if snapshot.get("stage") or snapshot.get("status"):
            lines.append(f"- Stage/Status: {snapshot.get('stage')} / {snapshot.get('status')}")
        if snapshot.get("risk_tier"):
            lines.append(f"- Risk Tier: {snapshot.get('risk_tier')}")
        if snapshot.get("goal"):
            lines.append(f"- Goal: {snapshot.get('goal')}")
        lines.append(f"- Outputs (md): {snapshot.get('outputs')}")
        if snapshot.get("latest_log"):
            lines.append(f"- Latest Log: {snapshot.get('latest_log')}")
        lines.append("")
        return lines

    def _section_openclaw(self) -> List[str]:
        lines = ["## OpenClaw"]
        status = self._latest_openclaw_status()
        health = self._latest_openclaw_health()
        if status:
            lines.append(f"- {status}")
        if health:
            lines.append(f"- {health}")
        if not status and not health:
            lines.append("- No OpenClaw status captured")
        lines.append("")
        return lines

    def _section_email_summary(self, summary: Dict[str, Any]) -> List[str]:
        lines = ["## Email"]
        if summary.get("missing"):
            lines.append("- No email triage report found")
            lines.append("")
            return lines
        p2_items = summary.get("p2_items", [])
        p2_count = summary.get("p2", 0)
        p3_count = summary.get("p3", 0)
        lines.append(f"- P2: {p2_count} items needing action")
        if p2_items:
            for item in p2_items[:5]:
                lines.append(f"  - {item}")
        lines.append(f"- P3: {p3_count} items auto-archived")
        inbox_zero = (summary.get("p0", 0) + summary.get("p1", 0) + summary.get("p2", 0)) == 0
        lines.append(f"- Inbox zero: {'YES' if inbox_zero else 'NO'}")
        lines.append("")
        return lines

    def _section_health_summary(self, summary: Dict[str, Any]) -> List[str]:
        lines = ["## Health"]
        if summary.get("not_connected"):
            lines.append("- Health data not connected")
            lines.append("")
            return lines
        lines.append(f"- Sleep (avg): {summary.get('avg_sleep_hours')}")
        lines.append(f"- HRV (avg): {summary.get('avg_hrv')}")
        lines.append(f"- Recovery (avg): {summary.get('avg_recovery')}")
        lines.append(f"- Strain (avg): {summary.get('avg_strain')}")
        latest = summary.get("latest") or {}
        if latest:
            lines.append("- Latest entry:")
            for key in ["date", "sleep_hours", "hrv", "recovery_score", "strain"]:
                if key in latest:
                    lines.append(f"  - {key}: {latest.get(key)}")
        recommendation = self._recommendation_from_health(summary)
        if recommendation:
            lines.append(f"- Recommendation: {recommendation}")
        lines.append("")
        return lines

    def _section_social_summary(self, summary: Dict[str, Any]) -> List[str]:
        lines = ["## Social"]
        if summary.get("not_connected"):
            lines.append("- Social data not connected")
            lines.append("")
            return lines
        lines.append(f"- Notifications: {summary.get('notifications', 0)}")
        lines.append(f"- DMs pending: {summary.get('dms_pending', 0)}")
        lines.append(f"- Draft queue: {summary.get('drafts_ready', 0)} ready")
        lines.append("")
        return lines

    def _section_reception_summary(self, summary: Dict[str, Any]) -> List[str]:
        name = os.getenv("PERMANENCE_RECEPTIONIST_NAME", "Ari").strip() or "Ari"
        lines = [f"## {name} Reception"]
        if summary.get("not_connected"):
            lines.append(f"- {name} queue not connected yet")
            lines.append("")
            return lines
        lines.append(f"- Total entries: {summary.get('total_entries', 0)}")
        lines.append(f"- Open entries: {summary.get('open_entries', 0)}")
        lines.append(f"- Urgent open entries: {summary.get('urgent_open_entries', 0)}")
        lines.append("")
        return lines

    def _section_operator_panel(self, panel: Dict[str, Any]) -> List[str]:
        lines = ["## Operator Panel"]
        if not panel.get("available"):
            lines.append("- Status glance not available yet")
            lines.append("")
            return lines
        lines.append(f"- Today gate: {panel.get('today_state')} ({panel.get('slot_progress')})")
        lines.append(f"- Reliability streak: {panel.get('streak_current')}/{panel.get('streak_target')}")
        lines.append(f"- Weekly phase gate: {panel.get('phase_gate')}")
        lines.append(f"- Updated (UTC): {panel.get('updated_at_utc')}")
        if panel.get("automation_report"):
            lines.append(f"- Automation report: {panel.get('automation_report')}")
        lines.append("")
        return lines

    def _section_v04_telemetry(self, telemetry: Dict[str, Any]) -> List[str]:
        lines = ["## V0.4 Telemetry"]
        if not telemetry.get("available"):
            lines.append("- Zero Point telemetry not available yet")
            lines.append("")
            return lines
        lines.append(
            f"- Interface intake (24h): {telemetry.get('intake_24h', 0)} "
            f"(malformed: {telemetry.get('malformed_24h', 0)})"
        )
        lines.append(
            f"- Practice Squad latest: {telemetry.get('latest_training_type') or 'none'} "
            f"at {telemetry.get('latest_training_at') or 'n/a'}"
        )
        lines.append(
            f"- Arcana latest: {telemetry.get('latest_forecast_type') or 'none'} "
            f"at {telemetry.get('latest_forecast_at') or 'n/a'}"
        )
        lines.append(
            f"- Arcana detail: alignments={telemetry.get('latest_forecast_alignment_count', 0)} "
            f"branches={telemetry.get('latest_forecast_branches', 0)}"
        )
        lines.append("")
        return lines

    def _section_documents(self, summary: Dict[str, Any]) -> List[str]:
        lines = ["## Documents"]
        if summary.get("missing") or summary.get("count", 0) == 0:
            lines.append("- No document sources found in sources.json")
            lines.append("")
            return lines
        lines.append(f"- Sources: {summary.get('count')}")
        for item in summary.get("items", [])[:5]:
            title = item.get("title") or "Untitled"
            ts = item.get("timestamp") or "unknown"
            lines.append(f"  - {title} ({ts})")
        excerpts = summary.get("excerpts") or []
        if excerpts:
            lines.append("- Top excerpts:")
            for title, note in excerpts:
                lines.append(f"  - {title}: {note}")
        lines.append("")
        return lines

    def _section_chronicle(self, summary: Dict[str, Any]) -> List[str]:
        lines = ["## Chronicle Intelligence"]
        if not summary.get("available"):
            lines.append("- No chronicle report found")
            lines.append("")
            return lines

        lines.append(
            f"- Window: {summary.get('days')}d | Events: {summary.get('events_count')} "
            f"| Commits: {summary.get('commit_count')}"
        )
        lines.append(
            f"- Signals: direction={summary.get('direction_hits')} "
            f"frustration={summary.get('frustration_hits')} "
            f"issues={summary.get('issue_hits')} "
            f"log_errors={summary.get('log_error_hits')}"
        )
        if summary.get("generated_at"):
            lines.append(f"- Report generated: {summary.get('generated_at')}")
        if summary.get("path"):
            lines.append(f"- Source: {summary.get('path')}")

        direction_events = summary.get("direction_events") or []
        if direction_events:
            lines.append("- Direction shifts:")
            for item in direction_events:
                lines.append(f"  - {item.get('timestamp', 'unknown')}: {item.get('summary', '')}")

        issue_events = summary.get("issue_events") or []
        if issue_events:
            lines.append("- Friction events:")
            for item in issue_events:
                lines.append(f"  - {item.get('timestamp', 'unknown')}: {item.get('summary', '')}")

        lines.append("")
        return lines

    def _section_focus(self, focus: List[str]) -> List[str]:
        lines = ["## Today's Focus"]
        for idx, item in enumerate(focus, 1):
            lines.append(f"{idx}. {item}")
        lines.append("")
        return lines

    def _section_system_health(self, summary: Dict[str, Any]) -> List[str]:
        lines = ["## System Health"]
        lines.append(f"- HR patterns detected: {summary.get('patterns_detected')}")
        lines.append(f"- Compliance holds: {summary.get('compliance_holds')}")
        lines.append(f"- Episodic entries (24h): {summary.get('episodic_entries_24h')}")
        lines.append(f"- Logos Praktikos: {summary.get('logos_status')}")
        lines.append("")
        return lines

    def _section_outputs(self) -> List[str]:
        output_dir = os.getenv(
            "PERMANENCE_OUTPUT_DIR",
            os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "outputs")),
        )
        lines = ["## Recent Outputs"]
        try:
            candidates = sorted(
                Path(output_dir).glob("*.md"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
        except FileNotFoundError:
            candidates = []
        if not candidates:
            lines.append("- (none)")
            lines.append("")
            return lines
        for path in candidates[:5]:
            lines.append(f"- {path.name}")
        lines.append("")
        return lines

    @staticmethod
    def _latest_social_summary() -> Optional[str]:
        output_dir = os.getenv(
            "PERMANENCE_OUTPUT_DIR",
            os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "outputs")),
        )
        try:
            candidates = sorted(
                Path(output_dir).glob("social_summary_*.md"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
        except FileNotFoundError:
            return None
        if not candidates:
            return None
        latest = candidates[0]
        excerpt = BriefingAgent._read_excerpt(latest, max_lines=6)
        if excerpt:
            return f"Social summary: {excerpt}"
        return f"Social summary captured: {latest}"

    @staticmethod
    def _latest_health_summary() -> Optional[str]:
        output_dir = os.getenv(
            "PERMANENCE_OUTPUT_DIR",
            os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "outputs")),
        )
        try:
            candidates = sorted(
                Path(output_dir).glob("health_summary_*.md"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
        except FileNotFoundError:
            return None
        if not candidates:
            return None
        latest = candidates[0]
        excerpt = BriefingAgent._read_excerpt(latest, max_lines=6)
        if excerpt:
            return f"Health summary: {excerpt}"
        return f"Health summary captured: {latest}"
