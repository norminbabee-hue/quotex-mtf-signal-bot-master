from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from quotex_mtf_signal_bot.data.mt5_adapter import Tick


@dataclass(frozen=True, slots=True)
class LiveCandle:
    symbol: str
    timeframe_seconds: int
    open_time_utc: datetime
    close_time_utc: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    tick_count: int


class CandleBuilder:
    """Build candles from timestamped ticks using UTC epoch boundaries."""

    def __init__(self, timeframe_seconds: int) -> None:
        if timeframe_seconds <= 0:
            raise ValueError("timeframe_seconds must be positive")
        self.timeframe_seconds = timeframe_seconds
        self._current: LiveCandle | None = None

    def _boundary(self, timestamp: datetime) -> datetime:
        ts = timestamp.astimezone(timezone.utc)
        epoch = int(ts.timestamp())
        start = epoch - (epoch % self.timeframe_seconds)
        return datetime.fromtimestamp(start, tz=timezone.utc)

    def update(self, tick: Tick) -> LiveCandle | None:
        if tick.timestamp_utc.tzinfo is None:
            raise ValueError("Tick timestamp must be timezone-aware")
        timestamp = tick.timestamp_utc.astimezone(timezone.utc)
        price = (tick.bid + tick.ask) / Decimal("2")
        start = self._boundary(timestamp)
        close_time = start + timedelta(seconds=self.timeframe_seconds)

        if self._current is None:
            self._current = LiveCandle(tick.symbol, self.timeframe_seconds, start, close_time,
                                       price, price, price, price, 1)
            return None

        if start < self._current.open_time_utc:
            raise ValueError("Ticks must arrive in chronological order")

        if start == self._current.open_time_utc:
            current = self._current
            self._current = LiveCandle(current.symbol, current.timeframe_seconds,
                                       current.open_time_utc, current.close_time_utc,
                                       current.open, max(current.high, price),
                                       min(current.low, price), price, current.tick_count + 1)
            return None

        completed = self._current
        self._current = LiveCandle(tick.symbol, self.timeframe_seconds, start, close_time,
                                   price, price, price, price, 1)
        return completed

    @property
    def current(self) -> LiveCandle | None:
        return self._current
