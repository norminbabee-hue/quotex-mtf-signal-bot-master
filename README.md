# Quotex MTF Signal Bot

Fresh, research-first V1 for multi-timeframe Forex binary-options signals using MetaTrader 5 (MT5) as the analysis feed and Telegram as the delivery channel.

## V1 scope

- Major Forex pairs
- M1 + M5 + M15 multi-timeframe analysis
- EMA + RSI + MACD
- Support / Resistance
- Price Action
- Market-condition-aware expiry selection
- English Telegram signals: Pair + CALL/PUT + expiry + confidence
- Backtesting engine and dashboard foundation
- PC / VPS deployment

## Non-negotiable engineering rules

1. MT5 is an analysis feed; never assume it is identical to the target Quotex feed.
2. Validate broker/server time, candle boundaries, OHLC, tick timing and feed alignment before live signalling.
3. A forming candle must never leak future information into historical backtests.
4. Live and backtest paths must share the same signal decision logic.
5. Confidence is a model score, not a guaranteed win probability.
6. V1 sends signals only; it does not place real-money trades automatically.
7. Secrets never belong in Git. Use environment variables / secret storage.
8. Keep the repository minimal and intentional. No random files or duplicated logic.

## Repository layout

```text
config/       Strategy and runtime configuration
src/          Application code
  data/       MT5 market-data and clock alignment
  analysis/   Indicators, price action, S/R and MTF scoring
  signals/    Signal and expiry decisions
  telegram/   Telegram delivery
  backtest/   Historical simulation
  dashboard/ Backtesting UI
  core/       Shared domain models and interfaces
tests/        Automated tests
scripts/      Small operational entry points
```

## Project status

**Phase 0 — initialized.** Next: implement and test the MT5 data/time synchronization layer before adding live signal generation.

## Safety note

Binary options are highly risky. This project is for research, analysis and controlled backtesting. Historical performance does not guarantee future results.
