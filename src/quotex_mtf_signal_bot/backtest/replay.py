from __future__ import annotations

from collections import defaultdict
from datetime import datetime

from quotex_mtf_signal_bot.analysis.mtf import analyze_mtf
from quotex_mtf_signal_bot.core.models import Candle, Timeframe
from quotex_mtf_signal_bot.signals.model import Signal, build_signal


DEFAULT_WINDOWS = {
    Timeframe.M1: 60,
    Timeframe.M5: 60,
    Timeframe.M15: 60,
}


def _closed_before(candles: list[Candle], timestamp: datetime) -> list[Candle]:
    return [c for c in candles if c.timestamp_utc < timestamp]


def generate_signals(
    candles_by_timeframe: dict[Timeframe, list[Candle]],
    *,
    symbol: str,
    min_history: dict[Timeframe, int] | None = None,
) -> list[Signal]:
    """Replay closed candles and generate signals without using future candles."""
    history = {**DEFAULT_WINDOWS, **(min_history or {})}
    entry_candles = sorted(candles_by_timeframe.get(Timeframe.M1, []), key=lambda c: c.timestamp_utc)
    signals: list[Signal] = []

    for entry in entry_candles:
        snapshot: dict[Timeframe, list[Candle]] = {}
        ready = True
        for timeframe in (Timeframe.M1, Timeframe.M5, Timeframe.M15):
            closed = _closed_before(candles_by_timeframe.get(timeframe, []), entry.timestamp_utc)
            if len(closed) < history[timeframe]:
                ready = False
                break
            snapshot[timeframe] = closed[-history[timeframe]:]
        if not ready:
            continue

        analysis = analyze_mtf(snapshot)
        signal = build_signal(symbol, entry.timestamp_utc, analysis)
        if signal is not None:
            signals.append(signal)

    return signals
