from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from quotex_mtf_signal_bot.data.candle_builder import CandleBuilder, LiveCandle
from quotex_mtf_signal_bot.data.mt5_adapter import MarketDataAdapter, Tick


@dataclass(frozen=True, slots=True)
class CandleCloseEvent:
    candle: LiveCandle


class LiveCandleManager:
    """Maintain synchronized M1/M5/M15 candles from one MT5 tick stream."""

    TIMEFRAMES = {"M1": 60, "M5": 300, "M15": 900}

    def __init__(self, adapter: MarketDataAdapter, symbol: str) -> None:
        self.adapter = adapter
        self.symbol = symbol
        self.builders = {name: CandleBuilder(seconds) for name, seconds in self.TIMEFRAMES.items()}
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

    def seed_history(self, count: int = 100) -> None:
        """Validate that MT5 can provide history before live processing starts."""
        for timeframe in self.TIMEFRAMES:
            bars = self.adapter.bars(self.symbol, timeframe, count)
            if len(bars) < count:
                raise RuntimeError(f"Insufficient MT5 {timeframe} history: expected {count}, got {len(bars)}")
