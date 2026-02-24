"""
context_loader.py
Permanence OS — Brand & Identity Context Injection
────────────────────────────────────────────────────
Purpose:
  Loads brand_identity.yaml from the Canon and injects relevant sections
  into agent system prompts when the task involves external communication,
  content creation, social media, or brand-adjacent work.

Usage:
  from context_loader import BrandContextLoader

  loader = BrandContextLoader()

  # Get voice rules for Executor Agent
  voice_context = loader.get_voice_context()

  # Get full identity brief for Social Agent
  full_context = loader.get_full_brand_context()

  # Check if a task needs brand context injected
  needs_context = loader.task_requires_brand_context(task_goal)

Canon Reference: brand_identity.yaml (CA-013)
Governance: READ operation only — this loader never modifies Canon files.
"""

import os
import json
from pathlib import Path
from typing import Optional

import yaml


# ─── CONFIG ────────────────────────────────────────────────────────────────────

CANON_DIR = Path(__file__).parent / "canon"
BRAND_IDENTITY_PATH = CANON_DIR / "brand_identity.yaml"
CHRONICLE_OUTPUT_DIR = Path(__file__).parent / "outputs" / "chronicle"
CHRONICLE_SHARED_LATEST = Path(__file__).parent / "memory" / "chronicle" / "shared" / "chronicle_latest.json"

# Tasks containing these keywords trigger brand context injection
BRAND_CONTEXT_TRIGGERS = [
    "write", "draft", "post", "tweet", "email", "content",
    "social", "caption", "essay", "blog", "copy", "message",
    "communicate", "brand", "voice", "tone", "publish",
    "announce", "release", "description", "bio", "about",
    "marketing", "campaign", "pitch", "present"
]

# Tasks containing these keywords trigger chronicle context injection
CHRONICLE_CONTEXT_TRIGGERS = [
    "improve",
    "improvement",
    "upgrade",
    "update",
    "research",
    "study",
    "roadmap",
    "priority",
    "next step",
    "agent",
    "system",
    "governance",
    "issue",
    "error",
    "friction",
]


# ─── LOADER ────────────────────────────────────────────────────────────────────

