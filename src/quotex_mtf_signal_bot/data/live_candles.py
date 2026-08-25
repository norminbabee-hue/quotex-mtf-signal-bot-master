from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from quotex_mtf_signal_bot.data.candle_builder import CandleBuilder, LiveCandle
from quotex_mtf_signal_bot.data.mt5_adapter import MT5Bar, MarketDataAdapter, Tick


@dataclass(frozen=True, slots=True)
class CandleCloseEvent:
    candle: LiveCandle


class LiveCandleManager:
    """Maintain synchronized M1/M5/M15 candles from one MT5 tick stream."""

    TIMEFRAMES = {"M15": 900, "M5": 300, "M1": 60}
    MIN_HISTORY_BARS = 60

    def __init__(
        self,
        adapter: MarketDataAdapter,
        symbol: str,
        *,
        server_offset_seconds: int | float = 6 * 60 * 60,
    ) -> None:
        self.adapter = adapter
        self.symbol = symbol
        self.server_offset_seconds = server_offset_seconds
        self.builders = {
            name: CandleBuilder(seconds, server_offset_seconds=server_offset_seconds)
            for name, seconds in self.TIMEFRAMES.items()
        }
        self.last_tick_time_utc: datetime | None = None

    def on_tick(self, tick: Tick) -> list[CandleCloseEvent]:
        if tick.symbol != self.symbol:
            return []
        if self.last_tick_time_utc and tick.timestamp_utc < self.last_tick_time_utc:
            raise ValueError("MT5 ticks must be processed in chronological order")
        self.last_tick_time_utc = tick.timestamp_utc
        closed: list[CandleCloseEvent] = []
        for builder in self.builders.values():
            completed = builder.update(tick)
            if completed is not None:
                closed.append(CandleCloseEvent(completed))
        return closed

    def seed_history(self, count: int = 100) -> dict[str, list[MT5Bar]]:
        """Load recent MT5 history, accepting shorter feeds when they still meet the live minimum.

        Some broker symbols do not return the requested number of bars even though
        they have enough history for the MTF model. The model needs 60 completed
        candles per timeframe, so a response such as 114 M1 bars is usable and
        should not abort the entire multi-pair scanner.
        """
        history: dict[str, list[MT5Bar]] = {}
        request_count = max(self.MIN_HISTORY_BARS, int(count))
        for timeframe in ("M1", "M5", "M15"):
            bars = self.adapter.bars(self.symbol, timeframe, request_count)
            if len(bars) < self.MIN_HISTORY_BARS:
                raise RuntimeError(
                    f"Insufficient MT5 {timeframe} history: minimum {self.MIN_HISTORY_BARS}, got {len(bars)}"
                )
            history[timeframe] = bars
        return history
