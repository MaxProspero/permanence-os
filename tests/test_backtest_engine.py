"""Tests for scripts/backtest_engine.py -- Strategy backtesting engine."""

import json
import math
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import backtest_engine as bt
import smc_ict_analyzer as smc


# ---------------------------------------------------------------------------
# Test data
# ---------------------------------------------------------------------------

def _trending_candles(n: int = 60, start: float = 100.0, step: float = 1.5) -> list[dict]:
    """Uptrending candles with enough range for pattern detection."""
    candles = []
    price = start
    for i in range(n):
        o = price
        c = price + step * 0.7
        h = max(o, c) + step * 0.4
        l = min(o, c) - step * 0.3
        candles.append({
            "date": f"2026-{(i//28)+1:02d}-{(i%28)+1:02d}",
            "o": round(o, 2), "h": round(h, 2),
            "l": round(l, 2), "c": round(c, 2),
            "v": 1000 + i * 50,
        })
        price = c + step * 0.2
    return candles


def _volatile_candles(n: int = 80) -> list[dict]:
    """Volatile data with swings and displacements."""
    candles = []
    price = 100.0
    import random
    rng = random.Random(42)  # deterministic
    for i in range(n):
        move = rng.gauss(0, 3)
        o = price
        c = price + move
        h = max(o, c) + abs(rng.gauss(0, 1.5))
        l = min(o, c) - abs(rng.gauss(0, 1.5))
        candles.append({
            "date": f"2026-{(i//28)+1:02d}-{(i%28)+1:02d}",
            "o": round(o, 2), "h": round(h, 2),
            "l": round(l, 2), "c": round(c, 2),
            "v": 1000 + i * 30,
        })
        price = c
    return candles


# ---------------------------------------------------------------------------
# Trade resolution
# ---------------------------------------------------------------------------

class TestTradeResolution:
    def test_long_hits_tp(self):
        candles = [
            {"date": "2026-01-01", "o": 100, "h": 101, "l": 99, "c": 100.5, "v": 100},
            {"date": "2026-01-02", "o": 100.5, "h": 103, "l": 100, "c": 102, "v": 100},
            {"date": "2026-01-03", "o": 102, "h": 106, "l": 101, "c": 105, "v": 100},
        ]
        trade = bt.Trade(
            entry_index=0, entry_date="2026-01-01",
            entry_price=100.5, direction="long",
            stop_loss=98, take_profit=105,
        )
        bt._resolve_trade(trade, candles)
        assert trade.exit_reason == "tp"
        assert trade.exit_price == 105
        assert trade.pnl_pct > 0

    def test_long_hits_sl(self):
        candles = [
            {"date": "2026-01-01", "o": 100, "h": 101, "l": 99, "c": 100.5, "v": 100},
            {"date": "2026-01-02", "o": 100.5, "h": 101, "l": 96, "c": 97, "v": 100},
        ]
        trade = bt.Trade(
            entry_index=0, entry_date="2026-01-01",
            entry_price=100.5, direction="long",
            stop_loss=97, take_profit=110,
        )
        bt._resolve_trade(trade, candles)
        assert trade.exit_reason == "sl"
        assert trade.pnl_pct < 0

    def test_short_hits_tp(self):
        candles = [
            {"date": "2026-01-01", "o": 100, "h": 101, "l": 99, "c": 100, "v": 100},
            {"date": "2026-01-02", "o": 100, "h": 100.5, "l": 95, "c": 95.5, "v": 100},
        ]
        trade = bt.Trade(
            entry_index=0, entry_date="2026-01-01",
            entry_price=100, direction="short",
            stop_loss=103, take_profit=96,
        )
        bt._resolve_trade(trade, candles)
        assert trade.exit_reason == "tp"
        assert trade.pnl_pct > 0

    def test_end_of_data_exit(self):
        candles = [
            {"date": "2026-01-01", "o": 100, "h": 101, "l": 99, "c": 100.5, "v": 100},
            {"date": "2026-01-02", "o": 100.5, "h": 101.5, "l": 100, "c": 101, "v": 100},
        ]
        trade = bt.Trade(
            entry_index=0, entry_date="2026-01-01",
            entry_price=100.5, direction="long",
            stop_loss=90, take_profit=120,  # neither hit
        )
        bt._resolve_trade(trade, candles)
        assert trade.exit_reason == "end_of_data"
        assert trade.exit_price == 101  # last candle close

    def test_r_multiple_calculated(self):
        candles = [
            {"date": "2026-01-01", "o": 100, "h": 101, "l": 99, "c": 100, "v": 100},
            {"date": "2026-01-02", "o": 100, "h": 106, "l": 99.5, "c": 105, "v": 100},
        ]
        trade = bt.Trade(
            entry_index=0, entry_date="2026-01-01",
            entry_price=100, direction="long",
            stop_loss=98, take_profit=104,  # 2R target
        )
        bt._resolve_trade(trade, candles)
        assert trade.r_multiple > 0


# ---------------------------------------------------------------------------
# Performance metrics
# ---------------------------------------------------------------------------

