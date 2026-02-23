"""
HORIZON AGENT — Permanence OS
Role: Observe the landscape. Detect what's being built. Propose elevation.
Authority: RESEARCHER tier. Read-only. No self-modification. No Canon writes.
Outputs: Structured elevation reports → human approval queue.

Canon Alignment:
  - "No autonomy without audit" — every observation logged with provenance
  - "Compression over accumulation" — signal extracted, noise discarded
  - "Human authority is final" — proposals only, never self-applied
  - "No memory without provenance" — every finding sourced and timestamped

The Horizon Agent does NOT improve Permanence OS.
It surfaces what COULD improve it. The human decides.
"""

import json
import hashlib
import datetime
import os
import argparse
from dataclasses import dataclass, field, asdict
from typing import Optional
from enum import Enum


# ─────────────────────────────────────────────
# CONSTANTS & CONFIG
# ─────────────────────────────────────────────

HORIZON_VERSION = "0.1.0"
APP_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.environ.get("PERMANENCE_BASE_DIR", APP_DIR)
REPORT_OUTPUT_DIR = os.path.join(BASE_DIR, "outputs", "horizon")
LOG_PATH = os.path.join(BASE_DIR, "logs", "horizon_agent.log")
APPROVAL_QUEUE_PATH = os.path.join(BASE_DIR, "memory", "approvals.json")
CANON_DEFAULT_PATH = os.path.join(BASE_DIR, "canon", "base_canon.yaml")

# Whitelisted signal sources — Canon-controlled, not agent-controlled
SIGNAL_SOURCES = {
    "github_repos": [
        "microsoft/autogen",
        "crewAIInc/crewAI",
        "langchain-ai/langchain",
        "openai/openai-agents-python",
        "anthropics/anthropic-sdk-python",
    ],
    "arxiv_topics": [
        "multi-agent systems governance",
        "constitutional AI enforcement",
        "LLM agent safety",
        "human-in-the-loop AI",
    ],
    "x_search_terms": [
        "agent governance shipped",
        "multi-agent architecture production",
        "AI agent audit trail",
        "governed AI agent",
    ],
}

# Banned signal types — noise, not signal
BANNED_SIGNAL_PATTERNS = [
    "autonomous without oversight",
    "fully autonomous",
    "no human needed",
    "AGI",
    "sentient",
    "motivational thread",
    "10x your productivity",
]


def utc_now() -> datetime.datetime:
    """Timezone-aware UTC timestamp for persistence and logs."""
    return datetime.datetime.now(datetime.timezone.utc)


def utc_iso() -> str:
    """Compact ISO string with explicit UTC marker."""
    return utc_now().isoformat().replace("+00:00", "Z")


def utc_stamp(fmt: str) -> str:
    return utc_now().strftime(fmt)

# How the agent classifies what it finds
class FindingType(str, Enum):
    CAPABILITY_GAP = "capability_gap"       # They have it, we don't
    THREAT_PATTERN = "threat_pattern"       # Failure mode we haven't guarded against
    ARCHITECTURE_INSIGHT = "arch_insight"   # Structural pattern worth examining
    AHEAD_CONFIRMATION = "ahead_confirm"    # We're already doing this correctly
    IRRELEVANT = "irrelevant"               # Filtered out

class ElevationPriority(str, Enum):
    HIGH = "HIGH"       # Canon amendment warranted
    MEDIUM = "MEDIUM"   # Agent enhancement warranted
    LOW = "LOW"         # Log and monitor
    SKIP = "SKIP"       # Noise, discard


# ─────────────────────────────────────────────
# DATA STRUCTURES
# ─────────────────────────────────────────────

@dataclass
class RawSignal:
    """A single observed data point from the outside world."""
    source_url: str
    source_type: str        # github | arxiv | x | blog
    raw_content: str
    retrieved_at: str
    content_hash: str = field(init=False)

    def __post_init__(self):
        self.content_hash = hashlib.sha256(
            self.raw_content.encode()
        ).hexdigest()[:16]


@dataclass
class ProcessedFinding:
    """Compressed output from analyzing a raw signal."""
    signal_hash: str
    finding_type: FindingType
    summary: str                    # What was found (1-2 sentences max)
    source: str
    confidence: str                 # HIGH | MEDIUM | LOW
    limitations: str                # What this doesn't tell us
    permanence_relevance: str       # Why this matters to POS specifically
    proposed_action: Optional[str]  # If null, no action needed
    priority: ElevationPriority
    timestamp: str


