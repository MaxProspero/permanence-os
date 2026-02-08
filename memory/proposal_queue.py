#!/usr/bin/env python3
"""Simple governed proposal queue for Muse outputs."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class QueueItem:
    proposal_id: str
    title: str
    risk_tier: str
    status: str
    created_at: str
    source_agent: str
    payload: Dict[str, Any]
    human_notes: Optional[str] = None


class ProposalQueue:
    """Append-only queue with explicit status transitions."""

    VALID_STATUSES = {"PENDING", "APPROVED", "REJECTED", "DEFERRED", "IMPLEMENTED"}

    def __init__(self, path: str = "memory/proposal_queue.json"):
        self.path = Path(path)
        self.items: List[QueueItem] = []
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text())
        except json.JSONDecodeError:
            return
        raw_items = data.get("proposals", [])
        parsed: List[QueueItem] = []
        for raw in raw_items:
            try:
                parsed.append(
                    QueueItem(
                        proposal_id=raw["proposal_id"],
                        title=raw.get("title", ""),
                        risk_tier=raw.get("risk_tier", "LOW"),
                        status=raw.get("status", "PENDING"),
                        created_at=raw.get("created_at", datetime.now(timezone.utc).isoformat()),
                        source_agent=raw.get("source_agent", "MUSE"),
                        payload=raw,
                        human_notes=raw.get("human_notes"),
                    )
                )
            except KeyError:
                continue
        self.items = parsed

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "proposals": [asdict(i) for i in self.items],
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "total": len(self.items),
        }
        self.path.write_text(json.dumps(payload, indent=2))

    def add(self, proposal: Dict[str, Any], source_agent: str = "MUSE") -> QueueItem:
        item = QueueItem(
            proposal_id=proposal["proposal_id"],
            title=proposal.get("title", ""),
            risk_tier=proposal.get("risk_tier", "LOW"),
            status=proposal.get("status", "PENDING"),
            created_at=proposal.get("created_at", datetime.now(timezone.utc).isoformat()),
            source_agent=source_agent,
            payload=proposal,
            human_notes=proposal.get("human_notes"),
        )
        self.items.append(item)
        self._save()
        return item

    def set_status(self, proposal_id: str, status: str, notes: str = "") -> bool:
        if status not in self.VALID_STATUSES:
            raise ValueError(f"invalid status: {status}")
        for item in self.items:
            if item.proposal_id == proposal_id:
                item.status = status
                item.human_notes = notes or item.human_notes
                self._save()
                return True
        return False

    def summary(self) -> Dict[str, int]:
        counts = {status: 0 for status in self.VALID_STATUSES}
        for item in self.items:
            counts[item.status] = counts.get(item.status, 0) + 1
        counts["total"] = len(self.items)
        return counts