class BrandContextLoader:
    """
    Loads brand identity Canon and provides context injection methods.
    All reads are logged. No writes permitted.
    """

    def __init__(self, canon_path: Optional[Path] = None):
        self.canon_path = canon_path or BRAND_IDENTITY_PATH
        self._data = None
        self._load()

    def _load(self):
        """Load and validate the brand identity Canon file."""
        if not self.canon_path.exists():
            raise FileNotFoundError(
                f"Brand Identity Canon not found at {self.canon_path}. "
                "Run Canon setup to initialize brand_identity.yaml."
            )
        with open(self.canon_path, "r") as f:
            self._data = yaml.safe_load(f)

    def task_requires_brand_context(self, task_goal: str) -> bool:
        """
        Returns True if the task goal contains keywords that suggest
        brand context should be injected into the agent prompt.

        Args:
            task_goal: The task description string

        Returns:
            bool: True if brand context injection is recommended
        """
        task_lower = task_goal.lower()
        return any(trigger in task_lower for trigger in BRAND_CONTEXT_TRIGGERS)

    def get_voice_context(self) -> str:
        """
        Returns a compressed voice brief for injection into Executor Agent prompts.
        Use this for content creation, writing, and communication tasks.
        """
        voice = self._data.get("brand_voice", {})
        principles = voice.get("principles", [])
        forbidden = voice.get("forbidden", [])
        preferred = voice.get("preferred_constructions", [])

        lines = [
            "═══ BRAND VOICE (Canon Reference: brand_identity.yaml) ═══",
            "",
            "PRINCIPLES:",
        ]
        for p in principles:
            lines.append(f"  — {p}")

        lines.append("")
        lines.append("FORBIDDEN:")
        for f in forbidden:
            lines.append(f"  ✗ {f}")

        lines.append("")
        lines.append("PREFERRED CONSTRUCTIONS:")
        for c in preferred:
            lines.append(f"  ✓ {c}")

        lines.append("")
        lines.append("TAGLINE: 'Intelligence without governance breaks.'")
        lines.append("═══════════════════════════════════════════════════")

        return "\n".join(lines)

    def get_identity_traits(self) -> str:
        """
        Returns the 10 core identity traits as a compressed brief.
        Use when the agent needs to understand the person behind the brand.
        """
        traits = self._data.get("identity_traits", [])

        lines = [
            "═══ IDENTITY TRAITS (Canon Reference: brand_identity.yaml) ═══",
            "",
            "The founder operates from these 10 core traits:",
            ""
        ]

        for trait in traits:
            name = trait.get("name", "").replace("_", " ")
            definition = trait.get("definition", "").strip().replace("\n", " ")
            anti = trait.get("anti_pattern", "")
            lines.append(f"[{name.upper()}]")
            lines.append(f"  {definition}")
            if anti:
                lines.append(f"  Anti-pattern: {anti}")
            lines.append("")

        lines.append("KEY PRINCIPLE: Cool is not the absence of fire.")
        lines.append("It is fire that knows when it's needed.")
        lines.append("═══════════════════════════════════════════════════════")

        return "\n".join(lines)

    def get_cultural_dna(self) -> str:
        """
        Returns cultural reference brief. Use when content needs to feel
        authentic to the founder's background, not generic.
        """
        dna = self._data.get("cultural_dna", {})

        lines = ["═══ CULTURAL DNA ═══", ""]

        geo = dna.get("geographic_roots", [])
        if geo:
            lines.append("ROOTS:")
            for g in geo:
                lines.append(f"  — {g}")
            lines.append("")

        sonic = dna.get("sonic_identity", {})
        if sonic:
            lines.append("SONIC IDENTITY:")
            for artist, lesson in sonic.items():
                lines.append(f"  — {artist.title()}: {lesson}")
            lines.append("")

        lines.append("═════════════════════")
        return "\n".join(lines)

    def get_full_brand_context(self) -> str:
        """
        Returns the complete brand context brief.
        Use for Social Agent, Executor on major content pieces, or any
        agent that needs to operate in full brand alignment.
        """
        system = self._data.get("system", {})

        sections = [
            "╔══════════════════════════════════════════════════════════╗",
            "║          PERMANENCE SYSTEMS — BRAND CONTEXT BRIEF        ║",
            "║          Canon Reference: brand_identity.yaml (CA-013)   ║",
            "╚══════════════════════════════════════════════════════════╝",
            "",
            f"Company: {system.get('company', 'Permanence Systems')}",
            f"Tagline: {system.get('tagline', '')}",
            f"Domain: {system.get('domain', '')}",
            "",
            self.get_voice_context(),
            "",
            self.get_identity_traits(),
            "",
            self.get_cultural_dna(),
        ]
        return "\n".join(sections)

    def get_system_info(self) -> dict:
        """Returns raw system identity dict."""
        return self._data.get("system", {})

    def get_colors(self) -> dict:
        """Returns color palette dict for design-related tasks."""
        return self._data.get("aesthetic", {}).get("color_palette", {})

    def get_apparel_lines(self) -> dict:
        """Returns apparel system for product-related tasks."""
        return self._data.get("apparel_lines", {})


# ─── CHRONICLE LOADER ─────────────────────────────────────────────────────────

