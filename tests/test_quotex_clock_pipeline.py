from datetime import datetime, timezone
from decimal import Decimal

from quotex_mtf_signal_bot.data.candle_builder import CandleBuilder
from quotex_mtf_signal_bot.data.mt5_adapter import Tick


def tick(hour: int, minute: int, second: int, price: str) -> Tick:
    return Tick(
        symbol="EURUSD",
        timestamp_utc=datetime(2026, 8, 21, hour, minute, second, tzinfo=timezone.utc),
        bid=Decimal(price),
        ask=Decimal(price),
    )


def test_m1_boundary_uses_quotex_server_clock():
    # UTC 16:59:59 is 22:59:59 on the configured +06:00 target clock.
    builder = CandleBuilder(60, server_offset_seconds=6 * 60 * 60)
    assert builder.update(tick(16, 59, 59, "1.1000")) is None
    closed = builder.update(tick(17, 0, 0, "1.1002"))

    assert closed is not None
    assert closed.open_time_utc == datetime(2026, 8, 21, 17, 0, tzinfo=timezone.utc)
    assert closed.close_time_utc == datetime(2026, 8, 21, 17, 1, tzinfo=timezone.utc)


def test_m5_boundary_uses_quotex_server_clock():
    builder = CandleBuilder(300, server_offset_seconds=6 * 60 * 60)
    builder.update(tick(16, 54, 59, "1.1000"))
    closed = builder.update(tick(16, 55, 0, "1.1003"))

    assert closed is not None
    assert closed.open_time_utc == datetime(2026, 8, 21, 16, 55, tzinfo=timezone.utc)
    assert closed.close_time_utc == datetime(2026, 8, 21, 17, 0, tzinfo=timezone.utc)
