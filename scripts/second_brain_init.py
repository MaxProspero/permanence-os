#!/usr/bin/env python3
"""
Initialize second-brain working files with editable templates.
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parents[1]
WORKING_DIR = Path(os.getenv("PERMANENCE_WORKING_DIR", str(BASE_DIR / "memory" / "working")))
ATTACHMENT_INBOX_DIR = Path(
    os.getenv("PERMANENCE_ATTACHMENT_INBOX_DIR", str(BASE_DIR / "memory" / "inbox" / "attachments"))
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _life_profile_template() -> dict[str, Any]:
    return {
        "owner": "Payton",
        "north_star": "Build an integrated life + business operating system with compounding outputs.",
        "identity_principles": [
            "Protect attention as a core asset.",
            "Ship consistently and review honestly.",
            "Preserve health and relationships while scaling income.",
        ],
        "daily_non_negotiables": [
            "Language output sprint (25 minutes)",
            "Top revenue action before noon",
            "Health baseline block",
            "Relationship touchpoint",
        ],
        "weekly_focus": [
            "Advance one side-income stream by one measurable stage.",
            "Ship one system-level automation improvement.",
        ],
        "updated_at": _now_iso(),
    }


def _life_tasks_template() -> list[dict[str, Any]]:
    return [
        {
            "task_id": "LIFE-001",
            "title": "Run language output sprint",
            "domain": "cognitive",
            "priority": "high",
            "status": "open",
            "due": "today",
            "next_action": "10 minutes active output + corrections log.",
        },
        {
            "task_id": "LIFE-002",
            "title": "Execute top revenue action",
            "domain": "business",
            "priority": "high",
            "status": "open",
            "due": "today",
            "next_action": "Move one lead to the next stage.",
        },
    ]


def _side_business_template() -> list[dict[str, Any]]:
    return [
        {
            "stream_id": "clip-studio",
            "name": "Shorts Clipping Studio",
            "model": "service",
            "stage": "validate",
            "risk": "medium",
            "weekly_goal_usd": 1500,
            "weekly_actual_usd": 0,
            "pipeline_count": 0,
            "manual_approval_required": True,
            "next_action": "Send 5 offers in one niche and collect conversion data.",
        },
        {
            "stream_id": "prediction-research",
            "name": "Prediction Research Desk",
            "model": "research",
            "stage": "build",
            "risk": "high",
            "weekly_goal_usd": 500,
            "weekly_actual_usd": 0,
            "pipeline_count": 0,
            "manual_approval_required": True,
            "next_action": "Backtest and paper-trade EV models only.",
        },
    ]


def _prediction_template() -> list[dict[str, Any]]:
    return [
        {
            "hypothesis_id": "PM-001",
            "title": "Sample policy outcome market",
            "market": "paper_demo",
            "status": "watchlist",
            "prior_prob": 0.50,
            "signal_score": 0.00,
            "market_prob": 0.50,
            "odds_decimal": 2.0,
            "confidence": "low",
            "notes": "Advisory only. Manual approval required for any real-money action.",
        }
    ]


def _prediction_feeds_template() -> list[dict[str, Any]]:
    return [
        {"name": "Reuters World", "url": "https://feeds.reuters.com/Reuters/worldNews"},
        {"name": "Reuters Business", "url": "https://feeds.reuters.com/reuters/businessNews"},
        {"name": "Yahoo Finance", "url": "https://finance.yahoo.com/news/rssindex"},
    ]


def _prediction_telegram_sources_template() -> list[dict[str, Any]]:
    return [
        {
            "name": "ICC Mafia",
            "channel": "iccmafia",
            "url": "https://t.me/s/iccmafia",
            "enabled": True,
            "notes": "Public Telegram channel ingest for signal discovery (read-only).",
        }
    ]


def _github_targets_template() -> list[dict[str, Any]]:
    return [
        {
            "repo": "octocat/Hello-World",
            "enabled": True,
            "focus_labels": ["bug", "enhancement", "help wanted"],
            "max_items": 20,
        }
    ]


def _github_trending_focus_template() -> dict[str, Any]:
    return {
        "since": "daily",
        "languages": ["python", "typescript", "rust"],
        "top_limit": 30,
        "watchlist_repos": [
            "MaxProspero/permanence-os",
            "ytdl-org/youtube-dl",
            "Asabeneh/30-Days-Of-Python",
            "tw93/Pake",
            "KRTirtho/spotube",
            "glanceapp/glance",
            "iawia002/lux",
            "InternLM/xtuner",
            "shaxiu/XianyuAutoAgent",
            "getsentry/XcodeBuildMCP",
            "mvanhorn/last30days-skill",
            "Josh-XT/AGiXT",
            "EvoAgentX/EvoAgentX",
            "ValueCell-ai/ClawX",
            "0xNyk/xint-rs",
            "qdev89/AppXDev.Opengravity",
            "xingbo778/xbworld",
            "azizkode/ArXiv-Agent",
            "maddada/agent-manager-x",
            "ruvnet/RuView",
            "moeru-ai/airi",
            "anthropics/prompt-eng-interactive-tutorial",
            "ruvnet/ruflo",
            "alibaba/OpenSandbox",
            "microsoft/markitdown",
            "K-Dense-AI/claude-scientific-skills",
            "superset-sh/superset",
            "servo/servo",
        ],
        "keywords": ["agent", "mcp", "automation", "finance", "trading", "research", "knowledge", "workflow"],
        "updated_at": _now_iso(),
    }


def _ecosystem_watchlist_template() -> dict[str, Any]:
    return {
        "docs_urls": [
            "https://docs.github.com/en/copilot/concepts/agents/coding-agent/about-coding-agent",
            "https://docs.github.com/en/copilot/concepts/about-copilot-coding-agent",
            "https://docs.github.com/en/codespaces/overview",
            "https://docs.github.com/en/organizations/organizing-members-into-teams/about-teams",
        ],
        "repos": [
            "ytdl-org/youtube-dl",
            "Asabeneh/30-Days-Of-Python",
            "tw93/Pake",
            "KRTirtho/spotube",
            "glanceapp/glance",
            "iawia002/lux",
            "InternLM/xtuner",
            "shaxiu/XianyuAutoAgent",
            "getsentry/XcodeBuildMCP",
            "mvanhorn/last30days-skill",
            "Josh-XT/AGiXT",
            "EvoAgentX/EvoAgentX",
            "ValueCell-ai/ClawX",
            "0xNyk/xint-rs",
            "qdev89/AppXDev.Opengravity",
            "xingbo778/xbworld",
            "azizkode/ArXiv-Agent",
            "maddada/agent-manager-x",
            "ruvnet/RuView",
            "moeru-ai/airi",
            "anthropics/prompt-eng-interactive-tutorial",
            "ruvnet/ruflo",
            "alibaba/OpenSandbox",
            "microsoft/markitdown",
            "K-Dense-AI/claude-scientific-skills",
            "superset-sh/superset",
            "servo/servo",
            "mitchellh/vouch",
            "ranaroussi/yfinance",
            "ekzhu/datasketch",
        ],
        "developers": [
            "ruvnet",
            "mxsm",
            "tjx666",
            "stephenberry",
            "njbrake",
            "andimarafioti",
            "mitchellh",
            "aurelleb",
            "masagrator",
            "krille-chan",
            "Th0rgal",
            "ranaroussi",
            "1c7",
            "gunnarmorling",
            "eitsupi",
            "jasnell",
            "marcus",
            "zhayujie",
            "nisalgunawardhana",
            "dkhamsing",
            "bradygaster",
            "zkochan",
            "FagnerMartinsBrack",
            "Kitenite",
            "ekzhu",
        ],
        "communities": [
            "https://t.me/iccmafia",
            "https://discord.gg/tradesbysci",
            "https://discord.gg/bpKbBHGqg",
            "https://workos.com/changelog",
        ],
        "keywords": [
            "agent",
            "copilot",
            "codespaces",
            "mcp",
            "orchestration",
            "research",
            "finance",
            "trading",
            "knowledge",
            "workflow",
        ],
        "updated_at": _now_iso(),
    }


def _social_feeds_template() -> list[dict[str, Any]]:
    return [
        {"name": "Reddit Entrepreneur", "platform": "reddit", "url": "https://www.reddit.com/r/Entrepreneur/.rss"},
        {"name": "Reddit SideProject", "platform": "reddit", "url": "https://www.reddit.com/r/SideProject/.rss"},
        {
            "name": "X Agents/Automation",
            "platform": "x",
            "query": "(ai OR agent OR automation OR saas) -is:retweet lang:en",
            "max_results": 25,
        },
        {
            "name": "X Market/Macro",
            "platform": "x",
            "query": "(stocks OR macro OR yields OR inflation OR fed OR recession OR risk-on OR risk-off) -is:retweet lang:en",
            "max_results": 25,
        },
        {
            "name": "X Gold/FX/Crypto",
            "platform": "x",
            "query": "(xauusd OR gold OR forex OR dxy OR bitcoin OR btc OR ethereum) -is:retweet lang:en",
            "max_results": 25,
        },
        {
            "name": "WorkOS Changelog",
            "platform": "changelog",
            "url": "https://workos.com/changelog/rss.xml",
        },
        {
            "name": "Discord Server A (set channel_id)",
            "platform": "discord",
            "enabled": False,
            "channel_id": "",
            "max_messages": 50,
        },
        {
            "name": "Discord Server B (set channel_id)",
            "platform": "discord",
            "enabled": False,
            "channel_id": "",
            "max_messages": 50,
        },
        {
            "name": "YouTube Reviewer A (set channel_id)",
            "platform": "youtube",
            "enabled": False,
            "channel_id": "",
        },
        {
            "name": "YouTube Reviewer B (set channel_id)",
            "platform": "youtube",
            "enabled": False,
            "channel_id": "",
        },
        {"name": "HN Frontpage", "platform": "hackernews", "url": "https://hnrss.org/frontpage"},
    ]


def _social_discernment_policy_template() -> dict[str, Any]:
    return {
        "min_score_keep": 0.5,
        "require_keyword_match": False,
        "drop_on_exclude_match": False,
        "include_keywords": [
            "ai",
            "agent",
            "automation",
            "saas",
            "growth",
            "monetize",
            "trading",
            "prediction",
            "backtest",
            "xauusd",
            "gold",
            "bitcoin",
            "liquidity",
            "yield",
        ],
        "exclude_keywords": ["meme", "giveaway", "nsfw", "airdrop"],
        "include_bonus": 0.25,
        "exclude_penalty": 1.5,
        "top_items_limit": 30,
        "updated_at": _now_iso(),
    }


def _market_backtest_watchlist_template() -> dict[str, Any]:
    return {
        "assets": [
            {"symbol": "XAUUSD", "keywords": ["xauusd", "gold", "bullion"], "timeframes": ["M15", "H1", "H4"]},
            {"symbol": "BTCUSD", "keywords": ["btc", "bitcoin", "btcusd"], "timeframes": ["M15", "H1", "H4", "D1"]},
            {"symbol": "SPY", "keywords": ["spy", "sp500", "equities"], "timeframes": ["H1", "H4", "D1"]},
            {"symbol": "NVDA", "keywords": ["nvda", "nvidia", "semiconductor"], "timeframes": ["H1", "H4", "D1"]},
        ],
        "strategy_lenses": [
            {
                "strategy_id": "liquidity_sweep_fvg",
                "name": "Liquidity Sweep + FVG (ICC/SMC)",
                "keywords": ["liquidity sweep", "fvg", "fair value gap", "bos", "choch", "order block", "displacement"],
                "lookback_days": 365,
                "min_samples": 80,
            },
            {
                "strategy_id": "event_volatility_breakout",
                "name": "Event Volatility Breakout",
                "keywords": ["cpi", "fomc", "fed", "nfp", "volatility", "breakout", "macro shock"],
                "lookback_days": 730,
                "min_samples": 60,
            },
        ],
        "money_keywords": ["yield", "rates", "dollar", "liquidity", "treasury", "oil", "gold", "bitcoin"],
        "min_signal_score": 2.0,
        "top_setups_limit": 12,
        "updated_at": _now_iso(),
    }


def _narrative_hypotheses_template() -> list[dict[str, Any]]:
    return [
        {
            "hypothesis_id": "NAR-001",
            "title": "Liquidity stress beneath official calm narrative",
            "category": "macro_liquidity",
            "support_keywords": ["liquidity stress", "funding stress", "repo", "credit stress", "bank stress"],
            "contradict_keywords": ["ample liquidity", "funding stable"],
            "money_keywords": ["yield", "rates", "dollar", "treasury", "gold", "volatility"],
        },
        {
            "hypothesis_id": "NAR-002",
            "title": "Geopolitical escalation reprices commodities before consensus",
            "category": "geopolitics_commodities",
            "support_keywords": ["strait", "shipping disruption", "sanction", "pipeline", "oil shock", "war"],
            "contradict_keywords": ["ceasefire", "supply normalizing"],
            "money_keywords": ["oil", "gas", "xauusd", "gold", "inflation", "freight"],
        },
        {
            "hypothesis_id": "NAR-003",
            "title": "Crypto leverage cycle vulnerable to forced unwind",
            "category": "crypto_leverage",
            "support_keywords": ["open interest spike", "liquidation", "funding rate", "overleveraged", "long squeeze"],
            "contradict_keywords": ["deleveraging complete", "funding normalized", "spot led rally"],
            "money_keywords": ["btc", "bitcoin", "eth", "ethereum", "stablecoin"],
        },
    ]


def _world_watch_sources_template() -> dict[str, Any]:
    return {
        "map_views": [
            {
                "name": "World Monitor",
                "url": "https://www.worldmonitor.app/?lat=20.0000&lon=0.0000&zoom=1.00&view=global&timeRange=7d&layers=conflicts%2Cbases%2Chotspots%2Cnuclear%2Csanctions%2Cweather%2Ceconomic%2Cwaterways%2Coutages%2Cmilitary%2Cnatural%2CiranAttacks",
            },
            {
                "name": "XED World Terminal",
                "url": "https://www.xed.one/",
            },
        ],
        "focus_keywords": [
            "conflict",
            "strait",
            "shipping",
            "nuclear",
            "sanction",
            "earthquake",
            "wildfire",
            "storm",
            "grid outage",
            "market shock",
            "oil",
            "inflation",
            "cyber",
        ],
        "data_sources": [
            {
                "id": "usgs_earthquakes",
                "enabled": True,
                "type": "earthquake_geojson",
                "url": "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_day.geojson",
            },
            {
                "id": "nasa_eonet_open_events",
                "enabled": True,
                "type": "eonet_events",
                "url": "https://eonet.gsfc.nasa.gov/api/v3/events?status=open&limit=50",
            },
            {
                "id": "noaa_active_alerts",
                "enabled": True,
                "type": "noaa_alerts",
                "url": "https://api.weather.gov/alerts/active",
            },
            {
                "id": "reliefweb_reports",
                "enabled": True,
                "type": "reliefweb_reports",
                "url": "https://api.reliefweb.int/v2/reports?appname=permanence-os&limit=50&sort[]=date:desc",
            },
        ],
    }


def _agent_constitution_template() -> dict[str, Any]:
    return {
        "version": "1.0",
        "identity_statement": (
            "PermanenceOS is a governed second-brain and execution copilot. "
            "It is designed to compound outcomes without violating safety or trust."
        ),
        "core_objectives": [
            "Increase clarity and decision quality across life + business.",
            "Generate sustainable income through disciplined research and execution.",
            "Protect reputation, legal posture, and long-term health while scaling.",
        ],
        "non_negotiables": [
            "No autonomous real-money transfers or trades.",
            "No secret exfiltration or credential disclosure.",
            "No autonomous outbound publishing or messaging without manual approval.",
            "No self-modification of governance without explicit human approval.",
        ],
        "privacy": {
            "store_raw_voice": False,
            "store_transcripts": "opt_in",
            "message_retention_days": 30,
        },
        "capability_toggles": {
            "allow_external_reads": True,
            "allow_external_writes": False,
            "allow_live_trading": False,
            "allow_voice_mode": False,
            "allow_self_modification": False,
        },
        "danger_patterns": {
            "block_keywords": [
                "disable guardrails",
                "bypass policy",
                "reveal api key",
                "export private key",
            ],
            "require_approval_keywords": [
                "autopilot",
                "auto trade",
                "auto post",
                "wire transfer",
            ],
        },
        "updated_at": _now_iso(),
    }


def _founder_vision_template() -> dict[str, Any]:
    return {
        "system_name": "Permanence OS",
        "thesis": (
            "A governed second-brain + agent operating system for life and business that compounds output, "
            "maintains discipline, and keeps final authority with the human operator."
        ),
        "mission_threads": [
            "Operate as a personal and professional intelligence layer.",
            "Build multi-stream income systems with evidence and risk controls.",
            "Deliver clear updates, reports, and actionable options daily.",
            "Stay design-forward: unique, useful, and emotionally resonant.",
        ],
        "design_taste": {
            "keywords": [
                "premium",
                "minimal but expressive",
                "map + intelligence surfaces",
                "modular themes",
                "mobile-first control",
                "desktop power mode",
            ],
            "inspirations": [
                "Apple interaction clarity",
                "finance terminal density",
                "editorial storytelling",
                "gen-z creator UX patterns",
            ],
        },
        "governance": {
            "guided_freedom": True,
            "manual_approval_required_for_money": True,
            "manual_approval_required_for_publishing": True,
            "no_autonomous_live_trading": True,
            "no_secret_exfiltration": True,
            "no_credential_leakage": True,
        },
        "agent_culture": {
            "values": [
                "discipline",
                "curiosity",
                "service",
                "professional etiquette",
                "continuous improvement",
            ],
            "operating_rule": "Learn continuously, propose clearly, execute only within approved boundaries.",
        },
        "updated_at": _now_iso(),
    }


def _clipping_template() -> list[dict[str, Any]]:
    return [
        {
            "job_id": "CLIP-001",
            "title": "Sample long-form source",
            "source_url": "https://example.com/video",
            "niche": "finance-ai",
            "status": "queued",
            "notes": "Add transcript segments to enable candidate scoring.",
            "transcript_segments": [
                {
                    "start": 12,
                    "end": 34,
                    "text": "Here is the key: first protect downside, then press edge responsibly.",
                }
            ],
        }
    ]


def _write_if_needed(path: Path, payload: Any, force: bool) -> bool:
    if path.exists() and not force:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return True


def _write_text_if_needed(path: Path, text: str, force: bool) -> bool:
    if path.exists() and not force:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Initialize second-brain working templates.")
    parser.add_argument("--force", action="store_true", help="Overwrite existing files")
    args = parser.parse_args(argv)

    targets = [
        (WORKING_DIR / "life_profile.json", _life_profile_template()),
        (WORKING_DIR / "life_tasks.json", _life_tasks_template()),
        (WORKING_DIR / "side_business_portfolio.json", _side_business_template()),
        (WORKING_DIR / "prediction_hypotheses.json", _prediction_template()),
        (WORKING_DIR / "prediction_news_feeds.json", _prediction_feeds_template()),
        (WORKING_DIR / "prediction_telegram_sources.json", _prediction_telegram_sources_template()),
        (WORKING_DIR / "github_research_targets.json", _github_targets_template()),
        (WORKING_DIR / "github_trending_focus.json", _github_trending_focus_template()),
        (WORKING_DIR / "ecosystem_watchlist.json", _ecosystem_watchlist_template()),
        (WORKING_DIR / "social_research_feeds.json", _social_feeds_template()),
        (WORKING_DIR / "social_discernment_policy.json", _social_discernment_policy_template()),
        (WORKING_DIR / "market_backtest_watchlist.json", _market_backtest_watchlist_template()),
        (WORKING_DIR / "narrative_tracker_hypotheses.json", _narrative_hypotheses_template()),
        (WORKING_DIR / "world_watch_sources.json", _world_watch_sources_template()),
        (WORKING_DIR / "agent_constitution.json", _agent_constitution_template()),
        (WORKING_DIR / "founder_vision.json", _founder_vision_template()),
        (WORKING_DIR / "transcription_queue.json", []),
        (WORKING_DIR / "clipping_jobs.json", _clipping_template()),
    ]
    text_targets = [
        (
            WORKING_DIR / "clipping_transcripts" / "sample_transcript.txt",
            "\n".join(
                [
                    "00:00:12 --> 00:00:34 Here is the key framework: protect downside first, then press your edge.",
                    "00:01:10 --> 00:01:32 The real reason most people lose is no risk cap and no review loop.",
                    "00:02:05 --> 00:02:30 Three steps: collect data, score candidates, approve manually.",
                    "",
                ]
            ),
        ),
        (
            ATTACHMENT_INBOX_DIR / "README.md",
            "\n".join(
                [
                    "# Attachment Inbox",
                    "",
                    "Drop documents, images, audio, and video files here.",
                    "Then run: python cli.py attachment-pipeline",
                    "",
                ]
            ),
        ),
    ]

    written = 0
    skipped = 0
    for path, payload in targets:
        if _write_if_needed(path, payload, force=args.force):
            written += 1
            print(f"[written] {path}")
        else:
            skipped += 1
            print(f"[skip] {path}")
    for path, text in text_targets:
        if _write_text_if_needed(path, text, force=args.force):
            written += 1
            print(f"[written] {path}")
        else:
            skipped += 1
            print(f"[skip] {path}")

    print(f"Second brain init complete: written={written} skipped={skipped}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