@dataclass
class ElevationProposal:
    """
    A formal proposal for system improvement.
    This is the ONLY output that reaches the human approval queue.
    The Horizon Agent cannot apply its own proposals.
    """
    proposal_id: str
    title: str
    finding_summary: str
    current_state: str          # What Permanence OS does now
    proposed_change: str        # What would change
    expected_benefit: str
    risk_if_ignored: str
    implementation_scope: str   # "canon_amendment" | "agent_update" | "new_agent" | "monitor"
    draft_canon_amendment: Optional[str]  # If scope is canon_amendment
    draft_codex_task: Optional[str]       # If scope is agent_update or new_agent
    source_findings: list[str]            # finding hashes that support this
    priority: ElevationPriority
    status: str = "PENDING_HUMAN_REVIEW"
    created_at: str = field(default_factory=utc_iso)


@dataclass
class HorizonReport:
    """Weekly output of the Horizon Agent. Sent to human approval queue."""
    report_id: str
    generated_at: str
    agent_version: str
    signals_observed: int
    signals_filtered: int           # Discarded as noise
    findings_count: int
    proposals: list[ElevationProposal]
    raw_findings: list[ProcessedFinding]
    ahead_confirmations: list[str]  # Areas where POS is already leading
    audit_log: list[str]


# ─────────────────────────────────────────────
# CORE AGENT
# ─────────────────────────────────────────────

