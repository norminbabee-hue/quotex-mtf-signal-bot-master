from __future__ import annotations

from collections import deque
from datetime import datetime, timezone

from quotex_mtf_signal_bot.analysis.mtf import analyze_mtf
from quotex_mtf_signal_bot.core.models import Candle, Timeframe
from quotex_mtf_signal_bot.data.candle_builder import LiveCandle
from quotex_mtf_signal_bot.signals.model import Signal, build_signal


class LiveMTFSignalService:
    """Turn completed M1/M5/M15 candles into live signals.

    Only completed candles are added to analysis history. A signal is evaluated
    at the close of an M1 candle using the latest closed M5 and M15 candles.
    """

    def __init__(self, symbol: str, history_size: int = 200) -> None:
        self.symbol = symbol
        self.history: dict[Timeframe, deque[Candle]] = {
            Timeframe.M1: deque(maxlen=history_size),
            Timeframe.M5: deque(maxlen=history_size),
            Timeframe.M15: deque(maxlen=history_size),
        }

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
        if any(not self.history[tf] for tf in required):
            return None

        snapshot = {tf: list(self.history[tf]) for tf in required}
        analysis = analyze_mtf(snapshot)
        entry_time = live.close_time_utc.astimezone(timezone.utc)
        return build_signal(self.symbol, entry_time, analysis)
