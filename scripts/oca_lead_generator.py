#!/usr/bin/env python3
"""
PERMANENCE OS -- OCA Lead Generator

Scans business directories for potential Boring Wedge automation clients.
Scores leads by AI automation potential, accessibility, and industry fit.
All data gathering is read-only. No outreach without human approval.

Pipeline: config -> scrape -> score -> filter -> output -> (optional) sales pipeline

Sources:
  - Google Places API (requires PERMANENCE_GOOGLE_PLACES_KEY)
  - Yelp Fusion API (requires PERMANENCE_YELP_API_KEY)
  - YellowPages HTML scraping (no key needed)

Usage:
  python scripts/oca_lead_generator.py --action scan --industry restaurants --geo "Fayetteville, AR"
  python scripts/oca_lead_generator.py --action list
  python scripts/oca_lead_generator.py --action stats
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from urllib.parse import quote_plus

import requests

try:
    from bs4 import BeautifulSoup
    _HAS_BS4 = True
except ImportError:
    _HAS_BS4 = False

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parents[1]
WORKING_DIR = Path(os.getenv("PERMANENCE_WORKING_DIR", str(BASE_DIR / "memory" / "working")))
OUTPUT_DIR = Path(os.getenv("PERMANENCE_OUTPUT_DIR", str(BASE_DIR / "outputs" / "oca_leads")))
CONFIG_PATH = WORKING_DIR / "oca_lead_config.json"
LEADS_STATE_PATH = WORKING_DIR / "oca_leads_state.json"

TIMEOUT = int(os.getenv("PERMANENCE_OCA_LEAD_TIMEOUT", "10"))
RATE_LIMIT_DELAY = 1.0  # seconds between scraping requests

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

DEFAULT_CONFIG = {
    "target_industries": ["restaurants", "real_estate", "dental", "law_firms", "hvac"],
    "target_keywords": ["small business", "local", "appointment", "scheduling"],
    "exclude_keywords": ["enterprise", "fortune 500", "corporate"],
    "min_score_threshold": 60,
    "max_leads_per_run": 50,
    "geo_targets": ["Fayetteville, AR", "Bentonville, AR", "Rogers, AR"],
}


def load_config(path: Optional[Path] = None) -> dict:
    """Load lead gen config, creating default if missing."""
    cfg_path = path or CONFIG_PATH
    if cfg_path.exists():
        try:
            with open(cfg_path, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    # Write default
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(cfg_path, "w") as f:
            json.dump(DEFAULT_CONFIG, f, indent=2)
    except OSError:
        pass
    return DEFAULT_CONFIG.copy()


# ---------------------------------------------------------------------------
# Lead data structure
# ---------------------------------------------------------------------------

def make_lead(
    name: str,
    industry: str = "",
    website: str = "",
    email: str = "",
    phone: str = "",
    city: str = "",
    state: str = "",
    address: str = "",
    size_indicator: str = "",
    source: str = "",
    description: str = "",
) -> dict:
    """Create a standardized lead dict."""
    lead_id = "L-" + hashlib.md5(
        f"{name}:{city}:{state}".lower().encode()
    ).hexdigest()[:12]
    return {
        "lead_id": lead_id,
        "name": name.strip(),
        "industry": industry,
        "website": website,
        "email": email,
        "phone": phone,
        "city": city,
        "state": state,
        "address": address,
        "size_indicator": size_indicator,
        "source": source,
        "description": description,
        "score": 0,
        "score_breakdown": {},
        "scanned_at": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def score_lead(lead: dict, config: dict) -> dict:
    """
    Score a lead 0-100 based on automation potential.

    Returns lead with score and score_breakdown populated.
    """
    breakdown = {}
    score = 50  # base

    # Industry match
    target_industries = config.get("target_industries", [])
    if lead.get("industry", "").lower() in [i.lower() for i in target_industries]:
        score += 15
        breakdown["industry_match"] = 15

    # Website presence (no website = they need help)
    if lead.get("website"):
        score += 5
        breakdown["has_website"] = 5
    else:
        score += 10
        breakdown["no_website_needs_help"] = 10

    # Keyword matches
    text = " ".join([
        lead.get("name", ""),
        lead.get("description", ""),
        lead.get("industry", ""),
    ]).lower()

    target_keywords = config.get("target_keywords", [])
    kw_hits = sum(1 for kw in target_keywords if kw.lower() in text)
    if kw_hits > 0:
        bonus = min(kw_hits * 5, 15)
        score += bonus
        breakdown["keyword_matches"] = bonus

    # Exclude keyword penalty
    exclude_keywords = config.get("exclude_keywords", [])
    excl_hits = sum(1 for kw in exclude_keywords if kw.lower() in text)
    if excl_hits > 0:
        penalty = min(excl_hits * 20, 40)
        score -= penalty
        breakdown["exclude_penalty"] = -penalty

    # Size indicator (5-50 employees is the sweet spot)
    size = lead.get("size_indicator", "").lower()
    if any(s in size for s in ["small", "5-", "10-", "20-", "local"]):
        score += 10
        breakdown["ideal_size"] = 10
    elif any(s in size for s in ["large", "enterprise", "1000+"]):
        score -= 10
        breakdown["too_large"] = -10

    # Contact accessibility
    if lead.get("email"):
        score += 5
        breakdown["has_email"] = 5
    if lead.get("phone"):
        score += 3
        breakdown["has_phone"] = 3

    # Clamp
    score = max(0, min(100, score))

    lead["score"] = score
    lead["score_breakdown"] = breakdown
    return lead


# ---------------------------------------------------------------------------
# Discernment filter
# ---------------------------------------------------------------------------

def apply_discernment(leads: list[dict], config: dict) -> list[dict]:
    """
    Filter, deduplicate, and rank leads.

    Returns filtered list sorted by score descending.
    """
    min_threshold = config.get("min_score_threshold", 60)
    max_leads = config.get("max_leads_per_run", 50)

    # Deduplicate by lead_id
    seen = set()
    unique = []
    for lead in leads:
        lid = lead.get("lead_id", "")
        if lid not in seen:
            seen.add(lid)
            unique.append(lead)

    # Filter by threshold
    filtered = [l for l in unique if l.get("score", 0) >= min_threshold]

    # Sort by score descending
    filtered.sort(key=lambda l: l.get("score", 0), reverse=True)

    # Cap
    return filtered[:max_leads]


# ---------------------------------------------------------------------------
# Source scrapers
# ---------------------------------------------------------------------------

def scrape_google_places(industry: str, geo: str) -> list[dict]:
    """
    Fetch leads from Google Places API.

    Requires PERMANENCE_GOOGLE_PLACES_KEY environment variable.
    """
    api_key = os.environ.get("PERMANENCE_GOOGLE_PLACES_KEY", "")
    if not api_key:
        return []

    url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
    params = {
        "query": f"{industry} in {geo}",
        "key": api_key,
    }

    leads = []
    try:
        resp = requests.get(url, params=params, timeout=TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        for place in data.get("results", [])[:20]:
            addr = place.get("formatted_address", "")
            city_match = re.search(r",\s*([^,]+),\s*(\w{2})\s", addr)
            leads.append(make_lead(
                name=place.get("name", ""),
                industry=industry,
                address=addr,
                city=city_match.group(1) if city_match else "",
                state=city_match.group(2) if city_match else "",
                source="google_places",
                description=place.get("types", []),
            ))
    except requests.RequestException:
        pass

    return leads


def scrape_yelp(industry: str, geo: str) -> list[dict]:
    """
    Fetch leads from Yelp Fusion API.

    Requires PERMANENCE_YELP_API_KEY environment variable.
    """
    api_key = os.environ.get("PERMANENCE_YELP_API_KEY", "")
    if not api_key:
        return []

    url = "https://api.yelp.com/v3/businesses/search"
    headers = {"Authorization": f"Bearer {api_key}"}
    params = {"term": industry, "location": geo, "limit": 20}

    leads = []
    try:
        resp = requests.get(url, headers=headers, params=params, timeout=TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        for biz in data.get("businesses", []):
            loc = biz.get("location", {})
            leads.append(make_lead(
                name=biz.get("name", ""),
                industry=industry,
                phone=biz.get("phone", ""),
                website=biz.get("url", ""),
                city=loc.get("city", ""),
                state=loc.get("state", ""),
                address=loc.get("address1", ""),
                source="yelp",
            ))
    except requests.RequestException:
        pass

    return leads


def scrape_yellowpages(industry: str, geo: str) -> list[dict]:
    """
    Scrape YellowPages for business listings.

    No API key required. Uses BeautifulSoup for HTML parsing.
    Rate-limited to 1 request per second.
    """
    if not _HAS_BS4:
        return []

    geo_slug = geo.lower().replace(", ", "-").replace(" ", "-")
    industry_slug = industry.lower().replace(" ", "-")
    url = f"https://www.yellowpages.com/search?search_terms={quote_plus(industry)}&geo_location_terms={quote_plus(geo)}"

    leads = []
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        }
        resp = requests.get(url, headers=headers, timeout=TIMEOUT)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")
        results = soup.select(".result")[:20]

        for r in results:
            name_el = r.select_one(".business-name")
            phone_el = r.select_one(".phones")
            addr_el = r.select_one(".adr")
            website_el = r.select_one("a.track-visit-website")

            if not name_el:
                continue

            city_text = ""
            state_text = ""
            if addr_el:
                locality = addr_el.select_one(".locality")
                if locality:
                    city_text = locality.get_text(strip=True).rstrip(",")
                region = addr_el.select_one(".region")  # state abbreviation
                if region:
                    state_text = region.get_text(strip=True)

            leads.append(make_lead(
                name=name_el.get_text(strip=True),
                industry=industry,
                phone=phone_el.get_text(strip=True) if phone_el else "",
                website=website_el.get("href", "") if website_el else "",
                city=city_text,
                state=state_text,
                source="yellowpages",
            ))

        time.sleep(RATE_LIMIT_DELAY)

    except requests.RequestException:
        pass

    return leads


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

def run_scan(
    industry: str = "",
    geo: str = "",
    config: Optional[dict] = None,
    config_path: Optional[Path] = None,
) -> dict:
    """
    Run a complete lead scan: scrape -> score -> filter -> output.

    Returns summary dict with leads and metadata.
    """
    cfg = config or load_config(config_path)

    industries = [industry] if industry else cfg.get("target_industries", [])
    geos = [geo] if geo else cfg.get("geo_targets", [])

    all_leads: list[dict] = []

    for ind in industries:
        for g in geos:
            all_leads.extend(scrape_google_places(ind, g))
            all_leads.extend(scrape_yelp(ind, g))
            all_leads.extend(scrape_yellowpages(ind, g))

    # Score all leads
    for lead in all_leads:
        score_lead(lead, cfg)

    # Apply discernment
    filtered = apply_discernment(all_leads, cfg)

    # Save outputs
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    _save_outputs(filtered, ts, all_leads)

    return {
        "leads": filtered,
        "count": len(filtered),
        "total_scraped": len(all_leads),
        "industries_scanned": industries,
        "geos_scanned": geos,
        "timestamp": ts,
    }


def _save_outputs(leads: list[dict], timestamp: str, all_raw: list[dict]) -> tuple:
    """Write markdown report and JSON payload."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    json_path = OUTPUT_DIR / f"leads_{timestamp}.json"
    md_path = OUTPUT_DIR / f"leads_{timestamp}.md"

    # JSON
    try:
        with open(json_path, "w") as f:
            json.dump({"leads": leads, "count": len(leads), "total_raw": len(all_raw)}, f, indent=2)
    except OSError:
        pass

    # Markdown
    lines = [
        f"# OCA Lead Scan Report",
        f"**Date:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        f"**Leads Found:** {len(leads)} (from {len(all_raw)} raw)",
        "",
        "## Ranked Leads",
        "",
        "| # | Name | Industry | City | Score | Source | Contact |",
        "|---|------|----------|------|-------|--------|---------|",
    ]
    for i, lead in enumerate(leads):
        contact = lead.get("email") or lead.get("phone") or "---"
        lines.append(
            f"| {i+1} | {lead['name']} | {lead['industry']} | "
            f"{lead.get('city', '')} | {lead['score']} | {lead['source']} | {contact} |"
        )
    lines.append("")
    lines.append("---")
    lines.append("*Read-only scan. No outreach without human approval.*")

    try:
        with open(md_path, "w") as f:
            f.write("\n".join(lines))
    except OSError:
        pass

    return str(md_path), str(json_path)


