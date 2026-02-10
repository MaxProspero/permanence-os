"""
Permanence OS — Practice Squad v0.4
Shadow scrimmage engine for governed habit reinforcement.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from agents.base import BaseAgent
from memory.zero_point import ConfidenceLevel, MemoryType, ZeroPoint
from special.arcana_engine import ArcanaEngine


class PracticeSquad(BaseAgent):
    ROLE = "PRACTICE_SQUAD"
    ROLE_DESCRIPTION = "Shadow scrimmage and hyper-sim habit reinforcement engine"
    ALLOWED_TOOLS = ["read_zero_point", "simulate", "write_zero_point"]
    FORBIDDEN_ACTIONS = ["execute_real_action", "modify_canon"]
    DEPARTMENT = "SPECIAL"

    NOISE_TYPES = [
        "emotional_compromise",
        "data_corruption",
        "resource_exhaustion",
        "adversarial_injection",
    ]

    def __init__(self, zero_point: ZeroPoint | None = None, arcana: ArcanaEngine | None = None):
        super().__init__(canon_path="canon/")
        self.zero_point = zero_point or ZeroPoint()
        self.arcana = arcana or ArcanaEngine(zero_point=self.zero_point)

    def _do_work(self, task: Dict) -> Dict:
        return {"status": "NOOP"}

    def _recent_entries(self, last_hours: int) -> List[Dict[str, Any]]:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=max(1, int(last_hours)))
        recent: List[Dict[str, Any]] = []
        for entry in self.zero_point.entries.values():
            created = datetime.fromisoformat(entry.created_at)
            if created >= cutoff:
                recent.append(
                    {
                        "entry_id": entry.entry_id,
                        "memory_type": entry.memory_type,
                        "content": entry.content,
                        "confidence": entry.confidence,
                        "tags": entry.tags,
                        "created_at": entry.created_at,
                    }
                )
        return recent

    def _apply_noise(self, payload: Dict[str, Any], noise_type: str) -> Dict[str, Any]:
        noisy = dict(payload)
        noisy["noise_type"] = noise_type
        if noise_type == "emotional_compromise":
            noisy["sentiment"] = "volatile"
        elif noise_type == "data_corruption":
            noisy["confidence"] = "LOW"
        elif noise_type == "resource_exhaustion":
            noisy["budget_remaining"] = 0
        elif noise_type == "adversarial_injection":
            noisy["adversarial_pattern"] = "<script>alert(1)</script>"
        return noisy

    def scrimmage(self, last_hours: int = 24, replays: int = 10) -> Dict[str, Any]:
        recent = self._recent_entries(last_hours)
        replay_count = max(1, int(replays))
        mutated: List[Dict[str, Any]] = []

        for item in recent:
            for idx in range(replay_count):
                noise_type = self.NOISE_TYPES[idx % len(self.NOISE_TYPES)]
                mutated.append(self._apply_noise(item, noise_type))

        pattern_report = self.arcana.scan_for_patterns(
            [m.get("entry_id", "") + m.get("noise_type", "") for m in mutated]
        )

        insight = {
            "type": "training_insight",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "window_hours": last_hours,
            "replays": replay_count,
            "source_count": len(recent),
            "mutated_count": len(mutated),
            "noise_profile": {
                noise: sum(1 for m in mutated if m.get("noise_type") == noise)
                for noise in self.NOISE_TYPES
            },
            "pattern_alignment_count": pattern_report.get("alignment_count", 0),
            "summary": "Scrimmage completed; review noise profile and alignments.",
        }

        write_res = self.zero_point.write(
            content=json.dumps(insight),
            memory_type=MemoryType.TRAINING,
            tags=["practice_squad", "scrimmage", "training"],
            source="practice_squad_scrimmage",
            author_agent=self.ROLE,
            confidence=ConfidenceLevel.MEDIUM,
            evidence_count=max(1, len(recent)),
            limitations="Simulation data only.",
        )

        return {
            "status": "OK",
            "last_hours": last_hours,
            "source_count": len(recent),
            "mutated_count": len(mutated),
            "insight_entry_id": write_res.get("entry_id"),
            "pattern_alignment_count": pattern_report.get("alignment_count", 0),
        }

    def hyper_sim(self, iterations: int = 10000, warp_speed: bool = True, last_hours: int = 24) -> Dict[str, Any]:
        # Keep runtime bounded for local laptops while still allowing large requested values.
        effective_iterations = min(max(1, int(iterations)), 10000 if warp_speed else 2500)
        sample = self._recent_entries(last_hours)
        if not sample:
            # Guarantee a minimal training event even with empty history.
            sample = [{"entry_id": "empty", "content": "no_recent_data", "confidence": "LOW", "tags": []}]

        score = 0
        for idx in range(effective_iterations):
            item = sample[idx % len(sample)]
            noise = self.NOISE_TYPES[idx % len(self.NOISE_TYPES)]
            noisy = self._apply_noise(item, noise)
            score += 1 if noisy.get("confidence") != "LOW" else 0

        summary = {
            "type": "hyper_sim",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "iterations_requested": int(iterations),
            "iterations_ran": effective_iterations,
            "warp_speed": bool(warp_speed),
            "score": score,
        }

        write_res = self.zero_point.write(
            content=json.dumps(summary),
            memory_type=MemoryType.TRAINING,
            tags=["practice_squad", "hyper_sim", "training"],
            source="practice_squad_hyper_sim",
            author_agent=self.ROLE,
            confidence=ConfidenceLevel.MEDIUM if effective_iterations >= 1000 else ConfidenceLevel.LOW,
            evidence_count=max(1, len(sample)),
            limitations="Compressed simulation loop.",
        )

        return {
            "status": "OK",
            "iterations_ran": effective_iterations,
            "entry_id": write_res.get("entry_id"),
            "warp_speed": bool(warp_speed),
        }
