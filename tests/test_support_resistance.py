from datetime import datetime, timedelta, timezone
from decimal import Decimal

from quotex_mtf_signal_bot.analysis.support_resistance import find_levels
from quotex_mtf_signal_bot.core.models import Candle, Timeframe


def make(values: list[tuple[str, str, str, str]]) -> list[Candle]:
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return [
        Candle(
            symbol="EURUSD",
            timeframe=Timeframe.M1,
            timestamp_utc=base + timedelta(minutes=i),
            open=Decimal(o), high=Decimal(h), low=Decimal(l), close=Decimal(c),
        )
        for i, (o, h, l, c) in enumerate(values)
    ]


def test_finds_swing_support_and_resistance():
    data = make([
        ("1.1000", "1.1010", "1.0995", "1.1005"),
        ("1.1005", "1.1015", "1.0990", "1.1010"),
        ("1.1010", "1.1020", "1.1000", "1.1015"),
        ("1.1015", "1.1035", "1.1010", "1.1020"),
        ("1.1020", "1.1040", "1.1015", "1.1030"),
        ("1.1030", "1.1032", "1.1018", "1.1025"),
        ("1.1025", "1.1030", "1.1000", "1.1010"),
    ])
    result = find_levels(data, swing_strength=2)
    assert result.supports
    assert result.resistances
    assert all(level.price <= data[-1].close for level in result.supports)
    assert all(level.price >= data[-1].close for level in result.resistances)
