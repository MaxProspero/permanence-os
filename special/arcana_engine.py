"""
Permanence OS — Arcana Engine v0.4
Heuristic 3-6-9 pattern scanning and governed branch projection.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List

from agents.base import BaseAgent
from memory.zero_point import ConfidenceLevel, MemoryType, ZeroPoint
from special.digital_twin import DigitalTwinSimulator


class ArcanaEngine(BaseAgent):
    ROLE = "ARCANA"
    ROLE_DESCRIPTION = "Heuristic signal engine with confidence-calibrated outputs"
    ALLOWED_TOOLS = ["read_zero_point", "simulate", "write_zero_point"]
    FORBIDDEN_ACTIONS = ["execute_real_action", "modify_canon", "present_oracle_claims"]
    DEPARTMENT = "SPECIAL"

    def __init__(
        self,
        zero_point: ZeroPoint | None = None,
        twin: DigitalTwinSimulator | None = None,
        canon_path: str = "canon/",
    ):
        super().__init__(canon_path=canon_path)
        self.zero_point = zero_point or ZeroPoint()
        self.twin = twin or DigitalTwinSimulator()

    def _do_work(self, task: Dict) -> Dict:
        # Arcana is called through explicit methods in this module.
        return {"status": "NOOP"}

    def calculate_digital_root(self, n: int) -> int:
        if n == 0:
            return 0
        value = abs(int(n))
        while value >= 10:
            value = sum(int(ch) for ch in str(value))
        return value

    def _iter_numbers(self, data_stream: Iterable[Any]) -> Iterable[int]:
        for item in data_stream:
            if isinstance(item, bool):
                continue
            if isinstance(item, int):
                yield item
            elif isinstance(item, float):
                yield int(item)
            elif isinstance(item, str):
                token = "".join(ch if ch.isdigit() else " " for ch in item)
                for part in token.split():
                    yield int(part)
            elif isinstance(item, dict):
                for value in item.values():
                    yield from self._iter_numbers([value])
            elif isinstance(item, (list, tuple)):
                yield from self._iter_numbers(item)

    def _confidence_from_evidence(self, evidence_count: int) -> str:
        if evidence_count >= 10:
            return ConfidenceLevel.HIGH.value
        if evidence_count >= 4:
            return ConfidenceLevel.MEDIUM.value
        return ConfidenceLevel.LOW.value

    def scan_for_patterns(self, data_stream: Iterable[Any]) -> Dict[str, Any]:
        numbers = list(self._iter_numbers(data_stream))
        alignments: List[Dict[str, Any]] = []
        for value in numbers:
            root = self.calculate_digital_root(value)
            if root in (3, 6, 9):
                alignments.append(
                    {
                        "value": value,
                        "digital_root": root,
                        "signal_type": "heuristic",
                        "heuristic_source": "arcana_3_6_9",
                    }
                )

        evidence_count = len(numbers)
        confidence = self._confidence_from_evidence(evidence_count)
        report = {
            "signal_type": "heuristic",
            "heuristic_source": "arcana_3_6_9",
            "confidence": confidence,
            "evidence_count": evidence_count,
            "alignment_count": len(alignments),
            "alignments": alignments,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

        self.zero_point.write(
            content=json.dumps(report),
            memory_type=MemoryType.FORECAST,
            tags=["arcana", "scan", "heuristic"],
            source="arcana_engine.scan_for_patterns",
            author_agent=self.ROLE,
            confidence=ConfidenceLevel[confidence],
            evidence_count=max(1, evidence_count),
            limitations="Heuristic only; not an oracle.",
        )
        return report

    def project_looking_glass(self, data_context: Dict[str, Any], branches: int = 3) -> Dict[str, Any]:
        timeline = self.twin.project_timeline(data_context, branches=branches)
        evidence_count = len(timeline.get("branches", []))
        confidence = self._confidence_from_evidence(evidence_count)
        report = {
            "signal_type": "heuristic",
            "heuristic_source": "arcana_looking_glass",
            "confidence": confidence,
            "branches": timeline.get("branches", []),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

        self.zero_point.write(
            content=json.dumps(report),
            memory_type=MemoryType.FORECAST,
            tags=["arcana", "looking_glass", "heuristic"],
            source="arcana_engine.project_looking_glass",
            author_agent=self.ROLE,
            confidence=ConfidenceLevel[confidence],
            evidence_count=max(1, evidence_count),
            limitations="Branching heuristics for human review only.",
        )
        return report
