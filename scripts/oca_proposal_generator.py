#!/usr/bin/env python3
"""
PERMANENCE OS -- OCA Proposal Generator

Generates Boring Wedge scope documents for potential OCA clients.
Applies brand voice compliance on all output. Nothing is sent
without human approval.

Pipeline: lead + workflow -> scope doc -> voice check -> draft queue -> human review

Usage:
  python scripts/oca_proposal_generator.py --lead-name "Bobs HVAC" --workflow lead_gen
  python scripts/oca_proposal_generator.py --list-workflows
"""

from __future__ import annotations

import argparse
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

BASE_DIR = Path(__file__).resolve().parents[1]
OUTPUT_DIR = Path(os.getenv("PERMANENCE_OUTPUT_DIR", str(BASE_DIR / "outputs" / "oca_proposals")))

# ---------------------------------------------------------------------------
# Boring Wedge workflow catalog
# ---------------------------------------------------------------------------

WORKFLOW_CATALOG = {
    "lead_gen": {
        "name": "Lead Generation Automation",
        "description": (
            "Automated lead discovery and qualification pipeline. "
            "Scans business directories, scores prospects by automation potential, "
            "and delivers ranked lead lists daily."
        ),
        "deliverables": [
            "Automated lead scraping from 3+ sources",
            "Scoring engine tuned to your target market",
            "Daily ranked lead report delivered to your inbox",
            "CRM integration for lead tracking",
            "Weekly optimization based on conversion data",
        ],
        "timeline": "7 days",
        "pricing": {"setup": 500, "monthly": 200},
    },
    "appointment_booking": {
        "name": "Appointment Booking Automation",
        "description": (
            "End-to-end appointment scheduling automation. "
            "Monitors inbound requests, manages calendar availability, "
            "sends confirmations and reminders without manual intervention."
        ),
        "deliverables": [
            "Inbound request monitoring (email, web forms)",
            "Calendar availability checking and slot selection",
            "Automated confirmation and reminder sequences",
            "No-show follow-up automation",
            "Monthly scheduling analytics report",
        ],
        "timeline": "7 days",
        "pricing": {"setup": 750, "monthly": 300},
    },
    "review_management": {
        "name": "Review Response Automation",
        "description": (
            "Automated monitoring and response drafting for online reviews. "
            "Tracks Google, Yelp, and industry-specific platforms. "
            "Generates voice-appropriate responses for human approval."
        ),
        "deliverables": [
            "Multi-platform review monitoring (Google, Yelp, Facebook)",
            "Sentiment analysis on incoming reviews",
            "Draft response generation (human-approved before posting)",
            "Review trend reporting (weekly summary)",
            "Escalation alerts for negative reviews",
        ],
        "timeline": "5 days",
        "pricing": {"setup": 400, "monthly": 150},
    },
    "invoice_follow_up": {
        "name": "Invoice Triage Automation",
        "description": (
            "Automated invoice processing and follow-up pipeline. "
            "Scans email for invoices, extracts due dates and amounts, "
            "generates priority payment lists and sends reminders."
        ),
        "deliverables": [
            "Email inbox scanning for invoice detection",
            "Data extraction (vendor, amount, due date, terms)",
            "Priority queue based on due date and amount",
            "Automated payment reminder sequences",
            "Monthly cash flow summary report",
        ],
        "timeline": "7 days",
        "pricing": {"setup": 600, "monthly": 250},
    },
    "price_monitoring": {
        "name": "Competitive Price Tracking",
        "description": (
            "Real-time competitor price monitoring automation. "
            "Tracks competitor websites, detects price changes, "
            "and delivers actionable pricing intelligence."
        ),
        "deliverables": [
            "Competitor website monitoring (up to 10 competitors)",
            "Price change detection with delta tracking",
            "Daily pricing comparison dashboard",
            "Alert system for significant price movements",
            "Monthly competitive analysis report",
        ],
        "timeline": "7 days",
        "pricing": {"setup": 500, "monthly": 200},
    },
}


# ---------------------------------------------------------------------------
# Voice compliance (reuse from content_generator)
# ---------------------------------------------------------------------------

FORBIDDEN_PATTERNS = [
    (r"!{2,}", "Multiple exclamation marks"),
    (r"(?i)\b(amazing|incredible|revolutionary|game.?changing|mind.?blowing)\b", "Hype language"),
    (r"(?i)\b(i think maybe|i feel like maybe|could possibly be)\b", "Excessive hedging"),
    (r"(?i)\b(let\'s go|crushing it|killing it|so excited)\b", "Cheerleading"),
    (r"(?i)\b(sorry but|i apologize for|forgive me for)\b", "Apologizing for substance"),
]


def check_voice_compliance(text: str) -> list[dict]:
    """Check text against brand voice rules."""
    violations = []
    for pattern, description in FORBIDDEN_PATTERNS:
        matches = re.findall(pattern, text)
        if matches:
            violations.append({"rule": description, "matches": matches[:3]})
    return violations


# ---------------------------------------------------------------------------
# Proposal generator
# ---------------------------------------------------------------------------

def list_workflows() -> list[dict]:
    """Return available Boring Wedge workflows."""
    return [
        {
            "id": wid,
            "name": w["name"],
            "timeline": w["timeline"],
            "setup_cost": w["pricing"]["setup"],
            "monthly_cost": w["pricing"]["monthly"],
        }
        for wid, w in WORKFLOW_CATALOG.items()
    ]


