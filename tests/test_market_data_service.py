#!/usr/bin/env python3
"""Tests for market data service."""

from __future__ import annotations

import json
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import scripts.market_data_service as mds  # noqa: E402


SAMPLE_STOOQ_CSV = """Date,Open,High,Low,Close,Volume
2026-03-14,185.20,187.50,184.80,186.90,52400000
2026-03-15,186.90,188.20,185.60,187.40,48200000
2026-03-16,187.40,189.00,186.20,188.50,51000000
2026-03-17,188.50,190.10,187.80,189.20,49500000
"""

SAMPLE_COINGECKO = [
    {
        "symbol": "btc",
        "name": "Bitcoin",
        "current_price": 104280.0,
        "price_change_percentage_24h": 2.4,
        "price_change_percentage_7d_in_currency": 5.1,
        "market_cap": 2040000000000,
        "total_volume": 38200000000,
        "image": "https://example.com/btc.png",
        "last_updated": "2026-03-17T12:00:00Z",
    },
    {
        "symbol": "eth",
        "name": "Ethereum",
        "current_price": 3842.0,
        "price_change_percentage_24h": 1.8,
        "price_change_percentage_7d_in_currency": 3.2,
        "market_cap": 462000000000,
        "total_volume": 18400000000,
        "image": "https://example.com/eth.png",
        "last_updated": "2026-03-17T12:00:00Z",
    },
]


class TestSafeFloat:
    def test_valid(self):
        assert mds._safe_float("3.14") == 3.14

    def test_invalid(self):
        assert mds._safe_float("abc", 0.0) == 0.0

    def test_none(self):
        assert mds._safe_float(None) == 0.0


class TestCache:
    def test_write_and_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(mds, "CACHE_DIR", Path(tmp)):
                mds._write_cache("test_key", {"price": 100})
                result = mds._read_cache("test_key")
                assert result is not None
                assert result["price"] == 100

    def test_expired_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(mds, "CACHE_DIR", Path(tmp)):
                with patch.object(mds, "CACHE_TTL_SECONDS", 0):
                    mds._write_cache("expired_key", {"price": 100})
                    result = mds._read_cache("expired_key")
                    assert result is None

    def test_missing_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(mds, "CACHE_DIR", Path(tmp)):
                result = mds._read_cache("nonexistent")
                assert result is None


class TestStooqQuote:
    def test_parses_csv(self):
        mock_resp = MagicMock()
        mock_resp.text = SAMPLE_STOOQ_CSV
        mock_resp.raise_for_status = MagicMock()
        with patch("requests.get", return_value=mock_resp):
            quote = mds._stooq_quote("AAPL.US")
            assert quote is not None
            assert quote["ticker"] == "AAPL"
            assert quote["price"] == 189.2
            assert quote["change"] != 0
            assert "change_pct" in quote

    def test_no_data(self):
        mock_resp = MagicMock()
        mock_resp.text = "No data"
        mock_resp.raise_for_status = MagicMock()
        with patch("requests.get", return_value=mock_resp):
            quote = mds._stooq_quote("INVALID")
            assert quote is None

    def test_ohlcv(self):
        mock_resp = MagicMock()
        mock_resp.text = SAMPLE_STOOQ_CSV
        mock_resp.raise_for_status = MagicMock()
        with patch("requests.get", return_value=mock_resp):
            data = mds._stooq_ohlcv("AAPL.US", limit=10)
            assert len(data) == 4
            assert "o" in data[0]
            assert "h" in data[0]
            assert "c" in data[0]


class TestCoinGecko:
    def test_parses_response(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = SAMPLE_COINGECKO
        mock_resp.raise_for_status = MagicMock()
        with patch("requests.get", return_value=mock_resp):
            with patch.object(mds, "_read_cache", return_value=None):
                with patch.object(mds, "_write_cache"):
                    data = mds._fetch_coingecko_markets()
                    assert len(data) == 2
                    assert data[0]["symbol"] == "BTC"
                    assert data[0]["price"] == 104280.0
                    assert data[1]["symbol"] == "ETH"

    def test_uses_cache(self):
        cached = [{"symbol": "BTC", "price": 100000}]
        with patch.object(mds, "_read_cache", return_value=cached):
            data = mds._fetch_coingecko_markets()
            assert data == cached


class TestGetEquityQuotes:
    def test_returns_list(self):
        mock_resp = MagicMock()
        mock_resp.text = SAMPLE_STOOQ_CSV
        mock_resp.raise_for_status = MagicMock()
        with patch("requests.get", return_value=mock_resp):
            with patch.object(mds, "_read_cache", return_value=None):
                with patch.object(mds, "_write_cache"):
                    data = mds.get_equity_quotes(["AAPL.US"])
                    assert len(data) == 1
                    assert data[0]["ticker"] == "AAPL"

    def test_uses_cache(self):
        cached = [{"ticker": "AAPL", "price": 190}]
        with patch.object(mds, "_read_cache", return_value=cached):
            data = mds.get_equity_quotes(["AAPL.US"])
            assert data == cached


class TestGetAllQuotes:
    def test_structure(self):
        with patch.object(mds, "get_equity_quotes", return_value=[]):
            with patch.object(mds, "get_crypto_quotes", return_value=[]):
                with patch.object(mds, "get_forex_quotes", return_value=[]):
                    with patch.object(mds, "get_commodity_quotes", return_value=[]):
                        data = mds.get_all_quotes()
                        assert "equities" in data
                        assert "crypto" in data
                        assert "forex" in data
                        assert "commodities" in data
                        assert "updated_at" in data


class TestSymbolLabels:
    def test_known_symbols(self):
        assert "Apple" in mds.SYMBOL_LABELS["AAPL.US"]
        assert "Gold" in mds.SYMBOL_LABELS["GC.F"]
        assert "EUR/USD" in mds.SYMBOL_LABELS["EURUSD"]

    def test_watchlists_populated(self):
        assert len(mds.EQUITY_WATCHLIST) > 10
        assert len(mds.CRYPTO_IDS) > 5
        assert len(mds.FOREX_PAIRS) > 3
        assert len(mds.COMMODITY_SYMBOLS) > 3


class TestCLI:
    def test_all_action(self):
        with patch.object(mds, "get_all_quotes", return_value={"equities": [], "crypto": [], "forex": [], "commodities": [], "updated_at": "now"}):
            result = mds.main(["--action", "all"])
            assert result == 0

    def test_watchlist_action(self):
        sample = [{"ticker": "AAPL", "price": 190.0, "change_pct": 1.5}]
        with patch.object(mds, "get_equity_quotes", return_value=sample):
            result = mds.main(["--action", "watchlist"])
            assert result == 0
