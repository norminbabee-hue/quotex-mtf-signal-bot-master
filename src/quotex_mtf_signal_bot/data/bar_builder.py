from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from quotex_mtf_signal_bot.core.models import Candle, Tick, Timeframe
from quotex_mtf_signal_bot.data.candle_timing import (
    DEFAULT_QUOTEX_SERVER_OFFSET_SECONDS,
    candle_boundary_utc,
)


MINUTES = {Timeframe.M1: 1, Timeframe.M5: 5, Timeframe.M15: 15}


@dataclass(slots=True)
class MutableBar:
    symbol: str
    timeframe: Timeframe
    start_utc: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    tick_count: int = 1

    def update(self, price: Decimal) -> None:
        self.high = max(self.high, price)
        self.low = min(self.low, price)
        self.close = price
        self.tick_count += 1

    def closed(self) -> Candle:
        return Candle(
            symbol=self.symbol,
            timeframe=self.timeframe,
            timestamp_utc=self.start_utc,
            open=self.open,
            high=self.high,
            low=self.low,
            close=self.close,
            tick_volume=self.tick_count,
        )


class TickBarBuilder:
    """Build M1/M5/M15 bars using the configured Quotex server boundaries."""

    def __init__(self, *, server_offset_seconds: int | float = DEFAULT_QUOTEX_SERVER_OFFSET_SECONDS) -> None:
        self._active: dict[tuple[str, Timeframe], MutableBar] = {}
        self.server_offset_seconds = server_offset_seconds

    def bucket_start(self, timestamp_utc: datetime, timeframe: Timeframe) -> datetime:
        if timestamp_utc.tzinfo is None:
            raise ValueError("Tick timestamp must be timezone-aware")
        return candle_boundary_utc(
            timestamp_utc,
            MINUTES[timeframe] * 60,
            server_offset_seconds=self.server_offset_seconds,
        )

    def update(self, tick: Tick) -> list[Candle]:
        if tick.timestamp_utc.tzinfo is None:
            raise ValueError("Tick timestamp must be timezone-aware")
        price = (tick.bid + tick.ask) / Decimal("2")
        closed: list[Candle] = []

        for timeframe in MINUTES:
            key = (tick.symbol, timeframe)
            start = self.bucket_start(tick.timestamp_utc, timeframe)
            current = self._active.get(key)

            if current is None:
                self._active[key] = MutableBar(
                    tick.symbol, timeframe, start, price, price, price, price
                )
                continue

            if start < current.start_utc:
                raise ValueError("Out-of-order tick received")

            if start != current.start_utc:
                closed.append(current.closed())
                self._active[key] = MutableBar(
                    tick.symbol, timeframe, start, price, price, price, price
                )
            else:
                current.update(price)

        return closed

    def flush(self, now_utc: datetime) -> list[Candle]:
        """Close bars only after their full server-clock interval has elapsed."""
        if now_utc.tzinfo is None:
            raise ValueError("Flush time must be timezone-aware")
        result: list[Candle] = []
        now = now_utc.astimezone(timezone.utc)
        for key, bar in list(self._active.items()):
            end = bar.start_utc + timedelta(minutes=MINUTES[bar.timeframe])
            if now >= end:
                result.append(bar.closed())
                del self._active[key]
        return result
