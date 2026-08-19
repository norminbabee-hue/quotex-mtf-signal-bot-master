from datetime import datetime, timedelta, timezone

import pytest

from quotex_mtf_signal_bot.core.models import Candle, Timeframe
from quotex_mtf_signal_bot.data.candles import validate_closed_candle_sequence


def candle(ts: datetime) -> Candle:
    return Candle("EURUSD", Timeframe.M1, ts, 1.0, 1.1, 0.9, 1.05, 10)


def test_valid_m1_sequence() -> None:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    validate_closed_candle_sequence([candle(start), candle(start + timedelta(minutes=1))], Timeframe.M1)


def test_gap_is_rejected() -> None:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    with pytest.raises(ValueError, match="Invalid M1 candle sequence"):
        validate_closed_candle_sequence([candle(start), candle(start + timedelta(minutes=2))], Timeframe.M1)