class ChronicleContextLoader:
    """
    Loads latest chronicle timeline report and provides compressed system-learning
    context for self-improving workflows.
    """

    def __init__(self, chronicle_output_dir: Optional[Path] = None):
        self.chronicle_output_dir = chronicle_output_dir or CHRONICLE_OUTPUT_DIR

    def task_requires_chronicle_context(self, task_goal: str) -> bool:
        task_lower = task_goal.lower()
        return any(trigger in task_lower for trigger in CHRONICLE_CONTEXT_TRIGGERS)

    def _latest_report_path(self) -> Optional[Path]:
        if CHRONICLE_SHARED_LATEST.exists():
            return CHRONICLE_SHARED_LATEST

        if not self.chronicle_output_dir.exists():
            return None

        candidates = sorted(
            self.chronicle_output_dir.glob("chronicle_report_*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        return candidates[0] if candidates else None

    def load_latest_report(self) -> Optional[dict]:
        path = self._latest_report_path()
        if not path:
            return None
        try:
            with open(path, "r") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return data
        except (OSError, json.JSONDecodeError):
            return None
        return None

    def get_chronicle_context(
        self,
        max_direction_events: int = 3,
        max_issue_events: int = 3,
    ) -> str:
        report = self.load_latest_report()
        if not report:
            return "\n".join(
                [
                    "═══ CHRONICLE CONTEXT ═══",
                    "No chronicle report found.",
                    "Run: python cli.py chronicle-report",
                    "═════════════════════════",
                ]
            )

        totals = report.get("signal_totals") or {}
        direction_events = report.get("direction_events") or []
        issue_events = report.get("issue_events") or []
        source_artifacts = report.get("source_artifacts") or []

        lines = [
            "═══ CHRONICLE CONTEXT ═══",
            f"Generated: {report.get('generated_at', 'unknown')}",
            f"Window days: {report.get('days', 'unknown')}",
            f"Events: {report.get('events_count', 0)}",
            f"Commits: {report.get('commit_count', 0)}",
            "",
            "SIGNAL TOTALS:",
            f"  - Direction hits: {totals.get('direction_hits', 0)}",
            f"  - Frustration hits: {totals.get('frustration_hits', 0)}",
            f"  - Issue hits: {totals.get('issue_hits', 0)}",
            f"  - Log errors: {totals.get('log_error_hits', 0)}",
            "",
            "DIRECTION EVENTS:",
        ]
        for item in direction_events[-max_direction_events:]:
            lines.append(f"  - {item.get('timestamp', 'unknown')}: {item.get('summary', '')}")
        if not direction_events:
            lines.append("  - none")

        lines.extend(["", "ISSUE EVENTS:"])
        for item in issue_events[-max_issue_events:]:
            lines.append(f"  - {item.get('timestamp', 'unknown')}: {item.get('summary', '')}")
        if not issue_events:
            lines.append("  - none")

        if source_artifacts:
            lines.extend(["", f"Artifacts tracked: {len(source_artifacts)}"])
        lines.append("═════════════════════════")
        return "\n".join(lines)


# ─── AGENT INJECTION HELPER ────────────────────────────────────────────────────

def inject_brand_context_if_needed(
    task_goal: str,
    base_system_prompt: str,
    level: str = "voice"
) -> str:
    """
    Convenience function. Checks if task needs brand context and returns
    an augmented system prompt if so.

    Args:
        task_goal:          The task description
        base_system_prompt: The agent's existing system prompt
        level:              'voice' | 'identity' | 'full'
                            voice    = just voice rules (default, lightweight)
                            identity = voice + identity traits
                            full     = complete brand context

    Returns:
        str: The system prompt, augmented with brand context if relevant
    """
    loader = BrandContextLoader()

    if not loader.task_requires_brand_context(task_goal):
        return base_system_prompt

    if level == "full":
        context = loader.get_full_brand_context()
    elif level == "identity":
        context = loader.get_voice_context() + "\n\n" + loader.get_identity_traits()
    else:
        context = loader.get_voice_context()

    return f"{base_system_prompt}\n\n{context}"


def inject_chronicle_context_if_needed(
    task_goal: str,
    base_system_prompt: str,
    max_direction_events: int = 3,
    max_issue_events: int = 3,
) -> str:
    """
    Checks if task semantics indicate self-improvement/system-learning context
    should be injected and returns augmented prompt if so.
    """
    loader = ChronicleContextLoader()
    if not loader.task_requires_chronicle_context(task_goal):
        return base_system_prompt

    context = loader.get_chronicle_context(
        max_direction_events=max_direction_events,
        max_issue_events=max_issue_events,
    )
    return f"{base_system_prompt}\n\n{context}"


# ─── CLI (for testing) ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    loader = BrandContextLoader()

    if len(sys.argv) > 1:
        command = sys.argv[1]
        if command == "voice":
            print(loader.get_voice_context())
        elif command == "identity":
            print(loader.get_identity_traits())
        elif command == "dna":
            print(loader.get_cultural_dna())
        elif command == "full":
            print(loader.get_full_brand_context())
        elif command == "check":
            task = " ".join(sys.argv[2:])
            result = loader.task_requires_brand_context(task)
            print(f"Task: '{task}'")
            print(f"Needs brand context: {result}")
        elif command == "chronicle":
            print(ChronicleContextLoader().get_chronicle_context())
        elif command == "chronicle-check":
            task = " ".join(sys.argv[2:])
            result = ChronicleContextLoader().task_requires_chronicle_context(task)
            print(f"Task: '{task}'")
            print(f"Needs chronicle context: {result}")
        else:
            print(
                "Unknown command. Use: voice | identity | dna | full | check <task> "
                "| chronicle | chronicle-check <task>"
            )
    else:
        # Default: show voice context
        print(loader.get_voice_context())
