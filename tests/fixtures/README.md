# Backtest fixtures

Test fixtures should use the canonical candle CSV schema:

`timestamp_utc,symbol,open,high,low,close`

Use deterministic synthetic candles for automated tests. Do not treat fixture data as real market performance evidence.
