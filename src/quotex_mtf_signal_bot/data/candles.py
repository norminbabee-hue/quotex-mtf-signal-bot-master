from __future__ import annotations

from datetime import timedelta

from quotex_mtf_signal_bot.core.models import Candle, Timeframe


_SECONDS = {
    Timeframe.M1: 60,
    Timeframe.M5: 300,
    Timeframe.M15: 900,
}


def validate_closed_candle_sequence(candles: list[Candle], timeframe: Timeframe) -> None:
    """Reject gaps, duplicates and out-of-order bars in a historical sequence."""
    if not candles:
        return

    expected = timedelta(seconds=_SECONDS[timeframe])
    previous = candles[0].timestamp_utc
    for candle in candles[1:]:
        delta = candle.timestamp_utc - previous
        if delta != expected:
            raise ValueError(
                f"Invalid {timeframe} candle sequence: expected {expected}, got {delta}"
            )
        previous = candle.timestamp_utc


def drop_forming_candle(candles: list[Candle], now_utc) -> list[Candle]:
    """Return bars whose opening time is strictly before the current time.

    This is a conservative boundary check; live code must additionally verify
    the broker feed's candle-close state before using the last bar for a signal.
    """
    return [c for c in candles if c.timestamp_utc < now_utc]
