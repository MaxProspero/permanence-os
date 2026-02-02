#!/usr/bin/env python3
"""
EXECUTOR AGENT
Produces outputs strictly from approved plans. No scope changes.
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

from agents.utils import log


@dataclass
class ExecutionResult:
    status: str
    artifact: Optional[Any]
    notes: List[str]
    created_at: str


class ExecutorAgent:
    """
    ROLE: Produce outputs per an approved task specification.

    CONSTRAINTS:
    - Cannot improvise scope
    - Cannot execute without a plan/spec
    - Cannot alter Canon or governance rules
    """

    def execute(self, spec: Optional[Dict[str, Any]], inputs: Optional[Dict[str, Any]] = None) -> ExecutionResult:
        if not spec:
            log("Executor refused: missing task specification", level="WARNING")
            return ExecutionResult(
                status="REFUSED",
                artifact=None,
                notes=["Execution requires an approved task specification."],
                created_at=datetime.now(timezone.utc).isoformat(),
            )

        log("Executor received spec; no-op execution (stub)", level="INFO")
        return ExecutionResult(
            status="NOOP",
            artifact=None,
            notes=["Executor is a stub; provide an implementation to produce artifacts."],
            created_at=datetime.now(timezone.utc).isoformat(),
        )


if __name__ == "__main__":
    ea = ExecutorAgent()
    print(ea.execute(spec=None))
