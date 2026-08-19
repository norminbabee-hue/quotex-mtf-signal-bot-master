from datetime import datetime, timezone

import pytest

from quotex_mtf_signal_bot.core.models import Candle, Timeframe
from quotex_mtf_signal_bot.data.synchronizer import (
    candle_open_time,
    is_completed,
    synchronize_completed,
    validate_sequence,
)


def candle(timeframe: Timeframe, minute: int, close: float = 1.1) -> Candle:
    ts = datetime(2026, 1, 2, 12, minute, tzinfo=timezone.utc)
    return Candle("EURUSD", timeframe, ts, 1.0, 1.2, 0.9, close, 10)


def test_candle_open_time_aligns_to_boundary() -> None:
    assert candle_open_time(
        datetime(2026, 1, 2, 12, 7, 23, tzinfo=timezone.utc), Timeframe.M5
    ) == datetime(2026, 1, 2, 12, 5, tzinfo=timezone.utc)


def test_forming_candle_is_not_completed() -> None:
    c = candle(Timeframe.M1, 7)
    now = datetime(2026, 1, 2, 12, 7, 30, tzinfo=timezone.utc)
    assert not is_completed(c, now)


def test_completed_candle_is_completed() -> None:
    c = candle(Timeframe.M1, 7)
    now = datetime(2026, 1, 2, 12, 8, tzinfo=timezone.utc)
    assert is_completed(c, now)


def test_sequence_rejects_gaps() -> None:
    candles = [candle(Timeframe.M1, 1), candle(Timeframe.M1, 3)]
    with pytest.raises(ValueError, match="Invalid M1 sequence"):
        validate_sequence(candles)


def test_synchronizer_uses_only_completed_aligned_candles() -> None:
    data = {
        Timeframe.M1: [candle(Timeframe.M1, 0), candle(Timeframe.M1, 1)],
        Timeframe.M5: [candle(Timeframe.M5, 0), candle(Timeframe.M5, 5)],
        Timeframe.M15: [candle(Timeframe.M15, 0), candle(Timeframe.M15, 15)],
    }
    now = datetime(2026, 1, 2, 12, 16, tzinfo=timezone.utc)
    result = synchronize_completed(data, now)

    assert result.candles[Timeframe.M1].timestamp_utc.minute == 14
    assert result.candles[Timeframe.M5].timestamp_utc.minute == 10
    assert result.candles[Timeframe.M15].timestamp_utc.minute == 0
