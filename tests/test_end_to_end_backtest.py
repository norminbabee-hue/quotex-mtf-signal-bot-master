from datetime import datetime, timedelta, timezone
from decimal import Decimal

from quotex_mtf_signal_bot.backtest.engine import run_backtest
from quotex_mtf_signal_bot.backtest.replay import generate_signals
from quotex_mtf_signal_bot.core.models import Candle, Timeframe


def candles(timeframe: Timeframe, count: int) -> list[Candle]:
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    step = Decimal("0.00010")
    return [
        Candle(
            symbol="EURUSD",
            timeframe=timeframe,
            timestamp_utc=base + timedelta(minutes=i * timeframe.minutes),
            open=Decimal("1.10000") + step * i,
            high=Decimal("1.10003") + step * i,
            low=Decimal("1.09997") + step * i,
            close=Decimal("1.10000") + step * i,
        )
        for i in range(count)
    ]


def test_full_replay_to_backtest_pipeline():
    # Each timeframe needs enough *elapsed time*, not merely the same number
    # of candles. The replay requires 60 closed candles on M1/M5/M15, so 180
    # candles on each timeframe leaves the M15 stream with only 12 closed bars
    # by the time the 180th M1 candle arrives.
    data = {
        Timeframe.M1: candles(Timeframe.M1, 1800),
        Timeframe.M5: candles(Timeframe.M5, 360),
        Timeframe.M15: candles(Timeframe.M15, 120),
    }
    signals = generate_signals(data, symbol="EURUSD")
    report = run_backtest(signals, data[Timeframe.M1])

    assert signals
    assert report.total <= len(signals)
    assert report.wins + report.losses + report.ties == report.total
    assert report.win_rate >= Decimal(0)
    assert report.win_rate <= Decimal(100)
