from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from quotex_mtf_signal_bot.backtest.engine import run_backtest
from quotex_mtf_signal_bot.backtest.export import write_dashboard_json
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


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the research backtest pipeline")
    parser.add_argument("csv", type=Path, help="Historical candle CSV")
    parser.add_argument("--timeframe", choices=["M1", "M5", "M15"], default="M1")
    parser.add_argument("--output", type=Path, default=Path("data/backtest.json"))
    args = parser.parse_args()

    candles = load_candles(args.csv, Timeframe[args.timeframe])
    # Signal generation will be wired here once the historical replay/signal loop is added.
    report = run_backtest([], candles)
    output = write_dashboard_json(report, args.output)
    print(f"Exported {report.total} evaluated signals to {output}")


if __name__ == "__main__":
    main()
