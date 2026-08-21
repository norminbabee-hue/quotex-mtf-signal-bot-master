from __future__ import annotations

from bisect import bisect_left

from quotex_mtf_signal_bot.analysis.mtf import analyze_mtf
from quotex_mtf_signal_bot.core.models import Candle, Timeframe
from quotex_mtf_signal_bot.signals.model import Signal, build_signal


DEFAULT_WINDOWS = {
    Timeframe.M1: 60,
    Timeframe.M5: 60,
    Timeframe.M15: 60,
}


def generate_signals(
    candles_by_timeframe: dict[Timeframe, list[Candle]],
    *,
    symbol: str,
    min_history: dict[Timeframe, int] | None = None,
) -> list[Signal]:
    """Replay closed-candle streams using timestamp alignment, with no look-ahead.

    A common MTF replay bug is to use the M1 array index to slice M5/M15
    arrays. That leaks future higher-timeframe candles into earlier M1 entries
    because one M15 candle spans fifteen M1 candles. We therefore align every
    timeframe by the entry timestamp and only use candles whose timestamps are
    strictly earlier than the entry candle.
    """
    history = {**DEFAULT_WINDOWS, **(min_history or {})}
    streams = {
        timeframe: sorted(
            candles_by_timeframe.get(timeframe, []), key=lambda candle: candle.timestamp_utc
        )
        for timeframe in (Timeframe.M1, Timeframe.M5, Timeframe.M15)
    }
    timestamps = {
        timeframe: [candle.timestamp_utc for candle in stream]
        for timeframe, stream in streams.items()
    }

    entry_candles = streams[Timeframe.M1]
    signals: list[Signal] = []

    for entry in entry_candles:
        snapshot: dict[Timeframe, list[Candle]] = {}
        ready = True
        for timeframe, stream in streams.items():
            # bisect_left excludes a candle at exactly the entry timestamp.
            closed_end = bisect_left(timestamps[timeframe], entry.timestamp_utc)
            closed = stream[:closed_end]
            if len(closed) < history[timeframe]:
                ready = False
                break
            snapshot[timeframe] = closed[-history[timeframe] :]

        if not ready:
            continue

        analysis = analyze_mtf(snapshot)
        signal = build_signal(symbol, entry.timestamp_utc, analysis)
        if signal is not None:
            signals.append(signal)

    return signals
