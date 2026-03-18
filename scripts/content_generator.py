#!/usr/bin/env python3
"""
PERMANENCE OS -- Content Generator

Transforms bookmark insights, research feeds, and knowledge graph themes
into publishable content drafts. All output flows into social_draft_queue.py
for human approval before publishing.

Content types:
  - X threads (multi-tweet, 280-char per segment)
  - Newsletter issues (structured markdown for Beehiiv)
  - LinkedIn posts (professional, 1300-char target)
  - Short-form scripts (TikTok/Reels, 60s spoken)

Voice governance:
  Loads brand_identity.yaml and enforces voice rules on all output.
  Forbidden patterns are checked before draft submission.

Pipeline:
  bookmarks/research -> theme extraction -> content framing -> voice check -> draft queue

Usage:
  python scripts/content_generator.py --action thread --topic "AI governance"
  python scripts/content_generator.py --action newsletter --issue 1
  python scripts/content_generator.py --action from-bookmarks --limit 5
  python scripts/content_generator.py --action stats
"""

from __future__ import annotations

import json
import os
import re
import textwrap
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parents[1]
CANON_DIR = BASE_DIR / "canon"
WORKING_DIR = Path(os.getenv("PERMANENCE_WORKING_DIR", str(BASE_DIR / "memory" / "working")))
OUTPUT_DIR = Path(os.getenv("PERMANENCE_OUTPUT_DIR", str(BASE_DIR / "outputs")))
BOOKMARK_INTAKE = BASE_DIR / "memory" / "inbox" / "bookmark_intake.jsonl"
CONTENT_STATE_DIR = WORKING_DIR / "content_generator"
CONTENT_LOG = CONTENT_STATE_DIR / "generation_log.jsonl"
NEWSLETTER_DIR = OUTPUT_DIR / "newsletters"


# ---------------------------------------------------------------------------
# Brand voice loader
# ---------------------------------------------------------------------------

def load_brand_voice() -> dict:
    """Load voice rules from canon/brand_identity.yaml."""
    voice = {
        "principles": [],
        "forbidden": [],
        "preferred_constructions": [],
        "identity_traits": [],
    }
    brand_path = CANON_DIR / "brand_identity.yaml"
    if not brand_path.exists():
        return voice
    try:
        import yaml
        with open(brand_path, "r") as f:
            data = yaml.safe_load(f)
        bv = data.get("brand_voice", {})
        voice["principles"] = bv.get("principles", [])
        voice["forbidden"] = bv.get("forbidden", [])
        voice["preferred_constructions"] = bv.get("preferred_constructions", [])
        traits = data.get("identity_traits", [])
        voice["identity_traits"] = [t.get("name", "") for t in traits if isinstance(t, dict)]
    except ImportError:
        # YAML not available -- use hardcoded essentials
        voice["forbidden"] = [
            "Motivational language or cheerleading",
            "Hedging out of fear",
            "Performing intelligence through vocabulary complexity",
            "Apologizing for substance",
            "Excessive enthusiasm or exclamation marks",
            "Vague inspirational metaphors without concrete mechanisms",
        ]
        voice["preferred_constructions"] = [
            "This works because...",
            "The constraint is...",
            "Pattern: X appears when Y",
            "Trade-off: gain X, lose Y",
            "Failure mode: ...",
            "Under these conditions...",
        ]
    except Exception:
        pass
    return voice


# ---------------------------------------------------------------------------
# Voice compliance checker
# ---------------------------------------------------------------------------

FORBIDDEN_PATTERNS = [
    (r"!{2,}", "Multiple exclamation marks"),
    (r"(?i)\b(amazing|incredible|revolutionary|game.?changing|mind.?blowing)\b", "Hype language"),
    (r"(?i)\b(i think maybe|i feel like maybe|could possibly be)\b", "Excessive hedging"),
    (r"(?i)\b(let\'s go|crushing it|killing it|so excited)\b", "Cheerleading"),
    (r"(?i)\b(sorry but|i apologize for|forgive me for)\b", "Apologizing for substance"),
]


def check_voice_compliance(text: str) -> list[dict]:
    """
    Check text against brand voice rules.

    Returns list of violations (empty = compliant).
    """
    violations = []
    for pattern, description in FORBIDDEN_PATTERNS:
        matches = re.findall(pattern, text)
        if matches:
            violations.append({
                "rule": description,
                "matches": matches[:3],  # cap at 3 examples
            })

    # Check exclamation density
    excl_count = text.count("!")
    word_count = max(1, len(text.split()))
    if excl_count / word_count > 0.03:  # more than 3% words end with !
        violations.append({
            "rule": "Excessive enthusiasm (exclamation density)",
            "matches": [f"{excl_count} exclamation marks in {word_count} words"],
        })

    return violations


