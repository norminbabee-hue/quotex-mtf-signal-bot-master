from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone, tzinfo


@dataclass(frozen=True, slots=True)
class CandleWindow:
    """A target candle window expressed in UTC and a display timezone."""

    timeframe_seconds: int
    open_time_utc: datetime
    close_time_utc: datetime
    seconds_to_open: int


def timeframe_seconds(label: str) -> int:
    mapping = {"M1": 60, "M5": 300, "M15": 900}
    try:
        return mapping[label.upper()]
    except KeyError as exc:
        raise ValueError(f"Unsupported candle timeframe: {label}") from exc


def next_candle_window(now_utc: datetime, timeframe_seconds_value: int) -> CandleWindow:
    """Return the candle that opens at the next timeframe boundary."""
    if now_utc.tzinfo is None:
        raise ValueError("now_utc must be timezone-aware")
    if timeframe_seconds_value <= 0:
        raise ValueError("timeframe_seconds must be positive")

    now = now_utc.astimezone(timezone.utc)
    epoch = int(now.timestamp())
    next_epoch = epoch - (epoch % timeframe_seconds_value) + timeframe_seconds_value
    open_time = datetime.fromtimestamp(next_epoch, tz=timezone.utc)
    close_time = open_time + timedelta(seconds=timeframe_seconds_value)
    seconds_to_open = max(0, int((open_time - now).total_seconds()))
    return CandleWindow(timeframe_seconds_value, open_time, close_time, seconds_to_open)


def display_timezone(offset_hours: float) -> tzinfo:
    """Build a fixed server-display timezone from a configured UTC offset."""
    return timezone(timedelta(hours=offset_hours))


def format_server_time(value_utc: datetime, offset_hours: float) -> str:
    """Format a UTC timestamp using the configured Quotex server display offset."""
    if value_utc.tzinfo is None:
        raise ValueError("value_utc must be timezone-aware")
    return value_utc.astimezone(display_timezone(offset_hours)).strftime("%Y-%m-%d %H:%M:%S")
