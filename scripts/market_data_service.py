#!/usr/bin/env python3
"""
Live market data service for Permanence OS.

Provides real-time quotes for equities, crypto, forex, and commodities
via Stooq (equities/forex/commodities), CoinGecko (crypto), and FRED (macro).
Used by dashboard_api.py to serve /api/markets/* endpoints.

Usage:
    python3 scripts/market_data_service.py --action quotes --symbols AAPL.US,MSFT.US
    python3 scripts/market_data_service.py --action watchlist
    python3 scripts/market_data_service.py --action crypto
    python3 scripts/market_data_service.py --action forex
    python3 scripts/market_data_service.py --action commodities
    python3 scripts/market_data_service.py --action ohlcv --symbol AAPL.US --range 1M
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

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
        if (value.startswith('"') and value.endswith('"')) or (
            value.startswith("'") and value.endswith("'")
        ):
            value = value[1:-1]
        os.environ[key] = value


_load_local_env()

TIMEOUT = int(os.getenv("PERMANENCE_MARKET_TIMEOUT", "10"))
CACHE_DIR = Path(os.getenv("PERMANENCE_CACHE_DIR", str(BASE_DIR / "memory" / "working" / "market_cache")))
CACHE_TTL_SECONDS = int(os.getenv("PERMANENCE_MARKET_CACHE_TTL", "60"))

# -- Watchlists --

EQUITY_WATCHLIST = [
    "AAPL.US", "MSFT.US", "NVDA.US", "TSLA.US", "AMZN.US",
    "GOOGL.US", "META.US", "JPM.US", "V.US", "BRK-B.US",
    "AMD.US", "PLTR.US", "NFLX.US", "AVGO.US", "SPY.US",
    "QQQ.US", "DIA.US", "IWM.US",
]

CRYPTO_IDS = [
    "bitcoin", "ethereum", "solana", "cardano", "dogecoin",
    "ripple", "polkadot", "avalanche-2", "chainlink", "litecoin",
]

FOREX_PAIRS = [
    "EURUSD", "USDJPY", "GBPUSD", "AUDUSD", "USDCAD", "USDCHF",
]

COMMODITY_SYMBOLS = [
    "GC.F",   # Gold
    "SI.F",   # Silver
    "CL.F",   # Crude Oil
    "NG.F",   # Natural Gas
    "HG.F",   # Copper
    "PL.F",   # Platinum
]

SYMBOL_LABELS: dict[str, str] = {
    "AAPL.US": "Apple", "MSFT.US": "Microsoft", "NVDA.US": "NVIDIA",
    "TSLA.US": "Tesla", "AMZN.US": "Amazon", "GOOGL.US": "Alphabet",
    "META.US": "Meta", "JPM.US": "JPMorgan", "V.US": "Visa",
    "BRK-B.US": "Berkshire B", "AMD.US": "AMD", "PLTR.US": "Palantir",
    "NFLX.US": "Netflix", "AVGO.US": "Broadcom", "SPY.US": "S&P 500 ETF",
    "QQQ.US": "Nasdaq 100 ETF", "DIA.US": "Dow ETF", "IWM.US": "Russell 2000 ETF",
    "GC.F": "Gold", "SI.F": "Silver", "CL.F": "Crude Oil",
    "NG.F": "Nat Gas", "HG.F": "Copper", "PL.F": "Platinum",
    "EURUSD": "EUR/USD", "USDJPY": "USD/JPY", "GBPUSD": "GBP/USD",
    "AUDUSD": "AUD/USD", "USDCAD": "USD/CAD", "USDCHF": "USD/CHF",
}

# -- Helpers --


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _cache_path(key: str) -> Path:
    return CACHE_DIR / f"{key}.json"


def _read_cache(key: str) -> Any | None:
    path = _cache_path(key)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if time.time() - data.get("_ts", 0) < CACHE_TTL_SECONDS:
            return data.get("payload")
    except (json.JSONDecodeError, OSError):
        pass
    return None


def _write_cache(key: str, payload: Any) -> None:
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        data = {"_ts": time.time(), "payload": payload}
        _cache_path(key).write_text(json.dumps(data), encoding="utf-8")
    except OSError:
        pass


# -- Stooq fetchers --


def _fetch_stooq_csv(symbol: str) -> list[tuple[str, float, float, float, float, float]]:
    """Fetch daily OHLCV from Stooq. Returns list of (date, open, high, low, close, volume)."""
    clean = symbol.strip().lower()
    if not clean:
        return []
    url = f"https://stooq.com/q/d/l/?s={clean}&i=d"
    try:
        resp = requests.get(url, timeout=TIMEOUT)
        resp.raise_for_status()
        text = resp.text
    except requests.RequestException:
        return []
    if text.strip().lower().startswith("no data"):
        return []
    reader = csv.reader(text.splitlines())
    header = next(reader, None)
    if not header or len(header) < 5:
        return []
    out: list[tuple[str, float, float, float, float, float]] = []
    for row in reader:
        if len(row) < 5:
            continue
        stamp = str(row[0]).strip()
        o = _safe_float(row[1])
        h = _safe_float(row[2])
        l = _safe_float(row[3])
        c = _safe_float(row[4])
        v = _safe_float(row[5]) if len(row) > 5 else 0.0
        if stamp and c > 0:
            out.append((stamp, o, h, l, c, v))
    return out


def _stooq_quote(symbol: str) -> dict[str, Any] | None:
    """Get latest quote for a Stooq symbol."""
    rows = _fetch_stooq_csv(symbol)
    if len(rows) < 2:
        return None
    date, o, h, l, c, v = rows[-1]
    prev_c = rows[-2][4]
    change = c - prev_c
    change_pct = (change / prev_c * 100.0) if prev_c else 0.0
    week_c = rows[-6][4] if len(rows) >= 6 else rows[0][4]
    week_change_pct = ((c - week_c) / week_c * 100.0) if week_c else 0.0
    label = SYMBOL_LABELS.get(symbol, symbol.replace(".US", "").replace(".F", ""))
    ticker = symbol.replace(".US", "").replace(".F", "").upper()
    return {
        "symbol": symbol,
        "ticker": ticker,
        "name": label,
        "price": round(c, 4),
        "open": round(o, 4),
        "high": round(h, 4),
        "low": round(l, 4),
        "change": round(change, 4),
        "change_pct": round(change_pct, 2),
        "week_change_pct": round(week_change_pct, 2),
        "volume": int(v),
        "date": date,
        "updated_at": _now_iso(),
    }


def _stooq_ohlcv(symbol: str, limit: int = 252) -> list[dict[str, Any]]:
    """Get OHLCV history for a symbol."""
    rows = _fetch_stooq_csv(symbol)
    out: list[dict[str, Any]] = []
    for date, o, h, l, c, v in rows[-limit:]:
        out.append({"date": date, "o": round(o, 4), "h": round(h, 4), "l": round(l, 4), "c": round(c, 4), "v": int(v)})
    return out


# -- CoinGecko fetcher --


def _fetch_coingecko_markets() -> list[dict[str, Any]]:
    """Fetch top crypto from CoinGecko free API."""
    cache = _read_cache("coingecko_markets")
    if cache is not None:
        return cache
    ids_param = ",".join(CRYPTO_IDS)
    url = (
        "https://api.coingecko.com/api/v3/coins/markets"
        f"?vs_currency=usd&ids={ids_param}"
        "&order=market_cap_desc&per_page=25&page=1"
        "&sparkline=false&price_change_percentage=24h,7d"
    )
    try:
        resp = requests.get(url, timeout=TIMEOUT, headers={"Accept": "application/json"})
        resp.raise_for_status()
        data = resp.json()
    except (requests.RequestException, ValueError):
        return []
    out: list[dict[str, Any]] = []
    for coin in data:
        if not isinstance(coin, dict):
            continue
        symbol = str(coin.get("symbol", "")).upper()
        price = _safe_float(coin.get("current_price"))
        chg_24 = _safe_float(coin.get("price_change_percentage_24h"))
        chg_7d = _safe_float(coin.get("price_change_percentage_7d_in_currency"))
        mcap = _safe_float(coin.get("market_cap"))
        vol = _safe_float(coin.get("total_volume"))
        out.append({
            "symbol": symbol,
            "name": str(coin.get("name", symbol)),
            "price": round(price, 4),
            "change_pct": round(chg_24, 2),
            "week_change_pct": round(chg_7d, 2),
            "market_cap": int(mcap),
            "volume": int(vol),
            "image": str(coin.get("image", "")),
            "updated_at": str(coin.get("last_updated", _now_iso())),
        })
    _write_cache("coingecko_markets", out)
    return out


# -- Public API --


def get_equity_quotes(symbols: list[str] | None = None) -> list[dict[str, Any]]:
    """Get quotes for equity symbols. Uses cache."""
    syms = symbols or EQUITY_WATCHLIST
    cache_key = "equity_" + "_".join(sorted(s.lower() for s in syms[:6]))
    cached = _read_cache(cache_key)
    if cached is not None:
        return cached
    out: list[dict[str, Any]] = []
    for sym in syms:
        q = _stooq_quote(sym)
        if q:
            out.append(q)
    if out:
        _write_cache(cache_key, out)
    return out


def get_crypto_quotes() -> list[dict[str, Any]]:
    """Get crypto market data from CoinGecko."""
    return _fetch_coingecko_markets()


def get_forex_quotes() -> list[dict[str, Any]]:
    """Get forex pair quotes from Stooq."""
    cache_key = "forex_quotes"
    cached = _read_cache(cache_key)
    if cached is not None:
        return cached
    out: list[dict[str, Any]] = []
    for pair in FOREX_PAIRS:
        q = _stooq_quote(pair)
        if q:
            out.append(q)
    if out:
        _write_cache(cache_key, out)
    return out


def get_commodity_quotes() -> list[dict[str, Any]]:
    """Get commodity futures quotes from Stooq."""
    cache_key = "commodity_quotes"
    cached = _read_cache(cache_key)
    if cached is not None:
        return cached
    out: list[dict[str, Any]] = []
    for sym in COMMODITY_SYMBOLS:
        q = _stooq_quote(sym)
        if q:
            out.append(q)
    if out:
        _write_cache(cache_key, out)
    return out


def get_ohlcv(symbol: str, range_key: str = "1M") -> list[dict[str, Any]]:
    """Get OHLCV candle data for charting."""
    limits = {"1D": 1, "1W": 5, "1M": 22, "3M": 66, "6M": 126, "1Y": 252, "5Y": 1260}
    limit = limits.get(range_key, 22)
    cache_key = f"ohlcv_{symbol.lower().replace('.', '_')}_{range_key}"
    cached = _read_cache(cache_key)
    if cached is not None:
        return cached
    data = _stooq_ohlcv(symbol, limit=limit)
    if data:
        _write_cache(cache_key, data)
    return data


def get_all_quotes() -> dict[str, Any]:
    """Full market snapshot for dashboard."""
    return {
        "equities": get_equity_quotes(),
        "crypto": get_crypto_quotes(),
        "forex": get_forex_quotes(),
        "commodities": get_commodity_quotes(),
        "updated_at": _now_iso(),
    }


# -- CLI --


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Permanence OS market data service.")
    parser.add_argument("--action", default="watchlist",
                        choices=["quotes", "watchlist", "crypto", "forex", "commodities", "ohlcv", "all"])
    parser.add_argument("--symbols", default="", help="Comma-separated symbols")
    parser.add_argument("--symbol", default="AAPL.US", help="Single symbol for OHLCV")
    parser.add_argument("--range", default="1M", help="OHLCV range: 1D,1W,1M,3M,6M,1Y,5Y")
    args = parser.parse_args(argv)

    if args.action == "quotes":
        syms = [s.strip() for s in args.symbols.split(",") if s.strip()] or None
        data = get_equity_quotes(syms)
        print(json.dumps(data, indent=2))
    elif args.action == "watchlist":
        data = get_equity_quotes()
        for q in data:
            sign = "+" if q["change_pct"] >= 0 else ""
            print(f"  {q['ticker']:<8} ${q['price']:>10,.2f}  {sign}{q['change_pct']:.2f}%")
    elif args.action == "crypto":
        data = get_crypto_quotes()
        for q in data:
            sign = "+" if q["change_pct"] >= 0 else ""
            print(f"  {q['symbol']:<8} ${q['price']:>12,.4f}  {sign}{q['change_pct']:.2f}%")
    elif args.action == "forex":
        data = get_forex_quotes()
        for q in data:
            sign = "+" if q["change_pct"] >= 0 else ""
            print(f"  {q['name']:<10} {q['price']:>10.4f}  {sign}{q['change_pct']:.2f}%")
    elif args.action == "commodities":
        data = get_commodity_quotes()
        for q in data:
            sign = "+" if q["change_pct"] >= 0 else ""
            print(f"  {q['name']:<10} ${q['price']:>10,.2f}  {sign}{q['change_pct']:.2f}%")
    elif args.action == "ohlcv":
        data = get_ohlcv(args.symbol, args.range)
        print(json.dumps(data, indent=2))
    elif args.action == "all":
        data = get_all_quotes()
        print(json.dumps(data, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