# ---------------------------------------------------------------------------
# Theme extraction from bookmarks
# ---------------------------------------------------------------------------

THEME_MAP = {
    "ai_governance": {
        "keywords": ["governance", "safety", "alignment", "compliance", "audit", "trust", "regulation"],
        "label": "AI Governance",
        "angle": "Why 95% of AI projects fail -- and why governance is the fix, not the bottleneck",
    },
    "agent_systems": {
        "keywords": ["agent", "swarm", "orchestration", "multi-agent", "autonomous", "agentic"],
        "label": "Agent Systems",
        "angle": "The shift from chatbots to agent swarms -- and what the architecture actually looks like",
    },
    "trading_intelligence": {
        "keywords": ["trading", "market", "backtest", "smc", "ict", "order block", "liquidity", "hedge fund"],
        "label": "Trading Intelligence",
        "angle": "AI-powered trading is not what Twitter thinks -- here is what actually works",
    },
    "open_source_infra": {
        "keywords": ["open source", "github", "framework", "infrastructure", "stack", "deploy"],
        "label": "Open Source Infrastructure",
        "angle": "The best AI tools no one is talking about -- and how to use them",
    },
    "personal_intelligence": {
        "keywords": ["personal", "memory", "knowledge graph", "life os", "second brain", "productivity"],
        "label": "Personal Intelligence",
        "angle": "Your AI should know you -- not just answer questions",
    },
    "data_sovereignty": {
        "keywords": ["local", "privacy", "self-hosted", "sovereignty", "own your data", "on-device"],
        "label": "Data Sovereignty",
        "angle": "Every AI company wants your data. Here is how to keep it.",
    },
}


def extract_themes(bookmarks: list[dict]) -> dict[str, list[dict]]:
    """
    Group bookmarks by theme using keyword matching.

    Returns {theme_id: [bookmark, ...]} with only themes that have matches.
    """
    themed: dict[str, list[dict]] = {}
    for bm in bookmarks:
        text = " ".join([
            bm.get("title", ""),
            bm.get("text", ""),
            bm.get("note", ""),
            " ".join(bm.get("topics", [])),
        ]).lower()

        for theme_id, theme_info in THEME_MAP.items():
            if any(kw in text for kw in theme_info["keywords"]):
                if theme_id not in themed:
                    themed[theme_id] = []
                themed[theme_id].append(bm)

    return themed


