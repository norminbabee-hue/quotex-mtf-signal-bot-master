from datetime import datetime, timedelta, timezone
from decimal import Decimal

from quotex_mtf_signal_bot.analysis.mtf import analyze_mtf
from quotex_mtf_signal_bot.core.models import Candle, Timeframe


def make(timeframe: Timeframe, start: int, count: int, step: str = "0.00010") -> list[Candle]:
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    values = [Decimal("1.10000") + Decimal(step) * i for i in range(count)]
    return [
        Candle(
            symbol="EURUSD",
            timeframe=timeframe,
            timestamp_utc=base + timedelta(minutes=start + i),
            open=value,
            high=value + Decimal("0.00003"),
            low=value - Decimal("0.00001"),
            close=value,
        )
        for i, value in enumerate(values)
    ]


def test_mtf_requires_strong_enough_alignment():
    result = analyze_mtf({
        Timeframe.M1: make(Timeframe.M1, 0, 60),
        Timeframe.M5: make(Timeframe.M5, 0, 60),
        Timeframe.M15: make(Timeframe.M15, 0, 60),
    })
    assert result.alignment == "bullish"
    assert result.bullish_score > result.bearish_score


def test_mtf_can_detect_conflict():
    up = make(Timeframe.M1, 0, 60)
    down = make(Timeframe.M5, 0, 60, step="-0.00010")
    flat = make(Timeframe.M15, 0, 60, step="0.00000")
    result = analyze_mtf({
        Timeframe.M1: up,
        Timeframe.M5: down,
        Timeframe.M15: flat,
    })
    assert result.alignment in {"conflict", "weak"}