class HorizonAgent:
    """
    Observer. Analyst. Proposer. Never executor.

    Lifecycle:
      1. observe()     — collect raw signals from whitelisted sources
      2. filter()      — discard noise, enforce signal budget
      3. analyze()     — extract findings with provenance
      4. compress()    — convert findings to elevation proposals
      5. report()      — package for human review
      6. log()         — append-only audit trail (always, even on failure)
    """

    def __init__(
        self,
        canon_path: Optional[str] = None,
        approvals_path: str = APPROVAL_QUEUE_PATH,
    ):
        self.canon_path = canon_path or CANON_DEFAULT_PATH
        self.approvals_path = approvals_path
        self.session_id = self._generate_session_id()
        self.audit_log: list[str] = []
        self.raw_signals: list[RawSignal] = []
        self.findings: list[ProcessedFinding] = []
        self.proposals: list[ElevationProposal] = []
        self.signals_filtered = 0

        self._log(f"HORIZON AGENT INITIALIZED | session={self.session_id} | version={HORIZON_VERSION}")
        self._log(f"Base directory: {BASE_DIR}")
        self._log(f"Canon path: {self.canon_path}")
        self._log(f"Approval queue: {self.approvals_path}")
        self._log(f"Signal sources loaded: {len(SIGNAL_SOURCES)} categories")

    # ── PHASE 1: OBSERVE ──────────────────────────────────────────────

    def observe(self, mock_signals: Optional[list[dict]] = None) -> list[RawSignal]:
        """
        Collect raw signals from whitelisted sources.

        In production: connect to GitHub API, arXiv API, web search.
        In testing: accepts mock_signals for deterministic evaluation.

        CONSTRAINT: Read-only. No write actions. No authentication storage.
        """
        self._log("PHASE: OBSERVE")

        if mock_signals:
            self._log(f"Mode: TEST | {len(mock_signals)} mock signals provided")
            for s in mock_signals:
                signal = RawSignal(
                    source_url=s.get("url", "mock://test"),
                    source_type=s.get("type", "test"),
                    raw_content=s.get("content", ""),
                    retrieved_at=utc_iso(),
                )
                self.raw_signals.append(signal)
                self._log(f"  Signal ingested: hash={signal.content_hash} source={signal.source_type}")
        else:
            # Production: would connect to APIs here
            # Each connection must be logged before execution
            self._log("Mode: PRODUCTION — API connections not yet implemented")
            self._log("ESCALATE: Real signal collection requires Researcher Agent integration")
            self._log("Current output: structural skeleton only, no real data")

        self._log(f"OBSERVE COMPLETE | signals={len(self.raw_signals)}")
        return self.raw_signals

    # ── PHASE 2: FILTER ───────────────────────────────────────────────

    def filter(self) -> list[RawSignal]:
        """
        Discard noise before analysis.
        Banned patterns are checked against the Canon signal filter config.
        Every discard is logged with reason.
        """
        self._log("PHASE: FILTER")
        clean_signals = []

        for signal in self.raw_signals:
            banned = self._check_banned_patterns(signal.raw_content)
            if banned:
                self.signals_filtered += 1
                self._log(f"  FILTERED: hash={signal.content_hash} reason='{banned}'")
            else:
                clean_signals.append(signal)
                self._log(f"  PASSED: hash={signal.content_hash}")

        self.raw_signals = clean_signals
        self._log(f"FILTER COMPLETE | passed={len(self.raw_signals)} filtered={self.signals_filtered}")
        return self.raw_signals

    # ── PHASE 3: ANALYZE ──────────────────────────────────────────────

    def analyze(self) -> list[ProcessedFinding]:
        """
        Convert raw signals into structured findings.
        Every finding must have: source, confidence, limitations.
        Single-source conclusions are flagged LOW confidence (Source Dominance Check).
        """
        self._log("PHASE: ANALYZE")

        for signal in self.raw_signals:
            finding = self._analyze_signal(signal)
            if finding.finding_type != FindingType.IRRELEVANT:
                self.findings.append(finding)
                self._log(
                    f"  FINDING: type={finding.finding_type} "
                    f"priority={finding.priority} "
                    f"confidence={finding.confidence} "
                    f"hash={finding.signal_hash}"
                )
            else:
                self._log(f"  IRRELEVANT: hash={signal.content_hash} — discarded")

        self._log(f"ANALYZE COMPLETE | findings={len(self.findings)}")
        return self.findings

    # ── PHASE 4: COMPRESS ─────────────────────────────────────────────

    def compress(self) -> list[ElevationProposal]:
        """
        Convert findings into actionable proposals.
        One proposal may aggregate multiple findings.
        Proposals are NEVER self-applied. They enter the human approval queue.
        """
        self._log("PHASE: COMPRESS")

        # Group findings by type for aggregation
        gaps = [f for f in self.findings if f.finding_type == FindingType.CAPABILITY_GAP]
        threats = [f for f in self.findings if f.finding_type == FindingType.THREAT_PATTERN]
        insights = [f for f in self.findings if f.finding_type == FindingType.ARCHITECTURE_INSIGHT]

        # Generate proposals from grouped findings
        if gaps:
            proposal = self._create_proposal_from_gaps(gaps)
            if proposal:
                self.proposals.append(proposal)
                self._log(f"  PROPOSAL CREATED: id={proposal.proposal_id} scope={proposal.implementation_scope}")

        if threats:
            proposal = self._create_proposal_from_threats(threats)
            if proposal:
                self.proposals.append(proposal)
                self._log(f"  PROPOSAL CREATED: id={proposal.proposal_id} scope={proposal.implementation_scope}")

        if insights:
            proposal = self._create_proposal_from_insights(insights)
            if proposal:
                self.proposals.append(proposal)
                self._log(f"  PROPOSAL CREATED: id={proposal.proposal_id} scope={proposal.implementation_scope}")

        self._log(f"COMPRESS COMPLETE | proposals={len(self.proposals)}")
        return self.proposals

    # ── PHASE 5: REPORT ───────────────────────────────────────────────

    def report(self) -> HorizonReport:
        """
        Package everything into a structured report for human review.
        This is the only output that leaves the agent.
        """
        self._log("PHASE: REPORT")

        ahead_confirmations = [
            f.summary for f in self.findings
            if f.finding_type == FindingType.AHEAD_CONFIRMATION
        ]

        report = HorizonReport(
            report_id=f"HR-{utc_stamp('%Y%m%d')}-{self.session_id[:6]}",
            generated_at=utc_iso(),
            agent_version=HORIZON_VERSION,
            signals_observed=len(self.raw_signals) + self.signals_filtered,
            signals_filtered=self.signals_filtered,
            findings_count=len(self.findings),
            proposals=self.proposals,
            raw_findings=self.findings,
            ahead_confirmations=ahead_confirmations,
            audit_log=self.audit_log,
        )

        # Write report to disk
        os.makedirs(REPORT_OUTPUT_DIR, exist_ok=True)
        report_path = f"{REPORT_OUTPUT_DIR}/{report.report_id}.json"
        with open(report_path, "w") as f:
            json.dump(self._serialize_report(report), f, indent=2)

        queued, skipped = self._sync_proposals_to_approval_queue(report)
        self._log(f"REPORT WRITTEN: {report_path}")
        self._log(f"APPROVAL QUEUE UPDATE | queued={queued} skipped_existing={skipped}")
        self._log(f"REPORT COMPLETE | id={report.report_id} proposals={len(self.proposals)}")
        self._write_audit_log()

        return report

    # ── FULL RUN ──────────────────────────────────────────────────────

    def run(self, mock_signals: Optional[list[dict]] = None) -> HorizonReport:
        """Execute all phases in sequence. No skipping."""
        self._reset_run_state()
        self._log("=== HORIZON AGENT RUN START ===")
        self.observe(mock_signals)
        self.filter()
        self.analyze()
        self.compress()
        report = self.report()
        self._log("=== HORIZON AGENT RUN COMPLETE ===")
        return report

    # ─────────────────────────────────────────────
    # INTERNAL METHODS
    # ─────────────────────────────────────────────

    def _reset_run_state(self):
        """Ensure each run is isolated when the same agent instance is reused."""
        self.audit_log = []
        self.raw_signals = []
        self.findings = []
        self.proposals = []
        self.signals_filtered = 0

    def _analyze_signal(self, signal: RawSignal) -> ProcessedFinding:
        """
        Classify and compress a single signal into a finding.
        In production: LLM inference call goes here, governed by budget.
        In current state: rule-based pattern matching as scaffold.
        """
        content_lower = signal.raw_content.lower()

        # Classify finding type based on content keywords
        if any(k in content_lower for k in ["we don't have", "missing", "gap", "lacks"]):
            finding_type = FindingType.CAPABILITY_GAP
            priority = ElevationPriority.MEDIUM
        elif any(k in content_lower for k in ["failed", "collapsed", "security issue", "exploit", "breach"]):
            finding_type = FindingType.THREAT_PATTERN
            priority = ElevationPriority.HIGH
        elif any(k in content_lower for k in ["architecture", "pattern", "structure", "approach"]):
            finding_type = FindingType.ARCHITECTURE_INSIGHT
            priority = ElevationPriority.LOW
        elif any(k in content_lower for k in ["governance", "audit", "human approval", "canon"]):
            finding_type = FindingType.AHEAD_CONFIRMATION
            priority = ElevationPriority.LOW
        else:
            finding_type = FindingType.IRRELEVANT
            priority = ElevationPriority.SKIP

        return ProcessedFinding(
            signal_hash=signal.content_hash,
            finding_type=finding_type,
            summary=signal.raw_content[:200] + "..." if len(signal.raw_content) > 200 else signal.raw_content,
            source=signal.source_url,
            confidence="LOW",  # Single source — Source Dominance Check applies
            limitations="Single source. Confidence will increase with corroborating signals.",
            permanence_relevance="To be assessed by human reviewer.",
            proposed_action=None if finding_type in [FindingType.IRRELEVANT, FindingType.AHEAD_CONFIRMATION] else "Review for elevation",
            priority=priority,
            timestamp=utc_iso(),
        )

    def _create_proposal_from_gaps(self, gaps: list[ProcessedFinding]) -> Optional[ElevationProposal]:
        if not gaps:
            return None
        return ElevationProposal(
            proposal_id=f"EP-GAP-{utc_stamp('%Y%m%d%H%M%S')}",
            title=f"Capability Gap Analysis — {len(gaps)} signals",
            finding_summary=f"{len(gaps)} capability gaps identified in the landscape.",
            current_state="Permanence OS does not yet implement the identified capabilities.",
            proposed_change="Review gap findings and determine which, if any, align with Canon values and build roadmap.",
            expected_benefit="Prevents POS from being surpassed in governance-relevant capabilities.",
            risk_if_ignored="Competitors may establish patterns that become industry standard before POS adopts them.",
            implementation_scope="agent_update",
            draft_canon_amendment=None,
            draft_codex_task="Review gap findings in attached report. For each: classify as (build | monitor | irrelevant). Add approved items to sprint backlog.",
            source_findings=[g.signal_hash for g in gaps],
            priority=ElevationPriority.MEDIUM,
        )

    def _create_proposal_from_threats(self, threats: list[ProcessedFinding]) -> Optional[ElevationProposal]:
        if not threats:
            return None
        return ElevationProposal(
            proposal_id=f"EP-THREAT-{utc_stamp('%Y%m%d%H%M%S')}",
            title=f"Threat Pattern Alert — {len(threats)} failure modes observed",
            finding_summary=f"{len(threats)} failure patterns observed in the landscape.",
            current_state="These failure modes may or may not be guarded against in current Canon.",
            proposed_change="Cross-reference each threat against Canon invariants and failure archive. Add any unguarded patterns as new Canon amendments.",
            expected_benefit="Proactive failure prevention before patterns reach Permanence OS.",
            risk_if_ignored="Known failure patterns enter system without governance response.",
            implementation_scope="canon_amendment",
            draft_canon_amendment="[HUMAN TO DRAFT] — Review threat findings, identify unguarded patterns, propose F-XXX entries for Failure Archive.",
            draft_codex_task=None,
            source_findings=[t.signal_hash for t in threats],
            priority=ElevationPriority.HIGH,
        )

    def _create_proposal_from_insights(self, insights: list[ProcessedFinding]) -> Optional[ElevationProposal]:
        if not insights:
            return None
        return ElevationProposal(
            proposal_id=f"EP-INSIGHT-{utc_stamp('%Y%m%d%H%M%S')}",
            title=f"Architecture Insights — {len(insights)} patterns",
            finding_summary=f"{len(insights)} architectural patterns identified for evaluation.",
            current_state="POS architecture may or may not incorporate these patterns.",
            proposed_change="Review insights for alignment with Canon values. Adopt patterns that increase survivability without increasing complexity.",
            expected_benefit="Architectural refinement informed by real-world evidence.",
            risk_if_ignored="Relevant structural improvements missed.",
            implementation_scope="monitor",
            draft_canon_amendment=None,
            draft_codex_task=None,
            source_findings=[i.signal_hash for i in insights],
            priority=ElevationPriority.LOW,
        )

    def _check_banned_patterns(self, content: str) -> Optional[str]:
        """Returns the matched banned pattern, or None if clean."""
        content_lower = content.lower()
        for pattern in BANNED_SIGNAL_PATTERNS:
            if pattern.lower() in content_lower:
                return pattern
        return None

    def _generate_session_id(self) -> str:
        return hashlib.sha256(
            utc_iso().encode()
        ).hexdigest()[:12]

    def _log(self, message: str):
        """Append-only. Every log entry timestamped."""
        entry = f"[{utc_iso()}] [HORIZON] {message}"
        self.audit_log.append(entry)
        print(entry)

    def _write_audit_log(self):
        os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
        with open(LOG_PATH, "a") as f:
            for entry in self.audit_log:
                f.write(entry + "\n")

    def _sync_proposals_to_approval_queue(self, report: HorizonReport) -> tuple[int, int]:
        """
        Add newly generated proposals to memory/approvals.json.
        Dedupe is enforced by proposal_id and a content fingerprint to keep
        the queue append-only and stable across repeated equivalent findings.
        """
        os.makedirs(os.path.dirname(self.approvals_path), exist_ok=True)

        approvals: list[dict] = []
        if os.path.exists(self.approvals_path):
            with open(self.approvals_path) as f:
                try:
                    existing = json.load(f)
                    if isinstance(existing, list):
                        approvals = existing
                    elif isinstance(existing, dict) and isinstance(existing.get("approvals"), list):
                        approvals = existing["approvals"]
                    else:
                        self._log("WARN: approvals.json had unexpected shape; treating as empty list")
                except json.JSONDecodeError:
                    self._log("WARN: approvals.json is invalid JSON; treating as empty list")

        original_count = len(approvals)

        existing_ids: set[str] = set()
        existing_fingerprints: set[str] = set()
        normalized_approvals: list[dict] = []

        for item in approvals:
            if not isinstance(item, dict):
                continue
            item_id = item.get("proposal_id") or item.get("id") or item.get("approval_id")
            fingerprint = item.get("proposal_fingerprint") or self._proposal_fingerprint(item)
            if item_id in existing_ids or fingerprint in existing_fingerprints:
                continue

            if item_id:
                existing_ids.add(item_id)
            existing_fingerprints.add(fingerprint)
            item["proposal_fingerprint"] = fingerprint
            normalized_approvals.append(item)

        approvals = normalized_approvals

        queued = 0
        skipped = 0
        for proposal in report.proposals:
            queue_item = asdict(proposal)
            queue_item["id"] = proposal.proposal_id
            queue_item["approval_id"] = proposal.proposal_id
            queue_item["source"] = "horizon_agent"
            queue_item["source_report_id"] = report.report_id
            queue_item["queued_at"] = utc_iso()
            fingerprint = self._proposal_fingerprint(queue_item)

            if proposal.proposal_id in existing_ids or fingerprint in existing_fingerprints:
                skipped += 1
                continue

            queue_item["proposal_fingerprint"] = fingerprint
            approvals.append(queue_item)
            existing_ids.add(proposal.proposal_id)
            existing_fingerprints.add(fingerprint)
            queued += 1

        if queued > 0 or not os.path.exists(self.approvals_path) or len(approvals) != original_count:
            with open(self.approvals_path, "w") as f:
                json.dump(approvals, f, indent=2)

        return queued, skipped

    def _proposal_fingerprint(self, item: dict) -> str:
        """
        Stable fingerprint for dedupe across runs when proposal IDs differ.
        """
        source_findings = item.get("source_findings") or []
        source_tokens = ",".join(sorted(str(x) for x in source_findings))
        fingerprint_input = "|".join([
            str(item.get("title", "")),
            str(item.get("implementation_scope", "")),
            str(item.get("finding_summary", "")),
            source_tokens,
        ])
        return hashlib.sha256(fingerprint_input.encode()).hexdigest()[:16]

    def _serialize_report(self, report: HorizonReport) -> dict:
        """Convert dataclasses to JSON-serializable dict."""
        return {
            "report_id": report.report_id,
            "generated_at": report.generated_at,
            "agent_version": report.agent_version,
            "signals_observed": report.signals_observed,
            "signals_filtered": report.signals_filtered,
            "findings_count": report.findings_count,
            "ahead_confirmations": report.ahead_confirmations,
            "proposals": [asdict(p) for p in report.proposals],
            "raw_findings": [asdict(f) for f in report.raw_findings],
            "audit_log": report.audit_log,
        }


