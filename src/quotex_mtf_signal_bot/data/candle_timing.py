from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


DEFAULT_QUOTEX_SERVER_OFFSET_SECONDS = 6 * 60 * 60


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


def _server_shift(offset_seconds: int | float) -> timedelta:
    return timedelta(seconds=offset_seconds)


def candle_boundary_utc(
    timestamp_utc: datetime,
    timeframe_seconds_value: int,
    *,
    server_offset_seconds: int | float = DEFAULT_QUOTEX_SERVER_OFFSET_SECONDS,
) -> datetime:
    """Return the candle-open boundary using the configured Quotex server clock.

    MT5 timestamps are kept in UTC internally. We temporarily move the timestamp
    into the Quotex server clock, apply the normal M1/M5/M15 boundary there, then
    convert the boundary back to UTC. This is what makes a candle such as
    22:00:00 on the Quotex clock open exactly at that server minute, even when
    the MT5 feed is represented in UTC.
    """
    if timestamp_utc.tzinfo is None:
        raise ValueError("timestamp_utc must be timezone-aware")
    if timeframe_seconds_value <= 0:
        raise ValueError("timeframe_seconds must be positive")

    utc_value = timestamp_utc.astimezone(timezone.utc)
    server_value = utc_value + _server_shift(server_offset_seconds)
    epoch = int(server_value.timestamp())
    start_epoch = epoch - (epoch % timeframe_seconds_value)
    server_start = datetime.fromtimestamp(start_epoch, tz=timezone.utc)
    return server_start - _server_shift(server_offset_seconds)


def next_candle_window(
    now_utc: datetime,
    timeframe_seconds_value: int,
    *,
    server_offset_seconds: int | float = 0,
) -> CandleWindow:
    """Return the next candle boundary according to the target server clock."""
    if now_utc.tzinfo is None:
        raise ValueError("now_utc must be timezone-aware")
    if timeframe_seconds_value <= 0:
        raise ValueError("timeframe_seconds must be positive")

    now = now_utc.astimezone(timezone.utc)
    current_start = candle_boundary_utc(
        now,
        timeframe_seconds_value,
        server_offset_seconds=server_offset_seconds,
    )
    open_time = current_start
    if open_time <= now:
        open_time += timedelta(seconds=timeframe_seconds_value)
    close_time = open_time + timedelta(seconds=timeframe_seconds_value)
    seconds_to_open = max(0, int((open_time - now).total_seconds()))
    return CandleWindow(timeframe_seconds_value, open_time, close_time, seconds_to_open)


def format_server_time(value_utc: datetime, offset_hours: float) -> str:
    """Format a UTC timestamp using the configured Quotex server display offset."""
    if value_utc.tzinfo is None:
        raise ValueError("value_utc must be timezone-aware")
    return (value_utc + timedelta(hours=offset_hours)).strftime("%Y-%m-%d %H:%M:%S")
