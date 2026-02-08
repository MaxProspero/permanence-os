"""
Permanence OS — Base Agent (v0.3)
Every agent inherits from this class.
DNA validation is mandatory. No exceptions.
"""

import yaml
import os
import json
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, field


class RiskTier(Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class AgentStatus(Enum):
    UNINITIALIZED = "UNINITIALIZED"
    DNA_VALIDATED = "DNA_VALIDATED"
    READY = "READY"
    EXECUTING = "EXECUTING"
    BLOCKED = "BLOCKED"
    DONE = "DONE"
    FAILED = "FAILED"


@dataclass
class AgentLog:
    timestamp: str
    agent_id: str
    action: str
    detail: str
    canon_ref: Optional[str] = None
    risk_tier: Optional[str] = None


@dataclass
class ProvenanceRecord:
    source: str
    timestamp: str
    confidence: str  # HIGH / MEDIUM / LOW
    author_agent: str
    evidence_count: int = 1
    limitations: Optional[str] = None


class BaseAgent:
    """
    Base class for all Permanence OS agents.

    Every agent MUST:
    1. Inherit from this class
    2. Pass DNA validation at initialization
    3. Declare its role, allowed_tools, and forbidden_actions
    4. Log every action
    5. Consult Canon before execution

    Agents that fail DNA validation CANNOT execute.
    """

    # Subclasses MUST override these
    ROLE: str = "UNDEFINED"
    ROLE_DESCRIPTION: str = "UNDEFINED"
    ALLOWED_TOOLS: List[str] = []
    FORBIDDEN_ACTIONS: List[str] = []
    DEPARTMENT: str = "CORE"

    def __init__(self, canon_path: str = "canon/", agent_id: Optional[str] = None):
        self.agent_id = agent_id or f"{self.ROLE}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
        self.canon_path = canon_path
        self.status = AgentStatus.UNINITIALIZED
        self.logs: List[AgentLog] = []
        self.dna_validated = False
        self.canon_loaded = False
        self._canon_data: Dict = {}
        self._dna_data: Dict = {}

        # Boot sequence
        self._load_canon()
        self._validate_dna()

    def _load_canon(self):
        """Load Canon files. Canon is read-only to all agents."""
        try:
            canon_files = [
                "values.yaml", "invariants.yaml", "tradeoffs.yaml",
                "decision_heuristics.yaml", "failure_archive.yaml",
                "long_arc.yaml", "dna.yaml"
            ]
            for fname in canon_files:
                fpath = os.path.join(self.canon_path, fname)
                if os.path.exists(fpath):
                    with open(fpath, 'r') as f:
                        self._canon_data[fname.replace('.yaml', '')] = yaml.safe_load(f)

            self.canon_loaded = True
            self._log("CANON_LOADED", f"Loaded {len(self._canon_data)} Canon files")
        except Exception as e:
            self._log("CANON_LOAD_FAILED", str(e))
            raise RuntimeError(f"Agent {self.agent_id} cannot load Canon: {e}")

    def _validate_dna(self):
        """
        Validate 3-6-9 DNA triad.
        Agent CANNOT proceed without passing this check.
        """
        dna = self._canon_data.get("dna", {})
        if not dna:
            self._log("DNA_VALIDATION_FAILED", "No DNA file found in Canon")
            raise RuntimeError(f"Agent {self.agent_id} has no DNA. Cannot initialize.")

        triad = dna.get("dna_triad", {})
        three = triad.get("three", {})
        genes = three.get("genes", [])

        if len(genes) != 3:
            self._log("DNA_VALIDATION_FAILED", f"Expected 3 genes, found {len(genes)}")
            raise RuntimeError(f"Agent {self.agent_id} DNA corrupted: wrong gene count")

        # Verify all three core genes present
        gene_names = {g["name"] for g in genes}
        required = {"Safety", "Abundance", "Service"}
        if gene_names != required:
            self._log("DNA_VALIDATION_FAILED", f"Missing genes: {required - gene_names}")
            raise RuntimeError(f"Agent {self.agent_id} DNA incomplete")

        self._dna_data = dna
        self.dna_validated = True
        self.status = AgentStatus.DNA_VALIDATED
        self._log("DNA_VALIDATED", f"3-6-9 DNA triad confirmed for {self.ROLE}")

    def _check_canon_compliance(self, action: str, context: Dict) -> bool:
        """
        Check proposed action against Canon invariants.
        Returns True if compliant, False if violation detected.
        """
        invariants = self._canon_data.get("invariants", {})
        if not invariants:
            self._log("CANON_CHECK_SKIP", "No invariants loaded")
            return True

        # Check forbidden actions
        if action in self.FORBIDDEN_ACTIONS:
            self._log("CANON_VIOLATION", f"Forbidden action attempted: {action}",
                      canon_ref="FORBIDDEN_ACTIONS")
            return False

        # Check tool authorization
        tool = context.get("tool")
        if tool and tool not in self.ALLOWED_TOOLS:
            self._log("CANON_VIOLATION", f"Unauthorized tool: {tool}",
                      canon_ref="ALLOWED_TOOLS")
            return False

        self._log("CANON_COMPLIANT", f"Action '{action}' passed Canon check")
        return True

    def _check_dna_alignment(self, action: str, context: Dict) -> Dict[str, bool]:
        """
        Check action against DNA genes.
        Returns dict of {gene_name: passed} for each gene.
        """
        results = {}
        genes = self._dna_data.get("dna_triad", {}).get("three", {}).get("genes", [])

        for gene in genes:
            gene_name = gene["name"]
            # Safety check
            if gene_name == "Safety":
                results["Safety"] = not context.get("endangers_human", False)
            # Abundance check
            elif gene_name == "Abundance":
                results["Abundance"] = context.get("creates_value", True)
            # Service check
            elif gene_name == "Service":
                results["Service"] = context.get("serves_human_goal", True)

        return results

    def _log(self, action: str, detail: str, canon_ref: Optional[str] = None,
             risk_tier: Optional[str] = None):
        """Append-only logging. Every action logged."""
        entry = AgentLog(
            timestamp=datetime.now(timezone.utc).isoformat(),
            agent_id=self.agent_id,
            action=action,
            detail=detail,
            canon_ref=canon_ref,
            risk_tier=risk_tier
        )
        self.logs.append(entry)

    def create_provenance(self, source: str, confidence: str,
                          evidence_count: int = 1,
                          limitations: Optional[str] = None) -> ProvenanceRecord:
        """Create a provenance record. Memory without provenance is fiction."""
        return ProvenanceRecord(
            source=source,
            timestamp=datetime.now(timezone.utc).isoformat(),
            confidence=confidence,
            author_agent=self.agent_id,
            evidence_count=evidence_count,
            limitations=limitations
        )

    def execute(self, task: Dict) -> Dict:
        """
        Main execution method. Subclasses MUST override this.
        Base implementation enforces pre-execution checks.
        """
        # Pre-execution gates
        if not self.dna_validated:
            return {"status": "BLOCKED", "reason": "DNA not validated"}

        if not self.canon_loaded:
            return {"status": "BLOCKED", "reason": "Canon not loaded"}

        if not self._check_canon_compliance(task.get("action", ""), task):
            return {"status": "BLOCKED", "reason": "Canon violation"}

        dna_check = self._check_dna_alignment(task.get("action", ""), task)
        if not all(dna_check.values()):
            failed = [k for k, v in dna_check.items() if not v]
            return {"status": "BLOCKED", "reason": f"DNA violation: {failed}"}

        self.status = AgentStatus.EXECUTING
        self._log("EXECUTE_START", f"Task: {task.get('goal', 'unknown')}")

        # Subclass implements actual work
        result = self._do_work(task)

        self.status = AgentStatus.DONE
        self._log("EXECUTE_DONE", f"Result status: {result.get('status', 'unknown')}")
        return result

    def _do_work(self, task: Dict) -> Dict:
        """Override in subclass. This is where actual agent work happens."""
        raise NotImplementedError(f"{self.ROLE} must implement _do_work()")

    def get_logs(self) -> List[Dict]:
        """Return all logs as serializable dicts."""
        return [
            {
                "timestamp": log.timestamp,
                "agent_id": log.agent_id,
                "action": log.action,
                "detail": log.detail,
                "canon_ref": log.canon_ref,
                "risk_tier": log.risk_tier
            }
            for log in self.logs
        ]

    def export_state(self) -> Dict:
        """Export agent state for debugging / audit."""
        return {
            "agent_id": self.agent_id,
            "role": self.ROLE,
            "department": self.DEPARTMENT,
            "status": self.status.value,
            "dna_validated": self.dna_validated,
            "canon_loaded": self.canon_loaded,
            "log_count": len(self.logs),
            "allowed_tools": self.ALLOWED_TOOLS,
            "forbidden_actions": self.FORBIDDEN_ACTIONS,
        }