# ─────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run the Permanence OS Horizon Agent."
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Run with built-in mock signals for deterministic testing.",
    )
    parser.add_argument(
        "--canon-path",
        default=None,
        help="Optional path override for the Canon base file.",
    )
    parser.add_argument(
        "--approvals-path",
        default=APPROVAL_QUEUE_PATH,
        help="Optional path override for memory/approvals.json.",
    )
    args = parser.parse_args()

    agent = HorizonAgent(
        canon_path=args.canon_path,
        approvals_path=args.approvals_path,
    )

    demo_signals = None
    if args.demo:
        demo_signals = [
            {
                "url": "https://github.com/crewAIInc/crewAI/issues/123",
                "type": "github",
                "content": "CrewAI agents failed catastrophically when one agent overwrote another's memory without audit trail. Security issue: no provenance tracking on shared state.",
            },
            {
                "url": "https://arxiv.org/abs/2401.example",
                "type": "arxiv",
                "content": "Architecture pattern: Constitutional AI enforcement via read-only policy documents outperforms prompt-based governance in long-horizon tasks.",
            },
            {
                "url": "https://x.com/builder/status/example",
                "type": "x",
                "content": "AutoGen lacks human-in-the-loop for irreversible actions. Governance lives in prompts, not structure. We don't have a Canon equivalent.",
            },
            {
                "url": "https://blog.example.com/agent-post",
                "type": "blog",
                "content": "10x your productivity with fully autonomous agents — no human needed in the loop!",
            },
        ]

    report = agent.run(mock_signals=demo_signals)

    print(f"\n{'='*60}")
    print(f"HORIZON REPORT SUMMARY")
    print(f"{'='*60}")
    print(f"Report ID:         {report.report_id}")
    print(f"Signals observed:  {report.signals_observed}")
    print(f"Signals filtered:  {report.signals_filtered}")
    print(f"Findings:          {report.findings_count}")
    print(f"Proposals:         {len(report.proposals)}")
    print(f"Ahead of peers:    {len(report.ahead_confirmations)} confirmed")
    print(f"{'='*60}")
    if args.demo:
        print("\nDemo mode used mock signals. All proposals require human review before any action is taken.")
    else:
        print("\nProduction mode used live connectors (currently scaffolded). All proposals require human review before any action is taken.")
