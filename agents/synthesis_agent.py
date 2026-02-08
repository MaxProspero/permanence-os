#!/usr/bin/env python3
"""
Governed synthesis brief generator (non-LLM, extractive).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Tuple
import json
import os
import re

from core.storage import storage
from agents.utils import log, BASE_DIR


THEME_FALLBACK = ["Compression", "AI Governance", "Trading Systems", "Personal Development"]

KEYWORD_MAP = {
    "Compression": ["compression", "compress", "signal", "decision", "identity"],
    "AI Governance": ["governance", "canon", "policy", "risk", "alignment", "audit"],
    "Trading Systems": ["trading", "market", "signal", "risk", "portfolio"],
    "Personal Development": ["habit", "sleep", "focus", "training", "health", "discipline"],
}


@dataclass
class ThemeBlock:
    name: str
    excerpts: List[str]
    sources: List[str]


class SynthesisAgent:
    def __init__(self, days: int = 30, max_sources: int = 50):
        self.days = days
        self.max_sources = max_sources
        self.sources_path = Path(BASE_DIR) / "memory" / "working" / "sources.json"

    def _load_sources(self) -> List[Dict]:
        if not self.sources_path.exists():
            return []
        try:
            data = json.loads(self.sources_path.read_text())
        except json.JSONDecodeError:
            return []
        if not isinstance(data, list):
            return []
        return data

    def _filter_sources(self, sources: List[Dict]) -> List[Dict]:
        cutoff = datetime.now(timezone.utc) - timedelta(days=self.days)
        recent: List[Dict] = []
        for src in sources:
            ts = src.get("timestamp") or ""
            try:
                ts_dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            except Exception:
                ts_dt = None
            if ts_dt and ts_dt >= cutoff:
                recent.append(src)
        if recent:
            return recent[: self.max_sources]
        return sources[: self.max_sources]

    def _extract_text(self, src: Dict) -> str:
        parts = [
            str(src.get("title") or ""),
            str(src.get("notes") or ""),
            str(src.get("source") or ""),
        ]
        return " ".join(parts).lower()

    def _detect_themes(self, sources: List[Dict]) -> Tuple[List[str], str]:
        scores: Dict[str, int] = {k: 0 for k in KEYWORD_MAP}
        for src in sources:
            text = self._extract_text(src)
            for theme, keywords in KEYWORD_MAP.items():
                for kw in keywords:
                    if kw in text:
                        scores[theme] += 1
        ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
        top = [name for name, score in ranked if score > 0][:3]
        top_score = ranked[0][1] if ranked else 0
        # Treat sparse keyword matches as low confidence and fall back to canonical themes.
        if not top or top_score < 2:
            return THEME_FALLBACK[:3], "LOW"
        return top, "MEDIUM"

    def _build_theme_blocks(self, sources: List[Dict], themes: List[str]) -> List[ThemeBlock]:
        blocks: List[ThemeBlock] = []
        for theme in themes:
            keywords = KEYWORD_MAP.get(theme, [])
            excerpts: List[str] = []
            srcs: List[str] = []
            for src in sources:
                text = self._extract_text(src)
                if keywords and not any(kw in text for kw in keywords):
                    continue
                note = (src.get("notes") or "").strip()
                if note:
                    excerpts.append(note)
                srcs.append(src.get("source") or src.get("title") or "unknown")
                if len(excerpts) >= 3:
                    break
            blocks.append(ThemeBlock(name=theme, excerpts=excerpts, sources=srcs[:3]))
        return blocks

    def _format_theme_block(self, block: ThemeBlock) -> str:
        lines = [f"### {block.name}"]
        if block.excerpts:
            for ex in block.excerpts:
                lines.append(f"- {ex}")
        else:
            lines.append("- No strong excerpts available yet.")
        if block.sources:
            lines.append(f"*Citations:* {', '.join(block.sources)}")
        return "\n".join(lines)

    def _actions_from_themes(self, themes: List[ThemeBlock]) -> List[str]:
        actions: List[str] = []
        for block in themes:
            actions.append(f"Review {block.name} sources and decide one concrete next step.")
        return actions[:5]

    def generate(self, auto_detect: bool = True) -> Tuple[Path, Path]:
        sources = self._filter_sources(self._load_sources())
        if not sources:
            raise ValueError("No sources available for synthesis.")

        if auto_detect:
            themes, theme_confidence = self._detect_themes(sources)
        else:
            themes, theme_confidence = (THEME_FALLBACK[:3], "LOW")
        blocks = self._build_theme_blocks(sources, themes)
        actions = self._actions_from_themes(blocks)

        now = datetime.now(timezone.utc)
        date_range = f"{(now - timedelta(days=self.days)).date()} to {now.date()}"
        stamp = now.strftime("%Y%m%d-%H%M%S")

        draft_path = storage.paths.outputs_synthesis_drafts / f"synthesis_{stamp}.md"
        final_path = storage.paths.outputs_synthesis_final / f"synthesis_{stamp}.md"

        content = [
            f"# Strategic Synthesis — {date_range}",
            "",
            "## Executive Summary",
            "This is an extractive draft based on recent sources. Review required.",
            f"Theme detection confidence: {theme_confidence}",
            "",
            "## Key Themes",
            "",
            "\n\n".join(self._format_theme_block(b) for b in blocks),
            "",
            "## Actionable Next Steps",
            "\n".join(f"{i+1}. {a}" for i, a in enumerate(actions)),
            "",
            "## Source Provenance",
            "\n".join(f"- {s.get('source','unknown')} ({s.get('timestamp','')})" for s in sources[:10]),
            "",
            "---",
            f"Generated: {now.isoformat()}",
            "Governance: No claims without sources. Human approval required.",
            "",
        ]

        draft_path.write_text("\n".join(content))
        log(f"Synthesis draft written: {draft_path}", level="INFO")
        return draft_path, final_path

    def approve(self, draft_path: Path, final_path: Path) -> Path:
        final_path.write_text(draft_path.read_text())
        log(f"Synthesis final written: {final_path}", level="INFO")
        return final_path
