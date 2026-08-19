from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pandas as pd

from quotex_mtf_signal_bot.core.models import Candle, Tick, Timeframe


_MT5_TIMEFRAME_NAMES = {
    Timeframe.M1: "TIMEFRAME_M1",
    Timeframe.M5: "TIMEFRAME_M5",
    Timeframe.M15: "TIMEFRAME_M15",
}


class MT5DataSource:
    """Thin MT5 adapter; strategy code stays independent of MetaTrader5."""

    def __init__(self, mt5_module: Any) -> None:
        self._mt5 = mt5_module

    def connect(self, **kwargs: Any) -> bool:
        return bool(self._mt5.initialize(**kwargs))

    def shutdown(self) -> None:
        self._mt5.shutdown()

    def tick(self, symbol: str) -> Tick:
        """Read the latest broker tick with millisecond precision when MT5 exposes it."""
        raw = self._mt5.symbol_info_tick(symbol)
        if raw is None:
            raise RuntimeError(f"No tick available for {symbol}")

        if hasattr(raw, "time_msc"):
            timestamp = datetime.fromtimestamp(int(raw.time_msc) / 1000, tz=timezone.utc)
        else:
            timestamp = datetime.fromtimestamp(int(raw.time), tz=timezone.utc)

        return Tick(
            symbol=symbol,
            timestamp_utc=timestamp,
            bid=float(raw.bid),
            ask=float(raw.ask),
        )

    def server_tick_time(self, symbol: str) -> datetime:
        return self.tick(symbol).timestamp_utc

    def candles(self, symbol: str, timeframe: Timeframe, count: int = 500) -> list[Candle]:
        mt5_tf = getattr(self._mt5, _MT5_TIMEFRAME_NAMES[timeframe])
        rows = self._mt5.copy_rates_from_pos(symbol, mt5_tf, 0, count)
        if rows is None:
            raise RuntimeError(f"MT5 returned no rates for {symbol} {timeframe}")

        frame = pd.DataFrame(rows)
        required = {"time", "open", "high", "low", "close", "tick_volume"}
        missing = required.difference(frame.columns)
        if missing:
            raise RuntimeError(f"MT5 rates missing columns: {sorted(missing)}")

        return [
            Candle(
                symbol=symbol,
                timeframe=timeframe,
                timestamp_utc=datetime.fromtimestamp(int(row.time), tz=timezone.utc),
                open=float(row.open),
                high=float(row.high),
                low=float(row.low),
                close=float(row.close),
                tick_volume=int(row.tick_volume),
            )
            for row in frame.itertuples(index=False)
        ]
