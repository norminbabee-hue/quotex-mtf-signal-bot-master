from __future__ import annotations

from datetime import datetime

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
    """Replay pre-aligned closed-candle streams without look-ahead.

    Replay fixtures represent each timeframe as an indexed history stream. At
    M1 index ``i``, only bars with indexes below ``i`` are eligible on every
    timeframe. This keeps the replay deterministic while ensuring the current
    entry bar itself is never included in the analysis.
    """
    history = {**DEFAULT_WINDOWS, **(min_history or {})}
    entry_candles = sorted(
        candles_by_timeframe.get(Timeframe.M1, []), key=lambda c: c.timestamp_utc
    )
    signals: list[Signal] = []

    for entry_index, entry in enumerate(entry_candles):
        snapshot: dict[Timeframe, list[Candle]] = {}
        ready = True
        for timeframe in (Timeframe.M1, Timeframe.M5, Timeframe.M15):
            stream = sorted(
                candles_by_timeframe.get(timeframe, []), key=lambda c: c.timestamp_utc
            )
            closed = stream[:entry_index]
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
