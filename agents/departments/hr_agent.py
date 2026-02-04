#!/usr/bin/env python3
"""
HR Agent (The Shepherd)
System health and agent relations monitor.
Observation + recommendation only.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import json
import os

from agents.utils import log, BASE_DIR

MEMORY_DIR = os.getenv("PERMANENCE_MEMORY_DIR", os.path.join(BASE_DIR, "memory"))
EPISODIC_DIR = os.path.join(MEMORY_DIR, "episodic")
LOG_DIR = os.getenv("PERMANENCE_LOG_DIR", os.path.join(BASE_DIR, "logs"))
OUTPUT_DIR = os.getenv("PERMANENCE_OUTPUT_DIR", os.path.join(BASE_DIR, "outputs"))
HISTORY_PATH = os.getenv(
    "PERMANENCE_HR_HISTORY", os.path.join(LOG_DIR, "hr_agent_history.json")
)

AGENT_NAMES = [
    "polemarch",
    "planner",
    "researcher",
    "executor",
    "reviewer",
    "conciliator",
    "compliance_gate",
    "hr_agent",
    "email_agent",
    "device_agent",
    "social_agent",
    "health_agent",
    "briefing_agent",
    "trainer_agent",
    "therapist_agent",
]


class HealthStatus(Enum):
    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    NEEDS_ATTENTION = "needs_attention"
    CRITICAL = "critical"


class ConcernLevel(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class PatternType(Enum):
    BOTTLENECK = "bottleneck"
    AVOIDANCE = "avoidance"
    CLUSTERING = "clustering"
    ISOLATION = "isolation"
    TRIANGULATION = "triangulation"
    SCAPEGOATING = "scapegoating"
    ENMESHMENT = "enmeshment"
    TOOL_DEGRADATION = "tool_degradation"


@dataclass
class AgentMetrics:
    agent_name: str
    tasks_processed: int = 0
    retries: int = 0
    escalations: int = 0
    budget_overruns: int = 0
    avg_execution_time: float = 0.0
    canon_consultations: int = 0
    total_reviews: int = 0
    rejections: int = 0
    last_active: Optional[datetime] = None
    relationships: Dict[str, int] = field(default_factory=dict)

    @property
    def retry_rate(self) -> float:
        if self.tasks_processed == 0:
            return 0.0
        return (self.retries / self.tasks_processed) * 100

    @property
    def escalation_rate(self) -> float:
        if self.tasks_processed == 0:
            return 0.0
        return (self.escalations / self.tasks_processed) * 100

    @property
    def rejection_rate(self) -> float:
        if self.total_reviews == 0:
            return 0.0
        return (self.rejections / self.total_reviews) * 100

    @property
    def health_status(self) -> HealthStatus:
        score = 100
        if self.retry_rate > 25:
            score -= 30
        elif self.retry_rate > 15:
            score -= 15
        elif self.retry_rate > 10:
            score -= 5

        if self.escalation_rate > 30:
            score -= 25
        elif self.escalation_rate > 20:
            score -= 10

        if self.rejection_rate > 35:
            score -= 25
        elif self.rejection_rate > 20:
            score -= 10

        overrun_rate = (self.budget_overruns / max(self.tasks_processed, 1)) * 100
        if overrun_rate > 15:
            score -= 20
        elif overrun_rate > 5:
            score -= 10

        if score >= 90:
            return HealthStatus.EXCELLENT
        if score >= 75:
            return HealthStatus.GOOD
        if score >= 60:
            return HealthStatus.FAIR
        if score >= 40:
            return HealthStatus.NEEDS_ATTENTION
        return HealthStatus.CRITICAL


@dataclass
class DetectedPattern:
    pattern_type: PatternType
    description: str
    evidence: List[str]
    agents_involved: List[str]
    concern_level: ConcernLevel
    detected_at: datetime
    recommendation: str


@dataclass
class SystemHealthReport:
    week_start: datetime
    week_end: datetime
    overall_score: int
    trend: str
    agent_metrics: Dict[str, AgentMetrics]
    patterns_detected: List[DetectedPattern]
    wins: List[str]
    recommendations: List[str]
    canon_alignment_rate: float
    source_quality_rate: float
    avg_execution_time: float
    compliance_hold_rate: float
    openclaw_status_path: Optional[str]
    logos_praktikos_ready: bool
    logos_praktikos_blockers: List[str]


class HRAgent:
    """
    The Shepherd - monitors system health and agent relations.
    Read-only, recommendation-only.
    """

    HEALTHY_RETRY_RATE = 10.0
    ALERT_RETRY_RATE = 25.0
    HEALTHY_ESCALATION_MIN = 5.0
    HEALTHY_ESCALATION_MAX = 15.0
    ALERT_ESCALATION_RATE = 30.0
    HEALTHY_REJECTION_RATE = 15.0
    ALERT_REJECTION_RATE = 35.0
    HEALTHY_BUDGET_OVERRUN = 5.0
    ALERT_BUDGET_OVERRUN = 15.0
    CANON_ALIGNMENT_TARGET = 95.0

    LOGOS_MIN_WEEKS_HEALTHY = 12
    LOGOS_MIN_WEEKS_NO_HIGH_PATTERNS = 8
    LOGOS_MIN_HEALTH_SCORE = 85

    def __init__(self, memory_dir: Optional[str] = None, logs_dir: Optional[str] = None):
        self.memory_dir = Path(memory_dir or MEMORY_DIR)
        self.logs_dir = Path(logs_dir or LOG_DIR)
        self.episodic_dir = self.memory_dir / "episodic"
        self.agent_metrics: Dict[str, AgentMetrics] = {
            name: AgentMetrics(agent_name=name) for name in AGENT_NAMES
        }
        self.historical_scores: List[Tuple[datetime, int]] = []
        self.detected_patterns: List[DetectedPattern] = []
        self.relationship_map: Dict[str, Dict[str, int]] = {}
        self.source_quality_rate: float = 0.0
        self.avg_execution_time: float = 0.0
        self.compliance_hold_rate: float = 0.0
        self.openclaw_status_path: Optional[str] = None

        self.family_covenant = {
            "common_goal": "Build Permanence. Compound judgment. Become extraordinary without becoming evil.",
            "principles": [
                "Every agent serves the whole",
                "No agent is more important than the system",
                "Disagreements are surfaced, not suppressed",
                "Conflict is data, not failure",
                "We celebrate wins together",
                "We fail and learn together",
            ],
        }

        self._load_history()

    def _load_history(self) -> None:
        if Path(HISTORY_PATH).exists():
            try:
                with open(HISTORY_PATH, "r") as f:
                    data = json.load(f)
                self.historical_scores = [
                    (datetime.fromisoformat(d), s) for d, s in data.get("scores", [])
                ]
            except (OSError, json.JSONDecodeError, ValueError):
                self.historical_scores = []

    def _save_history(self) -> None:
        os.makedirs(self.logs_dir, exist_ok=True)
        data = {
            "scores": [
                (d.isoformat(), s) for d, s in self.historical_scores[-52:]
            ]
        }
        with open(HISTORY_PATH, "w") as f:
            json.dump(data, f, indent=2)

    def _load_episodes(self, since: Optional[datetime] = None, until: Optional[datetime] = None) -> List[Dict[str, Any]]:
        episodes: List[Dict[str, Any]] = []
        if not self.episodic_dir.exists():
            return episodes

        for name in os.listdir(self.episodic_dir):
            if not name.endswith(".json"):
                continue
            path = self.episodic_dir / name
            try:
                with open(path, "r") as f:
                    data = json.load(f)
            except (OSError, json.JSONDecodeError):
                continue

            updated_at = self._parse_dt(data.get("updated_at")) or self._parse_dt(data.get("created_at"))
            if since and updated_at and updated_at < since:
                continue
            if until and updated_at and updated_at > until:
                continue

            episodes.append(data)

        return episodes

    def _parse_dt(self, value: Optional[str]) -> Optional[datetime]:
        if not value:
            return None
        try:
            dt = datetime.fromisoformat(value)
        except ValueError:
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt

    def collect_metrics(self, since: Optional[datetime] = None, until: Optional[datetime] = None) -> Dict[str, AgentMetrics]:
        self.agent_metrics = {name: AgentMetrics(agent_name=name) for name in AGENT_NAMES}
        episodes = self._load_episodes(since=since, until=until)

        total_sources = 0
        high_sources = 0
        total_exec_time = 0.0
        exec_time_count = 0
        compliance_total = 0
        compliance_holds = 0
        compliance_rejects = 0

        for episode in episodes:
            logs = episode.get("logs", []) if isinstance(episode.get("logs"), list) else []
            last_agent: Optional[str] = None

            created_at = self._parse_dt(episode.get("created_at"))
            updated_at = self._parse_dt(episode.get("updated_at"))
            if created_at and updated_at:
                total_exec_time += (updated_at - created_at).total_seconds()
                exec_time_count += 1

            review_outcome = None
            for line in logs:
                message = self._extract_message(line)
                if not message:
                    continue

                if "Routing to agent:" in message:
                    agent = message.split("Routing to agent:", 1)[-1].strip()
                    if agent in self.agent_metrics:
                        self.agent_metrics[agent].tasks_processed += 1
                        if updated_at:
                            self.agent_metrics[agent].last_active = updated_at
                        if last_agent and last_agent != agent:
                            self._register_relationship(last_agent, agent)
                        last_agent = agent

                if "Validating task against Canon" in message:
                    self.agent_metrics["polemarch"].canon_consultations += 1

                if "ESCALATING TO HUMAN" in message:
                    self.agent_metrics["polemarch"].escalations += 1

                if "BUDGET EXCEEDED" in message or "Budget exceeded" in message:
                    self.agent_metrics["polemarch"].budget_overruns += 1

                if "Retry recommended" in message or "Conciliator decision: ESCALATE" in message:
                    self.agent_metrics["conciliator"].retries += 1
                    review_outcome = "rejected"

                if "Conciliator decision: ACCEPT" in message:
                    review_outcome = "accepted"

            if review_outcome:
                reviewer = self.agent_metrics["reviewer"]
                reviewer.total_reviews += 1
                if review_outcome == "rejected":
                    reviewer.rejections += 1

            compliance = episode.get("artifacts", {}).get("compliance") if isinstance(episode.get("artifacts"), dict) else None
            if isinstance(compliance, dict):
                verdict = compliance.get("verdict")
                if verdict:
                    compliance_total += 1
                if verdict == "HOLD":
                    compliance_holds += 1
                if verdict == "REJECT":
                    compliance_rejects += 1
                if verdict in {"HOLD", "REJECT"}:
                    self.agent_metrics["compliance_gate"].escalations += 1

            sources = episode.get("sources", []) if isinstance(episode.get("sources"), list) else []
            for src in sources:
                total_sources += 1
                conf = src.get("confidence")
                try:
                    if conf is not None and float(conf) >= 0.8:
                        high_sources += 1
                except (TypeError, ValueError):
                    continue

        if total_sources:
            self.source_quality_rate = (high_sources / total_sources) * 100
        else:
            self.source_quality_rate = 0.0

        if exec_time_count:
            self.avg_execution_time = total_exec_time / exec_time_count
        else:
            self.avg_execution_time = 0.0

        if compliance_total:
            self.compliance_hold_rate = (compliance_holds / compliance_total) * 100
        else:
            self.compliance_hold_rate = 0.0

        return self.agent_metrics

    def _register_relationship(self, agent_a: str, agent_b: str) -> None:
        if agent_a in self.agent_metrics:
            self.agent_metrics[agent_a].relationships[agent_b] = (
                self.agent_metrics[agent_a].relationships.get(agent_b, 0) + 1
            )
        if agent_b in self.agent_metrics:
            self.agent_metrics[agent_b].relationships[agent_a] = (
                self.agent_metrics[agent_b].relationships.get(agent_a, 0) + 1
            )

    def _extract_message(self, line: str) -> str:
        if not isinstance(line, str):
            return ""
        parts = line.split("] ", 2)
        if len(parts) == 3:
            return parts[2].strip()
        return line.strip()

    def detect_patterns(self) -> List[DetectedPattern]:
        self.detected_patterns = []
        self._detect_bottleneck()
        self._detect_avoidance()
        self._detect_clustering()
        self._detect_isolation()
        self._detect_triangulation()
        self._detect_scapegoating()
        self._detect_enmeshment()
        return self.detected_patterns

    def _detect_bottleneck(self) -> None:
        counts = [(name, m.tasks_processed) for name, m in self.agent_metrics.items()]
        if not counts:
            return
        avg = sum(c for _, c in counts) / max(len(counts), 1)
        for name, count in counts:
            if count > avg * 2 and count > 5:
                self.detected_patterns.append(
                    DetectedPattern(
                        pattern_type=PatternType.BOTTLENECK,
                        description=f"{name} handles {count} tasks vs avg {avg:.1f}",
                        evidence=[f"{name}: {count}", f"avg: {avg:.1f}"],
                        agents_involved=[name],
                        concern_level=ConcernLevel.MEDIUM,
                        detected_at=datetime.now(timezone.utc),
                        recommendation=f"Redistribute workload from {name} or add capacity.",
                    )
                )

    def _detect_avoidance(self) -> None:
        counts = [(name, m.tasks_processed) for name, m in self.agent_metrics.items()]
        if not counts:
            return
        avg = sum(c for _, c in counts) / max(len(counts), 1)
        for name, count in counts:
            if avg > 5 and count < avg * 0.25:
                self.detected_patterns.append(
                    DetectedPattern(
                        pattern_type=PatternType.AVOIDANCE,
                        description=f"{name} appears underused ({count} vs avg {avg:.1f})",
                        evidence=[f"{name}: {count}", f"avg: {avg:.1f}"],
                        agents_involved=[name],
                        concern_level=ConcernLevel.HIGH,
                        detected_at=datetime.now(timezone.utc),
                        recommendation=f"Check if {name} is being bypassed due to misconfig or quality issues.",
                    )
                )

    def _detect_clustering(self) -> None:
        seen_pairs = set()
        for name, metrics in self.agent_metrics.items():
            total = sum(metrics.relationships.values())
            if total < 5:
                continue
            for other, count in metrics.relationships.items():
                if other not in self.agent_metrics:
                    continue
                ratio = count / total if total else 0.0
                other_metrics = self.agent_metrics[other]
                other_total = sum(other_metrics.relationships.values())
                if other_total == 0:
                    continue
                other_ratio = other_metrics.relationships.get(name, 0) / other_total
                if ratio >= 0.6 and other_ratio >= 0.6:
                    pair = tuple(sorted([name, other]))
                    if pair in seen_pairs:
                        continue
                    seen_pairs.add(pair)
                    self.detected_patterns.append(
                        DetectedPattern(
                            pattern_type=PatternType.CLUSTERING,
                            description=f"{pair[0]} and {pair[1]} are tightly clustered",
                            evidence=[
                                f"{name}->{other}: {count}",
                                f"{other}->{name}: {other_metrics.relationships.get(name, 0)}",
                            ],
                            agents_involved=[pair[0], pair[1]],
                            concern_level=ConcernLevel.MEDIUM,
                            detected_at=datetime.now(timezone.utc),
                            recommendation="Review whether clustering is intentional or causing narrow routing.",
                        )
                    )

    def _detect_enmeshment(self) -> None:
        seen_pairs = set()
        for name, metrics in self.agent_metrics.items():
            total = sum(metrics.relationships.values())
            if total < 5 or len(metrics.relationships) != 1:
                continue
            other, count = next(iter(metrics.relationships.items()))
            ratio = count / total if total else 0.0
            if ratio < 0.8:
                continue
            other_metrics = self.agent_metrics.get(other)
            if not other_metrics:
                continue
            other_total = sum(other_metrics.relationships.values())
            if other_total == 0:
                continue
            other_ratio = other_metrics.relationships.get(name, 0) / other_total
            if other_ratio < 0.8:
                continue
            pair = tuple(sorted([name, other]))
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)
            self.detected_patterns.append(
                DetectedPattern(
                    pattern_type=PatternType.ENMESHMENT,
                    description=f"{pair[0]} and {pair[1]} show enmeshment (limited independent routing)",
                    evidence=[
                        f"{name}->{other}: {count}",
                        f"{other}->{name}: {other_metrics.relationships.get(name, 0)}",
                    ],
                    agents_involved=[pair[0], pair[1]],
                    concern_level=ConcernLevel.MEDIUM,
                    detected_at=datetime.now(timezone.utc),
                    recommendation="Check if the pair can operate independently; add alternate routing paths.",
                )
            )

    def _detect_isolation(self) -> None:
        for name, metrics in self.agent_metrics.items():
            if metrics.tasks_processed > 5 and len(metrics.relationships) < 2:
                self.detected_patterns.append(
                    DetectedPattern(
                        pattern_type=PatternType.ISOLATION,
                        description=f"{name} has limited interactions",
                        evidence=[f"connections: {len(metrics.relationships)}"],
                        agents_involved=[name],
                        concern_level=ConcernLevel.LOW,
                        detected_at=datetime.now(timezone.utc),
                        recommendation=f"Verify {name} integration and routing.",
                    )
                )

    def _detect_triangulation(self) -> None:
        agents = [
            name
            for name, metrics in self.agent_metrics.items()
            if metrics.tasks_processed > 0 and metrics.escalations / metrics.tasks_processed > 0.3
        ]
        if len(agents) >= 2:
            self.detected_patterns.append(
                DetectedPattern(
                    pattern_type=PatternType.TRIANGULATION,
                    description="Multiple agents show high escalation rates",
                    evidence=[f"{a}" for a in agents],
                    agents_involved=agents,
                    concern_level=ConcernLevel.HIGH,
                    detected_at=datetime.now(timezone.utc),
                    recommendation="Review escalation causes and clarify resolution paths.",
                )
            )

    def _detect_scapegoating(self) -> None:
        rates = [m.rejection_rate for m in self.agent_metrics.values() if m.total_reviews > 0]
        if not rates:
            return
        avg = sum(rates) / len(rates)
        for name, metrics in self.agent_metrics.items():
            if metrics.total_reviews > 0 and metrics.rejection_rate > avg * 2.5 and metrics.rejection_rate > self.ALERT_REJECTION_RATE:
                self.detected_patterns.append(
                    DetectedPattern(
                        pattern_type=PatternType.SCAPEGOATING,
                        description=f"{name} rejection rate {metrics.rejection_rate:.1f}% vs avg {avg:.1f}%",
                        evidence=[f"{name}: {metrics.rejection_rate:.1f}%", f"avg: {avg:.1f}%"],
                        agents_involved=[name],
                        concern_level=ConcernLevel.HIGH,
                        detected_at=datetime.now(timezone.utc),
                        recommendation=f"Investigate inputs or specs feeding {name}.",
                    )
                )

    def calculate_system_health_score(self) -> int:
        score = 100
        total_tasks = sum(m.tasks_processed for m in self.agent_metrics.values())
        total_retries = sum(m.retries for m in self.agent_metrics.values())
        total_escalations = sum(m.escalations for m in self.agent_metrics.values())
        total_overruns = sum(m.budget_overruns for m in self.agent_metrics.values())

        if total_tasks > 0:
            retry_rate = (total_retries / total_tasks) * 100
            esc_rate = (total_escalations / total_tasks) * 100
            overrun_rate = (total_overruns / total_tasks) * 100

            if retry_rate > self.ALERT_RETRY_RATE:
                score -= 20
            elif retry_rate > self.HEALTHY_RETRY_RATE:
                score -= 10

            if esc_rate > self.ALERT_ESCALATION_RATE:
                score -= 15
            elif esc_rate < self.HEALTHY_ESCALATION_MIN:
                score -= 5

            if overrun_rate > self.ALERT_BUDGET_OVERRUN:
                score -= 15
            elif overrun_rate > self.HEALTHY_BUDGET_OVERRUN:
                score -= 5

        for pattern in self.detected_patterns:
            if pattern.concern_level == ConcernLevel.HIGH:
                score -= 10
            elif pattern.concern_level == ConcernLevel.MEDIUM:
                score -= 5

        for metrics in self.agent_metrics.values():
            if metrics.health_status == HealthStatus.CRITICAL:
                score -= 10
            elif metrics.health_status == HealthStatus.NEEDS_ATTENTION:
                score -= 5

        return max(0, min(100, score))

    def determine_trend(self) -> str:
        if len(self.historical_scores) < 2:
            return "stable"
        recent = [s for _, s in self.historical_scores[-4:]]
        if len(recent) < 2:
            return "stable"
        avg_recent = sum(recent) / len(recent)
        older = [s for _, s in self.historical_scores[-8:-4]]
        avg_older = sum(older) / len(older) if older else recent[0]
        diff = avg_recent - avg_older
        if diff > 5:
            return "improving"
        if diff < -5:
            return "declining"
        return "stable"

    def check_logos_praktikos_readiness(self) -> Tuple[bool, List[str]]:
        blockers: List[str] = []
        healthy_weeks = 0
        for _, score in reversed(self.historical_scores):
            if score >= self.LOGOS_MIN_HEALTH_SCORE:
                healthy_weeks += 1
            else:
                break
        if healthy_weeks < self.LOGOS_MIN_WEEKS_HEALTHY:
            blockers.append(
                f"Need {self.LOGOS_MIN_WEEKS_HEALTHY} consecutive weeks >= {self.LOGOS_MIN_HEALTH_SCORE}. Currently {healthy_weeks}."
            )

        high_patterns = [p for p in self.detected_patterns if p.concern_level == ConcernLevel.HIGH]
        if high_patterns:
            blockers.append(
                f"System has {len(high_patterns)} HIGH-severity patterns. Need {self.LOGOS_MIN_WEEKS_NO_HIGH_PATTERNS} weeks with zero."
            )

        current_score = self.calculate_system_health_score()
        if current_score < self.LOGOS_MIN_HEALTH_SCORE:
            blockers.append(
                f"Current health score ({current_score}) below threshold ({self.LOGOS_MIN_HEALTH_SCORE})."
            )

        alignment_rate = self._calculate_canon_alignment()
        if alignment_rate < self.CANON_ALIGNMENT_TARGET:
            blockers.append(
                f"Canon alignment rate ({alignment_rate:.1f}%) below target ({self.CANON_ALIGNMENT_TARGET}%)."
            )

        return (len(blockers) == 0, blockers)

    def identify_wins(self) -> List[str]:
        wins: List[str] = []
        for name, metrics in self.agent_metrics.items():
            if metrics.health_status == HealthStatus.EXCELLENT and metrics.tasks_processed > 0:
                wins.append(f"{name} is performing excellently")
        total_tasks = sum(m.tasks_processed for m in self.agent_metrics.values())
        total_retries = sum(m.retries for m in self.agent_metrics.values())
        if total_tasks > 10:
            retry_rate = (total_retries / total_tasks) * 100
            if retry_rate < 5:
                wins.append(f"System retry rate is excellent at {retry_rate:.1f}%")
        high_patterns = [p for p in self.detected_patterns if p.concern_level == ConcernLevel.HIGH]
        if not high_patterns:
            wins.append("No HIGH-severity patterns detected this period")
        return wins

    def generate_recommendations(self) -> List[str]:
        recommendations: List[str] = []
        for pattern in self.detected_patterns:
            if pattern.concern_level in {ConcernLevel.HIGH, ConcernLevel.MEDIUM}:
                recommendations.append(pattern.recommendation)
        for name, metrics in self.agent_metrics.items():
            if metrics.health_status == HealthStatus.CRITICAL:
                recommendations.append(f"URGENT: Review {name} (critical health status).")
            elif metrics.health_status == HealthStatus.NEEDS_ATTENTION:
                recommendations.append(f"Monitor {name} (needs attention).")
        if not recommendations:
            recommendations.append("System is healthy. Continue monitoring.")
        return recommendations

    def generate_weekly_report(self) -> SystemHealthReport:
        now = datetime.now(timezone.utc)
        since = now - timedelta(days=7)
        self.collect_metrics(since=since, until=now)
        self.detect_patterns()
        self._ingest_tool_notifications()
        score = self.calculate_system_health_score()
        self.historical_scores.append((now, score))
        self._save_history()
        logos_ready, logos_blockers = self.check_logos_praktikos_readiness()
        self.openclaw_status_path = self._latest_openclaw_status()
        return SystemHealthReport(
            week_start=since,
            week_end=now,
            overall_score=score,
            trend=self.determine_trend(),
            agent_metrics=self.agent_metrics.copy(),
            patterns_detected=self.detected_patterns.copy(),
            wins=self.identify_wins(),
            recommendations=self.generate_recommendations(),
            canon_alignment_rate=self._calculate_canon_alignment(),
            source_quality_rate=self.source_quality_rate,
            avg_execution_time=self.avg_execution_time,
            compliance_hold_rate=self.compliance_hold_rate,
            openclaw_status_path=self.openclaw_status_path,
            logos_praktikos_ready=logos_ready,
            logos_praktikos_blockers=logos_blockers,
        )

    def _calculate_canon_alignment(self) -> float:
        total_consultations = self.agent_metrics["polemarch"].canon_consultations
        total_tasks = sum(m.tasks_processed for m in self.agent_metrics.values())
        if total_tasks == 0:
            return 100.0
        return (total_consultations / total_tasks) * 100

    def format_report(self, report: SystemHealthReport) -> str:
        trend_symbol = {"improving": "up", "stable": "flat", "declining": "down"}.get(report.trend, "flat")
        lines: List[str] = []
        lines.append("=" * 70)
        lines.append("PERMANENCE OS - WEEKLY SYSTEM HEALTH REPORT")
        lines.append(f"Week of: {report.week_start.strftime('%Y-%m-%d')} to {report.week_end.strftime('%Y-%m-%d')}")
        lines.append("Compiled by: HR Agent (The Shepherd)")
        lines.append("Reviewed by: Dax (pending)")
        lines.append("=" * 70)
        lines.append("")
        lines.append("EXECUTIVE SUMMARY")
        lines.append(f"System health score: {report.overall_score}/100 ({trend_symbol})")
        lines.append("")
        lines.append("PERFORMANCE DASHBOARD")
        lines.append(f"- Retry rate: {self._system_retry_rate():.1f}%")
        lines.append(f"- Escalation rate: {self._system_escalation_rate():.1f}%")
        lines.append(f"- Compliance hold rate: {report.compliance_hold_rate:.1f}%")
        lines.append(f"- Budget overrun rate: {self._system_overrun_rate():.1f}%")
        lines.append(f"- Source quality (>=0.8): {report.source_quality_rate:.1f}%")
        lines.append(f"- Avg execution time (s): {report.avg_execution_time:.1f}")
        lines.append("")
        lines.append("AGENT STATUS")
        for name, metrics in sorted(report.agent_metrics.items()):
            lines.append(
                f"- {name}: {metrics.health_status.value} | tasks={metrics.tasks_processed} | retries={metrics.retry_rate:.1f}% | escalations={metrics.escalation_rate:.1f}%"
            )
        lines.append("")
        lines.append("PATTERNS DETECTED")
        if report.patterns_detected:
            for idx, pattern in enumerate(report.patterns_detected, 1):
                lines.append(f"{idx}. [{pattern.concern_level.value.upper()}] {pattern.pattern_type.value}")
                lines.append(f"   {pattern.description}")
                lines.append(f"   -> {pattern.recommendation}")
        else:
            lines.append("- None")
        lines.append("")
        lines.append("WINS THIS WEEK")
        if report.wins:
            for win in report.wins:
                lines.append(f"- {win}")
        else:
            lines.append("- (none)")
        lines.append("")
        lines.append("RECOMMENDATIONS")
        for rec in report.recommendations:
            lines.append(f"- {rec}")
        lines.append("")
        if report.openclaw_status_path:
            lines.append("OPENCLAW STATUS")
            lines.append(f"- Latest status file: {report.openclaw_status_path}")
            excerpt = self._openclaw_excerpt(report.openclaw_status_path)
            if excerpt:
                lines.append(f"- Excerpt: {excerpt}")
            lines.append("")
        lines.append("CANON ALIGNMENT")
        lines.append(f"- Alignment rate: {report.canon_alignment_rate:.1f}%")
        lines.append("")
        lines.append("LOGOS PRAKTIKOS STATUS")
        lines.append(f"- Ready: {'YES' if report.logos_praktikos_ready else 'NO'}")
        if report.logos_praktikos_blockers:
            lines.append("- Blockers:")
            for blocker in report.logos_praktikos_blockers:
                lines.append(f"  - {blocker}")
        lines.append("=" * 70)
        return "\n".join(lines)

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
        return str(candidates[0])

    @staticmethod
    def _openclaw_excerpt(path: str) -> str:
        try:
            with open(path, "r") as f:
                lines = [next(f).rstrip() for _ in range(6)]
        except (OSError, StopIteration):
            return ""
        return " | ".join([l for l in lines if l])

    def _ingest_tool_notifications(self) -> None:
        notifications = self._collect_tool_notifications()
        openclaw_issues = [n for n in notifications if n.get("tool") == "openclaw"]
        if not openclaw_issues:
            return
        recent = openclaw_issues[-5:]
        concern = ConcernLevel.MEDIUM if len(openclaw_issues) < 5 else ConcernLevel.HIGH
        self.detected_patterns.append(
            DetectedPattern(
                pattern_type=PatternType.TOOL_DEGRADATION,
                description=f"OpenClaw degradation events: {len(openclaw_issues)}",
                evidence=[f"{n.get('timestamp')}: {n.get('state')}" for n in recent],
                agents_involved=["openclaw"],
                concern_level=concern,
                detected_at=datetime.now(timezone.utc),
                recommendation="Review OpenClaw gateway connectivity and health",
            )
        )

    @staticmethod
    def _collect_tool_notifications() -> List[Dict[str, Any]]:
        hr_log = Path(os.path.join(LOG_DIR, "hr_notifications.jsonl"))
        if not hr_log.exists():
            return []
        notifications: List[Dict[str, Any]] = []
        with open(hr_log, "r") as f:
            for line in f:
                try:
                    notifications.append(json.loads(line.strip()))
                except json.JSONDecodeError:
                    continue
        return notifications

    def _system_retry_rate(self) -> float:
        total_tasks = sum(m.tasks_processed for m in self.agent_metrics.values())
        total_retries = sum(m.retries for m in self.agent_metrics.values())
        if total_tasks == 0:
            return 0.0
        return (total_retries / total_tasks) * 100

    def _system_escalation_rate(self) -> float:
        total_tasks = sum(m.tasks_processed for m in self.agent_metrics.values())
        total_escalations = sum(m.escalations for m in self.agent_metrics.values())
        if total_tasks == 0:
            return 0.0
        return (total_escalations / total_tasks) * 100

    def _system_overrun_rate(self) -> float:
        total_tasks = sum(m.tasks_processed for m in self.agent_metrics.values())
        total_overruns = sum(m.budget_overruns for m in self.agent_metrics.values())
        if total_tasks == 0:
            return 0.0
        return (total_overruns / total_tasks) * 100

    def execute(self, task: Dict[str, Any]) -> Dict[str, Any]:
        task_type = task.get("type", "weekly_report")
        if task_type == "weekly_report":
            report = self.generate_weekly_report()
            return {
                "status": "complete",
                "report": self.format_report(report),
                "score": report.overall_score,
                "patterns_count": len(report.patterns_detected),
                "logos_ready": report.logos_praktikos_ready,
            }
        if task_type == "logos_check":
            ready, blockers = self.check_logos_praktikos_readiness()
            return {"status": "complete", "logos_ready": ready, "blockers": blockers}
        if task_type == "check_agent":
            name = task.get("agent_name")
            if not name or name not in self.agent_metrics:
                return {"status": "error", "message": "Agent not found"}
            metrics = self.agent_metrics[name]
            return {
                "status": "complete",
                "agent": name,
                "health": metrics.health_status.value,
                "tasks": metrics.tasks_processed,
                "retry_rate": metrics.retry_rate,
                "escalation_rate": metrics.escalation_rate,
            }
        return {"status": "error", "message": f"Unknown task type: {task_type}"}


def create_hr_agent(memory_dir: Optional[str] = None, logs_dir: Optional[str] = None) -> HRAgent:
    return HRAgent(memory_dir=memory_dir, logs_dir=logs_dir)


if __name__ == "__main__":
    agent = create_hr_agent()
    result = agent.execute({"type": "weekly_report"})
    print(result.get("report", result))
