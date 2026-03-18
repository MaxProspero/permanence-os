#!/usr/bin/env python3
"""
PERMANENCE OS -- SMC/ICT Technical Analyzer

Smart Money Concepts (SMC) and Inner Circle Trader (ICT) pattern detection
on OHLCV candle data. Pure technical analysis -- no trade execution.

Patterns detected:
  - Swing highs / swing lows (structure mapping)
  - Break of Structure (BOS) / Change of Character (CHOCH)
  - Order blocks (bullish + bearish, with mitigation tracking)
  - Fair Value Gaps (FVGs) -- imbalance zones
  - Liquidity levels (equal highs/lows, swing pools)
  - Displacement candles (momentum candles)

All functions operate on lists of candle dicts:
  {"date": str, "o": float, "h": float, "l": float, "c": float, "v": float}

Usage:
  python scripts/smc_ict_analyzer.py --symbol AAPL.US --range 3M
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

BASE_DIR = Path(__file__).resolve().parents[1]

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class SwingPoint:
    """A swing high or swing low in price structure."""
    index: int
    date: str
    price: float
    swing_type: str  # "high" or "low"
    strength: int = 1  # how many candles on each side confirm it


@dataclass
class StructureBreak:
    """Break of Structure (BOS) or Change of Character (CHOCH)."""
    index: int
    date: str
    break_type: str  # "bos" or "choch"
    direction: str   # "bullish" or "bearish"
    broken_level: float
    candle_close: float


@dataclass
class OrderBlock:
    """An order block zone (last opposing candle before displacement)."""
    index: int
    date: str
    ob_type: str     # "bullish" or "bearish"
    high: float
    low: float
    mitigated: bool = False
    mitigation_index: Optional[int] = None


@dataclass
class FairValueGap:
    """An imbalance / Fair Value Gap between three candles."""
    index: int       # middle candle index
    date: str
    fvg_type: str    # "bullish" or "bearish"
    upper: float     # top of gap
    lower: float     # bottom of gap
    filled: bool = False
    fill_index: Optional[int] = None


@dataclass
class LiquidityLevel:
    """A liquidity pool (equal highs/lows or swing cluster)."""
    price: float
    level_type: str  # "buy_side" (above price) or "sell_side" (below price)
    touch_count: int
    indices: list[int] = field(default_factory=list)
    swept: bool = False
    sweep_index: Optional[int] = None


@dataclass
class AnalysisResult:
    """Complete SMC/ICT analysis output."""
    symbol: str
    candle_count: int
    swing_highs: list[SwingPoint]
    swing_lows: list[SwingPoint]
    structure_breaks: list[StructureBreak]
    order_blocks: list[OrderBlock]
    fair_value_gaps: list[FairValueGap]
    liquidity_levels: list[LiquidityLevel]
    trend: str  # "bullish", "bearish", "ranging"
    displacement_indices: list[int]
    analyzed_at: str = ""

    def __post_init__(self):
        if not self.analyzed_at:
            self.analyzed_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict:
        return asdict(self)

    def summary(self) -> dict:
        """Condensed summary for dashboard display."""
        return {
            "symbol": self.symbol,
            "trend": self.trend,
            "candles": self.candle_count,
            "swing_highs": len(self.swing_highs),
            "swing_lows": len(self.swing_lows),
            "bos_count": sum(1 for s in self.structure_breaks if s.break_type == "bos"),
            "choch_count": sum(1 for s in self.structure_breaks if s.break_type == "choch"),
            "order_blocks": len(self.order_blocks),
            "active_obs": sum(1 for ob in self.order_blocks if not ob.mitigated),
            "fvgs": len(self.fair_value_gaps),
            "unfilled_fvgs": sum(1 for f in self.fair_value_gaps if not f.filled),
            "liquidity_levels": len(self.liquidity_levels),
            "unswept_levels": sum(1 for ll in self.liquidity_levels if not ll.swept),
            "displacements": len(self.displacement_indices),
            "analyzed_at": self.analyzed_at,
        }


# ---------------------------------------------------------------------------
# Swing detection
# ---------------------------------------------------------------------------

def detect_swings(candles: list[dict], lookback: int = 3) -> tuple[list[SwingPoint], list[SwingPoint]]:
    """
    Detect swing highs and swing lows using N-bar lookback.

    A swing high: candle[i].high > all highs in [i-lookback, i+lookback].
    A swing low:  candle[i].low  < all lows  in [i-lookback, i+lookback].
    """
    highs: list[SwingPoint] = []
    lows: list[SwingPoint] = []
    n = len(candles)

    for i in range(lookback, n - lookback):
        h = candles[i]["h"]
        l = candles[i]["l"]

        is_high = all(h >= candles[j]["h"] for j in range(i - lookback, i + lookback + 1) if j != i)
        is_low = all(l <= candles[j]["l"] for j in range(i - lookback, i + lookback + 1) if j != i)

        if is_high:
            highs.append(SwingPoint(
                index=i, date=candles[i]["date"], price=h,
                swing_type="high", strength=lookback,
            ))
        if is_low:
            lows.append(SwingPoint(
                index=i, date=candles[i]["date"], price=l,
                swing_type="low", strength=lookback,
            ))

    return highs, lows


# ---------------------------------------------------------------------------
# Structure breaks (BOS / CHOCH)
# ---------------------------------------------------------------------------

def detect_structure_breaks(
    candles: list[dict],
    swing_highs: list[SwingPoint],
    swing_lows: list[SwingPoint],
) -> tuple[list[StructureBreak], str]:
    """
    Detect BOS and CHOCH from swing structure.

    BOS: price breaks a swing point in the same direction as existing trend.
    CHOCH: price breaks a swing point against the current trend (reversal signal).

    Returns (breaks, current_trend).
    """
    breaks: list[StructureBreak] = []
    trend = "ranging"

    # Merge and sort all swings by index
    all_swings = sorted(swing_highs + swing_lows, key=lambda s: s.index)
    if len(all_swings) < 3:
        return breaks, trend

    # Track last major swing high and low
    last_sh: Optional[SwingPoint] = None
    last_sl: Optional[SwingPoint] = None

    for swing in all_swings:
        if swing.swing_type == "high":
            if last_sh is not None:
                # Check if a candle after this swing broke the previous swing high
                for j in range(swing.index, min(swing.index + 10, len(candles))):
                    if candles[j]["c"] > last_sh.price:
                        # Break above previous swing high
                        if trend == "bullish":
                            bt = "bos"
                        else:
                            bt = "choch"
                        breaks.append(StructureBreak(
                            index=j, date=candles[j]["date"],
                            break_type=bt, direction="bullish",
                            broken_level=last_sh.price,
                            candle_close=candles[j]["c"],
                        ))
                        trend = "bullish"
                        break
            last_sh = swing

        elif swing.swing_type == "low":
            if last_sl is not None:
                for j in range(swing.index, min(swing.index + 10, len(candles))):
                    if candles[j]["c"] < last_sl.price:
                        if trend == "bearish":
                            bt = "bos"
                        else:
                            bt = "choch"
                        breaks.append(StructureBreak(
                            index=j, date=candles[j]["date"],
                            break_type=bt, direction="bearish",
                            broken_level=last_sl.price,
                            candle_close=candles[j]["c"],
                        ))
                        trend = "bearish"
                        break
            last_sl = swing

    return breaks, trend


# ---------------------------------------------------------------------------
# Order blocks
# ---------------------------------------------------------------------------

def detect_order_blocks(
    candles: list[dict],
    displacement_threshold: float = 0.015,
) -> list[OrderBlock]:
    """
    Detect order blocks: last opposing candle before a displacement move.

    Bullish OB: bearish candle followed by strong bullish displacement.
    Bearish OB: bullish candle followed by strong bearish displacement.
    """
    obs: list[OrderBlock] = []
    n = len(candles)

    for i in range(1, n - 1):
        c_prev = candles[i - 1]
        c_curr = candles[i]

        prev_body = c_prev["c"] - c_prev["o"]
        curr_body = c_curr["c"] - c_curr["o"]
        curr_range = c_curr["h"] - c_curr["l"]

        if curr_range == 0:
            continue

        body_ratio = abs(curr_body) / curr_range

        # Displacement: large body candle (body > 60% of range) with significant move
        is_displacement = (
            body_ratio > 0.6
            and abs(curr_body) / max(c_prev["c"], 0.01) > displacement_threshold
        )

        if not is_displacement:
            continue

        # Bullish displacement after bearish candle = bullish OB
        if curr_body > 0 and prev_body < 0:
            obs.append(OrderBlock(
                index=i - 1, date=c_prev["date"], ob_type="bullish",
                high=c_prev["h"], low=c_prev["l"],
            ))

        # Bearish displacement after bullish candle = bearish OB
        elif curr_body < 0 and prev_body > 0:
            obs.append(OrderBlock(
                index=i - 1, date=c_prev["date"], ob_type="bearish",
                high=c_prev["h"], low=c_prev["l"],
            ))

    # Check mitigation (price returns to OB zone)
    for ob in obs:
        for j in range(ob.index + 2, n):
            if ob.ob_type == "bullish" and candles[j]["l"] <= ob.high:
                ob.mitigated = True
                ob.mitigation_index = j
                break
            elif ob.ob_type == "bearish" and candles[j]["h"] >= ob.low:
                ob.mitigated = True
                ob.mitigation_index = j
                break

    return obs


# ---------------------------------------------------------------------------
# Fair Value Gaps
# ---------------------------------------------------------------------------

def detect_fvgs(candles: list[dict], min_gap_pct: float = 0.002) -> list[FairValueGap]:
    """
    Detect Fair Value Gaps (imbalances) in three-candle sequences.

    Bullish FVG: candle[i+1].low > candle[i-1].high (gap up, no overlap).
    Bearish FVG: candle[i+1].high < candle[i-1].low (gap down, no overlap).
    """
    fvgs: list[FairValueGap] = []
    n = len(candles)

    for i in range(1, n - 1):
        c_before = candles[i - 1]
        c_mid = candles[i]
        c_after = candles[i + 1]

        # Bullish FVG: gap between candle before's high and candle after's low
        if c_after["l"] > c_before["h"]:
            gap_size = c_after["l"] - c_before["h"]
            mid_price = (c_after["l"] + c_before["h"]) / 2
            if mid_price > 0 and gap_size / mid_price >= min_gap_pct:
                fvgs.append(FairValueGap(
                    index=i, date=c_mid["date"], fvg_type="bullish",
                    upper=c_after["l"], lower=c_before["h"],
                ))

        # Bearish FVG: gap between candle before's low and candle after's high
        if c_after["h"] < c_before["l"]:
            gap_size = c_before["l"] - c_after["h"]
            mid_price = (c_before["l"] + c_after["h"]) / 2
            if mid_price > 0 and gap_size / mid_price >= min_gap_pct:
                fvgs.append(FairValueGap(
                    index=i, date=c_mid["date"], fvg_type="bearish",
                    upper=c_before["l"], lower=c_after["h"],
                ))

    # Check fill status
    for fvg in fvgs:
        for j in range(fvg.index + 2, n):
            if fvg.fvg_type == "bullish" and candles[j]["l"] <= fvg.lower:
                fvg.filled = True
                fvg.fill_index = j
                break
            elif fvg.fvg_type == "bearish" and candles[j]["h"] >= fvg.upper:
                fvg.filled = True
                fvg.fill_index = j
                break

    return fvgs


# ---------------------------------------------------------------------------
# Liquidity levels
# ---------------------------------------------------------------------------

def detect_liquidity_levels(
    swing_highs: list[SwingPoint],
    swing_lows: list[SwingPoint],
    candles: list[dict],
    tolerance_pct: float = 0.003,
) -> list[LiquidityLevel]:
    """
    Detect liquidity pools from clusters of equal highs/lows.

    Equal highs = buy-side liquidity (stops above).
    Equal lows  = sell-side liquidity (stops below).
    """
    levels: list[LiquidityLevel] = []

    # Cluster swing highs (buy-side liquidity)
    _cluster_swings(swing_highs, candles, "buy_side", tolerance_pct, levels)
    # Cluster swing lows (sell-side liquidity)
    _cluster_swings(swing_lows, candles, "sell_side", tolerance_pct, levels)

    return levels


def _cluster_swings(
    swings: list[SwingPoint],
    candles: list[dict],
    level_type: str,
    tolerance_pct: float,
    levels: list[LiquidityLevel],
) -> None:
    """Group nearby swing points into liquidity levels."""
    used = set()
    for i, s1 in enumerate(swings):
        if i in used:
            continue
        cluster = [s1]
        used.add(i)
        for j, s2 in enumerate(swings):
            if j in used:
                continue
            if s1.price > 0 and abs(s1.price - s2.price) / s1.price <= tolerance_pct:
                cluster.append(s2)
                used.add(j)

        if len(cluster) >= 2:
            avg_price = sum(s.price for s in cluster) / len(cluster)
            indices = [s.index for s in cluster]

            # Check if swept
            swept = False
            sweep_idx = None
            max_idx = max(indices)
            for k in range(max_idx + 1, len(candles)):
                if level_type == "buy_side" and candles[k]["h"] > avg_price:
                    swept = True
                    sweep_idx = k
                    break
                elif level_type == "sell_side" and candles[k]["l"] < avg_price:
                    swept = True
                    sweep_idx = k
                    break

            levels.append(LiquidityLevel(
                price=round(avg_price, 4),
                level_type=level_type,
                touch_count=len(cluster),
                indices=indices,
                swept=swept,
                sweep_index=sweep_idx,
            ))


# ---------------------------------------------------------------------------
# Displacement detection
# ---------------------------------------------------------------------------

def detect_displacements(
    candles: list[dict],
    threshold: float = 0.02,
) -> list[int]:
    """
    Find displacement candles: large body moves indicating institutional activity.

    Returns indices of displacement candles.
    """
    indices = []
    for i, c in enumerate(candles):
        body = abs(c["c"] - c["o"])
        if c["c"] == 0:
            continue
        move_pct = body / c["c"]
        rng = c["h"] - c["l"]
        body_ratio = body / rng if rng > 0 else 0

        if move_pct >= threshold and body_ratio > 0.6:
            indices.append(i)

    return indices


# ---------------------------------------------------------------------------
# Full analysis
# ---------------------------------------------------------------------------

def analyze(
    candles: list[dict],
    symbol: str = "UNKNOWN",
    swing_lookback: int = 3,
    displacement_threshold: float = 0.015,
    fvg_min_gap_pct: float = 0.002,
    liquidity_tolerance_pct: float = 0.003,
) -> AnalysisResult:
    """
    Run full SMC/ICT analysis on OHLCV candle data.

    Returns AnalysisResult with all detected patterns.
    """
    if len(candles) < swing_lookback * 2 + 1:
        return AnalysisResult(
            symbol=symbol, candle_count=len(candles),
            swing_highs=[], swing_lows=[],
            structure_breaks=[], order_blocks=[],
            fair_value_gaps=[], liquidity_levels=[],
            trend="insufficient_data", displacement_indices=[],
        )

    swing_highs, swing_lows = detect_swings(candles, swing_lookback)
    structure_breaks, trend = detect_structure_breaks(candles, swing_highs, swing_lows)
    order_blocks = detect_order_blocks(candles, displacement_threshold)
    fvgs = detect_fvgs(candles, fvg_min_gap_pct)
    liquidity = detect_liquidity_levels(swing_highs, swing_lows, candles, liquidity_tolerance_pct)
    displacements = detect_displacements(candles, displacement_threshold)

    return AnalysisResult(
        symbol=symbol,
        candle_count=len(candles),
        swing_highs=swing_highs,
        swing_lows=swing_lows,
        structure_breaks=structure_breaks,
        order_blocks=order_blocks,
        fair_value_gaps=fvgs,
        liquidity_levels=liquidity,
        trend=trend,
        displacement_indices=displacements,
    )


# ---------------------------------------------------------------------------
# Integration: fetch + analyze
# ---------------------------------------------------------------------------

def analyze_symbol(
    symbol: str,
    range_key: str = "3M",
) -> AnalysisResult:
    """
    Fetch OHLCV data from market_data_service and run analysis.
    """
    sys.path.insert(0, str(BASE_DIR / "scripts"))
    try:
        import market_data_service as mds
    except ImportError as exc:
        raise ImportError("market_data_service required for live analysis") from exc

    candles = mds.get_ohlcv(symbol, range_key)
    if not candles:
        return AnalysisResult(
            symbol=symbol, candle_count=0,
            swing_highs=[], swing_lows=[],
            structure_breaks=[], order_blocks=[],
            fair_value_gaps=[], liquidity_levels=[],
            trend="no_data", displacement_indices=[],
        )

    return analyze(candles, symbol=symbol)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SMC/ICT Technical Analyzer")
    parser.add_argument("--symbol", default="AAPL.US")
    parser.add_argument("--range", default="3M", dest="range_key")
    parser.add_argument("--json", action="store_true", help="Output full JSON")
    args = parser.parse_args()

    result = analyze_symbol(args.symbol, args.range_key)
    s = result.summary()

    if args.json:
        print(json.dumps(result.to_dict(), indent=2, default=str))
    else:
        print(f"SMC/ICT Analysis: {s['symbol']}")
        print(f"  Candles: {s['candles']} | Trend: {s['trend']}")
        print(f"  Swing Highs: {s['swing_highs']} | Swing Lows: {s['swing_lows']}")
        print(f"  BOS: {s['bos_count']} | CHOCH: {s['choch_count']}")
        print(f"  Order Blocks: {s['order_blocks']} (active: {s['active_obs']})")
        print(f"  FVGs: {s['fvgs']} (unfilled: {s['unfilled_fvgs']})")
        print(f"  Liquidity: {s['liquidity_levels']} (unswept: {s['unswept_levels']})")
        print(f"  Displacements: {s['displacements']}")
