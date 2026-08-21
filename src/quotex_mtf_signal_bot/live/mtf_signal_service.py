from __future__ import annotations

from collections import deque
from datetime import datetime, timezone

from quotex_mtf_signal_bot.analysis.mtf import analyze_mtf
from quotex_mtf_signal_bot.core.models import Candle, Timeframe
from quotex_mtf_signal_bot.data.candle_builder import LiveCandle
from quotex_mtf_signal_bot.data.mt5_adapter import MT5Bar
from quotex_mtf_signal_bot.signals.model import Signal, build_signal


class LiveMTFSignalService:
    """Turn completed M1/M5/M15 candles into live signals.

    The service can be seeded with broker history before ticks start. This is
    important for a multi-pair scanner: every pair gets a real M1/M5/M15
    context immediately instead of waiting through 15 minutes of empty state.
    """

    def __init__(self, symbol: str, history_size: int = 200) -> None:
        self.symbol = symbol
        self.history: dict[Timeframe, deque[Candle]] = {
            Timeframe.M1: deque(maxlen=history_size),
            Timeframe.M5: deque(maxlen=history_size),
            Timeframe.M15: deque(maxlen=history_size),
        }
        self._last_signal_entry_time: datetime | None = None

    @staticmethod
    def _timeframe(seconds: int) -> Timeframe:
        mapping = {60: Timeframe.M1, 300: Timeframe.M5, 900: Timeframe.M15}
        try:
            return mapping[seconds]
        except KeyError as exc:
            raise ValueError(f"Unsupported live timeframe: {seconds}s") from exc

    @staticmethod
    def _to_candle(live: LiveCandle) -> Candle:
        return Candle(
            symbol=live.symbol,
            timeframe=LiveMTFSignalService._timeframe(live.timeframe_seconds),
            timestamp_utc=live.open_time_utc,
            open=live.open,
            high=live.high,
            low=live.low,
            close=live.close,
        )

    @staticmethod
    def _history_bar_to_candle(bar: MT5Bar) -> Candle:
        return Candle(
            symbol=bar.symbol,
            timeframe=LiveMTFSignalService._timeframe(
                {"M1": 60, "M5": 300, "M15": 900}[bar.timeframe]
            ),
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
            # copy_rates_from_pos includes the current bar at the end on normal
            # MT5 feeds. Keep only bars that are already closed by taking all but
            # the newest bar; if a fixture is already closed, the extra bar is
            # harmless because the live stream replaces it at the next close.
            if len(completed) > 1:
                completed = completed[:-1]
            self.history[timeframe].clear()
            for bar in completed:
                self.history[timeframe].append(self._history_bar_to_candle(bar))

    def on_closed_candle(self, live: LiveCandle) -> Signal | None:
        if live.symbol != self.symbol:
            return None
        timeframe = self._timeframe(live.timeframe_seconds)
        candle = self._to_candle(live)
        self.history[timeframe].append(candle)

        # Signals are evaluated only on M1 close. This prevents three signals
        # from being generated for the same market moment.
        if timeframe is not Timeframe.M1:
            return None

        required = (Timeframe.M1, Timeframe.M5, Timeframe.M15)
        if any(len(self.history[tf]) < 60 for tf in required):
            return None

        snapshot = {tf: list(self.history[tf]) for tf in required}
        analysis = analyze_mtf(snapshot)
        entry_time = live.close_time_utc.astimezone(timezone.utc)
        if self._last_signal_entry_time == entry_time:
            return None
        signal = build_signal(self.symbol, entry_time, analysis)
        if signal is not None:
            self._last_signal_entry_time = entry_time
        return signal
