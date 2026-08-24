from __future__ import annotations

from collections import deque
from datetime import datetime, timezone

from quotex_mtf_signal_bot.analysis.mtf import analyze_mtf
from quotex_mtf_signal_bot.core.models import Candle, Timeframe
from quotex_mtf_signal_bot.data.candle_builder import LiveCandle
from quotex_mtf_signal_bot.data.mt5_adapter import MT5Bar
from quotex_mtf_signal_bot.data.symbol_registry import SymbolRegistry
from quotex_mtf_signal_bot.signals.model import Signal, build_signal


class LiveMTFSignalService:
    """Turn completed M1/M5/M15 candles into live signals for one FX pair."""

    def __init__(self, symbol: str, history_size: int = 200) -> None:
        self.symbol = SymbolRegistry.canonical_symbol(symbol) or symbol
        self.history: dict[Timeframe, deque[Candle]] = {
            Timeframe.M1: deque(maxlen=history_size),
            Timeframe.M5: deque(maxlen=history_size),
            Timeframe.M15: deque(maxlen=history_size),
        }
        self._last_signal_entry_time: dict[Timeframe, datetime | None] = {
            Timeframe.M1: None,
            Timeframe.M5: None,
            Timeframe.M15: None,
        }

    @staticmethod
    def _timeframe(seconds: int) -> Timeframe:
        mapping = {60: Timeframe.M1, 300: Timeframe.M5, 900: Timeframe.M15}
        try:
            return mapping[seconds]
        except KeyError as exc:
            raise ValueError(f"Unsupported live timeframe: {seconds}s") from exc

    def _to_candle(self, live: LiveCandle) -> Candle:
        return Candle(
            symbol=self.symbol,
            timeframe=self._timeframe(live.timeframe_seconds),
            timestamp_utc=live.open_time_utc,
            open=live.open,
            high=live.high,
            low=live.low,
            close=live.close,
        )

    def _history_bar_to_candle(self, bar: MT5Bar) -> Candle:
        return Candle(
            symbol=self.symbol,
            timeframe=self._timeframe({"M1": 60, "M5": 300, "M15": 900}[bar.timeframe]),
            timestamp_utc=bar.timestamp_utc,
            open=bar.open,
            high=bar.high,
            low=bar.low,
            close=bar.close,
        )

    def seed_history(self, history: dict[str, list[MT5Bar]]) -> None:
        """Seed completed broker history; discard the current forming bar."""
        for label, bars in history.items():
            timeframe = self._timeframe({"M1": 60, "M5": 300, "M15": 900}[label])
            completed = sorted(bars, key=lambda bar: bar.timestamp_utc)
            if len(completed) > 1:
                completed = completed[:-1]
            self.history[timeframe].clear()
            for bar in completed:
                self.history[timeframe].append(self._history_bar_to_candle(bar))

    def on_closed_candle(self, live: LiveCandle) -> list[Signal]:
        """Return predictions for every requested timeframe whose boundary just closed.

        M1 closes every minute, M5 every five minutes, and M15 every fifteen minutes.
        At a shared boundary LiveCandleManager emits M15 -> M5 -> M1, so the
        M1 prediction sees the newly completed higher-timeframe candles.
        """
        if SymbolRegistry.canonical_symbol(live.symbol) != self.symbol:
            return []
        timeframe = self._timeframe(live.timeframe_seconds)
        candle = self._to_candle(live)
        self.history[timeframe].append(candle)

        required = (Timeframe.M1, Timeframe.M5, Timeframe.M15)
        if any(len(self.history[tf]) < 60 for tf in required):
            return []

        snapshot = {tf: list(self.history[tf]) for tf in required}
        analysis = analyze_mtf(snapshot)
        entry_time = live.close_time_utc.astimezone(timezone.utc)
        signal = build_signal(self.symbol, entry_time, analysis, target_timeframe=timeframe)
        if signal is None:
            return []
        if self._last_signal_entry_time[timeframe] == entry_time:
            return []
        self._last_signal_entry_time[timeframe] = entry_time
        return [signal]
