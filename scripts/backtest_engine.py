#!/usr/bin/env python3
"""
PERMANENCE OS -- Backtest Engine

Runs trading strategies against historical OHLCV data and calculates
performance metrics. Integrates with smc_ict_analyzer.py for pattern
detection and market_data_service.py for data.

Governance:
  - Paper-only. No real execution.
  - All results logged with full trade history.
  - Manual approval required before paper trading.

Metrics calculated:
  - Win rate, profit factor, max drawdown
  - Sharpe ratio, average R:R, expectancy
  - Trade count, holding period stats

Usage:
  python scripts/backtest_engine.py --symbol AAPL.US --range 6M --strategy ob_fvg
  python scripts/backtest_engine.py --symbol SPY.US --range 1Y --strategy liquidity_sweep
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

BASE_DIR = Path(__file__).resolve().parents[1]
OUTPUT_DIR = BASE_DIR / "outputs" / "backtests"
LOG_DIR = BASE_DIR / "logs"

sys.path.insert(0, str(BASE_DIR / "scripts"))

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class Trade:
    """A single backtest trade."""
    entry_index: int
    entry_date: str
    entry_price: float
    direction: str       # "long" or "short"
    stop_loss: float
    take_profit: float
    exit_index: Optional[int] = None
    exit_date: Optional[str] = None
    exit_price: Optional[float] = None
    exit_reason: str = ""  # "tp", "sl", "end_of_data"
    pnl_pct: float = 0.0
    r_multiple: float = 0.0
    holding_bars: int = 0


@dataclass
class BacktestResult:
    """Complete backtest output."""
    symbol: str
    strategy: str
    range_key: str
    candle_count: int
    trades: list[Trade]
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0
    avg_win_pct: float = 0.0
    avg_loss_pct: float = 0.0
    profit_factor: float = 0.0
    max_drawdown_pct: float = 0.0
    sharpe_ratio: float = 0.0
    avg_r_multiple: float = 0.0
    expectancy: float = 0.0
    avg_holding_bars: float = 0.0
    total_return_pct: float = 0.0
    analyzed_at: str = ""

    def __post_init__(self):
        if not self.analyzed_at:
            self.analyzed_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict:
        return asdict(self)

    def summary(self) -> dict:
        return {
            "symbol": self.symbol,
            "strategy": self.strategy,
            "range": self.range_key,
            "candles": self.candle_count,
            "trades": self.total_trades,
            "win_rate": round(self.win_rate, 2),
            "profit_factor": round(self.profit_factor, 2),
            "max_drawdown": round(self.max_drawdown_pct, 2),
            "sharpe": round(self.sharpe_ratio, 2),
            "expectancy": round(self.expectancy, 4),
            "total_return": round(self.total_return_pct, 2),
            "avg_r": round(self.avg_r_multiple, 2),
        }


# ---------------------------------------------------------------------------
# Strategy: Order Block + FVG confluence
# ---------------------------------------------------------------------------

def strategy_ob_fvg(
    candles: list[dict],
    analysis,
    risk_pct: float = 0.01,
    rr_target: float = 2.0,
) -> list[Trade]:
    """
    Enter at unmitigated order blocks that align with unfilled FVGs.

    Long: bullish OB + bullish FVG in same zone + bullish trend.
    Short: bearish OB + bearish FVG in same zone + bearish trend.
    """
    trades: list[Trade] = []
    in_trade = False
    n = len(candles)

    # Get active (unmitigated) OBs
    active_obs = [ob for ob in analysis.order_blocks if not ob.mitigated]
    # Get unfilled FVGs
    active_fvgs = [fvg for fvg in analysis.fair_value_gaps if not fvg.filled]

    for ob in active_obs:
        if in_trade:
            continue

        # Find FVG in same zone (overlapping price range)
        aligned_fvg = None
        for fvg in active_fvgs:
            if fvg.fvg_type == ob.ob_type:
                # Check overlap
                if fvg.lower <= ob.high and fvg.upper >= ob.low:
                    aligned_fvg = fvg
                    break

        if not aligned_fvg:
            continue

        # Look for price returning to zone after OB formation
        for j in range(ob.index + 2, min(ob.index + 30, n)):
            c = candles[j]

            if ob.ob_type == "bullish" and analysis.trend == "bullish":
                if c["l"] <= ob.high and c["c"] > ob.low:
                    entry = c["c"]
                    stop = ob.low * 0.998  # small buffer below OB
                    risk = entry - stop
                    if risk <= 0:
                        continue
                    tp = entry + (risk * rr_target)
                    trades.append(Trade(
                        entry_index=j, entry_date=c["date"],
                        entry_price=entry, direction="long",
                        stop_loss=stop, take_profit=tp,
                    ))
                    in_trade = True
                    break

            elif ob.ob_type == "bearish" and analysis.trend == "bearish":
                if c["h"] >= ob.low and c["c"] < ob.high:
                    entry = c["c"]
                    stop = ob.high * 1.002
                    risk = stop - entry
                    if risk <= 0:
                        continue
                    tp = entry - (risk * rr_target)
                    trades.append(Trade(
                        entry_index=j, entry_date=c["date"],
                        entry_price=entry, direction="short",
                        stop_loss=stop, take_profit=tp,
                    ))
                    in_trade = True
                    break

        # Resolve open trade
        if in_trade and trades:
            trade = trades[-1]
            resolved = _resolve_trade(trade, candles)
            if resolved:
                in_trade = False

    return trades


# ---------------------------------------------------------------------------
# Strategy: Liquidity sweep reversal
# ---------------------------------------------------------------------------

def strategy_liquidity_sweep(
    candles: list[dict],
    analysis,
    rr_target: float = 3.0,
) -> list[Trade]:
    """
    Enter after liquidity sweep + displacement candle.

    Look for swept liquidity levels followed by a displacement
    candle in the opposite direction (reversal).
    """
    trades: list[Trade] = []
    in_trade = False
    n = len(candles)
    displacements = set(analysis.displacement_indices)

    for ll in analysis.liquidity_levels:
        if not ll.swept or ll.sweep_index is None:
            continue
        if in_trade:
            continue

        sweep_idx = ll.sweep_index

        # Look for displacement candle within 5 bars of sweep
        for j in range(sweep_idx, min(sweep_idx + 5, n)):
            if j not in displacements:
                continue

            c = candles[j]
            body = c["c"] - c["o"]

            if ll.level_type == "buy_side" and body < 0:
                # Swept buy-side, bearish displacement = short
                entry = c["c"]
                stop = candles[sweep_idx]["h"] * 1.002
                risk = stop - entry
                if risk <= 0:
                    continue
                tp = entry - (risk * rr_target)
                trades.append(Trade(
                    entry_index=j, entry_date=c["date"],
                    entry_price=entry, direction="short",
                    stop_loss=stop, take_profit=tp,
                ))
                in_trade = True
                break

            elif ll.level_type == "sell_side" and body > 0:
                # Swept sell-side, bullish displacement = long
                entry = c["c"]
                stop = candles[sweep_idx]["l"] * 0.998
                risk = entry - stop
                if risk <= 0:
                    continue
                tp = entry + (risk * rr_target)
                trades.append(Trade(
                    entry_index=j, entry_date=c["date"],
                    entry_price=entry, direction="long",
                    stop_loss=stop, take_profit=tp,
                ))
                in_trade = True
                break

        if in_trade and trades:
            trade = trades[-1]
            resolved = _resolve_trade(trade, candles)
            if resolved:
                in_trade = False

    return trades


# ---------------------------------------------------------------------------
# Trade resolution
# ---------------------------------------------------------------------------

def _resolve_trade(trade: Trade, candles: list[dict]) -> bool:
    """
    Walk forward from entry to find exit via TP, SL, or end of data.

    Mutates trade in place. Returns True if trade was resolved.
    """
    n = len(candles)
    for j in range(trade.entry_index + 1, n):
        c = candles[j]

        if trade.direction == "long":
            # Check stop loss first (conservative)
            if c["l"] <= trade.stop_loss:
                trade.exit_index = j
                trade.exit_date = c["date"]
                trade.exit_price = trade.stop_loss
                trade.exit_reason = "sl"
                break
            if c["h"] >= trade.take_profit:
                trade.exit_index = j
                trade.exit_date = c["date"]
                trade.exit_price = trade.take_profit
                trade.exit_reason = "tp"
                break

        elif trade.direction == "short":
            if c["h"] >= trade.stop_loss:
                trade.exit_index = j
                trade.exit_date = c["date"]
                trade.exit_price = trade.stop_loss
                trade.exit_reason = "sl"
                break
            if c["l"] <= trade.take_profit:
                trade.exit_index = j
                trade.exit_date = c["date"]
                trade.exit_price = trade.take_profit
                trade.exit_reason = "tp"
                break
    else:
        # End of data -- close at last price
        last = candles[-1]
        trade.exit_index = n - 1
        trade.exit_date = last["date"]
        trade.exit_price = last["c"]
        trade.exit_reason = "end_of_data"

    # Calculate P&L
    if trade.exit_price is not None and trade.entry_price > 0:
        if trade.direction == "long":
            trade.pnl_pct = (trade.exit_price - trade.entry_price) / trade.entry_price
            risk = trade.entry_price - trade.stop_loss
        else:
            trade.pnl_pct = (trade.entry_price - trade.exit_price) / trade.entry_price
            risk = trade.stop_loss - trade.entry_price

        trade.r_multiple = (trade.pnl_pct * trade.entry_price) / risk if risk > 0 else 0
        trade.holding_bars = (trade.exit_index or 0) - trade.entry_index

    return trade.exit_price is not None


# ---------------------------------------------------------------------------
# Performance calculation
# ---------------------------------------------------------------------------

def calculate_metrics(trades: list[Trade]) -> dict:
    """Calculate backtest performance metrics from trade list."""
    if not trades:
        return {
            "total_trades": 0, "winning_trades": 0, "losing_trades": 0,
            "win_rate": 0, "avg_win_pct": 0, "avg_loss_pct": 0,
            "profit_factor": 0, "max_drawdown_pct": 0, "sharpe_ratio": 0,
            "avg_r_multiple": 0, "expectancy": 0, "avg_holding_bars": 0,
            "total_return_pct": 0,
        }

    resolved = [t for t in trades if t.exit_price is not None]
    if not resolved:
        return calculate_metrics([])  # empty result

    total = len(resolved)
    winners = [t for t in resolved if t.pnl_pct > 0]
    losers = [t for t in resolved if t.pnl_pct <= 0]

    win_rate = len(winners) / total if total > 0 else 0
    avg_win = sum(t.pnl_pct for t in winners) / len(winners) if winners else 0
    avg_loss = sum(abs(t.pnl_pct) for t in losers) / len(losers) if losers else 0

    gross_profit = sum(t.pnl_pct for t in winners)
    gross_loss = sum(abs(t.pnl_pct) for t in losers)
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else (999 if gross_profit > 0 else 0)

    # Max drawdown (equity curve)
    equity = 1.0
    peak = 1.0
    max_dd = 0.0
    returns = []
    for t in resolved:
        equity *= (1 + t.pnl_pct)
        returns.append(t.pnl_pct)
        if equity > peak:
            peak = equity
        dd = (peak - equity) / peak if peak > 0 else 0
        if dd > max_dd:
            max_dd = dd

    # Sharpe ratio (annualized, assuming ~252 trading days)
    if len(returns) >= 2:
        mean_r = sum(returns) / len(returns)
        var_r = sum((r - mean_r) ** 2 for r in returns) / (len(returns) - 1)
        std_r = math.sqrt(var_r) if var_r > 0 else 0.0001
        sharpe = (mean_r / std_r) * math.sqrt(252) if std_r > 0 else 0
    else:
        sharpe = 0

    avg_r = sum(t.r_multiple for t in resolved) / total if total > 0 else 0
    avg_holding = sum(t.holding_bars for t in resolved) / total if total > 0 else 0
    total_return = (equity - 1) * 100
    expectancy = (win_rate * avg_win) - ((1 - win_rate) * avg_loss)

    return {
        "total_trades": total,
        "winning_trades": len(winners),
        "losing_trades": len(losers),
        "win_rate": win_rate * 100,
        "avg_win_pct": avg_win * 100,
        "avg_loss_pct": avg_loss * 100,
        "profit_factor": profit_factor,
        "max_drawdown_pct": max_dd * 100,
        "sharpe_ratio": sharpe,
        "avg_r_multiple": avg_r,
        "expectancy": expectancy,
        "avg_holding_bars": avg_holding,
        "total_return_pct": total_return,
    }


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------

STRATEGIES = {
    "ob_fvg": {
        "name": "Order Block + FVG Confluence",
        "runner": strategy_ob_fvg,
        "description": "Enter at unmitigated order blocks aligned with unfilled FVGs",
    },
    "liquidity_sweep": {
        "name": "Liquidity Sweep Reversal",
        "runner": strategy_liquidity_sweep,
        "description": "Enter after liquidity sweep + displacement reversal",
    },
}


def run_backtest(
    candles: list[dict],
    strategy_id: str = "ob_fvg",
    symbol: str = "UNKNOWN",
    range_key: str = "3M",
    **kwargs,
) -> BacktestResult:
    """
    Run a full backtest: analyze -> generate trades -> calculate metrics.
    """
    import smc_ict_analyzer as smc

    if strategy_id not in STRATEGIES:
        raise ValueError(f"Unknown strategy: {strategy_id}. Available: {list(STRATEGIES.keys())}")

    analysis = smc.analyze(candles, symbol=symbol)
    strategy_fn = STRATEGIES[strategy_id]["runner"]
    trades = strategy_fn(candles, analysis, **kwargs)
    metrics = calculate_metrics(trades)

    result = BacktestResult(
        symbol=symbol,
        strategy=strategy_id,
        range_key=range_key,
        candle_count=len(candles),
        trades=trades,
        **metrics,
    )

    return result


def run_backtest_live(
    symbol: str,
    range_key: str = "6M",
    strategy_id: str = "ob_fvg",
) -> BacktestResult:
    """
    Fetch live data and run backtest.
    """
    import market_data_service as mds

    candles = mds.get_ohlcv(symbol, range_key)
    if not candles:
        return BacktestResult(
            symbol=symbol, strategy=strategy_id, range_key=range_key,
            candle_count=0, trades=[],
        )

    return run_backtest(candles, strategy_id, symbol, range_key)


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def save_report(result: BacktestResult) -> str:
    """Save backtest results to outputs/backtests/."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"backtest_{result.symbol}_{result.strategy}_{ts}"

    # JSON
    json_path = OUTPUT_DIR / f"{filename}.json"
    with open(json_path, "w") as f:
        json.dump(result.to_dict(), f, indent=2, default=str)

    # Markdown report
    md_path = OUTPUT_DIR / f"{filename}.md"
    s = result.summary()
    lines = [
        f"# Backtest Report: {result.symbol}",
        f"**Strategy**: {STRATEGIES.get(result.strategy, {}).get('name', result.strategy)}",
        f"**Range**: {result.range_key} ({result.candle_count} candles)",
        f"**Date**: {result.analyzed_at}",
        "",
        "## Performance",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Trades | {s['trades']} |",
        f"| Win Rate | {s['win_rate']}% |",
        f"| Profit Factor | {s['profit_factor']} |",
        f"| Total Return | {s['total_return']}% |",
        f"| Max Drawdown | {s['max_drawdown']}% |",
        f"| Sharpe Ratio | {s['sharpe']} |",
        f"| Avg R:R | {s['avg_r']} |",
        f"| Expectancy | {s['expectancy']} |",
        "",
        "## Trade Log",
    ]

    for i, t in enumerate(result.trades):
        lines.append(
            f"| {i+1} | {t.direction} | {t.entry_date} | {t.entry_price:.2f} | "
            f"{t.exit_price:.2f if t.exit_price else 'open'} | {t.exit_reason} | "
            f"{t.pnl_pct*100:.2f}% | {t.r_multiple:.1f}R |"
        )

    lines.append("")
    lines.append("---")
    lines.append("*Paper trading only. No real execution. Manual approval required.*")

    with open(md_path, "w") as f:
        f.write("\n".join(lines))

    return str(md_path)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Permanence OS Backtest Engine")
    parser.add_argument("--symbol", default="SPY.US")
    parser.add_argument("--range", default="6M", dest="range_key")
    parser.add_argument("--strategy", default="ob_fvg", choices=list(STRATEGIES.keys()))
    parser.add_argument("--save", action="store_true", help="Save report to outputs/")
    parser.add_argument("--json", action="store_true", help="Output full JSON")
    args = parser.parse_args()

    print(f"Running backtest: {args.symbol} | {args.strategy} | {args.range_key}")
    result = run_backtest_live(args.symbol, args.range_key, args.strategy)
    s = result.summary()

    if args.json:
        print(json.dumps(result.to_dict(), indent=2, default=str))
    else:
        print(f"\n  Trades: {s['trades']}")
        print(f"  Win Rate: {s['win_rate']}%")
        print(f"  Profit Factor: {s['profit_factor']}")
        print(f"  Total Return: {s['total_return']}%")
        print(f"  Max Drawdown: {s['max_drawdown']}%")
        print(f"  Sharpe: {s['sharpe']}")
        print(f"  Avg R: {s['avg_r']}")
        print(f"  Expectancy: {s['expectancy']}")

    if args.save:
        path = save_report(result)
        print(f"\n  Report saved: {path}")
