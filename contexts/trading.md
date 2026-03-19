# Trading Context

## Relevant Files
- scripts/smc_ict_analyzer.py -- SMC/ICT pattern detection
- scripts/backtest_engine.py -- Strategy backtesting
- scripts/market_data.py -- OHLCV data fetching
- site/foundation/trading_room.html -- Trading Room UI
- site/foundation/markets_terminal.html -- Markets terminal
- dashboard_api.py -- /api/analysis/* and /api/backtest/* endpoints
- tests/test_smc_ict_analyzer.py -- Analyzer tests
- tests/test_backtest_engine.py -- Backtest tests

## Key Concepts
- SMC/ICT: Order Blocks, Fair Value Gaps, Break of Structure, Change of Character
- Strategies: ob_fvg (OB+FVG confluence), liquidity_sweep (sweep reversal)
- Chart overlays render on canvas with priceToY/indexToX coordinate helpers
- Market data from EODHD API via /api/markets/ohlcv endpoint

## Testing
python3 -m pytest tests/test_smc_ict_analyzer.py tests/test_backtest_engine.py -v
