from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from quotex_mtf_signal_bot.core.models import Candle, Timeframe


_TIMEFRAME_MINUTES = {
    Timeframe.M1: 1,
    Timeframe.M5: 5,
    Timeframe.M15: 15,
}


@dataclass(frozen=True, slots=True)
class SynchronizedCandles:
    """Latest completed candles aligned to one decision timestamp."""

    decision_time_utc: datetime
    candles: dict[Timeframe, Candle]


def candle_open_time(timestamp_utc: datetime, timeframe: Timeframe) -> datetime:
    """Normalize a candle timestamp to the UTC boundary for its timeframe."""
    if timestamp_utc.tzinfo is None:
        raise ValueError("Candle timestamp must be timezone-aware")
    ts = timestamp_utc.astimezone(timezone.utc)
    minutes = _TIMEFRAME_MINUTES[timeframe]
    bucket = (ts.minute // minutes) * minutes
    return ts.replace(minute=bucket, second=0, microsecond=0)


def is_completed(candle: Candle, now_utc: datetime) -> bool:
    if now_utc.tzinfo is None:
        raise ValueError("Decision time must be timezone-aware")
    start = candle_open_time(candle.timestamp_utc, candle.timeframe)
    end = start + timedelta(minutes=_TIMEFRAME_MINUTES[candle.timeframe])
    return now_utc.astimezone(timezone.utc) >= end


def validate_sequence(candles: list[Candle]) -> None:
    """Reject duplicate, out-of-order, or gapped candle streams."""
    if not candles:
        return
    ordered = sorted(candles, key=lambda item: item.timestamp_utc)
    if ordered != candles:
        raise ValueError("Candle sequence is not ordered by timestamp")

    step = timedelta(minutes=_TIMEFRAME_MINUTES[candles[0].timeframe])
    for previous, current in zip(candles, candles[1:]):
        delta = current.timestamp_utc - previous.timestamp_utc
        if delta != step:
            raise ValueError(
                f"Invalid {candles[0].timeframe} sequence: expected {step}, got {delta}"
            )


def synchronize_completed(
    candles_by_timeframe: dict[Timeframe, list[Candle]],
    now_utc: datetime,
) -> SynchronizedCandles:
    """Return one completed M1/M5/M15 candle set sharing the same decision boundary.

    The newest candle in each timeframe is ignored when it is still forming.
    A common decision boundary is required so higher-timeframe candles cannot
    leak information from a period that has not closed yet.
    """
    if now_utc.tzinfo is None:
        raise ValueError("Decision time must be timezone-aware")

    completed: dict[Timeframe, list[Candle]] = {}
    for timeframe, candles in candles_by_timeframe.items():
        validate_sequence(candles)
        usable = [c for c in candles if is_completed(c, now_utc)]
        if not usable:
            raise ValueError(f"No completed {timeframe} candle is available")
        completed[timeframe] = usable

    latest_boundary = min(
        candle_open_time(items[-1].timestamp_utc, timeframe)
        + timedelta(minutes=_TIMEFRAME_MINUTES[timeframe])
        for timeframe, items in completed.items()
    )

    selected: dict[Timeframe, Candle] = {}
    for timeframe, items in completed.items():
        candidates = [
            candle
            for candle in items
            if candle_open_time(candle.timestamp_utc, timeframe)
            + timedelta(minutes=_TIMEFRAME_MINUTES[timeframe])
            <= latest_boundary
        ]
        if not candidates:
            raise ValueError(f"No aligned {timeframe} candle is available")
        selected[timeframe] = candidates[-1]

    return SynchronizedCandles(latest_boundary, selected)
