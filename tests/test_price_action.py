from datetime import datetime, timedelta, timezone
from decimal import Decimal

from quotex_mtf_signal_bot.analysis.price_action import features, snapshot
from quotex_mtf_signal_bot.core.models import Candle, Timeframe


def candle(o: str, h: str, l: str, c: str, minute: int = 0) -> Candle:
    return Candle(
        symbol="EURUSD",
        timeframe=Timeframe.M1,
        timestamp_utc=datetime(2026, 1, 1, 12, minute, tzinfo=timezone.utc),
        open=Decimal(o), high=Decimal(h), low=Decimal(l), close=Decimal(c),
    )


def test_features_measure_body_and_wicks():
    result = features(candle("1.1000", "1.1020", "1.0990", "1.1010"))
    assert result.body == Decimal("0.0010")
    assert result.upper_wick == Decimal("0.0010")
    assert result.lower_wick == Decimal("0.0010")


def test_bullish_engulfing_is_detected():
    result = snapshot([
        candle("1.1010", "1.1015", "1.0990", "1.0995", 0),
        candle("1.0990", "1.1030", "1.0985", "1.1020", 1),
    ])
    assert result.bullish_engulfing


def test_bearish_rejection_is_detected():
    result = snapshot([
        candle("1.1000", "1.1040", "1.0998", "1.1008", 0),
    ])
    assert result.bearish_rejection
