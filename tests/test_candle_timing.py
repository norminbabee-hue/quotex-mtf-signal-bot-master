from datetime import datetime, timezone

from quotex_mtf_signal_bot.data.candle_timing import (
    format_server_time,
    next_candle_window,
    timeframe_seconds,
)


def test_next_m1_window_is_the_next_minute_boundary():
    now = datetime(2026, 8, 21, 16, 48, 37, tzinfo=timezone.utc)

    window = next_candle_window(now, timeframe_seconds("M1"))

    assert window.open_time_utc == datetime(2026, 8, 21, 16, 49, tzinfo=timezone.utc)
    assert window.close_time_utc == datetime(2026, 8, 21, 16, 50, tzinfo=timezone.utc)
    assert window.seconds_to_open == 23


def test_next_m5_window_aligns_to_five_minute_boundary():
    now = datetime(2026, 8, 21, 16, 48, 37, tzinfo=timezone.utc)

    window = next_candle_window(now, timeframe_seconds("M5"))

    assert window.open_time_utc == datetime(2026, 8, 21, 16, 50, tzinfo=timezone.utc)
    assert window.close_time_utc == datetime(2026, 8, 21, 16, 55, tzinfo=timezone.utc)


def test_next_m15_window_aligns_to_fifteen_minute_boundary():
    now = datetime(2026, 8, 21, 16, 48, 37, tzinfo=timezone.utc)

    window = next_candle_window(now, timeframe_seconds("M15"))

    assert window.open_time_utc == datetime(2026, 8, 21, 17, 0, tzinfo=timezone.utc)
    assert window.close_time_utc == datetime(2026, 8, 21, 17, 15, tzinfo=timezone.utc)


def test_server_display_time_can_match_quotex_utc_plus_six_display():
    utc_value = datetime(2026, 8, 21, 16, 49, tzinfo=timezone.utc)

    assert format_server_time(utc_value, 6) == "2026-08-21 22:49:00"