class TestMetrics:
    def test_empty_trades(self):
        m = bt.calculate_metrics([])
        assert m["total_trades"] == 0
        assert m["win_rate"] == 0

    def test_all_winners(self):
        trades = [
            bt.Trade(0, "d1", 100, "long", 95, 110, 1, "d2", 110, "tp", 0.1, 2.0, 1),
            bt.Trade(2, "d3", 100, "long", 95, 110, 3, "d4", 110, "tp", 0.1, 2.0, 1),
        ]
        m = bt.calculate_metrics(trades)
        assert m["win_rate"] == 100
        assert m["winning_trades"] == 2
        assert m["losing_trades"] == 0
        assert m["profit_factor"] == 999  # no losses

    def test_mixed_results(self):
        trades = [
            bt.Trade(0, "d1", 100, "long", 95, 110, 1, "d2", 110, "tp", 0.1, 2.0, 1),  # win
            bt.Trade(2, "d3", 100, "long", 95, 110, 3, "d4", 95, "sl", -0.05, -1.0, 1),  # loss
        ]
        m = bt.calculate_metrics(trades)
        assert m["total_trades"] == 2
        assert m["winning_trades"] == 1
        assert m["losing_trades"] == 1
        assert m["win_rate"] == 50
        assert m["profit_factor"] > 0

    def test_max_drawdown(self):
        trades = [
            bt.Trade(0, "d", 100, "long", 95, 110, 1, "d", 95, "sl", -0.05, -1.0, 1),
            bt.Trade(2, "d", 100, "long", 95, 110, 3, "d", 95, "sl", -0.05, -1.0, 1),
        ]
        m = bt.calculate_metrics(trades)
        assert m["max_drawdown_pct"] > 0

    def test_sharpe_ratio_type(self):
        trades = [
            bt.Trade(0, "d", 100, "long", 95, 110, 1, "d", 110, "tp", 0.1, 2.0, 1),
            bt.Trade(2, "d", 100, "long", 95, 110, 3, "d", 95, "sl", -0.05, -1.0, 1),
            bt.Trade(4, "d", 100, "long", 95, 110, 5, "d", 108, "tp", 0.08, 1.6, 1),
        ]
        m = bt.calculate_metrics(trades)
        assert isinstance(m["sharpe_ratio"], float)

    def test_expectancy(self):
        trades = [
            bt.Trade(0, "d", 100, "long", 95, 110, 1, "d", 110, "tp", 0.10, 2.0, 1),
            bt.Trade(2, "d", 100, "long", 95, 110, 3, "d", 95, "sl", -0.05, -1.0, 1),
        ]
        m = bt.calculate_metrics(trades)
        # Expectancy = (win_rate * avg_win) - ((1-win_rate) * avg_loss)
        expected = (0.5 * 0.10) - (0.5 * 0.05)
        assert abs(m["expectancy"] - expected) < 0.001


# ---------------------------------------------------------------------------
# Strategy execution
# ---------------------------------------------------------------------------

class TestStrategies:
    def test_ob_fvg_runs_without_error(self):
        candles = _volatile_candles(80)
        analysis = smc.analyze(candles, symbol="TEST")
        trades = bt.strategy_ob_fvg(candles, analysis)
        assert isinstance(trades, list)

    def test_liquidity_sweep_runs_without_error(self):
        candles = _volatile_candles(80)
        analysis = smc.analyze(candles, symbol="TEST")
        trades = bt.strategy_liquidity_sweep(candles, analysis)
        assert isinstance(trades, list)

    def test_strategies_dict_complete(self):
        for sid, info in bt.STRATEGIES.items():
            assert "name" in info
            assert "runner" in info
            assert callable(info["runner"])
            assert "description" in info


# ---------------------------------------------------------------------------
# Full backtest
# ---------------------------------------------------------------------------

class TestFullBacktest:
    def test_run_backtest_ob_fvg(self):
        candles = _volatile_candles(80)
        result = bt.run_backtest(candles, "ob_fvg", "TEST", "3M")
        assert result.symbol == "TEST"
        assert result.strategy == "ob_fvg"
        assert result.candle_count == 80
        assert isinstance(result.trades, list)

    def test_run_backtest_liquidity_sweep(self):
        candles = _volatile_candles(80)
        result = bt.run_backtest(candles, "liquidity_sweep", "TEST", "3M")
        assert result.strategy == "liquidity_sweep"

    def test_unknown_strategy_raises(self):
        candles = _volatile_candles(20)
        with pytest.raises(ValueError, match="Unknown strategy"):
            bt.run_backtest(candles, "nonexistent", "TEST")

    def test_result_summary(self):
        candles = _volatile_candles(80)
        result = bt.run_backtest(candles, "ob_fvg", "TEST", "3M")
        s = result.summary()
        required_keys = [
            "symbol", "strategy", "range", "candles", "trades",
            "win_rate", "profit_factor", "max_drawdown", "sharpe",
            "expectancy", "total_return", "avg_r",
        ]
        for key in required_keys:
            assert key in s, f"Missing key: {key}"

    def test_result_serializable(self):
        candles = _volatile_candles(80)
        result = bt.run_backtest(candles, "ob_fvg", "TEST", "3M")
        d = result.to_dict()
        json.dumps(d, default=str)


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

class TestReportGeneration:
    def test_save_report(self, tmp_path, monkeypatch):
        monkeypatch.setattr(bt, "OUTPUT_DIR", tmp_path / "backtests")
        candles = _volatile_candles(80)
        result = bt.run_backtest(candles, "ob_fvg", "TEST", "3M")
        path = bt.save_report(result)
        assert os.path.exists(path)
        assert path.endswith(".md")
        # JSON should also exist
        json_path = path.replace(".md", ".json")
        assert os.path.exists(json_path)
