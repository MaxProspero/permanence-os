#!/usr/bin/env python3
"""
Global world-watch ingest for situational awareness and alerts.

Data collection is read-only. This tool does not execute trades or publish posts.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus, urlparse

import requests

BASE_DIR = Path(__file__).resolve().parents[1]


def _load_local_env() -> None:
    env_path = BASE_DIR / ".env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key or key in os.environ:
            continue
        value = value.strip()
        if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
            value = value[1:-1]
        os.environ[key] = value


_load_local_env()
WORKING_DIR = Path(os.getenv("PERMANENCE_WORKING_DIR", str(BASE_DIR / "memory" / "working")))
OUTPUT_DIR = Path(os.getenv("PERMANENCE_OUTPUT_DIR", str(BASE_DIR / "outputs")))
TOOL_DIR = Path(os.getenv("PERMANENCE_TOOL_DIR", str(BASE_DIR / "memory" / "tool")))
SOURCES_PATH = Path(
    os.getenv("PERMANENCE_WORLD_WATCH_SOURCES_PATH", str(WORKING_DIR / "world_watch_sources.json"))
)
TIMEOUT_SECONDS = int(os.getenv("PERMANENCE_WORLD_WATCH_TIMEOUT", "10"))

FRED_SERIES_DEFAULTS = {
    "SP500": "https://fred.stlouisfed.org/graph/fredgraph.csv?id=SP500",
    "DJIA": "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DJIA",
    "NASDAQCOM": "https://fred.stlouisfed.org/graph/fredgraph.csv?id=NASDAQCOM",
    "VIXCLS": "https://fred.stlouisfed.org/graph/fredgraph.csv?id=VIXCLS",
}

FRED_FX_SERIES_DEFAULTS = {
    "DTWEXBGS": "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DTWEXBGS",  # Broad dollar index
    "DEXUSEU": "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DEXUSEU",  # USD per EUR
    "DEXJPUS": "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DEXJPUS",  # JPY per USD
    "DEXUSUK": "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DEXUSUK",  # USD per GBP
}

DEFAULT_STOCK_WATCHLIST = [
    "SPY.US",
    "QQQ.US",
    "DIA.US",
    "IWM.US",
    "AAPL.US",
    "MSFT.US",
    "NVDA.US",
    "AMD.US",
    "PLTR.US",
    "AMZN.US",
    "GOOGL.US",
    "META.US",
    "TSLA.US",
    "AVGO.US",
    "NFLX.US",
    "JPM.US",
    "XOM.US",
]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now().isoformat()


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _optional_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _severity_label(score: float) -> str:
    if score >= 85:
        return "critical"
    if score >= 70:
        return "high"
    if score >= 45:
        return "medium"
    return "low"


def _parse_iso(value: str) -> datetime | None:
    token = (value or "").strip()
    if not token:
        return None
    try:
        parsed = datetime.fromisoformat(token.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed
    except ValueError:
        return None


def _freshness_bonus(occurred_at: str) -> float:
    dt = _parse_iso(occurred_at)
    if dt is None:
        return 0.0
    age_hours = max(0.0, (_now() - dt).total_seconds() / 3600.0)
    if age_hours <= 24:
        return 10.0
    if age_hours <= 72:
        return 4.0
    return 0.0


def _weather_code_label(code: int) -> str:
    mapping = {
        0: "clear",
        1: "mostly clear",
        2: "partly cloudy",
        3: "overcast",
        45: "fog",
        48: "rime fog",
        51: "light drizzle",
        53: "moderate drizzle",
        55: "dense drizzle",
        61: "light rain",
        63: "moderate rain",
        65: "heavy rain",
        66: "freezing rain",
        67: "heavy freezing rain",
        71: "light snow",
        73: "snow",
        75: "heavy snow",
        77: "snow grains",
        80: "rain showers",
        81: "heavy rain showers",
        82: "violent rain showers",
        85: "snow showers",
        86: "heavy snow showers",
        95: "thunderstorm",
        96: "thunderstorm with hail",
        99: "severe thunderstorm with hail",
    }
    return mapping.get(int(code), "weather")


def _default_sources() -> dict[str, Any]:
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
        "market_monitors": [
            {
                "name": "TradingView Stock Heatmap",
                "url": "https://www.tradingview.com/heatmap/stock/",
                "type": "equities_heatmap",
            },
            {
                "name": "TradingView World Economy Heatmap",
                "url": "https://www.tradingview.com/markets/world-economy/indicators-heatmap/",
                "type": "macro_heatmap",
            },
            {
                "name": "FRED VIX",
                "url": "https://fred.stlouisfed.org/series/VIXCLS",
                "type": "volatility",
            },
            {
                "name": "FRED 10Y Treasury Yield",
                "url": "https://fred.stlouisfed.org/series/DGS10",
                "type": "rates",
            },
            {
                "name": "FRED 10Y-2Y Spread",
                "url": "https://fred.stlouisfed.org/series/T10Y2Y",
                "type": "yield_curve",
            },
            {
                "name": "US Treasury Yield Curve",
                "url": "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/TextView?type=daily_treasury_yield_curve",
                "type": "rates",
            },
            {
                "name": "Yahoo Earnings Calendar",
                "url": "https://finance.yahoo.com/calendar/earnings/",
                "type": "earnings_calendar",
            },
            {
                "name": "TradingEconomics Calendar",
                "url": "https://tradingeconomics.com/calendar",
                "type": "macro_calendar",
            },
            {
                "name": "ForexFactory Calendar",
                "url": "https://www.forexfactory.com/calendar",
                "type": "fx_macro_calendar",
            },
            {
                "name": "TradingView XAUUSD",
                "url": "https://www.tradingview.com/symbols/XAUUSD/",
                "type": "gold_fx",
            },
            {
                "name": "Polymarket",
                "url": "https://polymarket.com/",
                "type": "prediction_market",
            },
            {
                "name": "Kalshi",
                "url": "https://kalshi.com/",
                "type": "prediction_market",
            },
        ],
        "focus_keywords": [
            "market crash",
            "selloff",
            "drawdown",
            "liquidation",
            "volatility",
            "vix",
            "bond yield",
            "yield curve",
            "dollar index",
            "xauusd",
            "gold",
            "btc",
            "bitcoin",
            "ethereum",
            "altcoin",
            "forex",
            "fx",
            "inflation",
            "rates",
            "recession",
            "war",
            "conflict",
            "sanction",
            "oil",
        ],
        "home_location": {
            "label": "Home",
            "latitude": None,
            "longitude": None,
        },
        "alert_focus": {
            "min_major_score": 68.0,
            "market_only": False,
            "major_categories": [
                "market_stress",
                "market_volatility",
                "market_index",
                "crypto_market",
                "crypto_market_stress",
                "fx_market",
                "weather_local_alert",
                "weather_local",
                "war_conflict",
            ],
            "always_include_categories": [
                "market_stress",
                "market_volatility",
                "market_index",
                "crypto_market",
                "fx_market",
                "weather_local",
            ],
            "headline_keywords": [
                "market crash",
                "selloff",
                "volatility",
                "vix",
                "yield",
                "inflation",
                "rates",
                "recession",
                "bitcoin",
                "ethereum",
                "sanction",
                "war",
                "conflict",
            ],
        },
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
                "id": "noaa_local_alerts",
                "enabled": True,
                "type": "noaa_alerts_local",
                "url": "https://api.weather.gov/alerts/active",
            },
            {
                "id": "open_meteo_local_weather",
                "enabled": True,
                "type": "open_meteo_local_weather",
                "url": "https://api.open-meteo.com/v1/forecast",
            },
            {
                "id": "reliefweb_reports",
                "enabled": True,
                "type": "reliefweb_reports",
                "url": "https://api.reliefweb.int/v2/reports?appname=permanence-os&limit=50&sort[]=date:desc",
            },
            {
                "id": "fred_market_stress",
                "enabled": True,
                "type": "fred_market_stress",
                "series_urls": FRED_SERIES_DEFAULTS,
            },
            {
                "id": "stooq_equity_watchlist",
                "enabled": True,
                "type": "stooq_equity_watchlist",
                "symbols": DEFAULT_STOCK_WATCHLIST,
                "min_abs_daily_pct": 1.8,
                "min_abs_weekly_pct": 4.0,
                "always_include_symbols": [
                    "SPY.US",
                    "QQQ.US",
                    "AAPL.US",
                    "MSFT.US",
                    "NVDA.US",
                    "AMD.US",
                    "PLTR.US",
                ],
                "max_events": 12,
            },
            {
                "id": "coingecko_top_assets",
                "enabled": True,
                "type": "coingecko_top_assets",
                "url": "https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&order=market_cap_desc&per_page=25&page=1&sparkline=false&price_change_percentage=24h,7d",
            },
            {
                "id": "fred_fx_watch",
                "enabled": True,
                "type": "fred_fx_watch",
                "series_urls": FRED_FX_SERIES_DEFAULTS,
            },
        ],
    }


def _merge_data_sources(default_rows: list[dict[str, Any]], user_rows: list[Any]) -> list[dict[str, Any]]:
    merged_rows: list[dict[str, Any]] = []
    index_by_id: dict[str, int] = {}
    for row in default_rows:
        if not isinstance(row, dict):
            continue
        row_copy = dict(row)
        source_id = str(row_copy.get("id") or "").strip()
        if source_id:
            index_by_id[source_id] = len(merged_rows)
        merged_rows.append(row_copy)

    for row in user_rows:
        if not isinstance(row, dict):
            continue
        source_id = str(row.get("id") or "").strip()
        if source_id and source_id in index_by_id:
            idx = index_by_id[source_id]
            base = dict(merged_rows[idx])
            base.update(row)
            base_series = base.get("series_urls")
            row_series = row.get("series_urls")
            if isinstance(base_series, dict) and isinstance(row_series, dict):
                merged_series = dict(base_series)
                merged_series.update(row_series)
                base["series_urls"] = merged_series
            base_symbols = base.get("symbols")
            row_symbols = row.get("symbols")
            if isinstance(base_symbols, list) and isinstance(row_symbols, list):
                merged_symbols: list[str] = []
                seen_symbols: set[str] = set()
                for token in [*base_symbols, *row_symbols]:
                    symbol = str(token).strip().upper()
                    if not symbol or symbol in seen_symbols:
                        continue
                    seen_symbols.add(symbol)
                    merged_symbols.append(symbol)
                base["symbols"] = merged_symbols
            merged_rows[idx] = base
        else:
            merged_rows.append(dict(row))
            if source_id:
                index_by_id[source_id] = len(merged_rows) - 1
    return merged_rows


def _ensure_sources(path: Path, force_template: bool) -> tuple[dict[str, Any], str]:
    defaults = _default_sources()
    if force_template or not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(defaults, indent=2) + "\n", encoding="utf-8")
        return defaults, "written"
    payload = _read_json(path, {})
    if not isinstance(payload, dict):
        payload = {}
    merged = dict(defaults)
    merged.update(payload)
    user_data_sources = payload.get("data_sources")
    if isinstance(user_data_sources, list):
        merged["data_sources"] = _merge_data_sources(defaults["data_sources"], user_data_sources)
    elif not isinstance(merged.get("data_sources"), list):
        merged["data_sources"] = defaults["data_sources"]
    if not isinstance(merged.get("map_views"), list):
        merged["map_views"] = defaults["map_views"]
    if not isinstance(merged.get("market_monitors"), list):
        merged["market_monitors"] = defaults["market_monitors"]
    if not isinstance(merged.get("focus_keywords"), list):
        merged["focus_keywords"] = defaults["focus_keywords"]
    if not isinstance(merged.get("home_location"), dict):
        merged["home_location"] = defaults["home_location"]
    if not isinstance(merged.get("alert_focus"), dict):
        merged["alert_focus"] = defaults["alert_focus"]
    if merged != payload:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(merged, indent=2) + "\n", encoding="utf-8")
        return merged, "updated"
    return merged, "existing"


def _fetch_json(url: str) -> Any:
    parsed = urlparse(url)
    if parsed.scheme == "file":
        path = Path(parsed.path)
        return _read_json(path, {})
    response = requests.get(
        url,
        timeout=TIMEOUT_SECONDS,
        headers={"User-Agent": "permanence-os-world-watch"},
    )
    response.raise_for_status()
    return response.json()


def _fetch_text(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme == "file":
        path = Path(parsed.path)
        return path.read_text(encoding="utf-8", errors="ignore")
    response = requests.get(
        url,
        timeout=TIMEOUT_SECONDS,
        headers={"User-Agent": "permanence-os-world-watch"},
    )
    response.raise_for_status()
    return response.text


def _coerce_region(raw: Any) -> str:
    if isinstance(raw, list):
        vals = [str(item).strip() for item in raw if str(item).strip()]
        return ", ".join(vals[:3])
    return str(raw or "").strip()


def _keyword_bonus(title: str, summary: str, focus_keywords: list[str]) -> tuple[float, list[str]]:
    text = f"{title} {summary}".lower()
    hits = [kw for kw in focus_keywords if kw in text]
    bonus = min(24.0, len(hits) * 8.0)
    return bonus, hits[:8]


def _resolve_home_location(config: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
    candidate = config.get("home_location")
    if isinstance(candidate, dict):
        lat = _optional_float(candidate.get("latitude"))
        lon = _optional_float(candidate.get("longitude"))
        if lat is not None and lon is not None:
            label = str(candidate.get("label") or "Home").strip() or "Home"
            return {
                "label": label,
                "latitude": lat,
                "longitude": lon,
                "source": "config",
            }, "home location from config"

    env_lat = _optional_float(os.getenv("PERMANENCE_HOME_LAT", ""))
    env_lon = _optional_float(os.getenv("PERMANENCE_HOME_LON", ""))
    if env_lat is not None and env_lon is not None:
        label = str(os.getenv("PERMANENCE_HOME_LABEL", "Home")).strip() or "Home"
        return {
            "label": label,
            "latitude": env_lat,
            "longitude": env_lon,
            "source": "env",
        }, "home location from env"

    home_city = str(os.getenv("PERMANENCE_HOME_CITY", "")).strip()
    if home_city:
        try:
            geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={quote_plus(home_city)}&count=1&language=en&format=json"
            payload = _fetch_json(geo_url)
            rows = payload.get("results") if isinstance(payload, dict) else []
            if isinstance(rows, list) and rows and isinstance(rows[0], dict):
                row = rows[0]
                lat = _optional_float(row.get("latitude"))
                lon = _optional_float(row.get("longitude"))
                if lat is not None and lon is not None:
                    label = str(row.get("name") or home_city).strip() or home_city
                    country = str(row.get("country") or "").strip()
                    if country:
                        label = f"{label}, {country}"
                    return {
                        "label": label,
                        "latitude": lat,
                        "longitude": lon,
                        "source": "home_city_geocode",
                    }, "home location from PERMANENCE_HOME_CITY"
        except Exception:  # noqa: BLE001
            pass

    try:
        payload = _fetch_json("https://ipapi.co/json/")
        if isinstance(payload, dict):
            lat = _optional_float(payload.get("latitude"))
            lon = _optional_float(payload.get("longitude"))
            if lat is not None and lon is not None:
                city = str(payload.get("city") or "").strip()
                region = str(payload.get("region") or "").strip()
                country = str(payload.get("country_name") or "").strip()
                label = ", ".join([part for part in [city, region, country] if part]) or "Auto-detected home"
                return {
                    "label": label,
                    "latitude": lat,
                    "longitude": lon,
                    "source": "ip_geolocation",
                }, "home location auto-detected from IP"
    except Exception:  # noqa: BLE001
        pass
    return None, "home location unavailable"


def _build_noaa_local_url(source_url: str, location: dict[str, Any]) -> str:
    lat = _optional_float(location.get("latitude"))
    lon = _optional_float(location.get("longitude"))
    if lat is None or lon is None:
        return source_url
    if "{lat}" in source_url or "{lon}" in source_url:
        return source_url.replace("{lat}", f"{lat:.4f}").replace("{lon}", f"{lon:.4f}")
    if "point=" in source_url:
        return source_url
    sep = "&" if "?" in source_url else "?"
    return f"{source_url}{sep}point={lat:.4f},{lon:.4f}"


def _build_open_meteo_local_url(source_url: str, location: dict[str, Any]) -> str:
    lat = _optional_float(location.get("latitude"))
    lon = _optional_float(location.get("longitude"))
    if lat is None or lon is None:
        return source_url
    if "{lat}" in source_url or "{lon}" in source_url:
        return source_url.replace("{lat}", f"{lat:.4f}").replace("{lon}", f"{lon:.4f}")
    sep = "&" if "?" in source_url else "?"
    return (
        f"{source_url}{sep}latitude={lat:.4f}&longitude={lon:.4f}"
        "&current=temperature_2m,apparent_temperature,precipitation,wind_speed_10m,weather_code"
        "&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,weather_code,wind_speed_10m_max"
        "&forecast_days=2&timezone=auto"
    )


def _read_fred_series(source_url: str) -> list[tuple[str, float]]:
    text = _fetch_text(source_url)
    reader = csv.reader(text.splitlines())
    header = next(reader, None)
    if not header or len(header) < 2:
        return []
    out: list[tuple[str, float]] = []
    for row in reader:
        if len(row) < 2:
            continue
        stamp = str(row[0]).strip()
        raw = str(row[1]).strip()
        if raw in {"", "."}:
            continue
        value = _optional_float(raw)
        if value is None:
            continue
        out.append((stamp, value))
    return out


def _read_stooq_series(symbol: str) -> list[tuple[str, float]]:
    clean = symbol.strip().lower()
    if not clean:
        return []
    if not clean.endswith(".us"):
        clean = f"{clean}.us"
    url = f"https://stooq.com/q/d/l/?s={clean}&i=d"
    text = _fetch_text(url)
    if text.strip().lower().startswith("no data"):
        return []
    reader = csv.reader(text.splitlines())
    header = next(reader, None)
    if not header or len(header) < 5:
        return []
    out: list[tuple[str, float]] = []
    for row in reader:
        if len(row) < 5:
            continue
        stamp = str(row[0]).strip()
        close_val = _optional_float(row[4])
        if not stamp or close_val is None:
            continue
        out.append((stamp, close_val))
    return out


def _normalize_fred_market_stress(
    source: dict[str, Any],
    source_id: str,
    focus_keywords: list[str],
) -> tuple[list[dict[str, Any]], list[str]]:
    warnings: list[str] = []
    out: list[dict[str, Any]] = []
    raw_series_urls = source.get("series_urls")
    series_urls = raw_series_urls if isinstance(raw_series_urls, dict) else FRED_SERIES_DEFAULTS
    metrics: dict[str, dict[str, Any]] = {}
    index_labels = {
        "SP500": "S&P 500",
        "DJIA": "Dow Jones",
        "NASDAQCOM": "Nasdaq Composite",
        "VIXCLS": "CBOE VIX",
    }

    for series_id, url_value in series_urls.items():
        series_key = str(series_id).strip().upper()
        series_url = str(url_value or "").strip()
        if not series_url:
            continue
        try:
            points = _read_fred_series(series_url)
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"{source_id}:{series_key}: {exc}")
            continue
        if len(points) < 2:
            warnings.append(f"{source_id}:{series_key}: insufficient data")
            continue

        current_date, current_value = points[-1]
        prev_value = points[-2][1]
        week_value = points[-6][1] if len(points) >= 6 else points[0][1]
        daily_change = ((current_value - prev_value) / prev_value * 100.0) if prev_value else 0.0
        weekly_change = ((current_value - week_value) / week_value * 100.0) if week_value else 0.0
        label = index_labels.get(series_key, series_key)
        occurred = f"{current_date}T00:00:00+00:00"

        if series_key == "VIXCLS":
            base_score = 46.0
            if current_value >= 35:
                base_score += 40.0
            elif current_value >= 30:
                base_score += 30.0
            elif current_value >= 25:
                base_score += 20.0
            elif current_value >= 20:
                base_score += 10.0
            if daily_change >= 20:
                base_score += 15.0
            elif daily_change >= 10:
                base_score += 8.0
            category = "market_volatility"
            title = f"{label} at {current_value:.2f} ({daily_change:+.2f}% day)"
            summary = f"{label} daily move {daily_change:+.2f}%, 5-day move {weekly_change:+.2f}%."
        else:
            base_score = 34.0
            if daily_change <= -5.0:
                base_score += 45.0
            elif daily_change <= -3.5:
                base_score += 32.0
            elif daily_change <= -2.0:
                base_score += 20.0
            elif daily_change <= -1.0:
                base_score += 10.0
            if weekly_change <= -7.0:
                base_score += 22.0
            elif weekly_change <= -4.0:
                base_score += 14.0
            category = "market_index"
            title = f"{label} {daily_change:+.2f}% day ({current_value:,.2f})"
            summary = f"{label} daily {daily_change:+.2f}% and 5-day {weekly_change:+.2f}%."
        keyword_boost, keyword_hits = _keyword_bonus(title, summary, focus_keywords)
        score = min(100.0, base_score + keyword_boost + _freshness_bonus(occurred))
        out.append(
            {
                "event_id": f"{source_id}:{series_key}",
                "source_id": source_id,
                "source_type": "fred_market",
                "category": category,
                "title": title,
                "summary": summary,
                "region": "Global markets",
                "occurred_at": occurred,
                "severity_score": round(score, 2),
                "severity_level": _severity_label(score),
                "url": f"https://fred.stlouisfed.org/series/{series_key}",
                "focus_hits": keyword_hits,
            }
        )
        metrics[series_key] = {
            "current_date": current_date,
            "current_value": current_value,
            "daily_change": daily_change,
            "weekly_change": weekly_change,
        }

    if metrics:
        spx = metrics.get("SP500")
        dji = metrics.get("DJIA")
        ndq = metrics.get("NASDAQCOM")
        vix = metrics.get("VIXCLS")
        stress_score = 30.0
        if spx and spx["daily_change"] <= -2.0:
            stress_score += 15.0
        if dji and dji["daily_change"] <= -2.0:
            stress_score += 12.0
        if ndq and ndq["daily_change"] <= -2.5:
            stress_score += 15.0
        if vix and vix["current_value"] >= 25.0:
            stress_score += 20.0
        if vix and vix["current_value"] >= 30.0:
            stress_score += 12.0
        if spx and spx["weekly_change"] <= -4.0:
            stress_score += 10.0
        if ndq and ndq["weekly_change"] <= -5.0:
            stress_score += 12.0

        latest_date = max(row.get("current_date", "1970-01-01") for row in metrics.values())
        occurred = f"{latest_date}T00:00:00+00:00"
        if stress_score >= 84.0:
            title = "Global market crash-risk spike detected"
        elif stress_score >= 70.0:
            title = "Global market stress elevated"
        else:
            title = "Global market risk watch"
        parts: list[str] = []
        if spx:
            parts.append(f"S&P {spx['daily_change']:+.2f}% day")
        if ndq:
            parts.append(f"Nasdaq {ndq['daily_change']:+.2f}% day")
        if dji:
            parts.append(f"Dow {dji['daily_change']:+.2f}% day")
        if vix:
            parts.append(f"VIX {vix['current_value']:.2f}")
        summary = " | ".join(parts)
        keyword_boost, keyword_hits = _keyword_bonus(title, summary, focus_keywords)
        score = min(100.0, stress_score + keyword_boost + _freshness_bonus(occurred))
        out.append(
            {
                "event_id": f"{source_id}:MARKET_STRESS",
                "source_id": source_id,
                "source_type": "fred_market",
                "category": "market_stress",
                "title": title,
                "summary": summary,
                "region": "Global markets",
                "occurred_at": occurred,
                "severity_score": round(score, 2),
                "severity_level": _severity_label(score),
                "url": "https://fred.stlouisfed.org/",
                "focus_hits": list(dict.fromkeys(keyword_hits + ["market_stress", "vix"]))[:8],
            }
        )

    return out, warnings


def _normalize_stooq_equity_watchlist(
    source: dict[str, Any],
    source_id: str,
    focus_keywords: list[str],
) -> tuple[list[dict[str, Any]], list[str]]:
    warnings: list[str] = []
    out: list[dict[str, Any]] = []
    symbols = source.get("symbols") if isinstance(source.get("symbols"), list) else DEFAULT_STOCK_WATCHLIST
    symbol_labels = {
        "SPY.US": "S&P 500 ETF (SPY)",
        "QQQ.US": "Nasdaq 100 ETF (QQQ)",
        "DIA.US": "Dow ETF (DIA)",
        "IWM.US": "Russell 2000 ETF (IWM)",
        "AAPL.US": "Apple (AAPL)",
        "MSFT.US": "Microsoft (MSFT)",
        "NVDA.US": "NVIDIA (NVDA)",
        "AMD.US": "AMD (AMD)",
        "PLTR.US": "Palantir (PLTR)",
        "AMZN.US": "Amazon (AMZN)",
        "GOOGL.US": "Alphabet (GOOGL)",
        "META.US": "Meta (META)",
        "TSLA.US": "Tesla (TSLA)",
        "AVGO.US": "Broadcom (AVGO)",
        "NFLX.US": "Netflix (NFLX)",
        "JPM.US": "JPMorgan (JPM)",
        "XOM.US": "Exxon Mobil (XOM)",
    }
    min_abs_daily = max(0.0, _safe_float(source.get("min_abs_daily_pct"), 1.8))
    min_abs_weekly = max(0.0, _safe_float(source.get("min_abs_weekly_pct"), 4.0))
    max_events = max(4, int(_safe_float(source.get("max_events"), 12.0)))
    always_symbols_raw = source.get("always_include_symbols")
    always_include_symbols = {
        str(token).strip().upper()
        for token in (always_symbols_raw if isinstance(always_symbols_raw, list) else [])
        if str(token).strip()
    }
    scored_rows: list[dict[str, Any]] = []
    for token in symbols:
        symbol = str(token).strip().upper()
        if not symbol:
            continue
        try:
            points = _read_stooq_series(symbol)
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"{source_id}:{symbol}: {exc}")
            continue
        if len(points) < 2:
            warnings.append(f"{source_id}:{symbol}: insufficient data")
            continue
        current_date, current_close = points[-1]
        prev_close = points[-2][1]
        week_close = points[-6][1] if len(points) >= 6 else points[0][1]
        daily_change = ((current_close - prev_close) / prev_close * 100.0) if prev_close else 0.0
        weekly_change = ((current_close - week_close) / week_close * 100.0) if week_close else 0.0
        abs_daily = abs(daily_change)
        abs_weekly = abs(weekly_change)
        if abs_daily < min_abs_daily and abs_weekly < min_abs_weekly and symbol not in always_include_symbols:
            continue

        base_score = 26.0 + min(46.0, abs_daily * 6.0 + abs_weekly * 2.0)
        if daily_change <= -4.0:
            base_score += 12.0
        elif daily_change <= -2.0:
            base_score += 6.0
        occurred = f"{current_date}T00:00:00+00:00"
        label = symbol_labels.get(symbol, symbol)
        title = f"{label} {daily_change:+.2f}% day ({current_close:,.2f})"
        summary = f"{label} daily {daily_change:+.2f}% and 5-day {weekly_change:+.2f}%."
        keyword_boost, keyword_hits = _keyword_bonus(title, summary, focus_keywords)
        score = min(100.0, base_score + keyword_boost + _freshness_bonus(occurred))
        row = {
            "event_id": f"{source_id}:{symbol}",
            "source_id": source_id,
            "source_type": "stooq_equity",
            "category": "equity_watch",
            "title": title,
            "summary": summary,
            "region": "US equities",
            "occurred_at": occurred,
            "severity_score": round(score, 2),
            "severity_level": _severity_label(score),
            "url": f"https://stooq.com/q/d/l/?s={symbol.lower()}&i=d",
            "focus_hits": keyword_hits,
            "_abs_daily": abs_daily,
        }
        scored_rows.append(row)

    scored_rows.sort(key=lambda row: _safe_float(row.get("_abs_daily"), 0.0), reverse=True)
    for row in scored_rows[:max_events]:
        row.pop("_abs_daily", None)
        out.append(row)
    return out, warnings


def _normalize_coingecko_assets(
    payload: list[dict[str, Any]],
    source_id: str,
    focus_keywords: list[str],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if not isinstance(payload, list):
        return out
    stress_values: list[float] = []
    for row in payload[:25]:
        if not isinstance(row, dict):
            continue
        symbol = str(row.get("symbol") or "").upper().strip()
        name = str(row.get("name") or symbol).strip()
        if not symbol:
            continue
        rank = int(_safe_float(row.get("market_cap_rank"), 999))
        price = _safe_float(row.get("current_price"), 0.0)
        chg_24 = _safe_float(row.get("price_change_percentage_24h"), 0.0)
        chg_7d = _safe_float(row.get("price_change_percentage_7d_in_currency"), 0.0)
        occurred = str(row.get("last_updated") or _now_iso())
        base_score = 24.0 + min(48.0, abs(chg_24) * 5.0 + abs(chg_7d) * 1.8)
        if rank <= 10:
            base_score += 6.0
        if chg_24 <= -8.0:
            base_score += 10.0
        summary = f"{name} ({symbol}) 24h {chg_24:+.2f}% | 7d {chg_7d:+.2f}% | price ${price:,.4f}"
        title = f"{name} ({symbol}) {chg_24:+.2f}% day"
        keyword_boost, keyword_hits = _keyword_bonus(title, summary, focus_keywords)
        score = min(100.0, base_score + keyword_boost + _freshness_bonus(occurred))
        out.append(
            {
                "event_id": f"{source_id}:{symbol}",
                "source_id": source_id,
                "source_type": "coingecko",
                "category": "crypto_market",
                "title": title,
                "summary": summary,
                "region": "Global crypto",
                "occurred_at": occurred,
                "severity_score": round(score, 2),
                "severity_level": _severity_label(score),
                "url": f"https://www.coingecko.com/en/coins/{str(row.get('id') or '').strip()}",
                "focus_hits": keyword_hits,
            }
        )
        if rank <= 10:
            stress_values.append(chg_24)

    if stress_values:
        avg_top10 = sum(stress_values) / len(stress_values)
        stress_score = 30.0 + min(50.0, abs(avg_top10) * 6.0)
        if avg_top10 <= -6.0:
            stress_score += 16.0
            title = "Crypto broad selloff risk"
        elif avg_top10 <= -3.0:
            stress_score += 8.0
            title = "Crypto market stress elevated"
        else:
            title = "Crypto market risk watch"
        summary = f"Average 24h move across top-10 market-cap assets: {avg_top10:+.2f}%."
        keyword_boost, keyword_hits = _keyword_bonus(title, summary, focus_keywords)
        score = min(100.0, stress_score + keyword_boost)
        out.append(
            {
                "event_id": f"{source_id}:CRYPTO_STRESS",
                "source_id": source_id,
                "source_type": "coingecko",
                "category": "crypto_market_stress",
                "title": title,
                "summary": summary,
                "region": "Global crypto",
                "occurred_at": _now_iso(),
                "severity_score": round(score, 2),
                "severity_level": _severity_label(score),
                "url": "https://www.coingecko.com/",
                "focus_hits": keyword_hits,
            }
        )
    return out


def _normalize_fred_fx_watch(
    source: dict[str, Any],
    source_id: str,
    focus_keywords: list[str],
) -> tuple[list[dict[str, Any]], list[str]]:
    warnings: list[str] = []
    out: list[dict[str, Any]] = []
    raw_series_urls = source.get("series_urls")
    series_urls = raw_series_urls if isinstance(raw_series_urls, dict) else FRED_FX_SERIES_DEFAULTS
    labels = {
        "DTWEXBGS": "USD Broad Dollar Index",
        "DEXUSEU": "USD per EUR",
        "DEXJPUS": "JPY per USD",
        "DEXUSUK": "USD per GBP",
    }
    for series_id, url_value in series_urls.items():
        series_key = str(series_id).strip().upper()
        series_url = str(url_value or "").strip()
        if not series_url:
            continue
        try:
            points = _read_fred_series(series_url)
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"{source_id}:{series_key}: {exc}")
            continue
        if len(points) < 2:
            warnings.append(f"{source_id}:{series_key}: insufficient data")
            continue
        current_date, current_value = points[-1]
        prev_value = points[-2][1]
        week_value = points[-6][1] if len(points) >= 6 else points[0][1]
        daily_change = ((current_value - prev_value) / prev_value * 100.0) if prev_value else 0.0
        weekly_change = ((current_value - week_value) / week_value * 100.0) if week_value else 0.0
        label = labels.get(series_key, series_key)
        occurred = f"{current_date}T00:00:00+00:00"
        base_score = 22.0 + min(36.0, abs(daily_change) * 8.0 + abs(weekly_change) * 2.5)
        if abs(daily_change) >= 1.0:
            base_score += 8.0
        summary = f"{label} daily {daily_change:+.2f}% and 5-day {weekly_change:+.2f}%."
        title = f"{label} {daily_change:+.2f}% day"
        keyword_boost, keyword_hits = _keyword_bonus(title, summary, focus_keywords)
        score = min(100.0, base_score + keyword_boost + _freshness_bonus(occurred))
        out.append(
            {
                "event_id": f"{source_id}:{series_key}",
                "source_id": source_id,
                "source_type": "fred_fx",
                "category": "fx_market",
                "title": title,
                "summary": summary,
                "region": "Global FX",
                "occurred_at": occurred,
                "severity_score": round(score, 2),
                "severity_level": _severity_label(score),
                "url": f"https://fred.stlouisfed.org/series/{series_key}",
                "focus_hits": keyword_hits,
            }
        )
    return out, warnings


def _normalize_open_meteo_local(
    payload: dict[str, Any],
    source_id: str,
    focus_keywords: list[str],
    location: dict[str, Any],
) -> list[dict[str, Any]]:
    current = payload.get("current") if isinstance(payload.get("current"), dict) else {}
    daily = payload.get("daily") if isinstance(payload.get("daily"), dict) else {}

    temp = _safe_float(current.get("temperature_2m"), 0.0)
    apparent = _safe_float(current.get("apparent_temperature"), temp)
    precip = _safe_float(current.get("precipitation"), 0.0)
    wind = _safe_float(current.get("wind_speed_10m"), 0.0)
    weather_code = int(_safe_float(current.get("weather_code"), 0.0))
    occurred = str(current.get("time") or _now_iso())
    max_temp = _safe_float((daily.get("temperature_2m_max") or [temp])[0], temp)
    min_temp = _safe_float((daily.get("temperature_2m_min") or [temp])[0], temp)
    daily_precip = _safe_float((daily.get("precipitation_sum") or [precip])[0], precip)
    daily_wind = _safe_float((daily.get("wind_speed_10m_max") or [wind])[0], wind)

    label = str(location.get("label") or "Home").strip() or "Home"
    weather_label = _weather_code_label(weather_code)
    title = f"Local weather watch ({label}): {weather_label}"
    summary = (
        f"Temp {temp:.1f}C (feels {apparent:.1f}C), wind {wind:.1f} km/h, "
        f"today precip {daily_precip:.1f} mm, high/low {max_temp:.1f}/{min_temp:.1f}C."
    )

    score = 32.0
    if weather_code in {95, 96, 99}:
        score += 45.0
    elif weather_code in {80, 81, 82}:
        score += 20.0
    elif weather_code in {71, 73, 75, 77, 85, 86}:
        score += 18.0
    if daily_wind >= 70.0:
        score += 30.0
    elif daily_wind >= 50.0:
        score += 20.0
    elif daily_wind >= 35.0:
        score += 12.0
    if daily_precip >= 30.0:
        score += 26.0
    elif daily_precip >= 15.0:
        score += 16.0
    elif daily_precip >= 5.0:
        score += 8.0
    if max_temp >= 38.0 or min_temp <= -10.0:
        score += 20.0
    if apparent >= 40.0 or apparent <= -15.0:
        score += 12.0
    keyword_boost, keyword_hits = _keyword_bonus(title, summary, focus_keywords)
    score = min(100.0, score + keyword_boost + _freshness_bonus(occurred))

    return [
        {
            "event_id": f"{source_id}:local_weather",
            "source_id": source_id,
            "source_type": "open_meteo",
            "category": "weather_local",
            "title": title,
            "summary": summary,
            "region": label,
            "occurred_at": occurred,
            "severity_score": round(score, 2),
            "severity_level": _severity_label(score),
            "url": "https://open-meteo.com/",
            "focus_hits": list(dict.fromkeys(keyword_hits + [weather_label]))[:8],
        }
    ]


def _normalize_usgs(payload: dict[str, Any], source_id: str, focus_keywords: list[str]) -> list[dict[str, Any]]:
    features = payload.get("features") if isinstance(payload, dict) else []
    if not isinstance(features, list):
        features = []
    out: list[dict[str, Any]] = []
    for row in features:
        if not isinstance(row, dict):
            continue
        props = row.get("properties") if isinstance(row.get("properties"), dict) else {}
        mag = _safe_float(props.get("mag"), 0.0)
        title = str(props.get("title") or props.get("place") or "Earthquake").strip()
        place = str(props.get("place") or "").strip()
        occurred = ""
        timestamp_ms = props.get("time")
        if isinstance(timestamp_ms, (int, float)):
            occurred = datetime.fromtimestamp(float(timestamp_ms) / 1000.0, timezone.utc).isoformat()
        base_score = max(15.0, mag * 12.0)
        alert_flag = str(props.get("alert") or "").strip().lower()
        if alert_flag == "red":
            base_score += 30.0
        elif alert_flag == "orange":
            base_score += 20.0
        elif alert_flag == "yellow":
            base_score += 10.0
        keyword_boost, keyword_hits = _keyword_bonus(title, place, focus_keywords)
        score = min(100.0, base_score + keyword_boost + _freshness_bonus(occurred))
        out.append(
            {
                "event_id": str(row.get("id") or ""),
                "source_id": source_id,
                "source_type": "usgs",
                "category": "earthquake",
                "title": title,
                "summary": place,
                "region": place,
                "occurred_at": occurred,
                "severity_score": round(score, 2),
                "severity_level": _severity_label(score),
                "url": str(props.get("url") or "").strip(),
                "focus_hits": keyword_hits,
            }
        )
    return out


def _normalize_eonet(payload: dict[str, Any], source_id: str, focus_keywords: list[str]) -> list[dict[str, Any]]:
    rows = payload.get("events") if isinstance(payload, dict) else []
    if not isinstance(rows, list):
        rows = []
    out: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        title = str(row.get("title") or "").strip()
        if not title:
            continue
        categories = row.get("categories") if isinstance(row.get("categories"), list) else []
        category = "natural_event"
        if categories and isinstance(categories[0], dict):
            category = str(categories[0].get("title") or category).strip().lower().replace(" ", "_")
        geometry = row.get("geometry") if isinstance(row.get("geometry"), list) else []
        occurred = ""
        if geometry and isinstance(geometry[-1], dict):
            occurred = str(geometry[-1].get("date") or "")
        source_link = str(row.get("link") or "").strip()
        base_score = 42.0
        if "wildfire" in category:
            base_score = 58.0
        elif "volcano" in category:
            base_score = 62.0
        elif "severe" in category or "storm" in category:
            base_score = 64.0
        keyword_boost, keyword_hits = _keyword_bonus(title, category, focus_keywords)
        score = min(100.0, base_score + keyword_boost + _freshness_bonus(occurred))
        out.append(
            {
                "event_id": str(row.get("id") or ""),
                "source_id": source_id,
                "source_type": "nasa_eonet",
                "category": category,
                "title": title,
                "summary": str(row.get("description") or "")[:280],
                "region": "",
                "occurred_at": occurred,
                "severity_score": round(score, 2),
                "severity_level": _severity_label(score),
                "url": source_link,
                "focus_hits": keyword_hits,
            }
        )
    return out


def _normalize_noaa(
    payload: dict[str, Any],
    source_id: str,
    focus_keywords: list[str],
    *,
    category: str = "weather_alert",
    region_fallback: str = "",
) -> list[dict[str, Any]]:
    rows = payload.get("features") if isinstance(payload, dict) else []
    if not isinstance(rows, list):
        rows = []
    out: list[dict[str, Any]] = []
    severity_points = {
        "extreme": 92.0,
        "severe": 80.0,
        "moderate": 62.0,
        "minor": 45.0,
        "unknown": 38.0,
    }
    for row in rows:
        if not isinstance(row, dict):
            continue
        props = row.get("properties") if isinstance(row.get("properties"), dict) else {}
        title = str(props.get("headline") or props.get("event") or "").strip()
        if not title:
            continue
        severity = str(props.get("severity") or "unknown").strip().lower()
        base_score = severity_points.get(severity, 40.0)
        if category == "weather_alert":
            # Global NOAA feed can flood alerts; keep generic weather slightly lower priority
            # than war/conflict, market stress, and home-area weather signals.
            base_score = max(24.0, base_score - 18.0)
        area = str(props.get("areaDesc") or "").strip()
        if not area and region_fallback:
            area = region_fallback
        summary = str(props.get("description") or props.get("event") or "")[:280]
        occurred = str(props.get("effective") or props.get("onset") or "")
        keyword_boost, keyword_hits = _keyword_bonus(title, summary, focus_keywords)
        score = min(100.0, base_score + keyword_boost + _freshness_bonus(occurred))
        out.append(
            {
                "event_id": str(props.get("id") or row.get("id") or ""),
                "source_id": source_id,
                "source_type": "noaa",
                "category": category,
                "title": title,
                "summary": summary,
                "region": area,
                "occurred_at": occurred,
                "severity_score": round(score, 2),
                "severity_level": _severity_label(score),
                "url": str(props.get("@id") or "").strip(),
                "focus_hits": keyword_hits,
            }
        )
    return out


def _normalize_reliefweb(payload: dict[str, Any], source_id: str, focus_keywords: list[str]) -> list[dict[str, Any]]:
    rows = payload.get("data") if isinstance(payload, dict) else []
    if not isinstance(rows, list):
        rows = []
    out: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        fields = row.get("fields") if isinstance(row.get("fields"), dict) else {}
        title = str(fields.get("title") or "").strip()
        if not title:
            continue
        body = str(fields.get("body-html") or fields.get("body") or "")
        summary = body.replace("\n", " ").replace("\r", " ")[:280]
        source_names: list[str] = []
        source = fields.get("source")
        if isinstance(source, list):
            for item in source:
                if isinstance(item, dict):
                    name = str(item.get("name") or "").strip()
                    if name:
                        source_names.append(name)
        countries = fields.get("country")
        region = ""
        if isinstance(countries, list):
            names = []
            for item in countries:
                if isinstance(item, dict):
                    token = str(item.get("name") or "").strip()
                    if token:
                        names.append(token)
            region = ", ".join(names[:3])
        date_payload = fields.get("date") if isinstance(fields.get("date"), dict) else {}
        occurred = str(date_payload.get("created") or date_payload.get("original") or "")
        title_lower = title.lower()
        category = "humanitarian_report"
        base_score = 52.0
        if any(
            token in title_lower
            for token in ["war", "conflict", "invasion", "missile", "airstrike", "military", "ceasefire", "attack"]
        ):
            category = "war_conflict"
            base_score = 78.0
        elif any(token in title_lower for token in ["displacement", "cholera", "famine", "outbreak"]):
            base_score = 68.0
        elif any(token in title_lower for token in ["earthquake", "flood", "cyclone", "hurricane", "wildfire"]):
            base_score = 72.0
        keyword_boost, keyword_hits = _keyword_bonus(title, summary, focus_keywords)
        score = min(100.0, base_score + keyword_boost + _freshness_bonus(occurred))
        out.append(
            {
                "event_id": str(row.get("id") or ""),
                "source_id": source_id,
                "source_type": "reliefweb",
                "category": category,
                "title": title,
                "summary": summary,
                "region": region,
                "occurred_at": occurred,
                "severity_score": round(score, 2),
                "severity_level": _severity_label(score),
                "url": str(fields.get("url") or ""),
                "focus_hits": keyword_hits + source_names[:2],
            }
        )
    return out


def _collect_events(config: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    warnings: list[str] = []
    statuses: list[dict[str, Any]] = []
    focus_keywords = [
        str(row).strip().lower()
        for row in (config.get("focus_keywords") or [])
        if str(row).strip()
    ]
    if not focus_keywords:
        focus_keywords = [str(row).lower() for row in _default_sources().get("focus_keywords", [])]

    local_source_types = {"noaa_alerts_local", "open_meteo_local_weather"}
    needs_home_location = False
    for source in (config.get("data_sources") or []):
        if not isinstance(source, dict):
            continue
        if not bool(source.get("enabled", True)):
            continue
        source_type = str(source.get("type") or "").strip().lower()
        if source_type in local_source_types:
            needs_home_location = True
            break

    home_location: dict[str, Any] | None = None
    if needs_home_location:
        home_location, location_note = _resolve_home_location(config)
        if home_location is None:
            warnings.append("home_location: unavailable (set PERMANENCE_HOME_LAT and PERMANENCE_HOME_LON for precise local weather)")
        else:
            statuses.append(
                {
                    "id": "home_location",
                    "type": "location",
                    "enabled": True,
                    "status": "ok",
                    "note": location_note,
                    "label": home_location.get("label"),
                }
            )

    events: list[dict[str, Any]] = []
    for source in (config.get("data_sources") or []):
        if not isinstance(source, dict):
            continue
        source_id = str(source.get("id") or "source").strip() or "source"
        source_type = str(source.get("type") or "").strip().lower()
        source_url = str(source.get("url") or "").strip()
        enabled = bool(source.get("enabled", True))
        if not enabled:
            statuses.append({"id": source_id, "type": source_type, "enabled": False, "status": "skipped"})
            continue
        if not source_url and source_type not in {"fred_market_stress", "stooq_equity_watchlist", "fred_fx_watch"}:
            warnings.append(f"{source_id}: missing URL")
            statuses.append({"id": source_id, "type": source_type, "enabled": True, "status": "invalid"})
            continue
        try:
            if source_type == "fred_market_stress":
                rows, series_warnings = _normalize_fred_market_stress(source, source_id, focus_keywords)
                warnings.extend(series_warnings)
            elif source_type == "stooq_equity_watchlist":
                rows, feed_warnings = _normalize_stooq_equity_watchlist(source, source_id, focus_keywords)
                warnings.extend(feed_warnings)
            elif source_type == "coingecko_top_assets":
                payload = _fetch_json(source_url)
                rows = _normalize_coingecko_assets(payload if isinstance(payload, list) else [], source_id, focus_keywords)
            elif source_type == "fred_fx_watch":
                rows, feed_warnings = _normalize_fred_fx_watch(source, source_id, focus_keywords)
                warnings.extend(feed_warnings)
            elif source_type == "earthquake_geojson":
                payload = _fetch_json(source_url)
                rows = _normalize_usgs(payload if isinstance(payload, dict) else {}, source_id, focus_keywords)
            elif source_type == "eonet_events":
                payload = _fetch_json(source_url)
                rows = _normalize_eonet(payload if isinstance(payload, dict) else {}, source_id, focus_keywords)
            elif source_type == "noaa_alerts":
                payload = _fetch_json(source_url)
                rows = _normalize_noaa(payload if isinstance(payload, dict) else {}, source_id, focus_keywords)
            elif source_type == "noaa_alerts_local":
                if home_location is None:
                    warnings.append(f"{source_id}: skipped (home location unavailable)")
                    statuses.append({"id": source_id, "type": source_type, "enabled": True, "status": "skipped"})
                    continue
                local_url = _build_noaa_local_url(source_url, home_location)
                payload = _fetch_json(local_url)
                rows = _normalize_noaa(
                    payload if isinstance(payload, dict) else {},
                    source_id,
                    focus_keywords,
                    category="weather_local_alert",
                    region_fallback=str(home_location.get("label") or ""),
                )
            elif source_type == "open_meteo_local_weather":
                if home_location is None:
                    warnings.append(f"{source_id}: skipped (home location unavailable)")
                    statuses.append({"id": source_id, "type": source_type, "enabled": True, "status": "skipped"})
                    continue
                local_url = _build_open_meteo_local_url(source_url, home_location)
                payload = _fetch_json(local_url)
                rows = _normalize_open_meteo_local(
                    payload if isinstance(payload, dict) else {},
                    source_id,
                    focus_keywords,
                    home_location,
                )
            elif source_type == "reliefweb_reports":
                payload = _fetch_json(source_url)
                rows = _normalize_reliefweb(payload if isinstance(payload, dict) else {}, source_id, focus_keywords)
            else:
                warnings.append(f"{source_id}: unsupported source type '{source_type}'")
                statuses.append({"id": source_id, "type": source_type, "enabled": True, "status": "unsupported"})
                continue
            events.extend(rows)
            statuses.append(
                {"id": source_id, "type": source_type, "enabled": True, "status": "ok", "event_count": len(rows)}
            )
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"{source_id}: {exc}")
            statuses.append({"id": source_id, "type": source_type, "enabled": True, "status": "error"})

    events.sort(key=lambda row: _safe_float(row.get("severity_score"), 0.0), reverse=True)
    return events, statuses, warnings


def _write_outputs(
    config: dict[str, Any],
    config_status: str,
    events: list[dict[str, Any]],
    statuses: list[dict[str, Any]],
    warnings: list[str],
) -> tuple[Path, Path]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    TOOL_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _now().strftime("%Y%m%d-%H%M%S")
    md_path = OUTPUT_DIR / f"world_watch_{stamp}.md"
    latest_md = OUTPUT_DIR / "world_watch_latest.md"
    json_path = TOOL_DIR / f"world_watch_{stamp}.json"

    high_alerts = [row for row in events if _safe_float(row.get("severity_score"), 0.0) >= 70.0][:20]
    top_events = events[:200]
    category_counts: dict[str, int] = {}
    for row in events:
        category = str(row.get("category") or "unknown")
        category_counts[category] = category_counts.get(category, 0) + 1

    map_views = config.get("map_views") if isinstance(config.get("map_views"), list) else []
    market_monitors = config.get("market_monitors") if isinstance(config.get("market_monitors"), list) else []
    home_location = config.get("home_location") if isinstance(config.get("home_location"), dict) else {}
    alert_focus = config.get("alert_focus") if isinstance(config.get("alert_focus"), dict) else {}
    major_categories = {
        str(row).strip().lower()
        for row in (alert_focus.get("major_categories") or [])
        if str(row).strip()
    }
    min_major_score = _safe_float(alert_focus.get("min_major_score"), 68.0)
    major_events = [
        row
        for row in events
        if str(row.get("category") or "").strip().lower() in major_categories
        and _safe_float(row.get("severity_score"), 0.0) >= min_major_score
    ][:20]
    focus_events: list[dict[str, Any]] = []
    for category in sorted(major_categories):
        category_rows = [
            row
            for row in events
            if str(row.get("category") or "").strip().lower() == category
        ][:5]
        focus_events.extend(category_rows)

    lines = [
        "# World Watch Ingest",
        "",
        f"Generated (UTC): {_now_iso()}",
        f"Sources file: {SOURCES_PATH} ({config_status})",
        "",
        "## Snapshot",
        f"- Events collected: {len(events)}",
        f"- High alerts (score >= 70): {len(high_alerts)}",
        f"- Major-event candidates: {len(major_events)}",
        f"- Source feeds active: {sum(1 for row in statuses if row.get('status') == 'ok')}",
        "",
        "## Local Focus",
        f"- Home label: {str(home_location.get('label') or 'not set')}",
        f"- Home coordinates: {str(home_location.get('latitude') or 'n/a')}, {str(home_location.get('longitude') or 'n/a')}",
        "",
        "## Map Views",
    ]
    if not map_views:
        lines.append("- No map views configured.")
    for view in map_views[:8]:
        if not isinstance(view, dict):
            continue
        name = str(view.get("name") or "Map").strip()
        url = str(view.get("url") or "").strip()
        if not url:
            continue
        lines.append(f"- {name}: {url}")

    lines.extend(["", "## Market Monitors"])
    if not market_monitors:
        lines.append("- No market monitors configured.")
    for item in market_monitors[:16]:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "Market monitor").strip()
        url = str(item.get("url") or "").strip()
        if not url:
            continue
        lines.append(f"- {name}: {url}")

    lines.extend(["", "## High Alerts"])
    if not high_alerts:
        lines.append("- No high alerts right now.")
    for idx, row in enumerate(high_alerts, start=1):
        lines.append(
            f"{idx}. [{row.get('category')}] score={row.get('severity_score')} | {row.get('title')} | region={row.get('region') or '-'}"
        )
        if row.get("url"):
            lines.append(f"   - {row.get('url')}")

    lines.extend(["", "## Category Totals"])
    if not category_counts:
        lines.append("- No categories detected.")
    for key, value in sorted(category_counts.items(), key=lambda item: item[1], reverse=True):
        lines.append(f"- {key}: {value}")

    if warnings:
        lines.extend(["", "## Warnings"])
        for warning in warnings:
            lines.append(f"- {warning}")

    lines.extend(
        [
            "",
            "## Governance Notes",
            "- Situational awareness only; no autonomous financial or publishing actions.",
            "- Human decision remains required for irreversible actions.",
            "",
        ]
    )

    report = "\n".join(lines)
    md_path.write_text(report, encoding="utf-8")
    latest_md.write_text(report, encoding="utf-8")

    payload = {
        "generated_at": _now_iso(),
        "sources_path": str(SOURCES_PATH),
        "sources_status": config_status,
        "map_views": map_views,
        "market_monitors": market_monitors,
        "home_location": home_location,
        "alert_focus": alert_focus,
        "source_status": statuses,
        "item_count": len(events),
        "high_alert_count": len(high_alerts),
        "major_event_count": len(major_events),
        "category_counts": category_counts,
        "top_alerts": high_alerts,
        "top_major_events": major_events,
        "focus_events": focus_events,
        "top_events": top_events,
        "warnings": warnings,
        "latest_markdown": str(latest_md),
    }
    json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return md_path, json_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ingest global world-watch data and produce alert summary.")
    parser.add_argument("--force-template", action="store_true", help="Rewrite world watch sources template file")
    args = parser.parse_args(argv)

    config, config_status = _ensure_sources(SOURCES_PATH, force_template=args.force_template)
    events, statuses, warnings = _collect_events(config)
    md_path, json_path = _write_outputs(config, config_status, events, statuses, warnings)

    print(f"World watch ingest written: {md_path}")
    print(f"World watch latest: {OUTPUT_DIR / 'world_watch_latest.md'}")
    print(f"Tool payload written: {json_path}")
    print(f"Events collected: {len(events)} | high alerts: {len([r for r in events if _safe_float(r.get('severity_score'), 0.0) >= 70.0])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