def generate_proposal(
    lead: dict,
    workflow_id: str,
    custom_notes: str = "",
    output_dir: Optional[Path] = None,
) -> dict:
    """
    Generate a scope document for a lead + workflow combination.

    Returns proposal dict with markdown content, voice check, and file paths.
    """
    if workflow_id not in WORKFLOW_CATALOG:
        return {
            "ok": False,
            "error": f"Unknown workflow: {workflow_id}. Available: {list(WORKFLOW_CATALOG.keys())}",
        }

    workflow = WORKFLOW_CATALOG[workflow_id]
    lead_name = lead.get("name", "Client")
    industry = lead.get("industry", "your industry")
    now = datetime.now(timezone.utc)

    # Build proposal sections
    sections = _build_sections(lead_name, industry, workflow, custom_notes)
    markdown = _render_markdown(sections, lead_name, workflow, now)

    # Voice check
    violations = check_voice_compliance(markdown)

    # Save outputs
    out_dir = output_dir or OUTPUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    safe_name = re.sub(r"[^a-zA-Z0-9]", "_", lead_name.lower())[:30]
    ts = now.strftime("%Y%m%d")
    md_path = out_dir / f"proposal_{safe_name}_{ts}.md"
    json_path = out_dir / f"proposal_{safe_name}_{ts}.json"

    result = {
        "ok": True,
        "lead_name": lead_name,
        "workflow_id": workflow_id,
        "workflow_name": workflow["name"],
        "markdown": markdown,
        "word_count": len(markdown.split()),
        "voice_compliant": len(violations) == 0,
        "voice_violations": violations,
        "pricing": workflow["pricing"],
        "timeline": workflow["timeline"],
        "generated_at": now.isoformat(),
        "md_path": str(md_path),
        "json_path": str(json_path),
    }

    try:
        with open(md_path, "w") as f:
            f.write(markdown)
    except OSError:
        result["md_path"] = ""

    try:
        with open(json_path, "w") as f:
            json.dump(result, f, indent=2)
    except OSError:
        result["json_path"] = ""

    return result


def _build_sections(
    lead_name: str,
    industry: str,
    workflow: dict,
    custom_notes: str,
) -> list[dict]:
    """Build proposal sections."""
    pricing = workflow["pricing"]

    sections = [
        {
            "heading": "Executive Summary",
            "body": (
                f"This proposal outlines a {workflow['name'].lower()} built specifically "
                f"for {lead_name}. {workflow['description']} "
                f"The system is operational within {workflow['timeline']} of project start."
            ),
        },
        {
            "heading": "What We Build",
            "body": "\n".join(f"- {d}" for d in workflow["deliverables"]),
        },
        {
            "heading": "Timeline",
            "body": (
                f"**Delivery:** {workflow['timeline']} from signed agreement.\n\n"
                "The process follows three phases:\n"
                "1. **Setup** (Days 1-2) -- Scope confirmation, access credentials, system configuration\n"
                "2. **Build and Test** (Days 3-5) -- Core automation built and tested against real data\n"
                "3. **Launch and Verify** (Days 6-7) -- Go-live, monitoring, and handoff documentation"
            ),
        },
        {
            "heading": "Pricing",
            "body": (
                f"| Component | Cost |\n"
                f"|-----------|------|\n"
                f"| One-time setup | ${pricing['setup']:,} |\n"
                f"| Monthly service | ${pricing['monthly']:,}/mo |\n"
                f"\n"
                f"Setup covers initial build, testing, and deployment. "
                f"Monthly covers ongoing operation, monitoring, and optimization."
            ),
        },
        {
            "heading": "How It Works",
            "body": (
                "The automation runs as a governed agent swarm inside a secure environment. "
                "Every consequential action requires human approval. "
                "You receive daily reports and can adjust parameters at any time.\n\n"
                "The system uses Permanence OS governance -- the same architecture that runs "
                "960+ automated tests on every change. Your data stays under your control."
            ),
        },
        {
            "heading": "Terms",
            "body": (
                "- Setup fee due at project start\n"
                "- Monthly billing begins after successful launch\n"
                "- 30-day cancellation notice on monthly service\n"
                "- One round of revisions included in setup\n"
                "- All automations include human approval gates for consequential actions"
            ),
        },
    ]

    if custom_notes:
        sections.append({
            "heading": "Additional Notes",
            "body": custom_notes,
        })

    return sections


def _render_markdown(
    sections: list[dict],
    lead_name: str,
    workflow: dict,
    now: datetime,
) -> str:
    """Render sections into full markdown document."""
    lines = [
        f"# Proposal: {workflow['name']}",
        f"**Prepared for:** {lead_name}",
        f"**Date:** {now.strftime('%B %d, %Y')}",
        f"**From:** Permanence Systems",
        "",
        "---",
        "",
    ]

    for section in sections:
        lines.append(f"## {section['heading']}")
        lines.append("")
        lines.append(section["body"])
        lines.append("")
        lines.append("---")
        lines.append("")

    lines.append("*Prepared by Permanence Systems. Governed by humans, amplified by agents.*")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="OCA Proposal Generator")
    parser.add_argument("--lead-name", default="")
    parser.add_argument("--workflow", default="lead_gen")
    parser.add_argument("--industry", default="")
    parser.add_argument("--notes", default="")
    parser.add_argument("--list-workflows", action="store_true")
    args = parser.parse_args()

    if args.list_workflows:
        for w in list_workflows():
            print(f"  {w['id']}: {w['name']} (${w['setup_cost']} setup, ${w['monthly_cost']}/mo, {w['timeline']})")
    elif args.lead_name:
        lead = {"name": args.lead_name, "industry": args.industry}
        result = generate_proposal(lead, args.workflow, custom_notes=args.notes)
        if result.get("ok"):
            print(f"Proposal generated: {result['workflow_name']}")
            print(f"  Words: {result['word_count']}")
            print(f"  Voice compliant: {result['voice_compliant']}")
            print(f"  Saved: {result['md_path']}")
        else:
            print(f"Error: {result.get('error')}")
    else:
        print("Provide --lead-name or --list-workflows")
