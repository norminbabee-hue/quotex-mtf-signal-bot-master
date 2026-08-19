from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from quotex_mtf_signal_bot.backtest.engine import run_backtest
from quotex_mtf_signal_bot.backtest.export import write_dashboard_json
from quotex_mtf_signal_bot.backtest.replay import generate_signals
from quotex_mtf_signal_bot.core.models import Candle, Timeframe


def load_candles(path: Path, timeframe: Timeframe) -> list[Candle]:
    candles: list[Candle] = []
    with path.open("r", newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            timestamp = datetime.fromisoformat(row["timestamp_utc"].replace("Z", "+00:00"))
            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=timezone.utc)
            candles.append(Candle(
                symbol=row["symbol"],
                timeframe=timeframe,
                timestamp_utc=timestamp,
                open=Decimal(row["open"]),
                high=Decimal(row["high"]),
                low=Decimal(row["low"]),
                close=Decimal(row["close"]),
            ))
    return sorted(candles, key=lambda candle: candle.timestamp_utc)


def load_multi_timeframe(csv_paths: dict[Timeframe, Path]) -> dict[Timeframe, list[Candle]]:
    return {timeframe: load_candles(path, timeframe) for timeframe, path in csv_paths.items()}


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the look-ahead-safe research backtest pipeline")
    parser.add_argument("--m1", type=Path, required=True, help="Historical M1 candle CSV")
    parser.add_argument("--m5", type=Path, required=True, help="Historical M5 candle CSV")
    parser.add_argument("--m15", type=Path, required=True, help="Historical M15 candle CSV")
    parser.add_argument("--output", type=Path, default=Path("data/backtest.json"))
    args = parser.parse_args()

    candles = load_multi_timeframe({
        Timeframe.M1: args.m1,
        Timeframe.M5: args.m5,
        Timeframe.M15: args.m15,
    })
    symbols = {c.symbol for values in candles.values() for c in values}
    if len(symbols) != 1:
        raise ValueError("M1, M5 and M15 files must contain the same single symbol")
    symbol = next(iter(symbols))

    signals = generate_signals(candles, symbol=symbol)
    # Evaluate expiry on the M1 stream so exit timing is checked at the finest available granularity.
    report = run_backtest(signals, candles[Timeframe.M1])
    output = write_dashboard_json(report, args.output)
    print(f"Generated {len(signals)} signals; evaluated {report.total} signals; exported to {output}")


if __name__ == "__main__":
    main()
