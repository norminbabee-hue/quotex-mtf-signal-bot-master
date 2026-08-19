from datetime import datetime, timedelta, timezone
from decimal import Decimal

from quotex_mtf_signal_bot.core.models import Tick, Timeframe
from quotex_mtf_signal_bot.data.bar_builder import TickBarBuilder


def tick(second: int, price: str) -> Tick:
    return Tick(
        symbol="EURUSD",
        timestamp_utc=datetime(2026, 1, 1, 12, 0, second, tzinfo=timezone.utc),
        bid=Decimal(price),
        ask=Decimal(price) + Decimal("0.00002"),
    )


def test_builder_creates_m1_bar_from_ticks():
    builder = TickBarBuilder()
    assert builder.update(tick(0, "1.10000")) == []
    assert builder.update(tick(10, "1.10020")) == []

    closed = builder.update(
        Tick(
            symbol="EURUSD",
            timestamp_utc=datetime(2026, 1, 1, 12, 1, 0, tzinfo=timezone.utc),
            bid=Decimal("1.10010"),
            ask=Decimal("1.10012"),
        )
    )

    m1 = [bar for bar in closed if bar.timeframe == Timeframe.M1]
    assert len(m1) == 1
    assert m1[0].open == Decimal("1.10001")
    assert m1[0].high == Decimal("1.10021")
    assert m1[0].low == Decimal("1.10001")
    assert m1[0].close == Decimal("1.10011")
    assert m1[0].tick_volume == 2


def test_flush_does_not_close_forming_bar():
    builder = TickBarBuilder()
    builder.update(tick(5, "1.20000"))
    now = datetime(2026, 1, 1, 12, 0, 59, tzinfo=timezone.utc)
    assert builder.flush(now) == []


def test_flush_closes_completed_bar():
    builder = TickBarBuilder()
    builder.update(tick(5, "1.20000"))
    now = datetime(2026, 1, 1, 12, 1, 0, tzinfo=timezone.utc)
    closed = builder.flush(now)
    assert any(bar.timeframe == Timeframe.M1 for bar in closed)