def load_bookmarks(limit: int = 50) -> list[dict]:
    """Load bookmarks from the intake JSONL file."""
    bookmarks = []
    if not BOOKMARK_INTAKE.exists():
        return bookmarks
    try:
        with open(BOOKMARK_INTAKE, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    bm = json.loads(line)
                    bookmarks.append(bm)
                except json.JSONDecodeError:
                    continue
                if len(bookmarks) >= limit:
                    break
    except OSError:
        pass
    return bookmarks


# ---------------------------------------------------------------------------
# Content generators
# ---------------------------------------------------------------------------

def generate_thread(
    topic: str,
    points: list[str],
    hook: str = "",
    cta: str = "",
    source_urls: Optional[list[str]] = None,
) -> dict:
    """
    Generate an X thread from structured points.

    Returns {
        "platform": "x",
        "content_type": "thread",
        "segments": [...],
        "full_text": "...",
        "metadata": {...}
    }
    """
    segments = []

    # Hook tweet (tweet 1)
    if hook:
        segments.append(_trim_tweet(hook))
    else:
        segments.append(_trim_tweet(f"{topic}\n\nA thread:"))

    # Body tweets
    for i, point in enumerate(points):
        prefix = f"{i + 1}/ "
        segments.append(_trim_tweet(prefix + point))

    # CTA tweet
    if cta:
        segments.append(_trim_tweet(cta))
    else:
        segments.append(_trim_tweet(
            "If this was useful, follow @kaeldax for more on AI governance, "
            "agent systems, and building intelligence that actually works."
        ))

    full_text = "\n\n---\n\n".join(segments)

    # Voice check
    violations = check_voice_compliance(full_text)

    result = {
        "platform": "x",
        "content_type": "thread",
        "segments": segments,
        "segment_count": len(segments),
        "full_text": full_text,
        "topic": topic,
        "voice_violations": violations,
        "voice_compliant": len(violations) == 0,
        "source_urls": source_urls or [],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    return result


def _trim_tweet(text: str, limit: int = 280) -> str:
    """Trim text to tweet length, breaking at word boundary."""
    text = text.strip()
    if len(text) <= limit:
        return text
    trimmed = text[:limit - 3]
    # Break at last space
    last_space = trimmed.rfind(" ")
    if last_space > limit // 2:
        trimmed = trimmed[:last_space]
    return trimmed + "..."


def generate_newsletter_issue(
    issue_number: int,
    title: str,
    sections: list[dict],
    intro: str = "",
    outro: str = "",
) -> dict:
    """
    Generate a newsletter issue in structured markdown.

    Each section: {"heading": str, "body": str, "links": [str]}

    Returns {
        "platform": "newsletter",
        "content_type": "newsletter_issue",
        "markdown": "...",
        "metadata": {...}
    }
    """
    lines = []
    lines.append(f"# Dark Horse Intelligence -- Issue #{issue_number}")
    lines.append(f"## {title}")
    lines.append("")
    lines.append(f"*{datetime.now(timezone.utc).strftime('%B %d, %Y')}*")
    lines.append("")

    if intro:
        lines.append(intro)
        lines.append("")

    lines.append("---")
    lines.append("")

    for section in sections:
        lines.append(f"### {section.get('heading', 'Untitled')}")
        lines.append("")
        lines.append(section.get("body", ""))
        lines.append("")
        links = section.get("links", [])
        if links:
            for link in links:
                lines.append(f"- [{link}]({link})")
            lines.append("")
        lines.append("---")
        lines.append("")

    if outro:
        lines.append(outro)
    else:
        lines.append("That is it for this issue. Forward to someone building with AI.")
        lines.append("")
        lines.append("-- Kael Dax / Permanence Systems")

    markdown = "\n".join(lines)
    violations = check_voice_compliance(markdown)

    return {
        "platform": "newsletter",
        "content_type": "newsletter_issue",
        "issue_number": issue_number,
        "title": title,
        "section_count": len(sections),
        "markdown": markdown,
        "word_count": len(markdown.split()),
        "voice_violations": violations,
        "voice_compliant": len(violations) == 0,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def generate_linkedin_post(
    topic: str,
    body: str,
    hashtags: Optional[list[str]] = None,
) -> dict:
    """
    Generate a LinkedIn post (1300 char target).

    Returns structured post dict.
    """
    # LinkedIn best practice: hook line, blank line, body, hashtags
    text = body.strip()

    if hashtags:
        tag_str = " ".join(f"#{h}" for h in hashtags)
        text = f"{text}\n\n{tag_str}"

    # Trim to ~1300 chars
    if len(text) > 1300:
        text = text[:1297] + "..."

    violations = check_voice_compliance(text)

    return {
        "platform": "linkedin",
        "content_type": "post",
        "content": text,
        "topic": topic,
        "char_count": len(text),
        "voice_violations": violations,
        "voice_compliant": len(violations) == 0,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def generate_short_script(
    topic: str,
    hook: str,
    body: str,
    cta: str = "",
    duration_target: int = 60,
) -> dict:
    """
    Generate a short-form video script (TikTok/Reels).

    Returns structured script dict with timing estimates.
    """
    parts = [hook.strip(), body.strip()]
    if cta:
        parts.append(cta.strip())

    full_script = "\n\n".join(parts)

    # Estimate duration: ~150 words per minute for speaking
    word_count = len(full_script.split())
    est_duration = round(word_count / 2.5)  # seconds (150wpm = 2.5wps)

    violations = check_voice_compliance(full_script)

    return {
        "platform": "tiktok",
        "content_type": "tiktok_script",
        "topic": topic,
        "hook": hook,
        "body": body,
        "cta": cta,
        "full_script": full_script,
        "word_count": word_count,
        "est_duration_seconds": est_duration,
        "duration_target": duration_target,
        "over_target": est_duration > duration_target,
        "voice_violations": violations,
        "voice_compliant": len(violations) == 0,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# Bookmark-to-content pipeline
# ---------------------------------------------------------------------------

def bookmarks_to_threads(limit: int = 5) -> list[dict]:
    """
    Load bookmarks, extract themes, and generate thread drafts.

    Returns list of thread dicts ready for draft queue submission.
    """
    bookmarks = load_bookmarks(limit=limit * 10)  # load extra for filtering
    if not bookmarks:
        return []

    themed = extract_themes(bookmarks)
    threads = []

    for theme_id, bms in themed.items():
        if len(threads) >= limit:
            break

        theme_info = THEME_MAP.get(theme_id, {})
        label = theme_info.get("label", theme_id)
        angle = theme_info.get("angle", f"Insights on {label}")

        # Build thread points from top bookmarks (by signal score)
        sorted_bms = sorted(bms, key=lambda b: b.get("signal_score", 0), reverse=True)[:5]

        points = []
        source_urls = []
        for bm in sorted_bms:
            title = bm.get("title", "")
            note = bm.get("note", bm.get("text", ""))
            url = bm.get("url", "")

            if title:
                point = f"{title}."
                if note and len(note) < 200:
                    point += f" {note}"
                points.append(point)
            if url:
                source_urls.append(url)

        if not points:
            continue

        thread = generate_thread(
            topic=label,
            points=points,
            hook=angle,
            source_urls=source_urls,
        )
        thread["theme_id"] = theme_id
        thread["bookmark_count"] = len(sorted_bms)
        threads.append(thread)

    return threads


def bookmarks_to_newsletter(issue_number: int = 1, max_sections: int = 5) -> dict:
    """
    Generate a newsletter issue from bookmark themes.
    """
    bookmarks = load_bookmarks(limit=100)
    if not bookmarks:
        return {"error": "No bookmarks found in intake"}

    themed = extract_themes(bookmarks)
    sections = []

    for theme_id, bms in themed.items():
        if len(sections) >= max_sections:
            break

        theme_info = THEME_MAP.get(theme_id, {})
        label = theme_info.get("label", theme_id)
        angle = theme_info.get("angle", "")

        sorted_bms = sorted(bms, key=lambda b: b.get("signal_score", 0), reverse=True)[:3]

        body_parts = [angle] if angle else []
        links = []
        for bm in sorted_bms:
            title = bm.get("title", "Untitled")
            url = bm.get("url", "")
            note = bm.get("note", "")
            body_parts.append(f"**{title}** -- {note}" if note else f"**{title}**")
            if url:
                links.append(url)

        sections.append({
            "heading": label,
            "body": "\n\n".join(body_parts),
            "links": links,
        })

    if not sections:
        return {"error": "No themes extracted from bookmarks"}

    return generate_newsletter_issue(
        issue_number=issue_number,
        title="Intelligence Briefing",
        sections=sections,
        intro="This week in AI governance, agent systems, and the infrastructure nobody is talking about.",
    )


# ---------------------------------------------------------------------------
# Draft queue integration
# ---------------------------------------------------------------------------

def submit_to_draft_queue(content: dict, db_path: Optional[str] = None) -> dict:
    """
    Submit generated content to social_draft_queue for human approval.
    """
    try:
        from social_draft_queue import submit_draft
    except ImportError:
        import sys
        sys.path.insert(0, str(BASE_DIR / "scripts"))
        from social_draft_queue import submit_draft

    platform = content.get("platform", "x")
    content_type = content.get("content_type", "post")

    # Map newsletter to a supported platform
    if platform == "newsletter":
        platform = "x"  # store under X, content_type differentiates
        content_type = "post"

    # Get the text content
    text = content.get("full_text", content.get("markdown", content.get("content", "")))

    metadata = {
        "generator": "content_generator",
        "topic": content.get("topic", ""),
        "voice_compliant": content.get("voice_compliant", False),
        "voice_violations": content.get("voice_violations", []),
        "source_urls": content.get("source_urls", []),
        "generated_at": content.get("generated_at", ""),
    }

    if content.get("segments"):
        metadata["segment_count"] = content.get("segment_count", 0)
        metadata["segments"] = content["segments"]

    return submit_draft(
        platform=platform,
        content=text,
        content_type=content_type,
        agent_id="content_generator",
        metadata=metadata,
        db_path=db_path,
    )


# ---------------------------------------------------------------------------
# Generation log
# ---------------------------------------------------------------------------

def _log_generation(action: str, result: dict) -> None:
    """Append-only generation log."""
    CONTENT_STATE_DIR.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "action": action,
        "result_keys": list(result.keys()),
        "voice_compliant": result.get("voice_compliant", None),
    }
    try:
        with open(CONTENT_LOG, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except OSError:
        pass


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

def get_stats() -> dict:
    """Return content generation statistics."""
    stats = {
        "bookmarks_available": 0,
        "themes_detected": 0,
        "generations_logged": 0,
        "newsletters_generated": 0,
    }

    # Count bookmarks
    if BOOKMARK_INTAKE.exists():
        try:
            with open(BOOKMARK_INTAKE, "r") as f:
                stats["bookmarks_available"] = sum(1 for line in f if line.strip())
        except OSError:
            pass

    # Count themes from bookmarks
    bookmarks = load_bookmarks(limit=200)
    if bookmarks:
        themed = extract_themes(bookmarks)
        stats["themes_detected"] = len(themed)

    # Count log entries
    if CONTENT_LOG.exists():
        try:
            with open(CONTENT_LOG, "r") as f:
                stats["generations_logged"] = sum(1 for line in f if line.strip())
        except OSError:
            pass

    # Count newsletters
    if NEWSLETTER_DIR.exists():
        try:
            stats["newsletters_generated"] = len(list(NEWSLETTER_DIR.glob("*.md")))
        except OSError:
            pass

    return stats


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Permanence OS Content Generator")
    parser.add_argument("--action", required=True,
                        choices=["thread", "newsletter", "linkedin", "short-script",
                                 "from-bookmarks", "stats", "voice-check"])
    parser.add_argument("--topic", default="AI Governance")
    parser.add_argument("--issue", type=int, default=1)
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--text", default="")
    parser.add_argument("--submit", action="store_true", help="Submit to draft queue")

    args = parser.parse_args()

    if args.action == "thread":
        result = generate_thread(
            topic=args.topic,
            points=[
                "Most AI systems ship speed. Zero ship trust.",
                "Governance is not a limitation -- it is the moat.",
                "The system that asks permission before spending $0.05 is the one a CFO trusts.",
                f"This is what we are building at Permanence Systems.",
            ],
            hook=f"{args.topic} -- a thread on why this matters:",
        )
        print(f"Thread: {result['segment_count']} segments")
        for i, seg in enumerate(result["segments"]):
            print(f"  [{i+1}] {seg[:80]}...")
        if result["voice_violations"]:
            print(f"  Voice violations: {len(result['voice_violations'])}")
        if args.submit:
            sub = submit_to_draft_queue(result)
            print(f"  Submitted to draft queue: {sub}")

    elif args.action == "newsletter":
        result = bookmarks_to_newsletter(issue_number=args.issue)
        if "error" in result:
            print(f"Error: {result['error']}")
        else:
            print(f"Newsletter #{result['issue_number']}: {result['title']}")
            print(f"  Sections: {result['section_count']}")
            print(f"  Words: {result['word_count']}")
            if result["voice_violations"]:
                print(f"  Voice violations: {len(result['voice_violations'])}")
            # Save to file
            NEWSLETTER_DIR.mkdir(parents=True, exist_ok=True)
            out_path = NEWSLETTER_DIR / f"issue_{args.issue:03d}.md"
            with open(out_path, "w") as f:
                f.write(result["markdown"])
            print(f"  Saved: {out_path}")

    elif args.action == "from-bookmarks":
        threads = bookmarks_to_threads(limit=args.limit)
        print(f"Generated {len(threads)} thread drafts from bookmarks:")
        for t in threads:
            print(f"  [{t.get('theme_id', '?')}] {t['segment_count']} segments, "
                  f"voice_ok={t['voice_compliant']}")
            if args.submit:
                sub = submit_to_draft_queue(t)
                print(f"    -> Submitted: {sub.get('ok', False)}")

    elif args.action == "linkedin":
        result = generate_linkedin_post(
            topic=args.topic,
            body=args.text or f"{args.topic}. The constraint is trust. Here is what that means for AI systems.",
            hashtags=["AI", "Governance", "AgentSystems"],
        )
        print(f"LinkedIn post: {result['char_count']} chars, voice_ok={result['voice_compliant']}")

    elif args.action == "short-script":
        result = generate_short_script(
            topic=args.topic,
            hook="Everyone is building AI agents. Almost nobody is governing them.",
            body=args.text or "Here is the pattern: speed without trust breaks at scale. "
                 "The system that asks before it spends is the one that survives.",
        )
        print(f"Script: {result['word_count']} words, ~{result['est_duration_seconds']}s, "
              f"voice_ok={result['voice_compliant']}")

    elif args.action == "stats":
        s = get_stats()
        print("Content Generator Stats:")
        for k, v in s.items():
            print(f"  {k}: {v}")

    elif args.action == "voice-check":
        text = args.text or "This is amazing and incredible! I think maybe we could possibly be game-changing!"
        violations = check_voice_compliance(text)
        if violations:
            print(f"Voice violations ({len(violations)}):")
            for v in violations:
                print(f"  - {v['rule']}: {v['matches']}")
        else:
            print("Voice compliant.")
