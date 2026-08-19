from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from quotex_mtf_signal_bot.analysis.indicators import ema, macd, rsi, snapshot
from quotex_mtf_signal_bot.core.models import Candle, Timeframe


def candles(values: list[str]) -> list[Candle]:
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return [
        Candle(
            symbol="EURUSD",
            timeframe=Timeframe.M1,
            timestamp_utc=base + timedelta(minutes=i),
            open=Decimal(value),
            high=Decimal(value),
            low=Decimal(value),
            close=Decimal(value),
        )
        for i, value in enumerate(values)
    ]


def test_ema_returns_none_until_period_is_available():
    assert ema(candles(["1", "2"]), 3) is None


def test_ema_uses_simple_seed():
    result = ema(candles(["1", "2", "3"]), 3)
    assert result == Decimal("2")


def test_rsi_handles_strong_uptrend():
    result = rsi(candles([str(i) for i in range(1, 17)]), 14)
    assert result == Decimal("100")


def test_macd_requires_enough_history():
    value, signal, histogram = macd(candles([str(i) for i in range(1, 30)]))
    assert value is not None
    assert signal is None
    assert histogram is None


def test_snapshot_has_indicator_values_with_sufficient_history():
    result = snapshot(candles([str(100 + i) for i in range(60)]))
    assert result.ema_fast is not None
    assert result.ema_slow is not None
    assert result.rsi is not None
    assert result.macd is not None


def test_invalid_periods_are_rejected():
    with pytest.raises(ValueError):
        ema(candles(["1", "2", "3"]), 0)
    with pytest.raises(ValueError):
        rsi(candles(["1", "2", "3"]), 0)
