from datetime import datetime, timedelta, timezone
from decimal import Decimal

from quotex_mtf_signal_bot.backtest.replay import generate_signals
from quotex_mtf_signal_bot.core.models import Candle, Timeframe


def make_candles(timeframe: Timeframe, count: int, step: str = "0.00010") -> list[Candle]:
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    step_decimal = Decimal(step)
    return [
        Candle(
            symbol="EURUSD",
            timeframe=timeframe,
            timestamp_utc=base + timedelta(minutes=i * timeframe.minutes),
            open=Decimal("1.10000") + step_decimal * i,
            high=Decimal("1.10003") + step_decimal * i,
            low=Decimal("1.09997") + step_decimal * i,
            close=Decimal("1.10000") + step_decimal * i,
        )
        for i in range(count)
    ]


def test_replay_uses_timestamp_aligned_closed_history():
    candles = {
        Timeframe.M1: make_candles(Timeframe.M1, 1000),
        Timeframe.M5: make_candles(Timeframe.M5, 200),
        Timeframe.M15: make_candles(Timeframe.M15, 100),
    }
    signals = generate_signals(candles, symbol="EURUSD")
    assert signals
    assert all(signal.entry_time_utc > candles[Timeframe.M1][899].timestamp_utc for signal in signals[-1:])


def test_replay_does_not_use_future_higher_timeframe_candles():
    candles = {
        Timeframe.M1: make_candles(Timeframe.M1, 100),
        Timeframe.M5: make_candles(Timeframe.M5, 100),
        Timeframe.M15: make_candles(Timeframe.M15, 100),
    }
    signals = generate_signals(candles, symbol="EURUSD")
    assert all(
        signal.entry_time_utc >= datetime(2026, 1, 1, 15, 0, tzinfo=timezone.utc)
        for signal in signals
    )


def test_replay_does_not_generate_before_all_timeframes_have_history():
    candles = {
        Timeframe.M1: make_candles(Timeframe.M1, 30),
        Timeframe.M5: make_candles(Timeframe.M5, 30),
        Timeframe.M15: make_candles(Timeframe.M15, 30),
    }
    assert generate_signals(candles, symbol="EURUSD") == []
