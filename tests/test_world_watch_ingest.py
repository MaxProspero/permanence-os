#!/usr/bin/env python3
"""Tests for world watch ingest."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import scripts.world_watch_ingest as world_mod  # noqa: E402


def _file_url(path: Path) -> str:
    return f"file://{path}"


def test_world_watch_ingest_collects_multi_source_events() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        working = root / "working"
        output = root / "outputs"
        tool = root / "tool"
        feed = root / "feeds"
        working.mkdir(parents=True, exist_ok=True)
        output.mkdir(parents=True, exist_ok=True)
        tool.mkdir(parents=True, exist_ok=True)
        feed.mkdir(parents=True, exist_ok=True)

        usgs_path = feed / "usgs.json"
        usgs_path.write_text(
            json.dumps(
                {
                    "features": [
                        {
                            "id": "usgs-1",
                            "properties": {
                                "title": "M 6.2 - Offshore",
                                "place": "Offshore Region",
                                "mag": 6.2,
                                "time": 1762000000000,
                                "url": "https://example.com/usgs-1",
                                "alert": "orange",
                            },
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        eonet_path = feed / "eonet.json"
        eonet_path.write_text(
            json.dumps(
                {
                    "events": [
                        {
                            "id": "eonet-1",
                            "title": "Wildfire in region",
                            "categories": [{"title": "Wildfires"}],
                            "geometry": [{"date": "2026-03-01T00:00:00Z"}],
                            "link": "https://example.com/eonet-1",
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        noaa_path = feed / "noaa.json"
        noaa_path.write_text(
            json.dumps(
                {
                    "features": [
                        {
                            "id": "noaa-1",
                            "properties": {
                                "id": "noaa-1",
                                "headline": "Severe Storm Warning",
                                "event": "Storm",
                                "severity": "Severe",
                                "description": "Strong weather system",
                                "areaDesc": "Test County",
                                "effective": "2026-03-01T00:00:00Z",
                                "@id": "https://example.com/noaa-1",
                            },
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        reliefweb_path = feed / "reliefweb.json"
        reliefweb_path.write_text(
            json.dumps(
                {
                    "data": [
                        {
                            "id": "relief-1",
                            "fields": {
                                "title": "Conflict displacement update",
                                "body": "Major displacement and humanitarian response update.",
                                "url": "https://example.com/relief-1",
                                "country": [{"name": "Country A"}],
                                "date": {"created": "2026-03-01T00:00:00Z"},
                            },
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )

        sources = {
            "map_views": [{"name": "World Monitor", "url": "https://www.worldmonitor.app/"}],
            "market_monitors": [{"name": "TradingView Heatmap", "url": "https://www.tradingview.com/heatmap/stock/"}],
            "focus_keywords": ["conflict", "storm", "earthquake"],
            "data_sources": [
                {"id": "usgs_earthquakes", "enabled": True, "type": "earthquake_geojson", "url": _file_url(usgs_path)},
                {"id": "nasa_eonet_open_events", "enabled": True, "type": "eonet_events", "url": _file_url(eonet_path)},
                {"id": "noaa_active_alerts", "enabled": True, "type": "noaa_alerts", "url": _file_url(noaa_path)},
                {"id": "reliefweb_reports", "enabled": True, "type": "reliefweb_reports", "url": _file_url(reliefweb_path)},
            ],
        }
        sources_path = working / "world_watch_sources.json"
        sources_path.write_text(json.dumps(sources, indent=2) + "\n", encoding="utf-8")

        original = {
            "WORKING_DIR": world_mod.WORKING_DIR,
            "OUTPUT_DIR": world_mod.OUTPUT_DIR,
            "TOOL_DIR": world_mod.TOOL_DIR,
            "SOURCES_PATH": world_mod.SOURCES_PATH,
        }
        try:
            world_mod.WORKING_DIR = working
            world_mod.OUTPUT_DIR = output
            world_mod.TOOL_DIR = tool
            world_mod.SOURCES_PATH = sources_path
            rc = world_mod.main([])
        finally:
            world_mod.WORKING_DIR = original["WORKING_DIR"]
            world_mod.OUTPUT_DIR = original["OUTPUT_DIR"]
            world_mod.TOOL_DIR = original["TOOL_DIR"]
            world_mod.SOURCES_PATH = original["SOURCES_PATH"]

        assert rc == 0
        assert (output / "world_watch_latest.md").exists()
        payload_files = sorted(tool.glob("world_watch_*.json"))
        assert payload_files
        payload = json.loads(payload_files[-1].read_text(encoding="utf-8"))
        assert int(payload.get("item_count", 0)) >= 4
        categories = payload.get("category_counts") or {}
        assert "earthquake" in categories
        assert "weather_alert" in categories
        assert ("humanitarian_report" in categories) or ("war_conflict" in categories)
        assert payload.get("map_views", [{}])[0].get("name") == "World Monitor"
        assert payload.get("market_monitors", [{}])[0].get("name") == "TradingView Heatmap"


def test_world_watch_ingest_adds_market_and_local_weather_focus() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        working = root / "working"
        output = root / "outputs"
        tool = root / "tool"
        feed = root / "feeds"
        working.mkdir(parents=True, exist_ok=True)
        output.mkdir(parents=True, exist_ok=True)
        tool.mkdir(parents=True, exist_ok=True)
        feed.mkdir(parents=True, exist_ok=True)

        noaa_local_path = feed / "noaa_local.json"
        noaa_local_path.write_text(
            json.dumps(
                {
                    "features": [
                        {
                            "id": "noaa-local-1",
                            "properties": {
                                "id": "noaa-local-1",
                                "headline": "Tornado Warning",
                                "event": "Tornado",
                                "severity": "Extreme",
                                "description": "Seek shelter immediately.",
                                "areaDesc": "Home County",
                                "effective": "2026-03-01T00:00:00Z",
                                "@id": "https://example.com/noaa-local-1",
                            },
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )

        open_meteo_path = feed / "open_meteo.json"
        open_meteo_path.write_text(
            json.dumps(
                {
                    "current": {
                        "time": "2026-03-01T09:00:00Z",
                        "temperature_2m": 22.4,
                        "apparent_temperature": 23.1,
                        "precipitation": 4.2,
                        "wind_speed_10m": 42.0,
                        "weather_code": 95,
                    },
                    "daily": {
                        "temperature_2m_max": [32.0],
                        "temperature_2m_min": [17.0],
                        "precipitation_sum": [26.0],
                        "wind_speed_10m_max": [64.0],
                    },
                }
            ),
            encoding="utf-8",
        )

        fred_sp500 = feed / "fred_sp500.csv"
        fred_sp500.write_text(
            "DATE,SP500\n2026-02-24,7010.10\n2026-02-25,6999.50\n2026-02-26,6908.86\n2026-02-27,6878.88\n2026-03-02,6800.00\n",
            encoding="utf-8",
        )
        fred_djia = feed / "fred_djia.csv"
        fred_djia.write_text(
            "DATE,DJIA\n2026-02-24,50120.00\n2026-02-25,49920.00\n2026-02-26,49499.20\n2026-02-27,48977.92\n2026-03-02,48200.00\n",
            encoding="utf-8",
        )
        fred_nasdaq = feed / "fred_nasdaq.csv"
        fred_nasdaq.write_text(
            "DATE,NASDAQCOM\n2026-02-24,23380.00\n2026-02-25,23152.08\n2026-02-26,22878.38\n2026-02-27,22668.21\n2026-03-02,22000.00\n",
            encoding="utf-8",
        )
        fred_vix = feed / "fred_vix.csv"
        fred_vix.write_text(
            "DATE,VIXCLS\n2026-02-24,16.60\n2026-02-25,17.93\n2026-02-26,18.63\n2026-02-27,19.86\n2026-03-02,33.10\n",
            encoding="utf-8",
        )

        sources = {
            "home_location": {"label": "Nashville, TN", "latitude": 36.1627, "longitude": -86.7816},
            "focus_keywords": ["war", "conflict", "market crash", "storm", "tornado"],
            "data_sources": [
                {"id": "noaa_local", "enabled": True, "type": "noaa_alerts_local", "url": _file_url(noaa_local_path)},
                {
                    "id": "open_meteo_local",
                    "enabled": True,
                    "type": "open_meteo_local_weather",
                    "url": _file_url(open_meteo_path),
                },
                {
                    "id": "fred_market_stress",
                    "enabled": True,
                    "type": "fred_market_stress",
                    "series_urls": {
                        "SP500": _file_url(fred_sp500),
                        "DJIA": _file_url(fred_djia),
                        "NASDAQCOM": _file_url(fred_nasdaq),
                        "VIXCLS": _file_url(fred_vix),
                    },
                },
            ],
        }
        sources_path = working / "world_watch_sources.json"
        sources_path.write_text(json.dumps(sources, indent=2) + "\n", encoding="utf-8")

        original = {
            "WORKING_DIR": world_mod.WORKING_DIR,
            "OUTPUT_DIR": world_mod.OUTPUT_DIR,
            "TOOL_DIR": world_mod.TOOL_DIR,
            "SOURCES_PATH": world_mod.SOURCES_PATH,
        }
        try:
            world_mod.WORKING_DIR = working
            world_mod.OUTPUT_DIR = output
            world_mod.TOOL_DIR = tool
            world_mod.SOURCES_PATH = sources_path
            rc = world_mod.main([])
        finally:
            world_mod.WORKING_DIR = original["WORKING_DIR"]
            world_mod.OUTPUT_DIR = original["OUTPUT_DIR"]
            world_mod.TOOL_DIR = original["TOOL_DIR"]
            world_mod.SOURCES_PATH = original["SOURCES_PATH"]

        assert rc == 0
        payload_files = sorted(tool.glob("world_watch_*.json"))
        assert payload_files
        payload = json.loads(payload_files[-1].read_text(encoding="utf-8"))
        categories = payload.get("category_counts") or {}
        assert "market_stress" in categories
        assert "weather_local" in categories
        assert "weather_local_alert" in categories
        assert int(payload.get("major_event_count", 0)) >= 1


def test_world_watch_ingest_adds_equity_crypto_fx_categories() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        working = root / "working"
        output = root / "outputs"
        tool = root / "tool"
        feed = root / "feeds"
        working.mkdir(parents=True, exist_ok=True)
        output.mkdir(parents=True, exist_ok=True)
        tool.mkdir(parents=True, exist_ok=True)
        feed.mkdir(parents=True, exist_ok=True)

        coingecko_path = feed / "coingecko.json"
        coingecko_path.write_text(
            json.dumps(
                [
                    {
                        "id": "bitcoin",
                        "symbol": "btc",
                        "name": "Bitcoin",
                        "market_cap_rank": 1,
                        "current_price": 87000.0,
                        "price_change_percentage_24h": -4.2,
                        "price_change_percentage_7d_in_currency": -6.4,
                        "last_updated": "2026-03-01T00:00:00Z",
                    },
                    {
                        "id": "ethereum",
                        "symbol": "eth",
                        "name": "Ethereum",
                        "market_cap_rank": 2,
                        "current_price": 4200.0,
                        "price_change_percentage_24h": -3.8,
                        "price_change_percentage_7d_in_currency": -5.5,
                        "last_updated": "2026-03-01T00:00:00Z",
                    },
                ]
            ),
            encoding="utf-8",
        )

        fred_dxy = feed / "fred_dxy.csv"
        fred_dxy.write_text(
            "DATE,DTWEXBGS\n2026-02-26,127.2\n2026-02-27,127.8\n2026-03-02,129.1\n",
            encoding="utf-8",
        )

        sources = {
            "focus_keywords": ["market crash", "selloff", "vix", "forex", "bitcoin"],
            "data_sources": [
                {
                    "id": "stooq_equity_watchlist",
                    "enabled": True,
                    "type": "stooq_equity_watchlist",
                    "symbols": ["AAPL.US", "MSFT.US"],
                },
                {
                    "id": "coingecko_top_assets",
                    "enabled": True,
                    "type": "coingecko_top_assets",
                    "url": _file_url(coingecko_path),
                },
                {
                    "id": "fred_fx_watch",
                    "enabled": True,
                    "type": "fred_fx_watch",
                    "series_urls": {"DTWEXBGS": _file_url(fred_dxy)},
                },
            ],
        }
        sources_path = working / "world_watch_sources.json"
        sources_path.write_text(json.dumps(sources, indent=2) + "\n", encoding="utf-8")

        original = {
            "WORKING_DIR": world_mod.WORKING_DIR,
            "OUTPUT_DIR": world_mod.OUTPUT_DIR,
            "TOOL_DIR": world_mod.TOOL_DIR,
            "SOURCES_PATH": world_mod.SOURCES_PATH,
            "_read_stooq_series": world_mod._read_stooq_series,
        }
        try:
            world_mod.WORKING_DIR = working
            world_mod.OUTPUT_DIR = output
            world_mod.TOOL_DIR = tool
            world_mod.SOURCES_PATH = sources_path

            def fake_stooq_series(symbol: str):
                if symbol.upper() == "AAPL.US":
                    return [
                        ("2026-02-26", 198.0),
                        ("2026-02-27", 194.0),
                        ("2026-03-02", 186.0),
                    ]
                return [
                    ("2026-02-26", 411.0),
                    ("2026-02-27", 408.0),
                    ("2026-03-02", 401.0),
                ]

            world_mod._read_stooq_series = fake_stooq_series  # type: ignore[assignment]
            rc = world_mod.main([])
        finally:
            world_mod.WORKING_DIR = original["WORKING_DIR"]
            world_mod.OUTPUT_DIR = original["OUTPUT_DIR"]
            world_mod.TOOL_DIR = original["TOOL_DIR"]
            world_mod.SOURCES_PATH = original["SOURCES_PATH"]
            world_mod._read_stooq_series = original["_read_stooq_series"]  # type: ignore[assignment]

        assert rc == 0
        payload_files = sorted(tool.glob("world_watch_*.json"))
        assert payload_files
        payload = json.loads(payload_files[-1].read_text(encoding="utf-8"))
        categories = payload.get("category_counts") or {}
        assert "equity_watch" in categories
        assert "crypto_market" in categories
        assert "fx_market" in categories


if __name__ == "__main__":
    test_world_watch_ingest_collects_multi_source_events()
    test_world_watch_ingest_adds_market_and_local_weather_focus()
    test_world_watch_ingest_adds_equity_crypto_fx_categories()
    print("✓ World watch ingest tests passed")