# ---------------------------------------------------------------------------
# Recent leads accessor
# ---------------------------------------------------------------------------

def get_recent_leads(limit: int = 50) -> list[dict]:
    """Load the most recent scan results."""
    if not OUTPUT_DIR.exists():
        return []
    json_files = sorted(OUTPUT_DIR.glob("leads_*.json"), reverse=True)
    if not json_files:
        return []
    try:
        with open(json_files[0], "r") as f:
            data = json.load(f)
        return data.get("leads", [])[:limit]
    except (json.JSONDecodeError, OSError):
        return []


# ---------------------------------------------------------------------------
# Sales pipeline integration
# ---------------------------------------------------------------------------

def push_to_pipeline(leads: list[dict], count: int = 5) -> list[dict]:
    """
    Push top leads to the sales pipeline for tracking.

    Returns list of pushed lead summaries.
    """
    try:
        import sys
        sys.path.insert(0, str(BASE_DIR / "scripts"))
        from sales_pipeline import cmd_add, _load_pipeline, _save_pipeline, PIPELINE_PATH
    except ImportError:
        return [{"error": "sales_pipeline not available"}]

    pushed = []
    for lead in leads[:count]:
        try:
            pipeline = _load_pipeline(PIPELINE_PATH)
            # Check for duplicate
            existing_ids = {l.get("lead_id", "") for l in pipeline.get("leads", [])}
            if lead["lead_id"] in existing_ids:
                continue

            entry = {
                "lead_id": lead["lead_id"],
                "name": lead["name"],
                "source": f"oca_scan_{lead['source']}",
                "stage": "lead",
                "offer": "Boring Wedge Automation",
                "est_value": 500,
                "actual_value": 0,
                "next_action": "Review and qualify",
                "next_action_due": "",
                "notes": f"Score: {lead['score']}. Industry: {lead['industry']}. City: {lead.get('city', '')}.",
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            pipeline.setdefault("leads", []).append(entry)
            _save_pipeline(pipeline, PIPELINE_PATH)
            pushed.append({"lead_id": lead["lead_id"], "name": lead["name"], "score": lead["score"]})
        except Exception:
            continue

    return pushed


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="OCA Lead Generator")
    parser.add_argument("--action", required=True, choices=["scan", "list", "stats", "push"])
    parser.add_argument("--industry", default="")
    parser.add_argument("--geo", default="")
    parser.add_argument("--limit", type=int, default=5)
    args = parser.parse_args()

    if args.action == "scan":
        results = run_scan(industry=args.industry, geo=args.geo)
        print(f"Scan complete: {results['count']} leads from {results['total_scraped']} raw")
        for i, lead in enumerate(results["leads"][:10]):
            print(f"  {i+1}. [{lead['score']}] {lead['name']} ({lead['industry']}, {lead.get('city', '')})")

    elif args.action == "list":
        leads = get_recent_leads(limit=args.limit)
        print(f"Recent leads ({len(leads)}):")
        for lead in leads:
            print(f"  [{lead['score']}] {lead['name']} -- {lead['source']}")

    elif args.action == "stats":
        leads = get_recent_leads(limit=200)
        if leads:
            avg = sum(l["score"] for l in leads) / len(leads)
            sources = {}
            for l in leads:
                s = l.get("source", "unknown")
                sources[s] = sources.get(s, 0) + 1
            print(f"Stats: {len(leads)} leads, avg score {avg:.0f}")
            for src, cnt in sources.items():
                print(f"  {src}: {cnt}")
        else:
            print("No leads found. Run a scan first.")

    elif args.action == "push":
        leads = get_recent_leads(limit=args.limit)
        pushed = push_to_pipeline(leads, count=args.limit)
        print(f"Pushed {len(pushed)} leads to sales pipeline")
