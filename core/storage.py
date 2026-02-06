#!/usr/bin/env python3
"""
Storage manager with LaCie primary + local fallback.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from agents.utils import log, BASE_DIR

try:
    from dotenv import load_dotenv  # type: ignore

    load_dotenv(os.path.join(BASE_DIR, ".env"))
except Exception:
    pass


@dataclass(frozen=True)
class StoragePaths:
    root: Path
    memory_episodic: Path
    logs: Path
    outputs_briefings: Path
    outputs_digests: Path
    outputs_synthesis: Path
    outputs_synthesis_drafts: Path
    outputs_synthesis_final: Path
    archives_notebooklm: Path


class StorageManager:
    def __init__(self, root: Path | None = None):
        env_root = os.getenv("PERMANENCE_STORAGE_ROOT")
        if root:
            storage_root = root
        elif env_root:
            storage_root = Path(os.path.expanduser(env_root))
        else:
            lacie = Path("/Volumes/LaCie_Permanence")
            storage_root = lacie if lacie.exists() else Path.home() / "permanence_storage"

        self.paths = self._ensure_structure(storage_root)
        if self.paths.root.exists():
            log(f"Storage root: {self.paths.root}", level="INFO")

    def _ensure_structure(self, root: Path) -> StoragePaths:
        memory_episodic = root / "memory" / "episodic"
        logs = root / "logs"
        outputs_briefings = root / "outputs" / "briefings"
        outputs_digests = root / "outputs" / "digests"
        outputs_synthesis = root / "outputs" / "synthesis"
        outputs_synthesis_drafts = outputs_synthesis / "drafts"
        outputs_synthesis_final = outputs_synthesis / "final"
        archives_notebooklm = root / "archives" / "notebooklm"

        for path in (
            memory_episodic,
            logs,
            outputs_briefings,
            outputs_digests,
            outputs_synthesis,
            outputs_synthesis_drafts,
            outputs_synthesis_final,
            archives_notebooklm,
        ):
            path.mkdir(parents=True, exist_ok=True)

        readme = root / "README.md"
        if not readme.exists():
            readme.write_text(
                "# Permanence OS Storage\n\n"
                f"Initialized: {datetime.now(timezone.utc).isoformat()}\n\n"
                "Structure:\n"
                "- memory/episodic\n"
                "- logs\n"
                "- outputs/briefings\n"
                "- outputs/digests\n"
                "- outputs/synthesis\n"
            )

        return StoragePaths(
            root=root,
            memory_episodic=memory_episodic,
            logs=logs,
            outputs_briefings=outputs_briefings,
            outputs_digests=outputs_digests,
            outputs_synthesis=outputs_synthesis,
            outputs_synthesis_drafts=outputs_synthesis_drafts,
            outputs_synthesis_final=outputs_synthesis_final,
            archives_notebooklm=archives_notebooklm,
        )


storage = StorageManager()
