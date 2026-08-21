from datetime import datetime, timedelta, timezone
from decimal import Decimal

from quotex_mtf_signal_bot.backtest.engine import run_backtest
from quotex_mtf_signal_bot.backtest.replay import generate_signals
from quotex_mtf_signal_bot.core.models import Candle, Timeframe


def candles(timeframe: Timeframe, count: int) -> list[Candle]:
    """Create deterministic but non-doji MTF history that can produce signals.

    Every 15-minute block has one directional regime, so M1/M5/M15 can align.
    Four bullish blocks are followed by one stronger bearish block, keeping the
    series trending while avoiding an RSI=100 synthetic fixture.
    """
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    price = Decimal("1.10000")
    candles_out: list[Candle] = []

    for i in range(count):
        block = (i * timeframe.minutes) // 15
        bullish = block % 5 != 4
        body = Decimal("0.00010") if bullish else Decimal("0.00020")
        close = price + body if bullish else price - body
        high = max(price, close) + Decimal("0.00002")
        low = min(price, close) - Decimal("0.00002")

        candles_out.append(
            Candle(
                symbol="EURUSD",
                timeframe=timeframe,
                timestamp_utc=base + timedelta(minutes=i * timeframe.minutes),
                open=price,
                high=high,
                low=low,
                close=close,
            )
        )
        price = close

    return candles_out


def test_full_replay_to_backtest_pipeline():
    # Each timeframe needs enough *elapsed time*, not merely the same number
    # of candles. The replay requires 60 closed candles on M1/M5/M15, so 1800
    # M1 candles, 360 M5 candles and 120 M15 candles give the replay enough
    # aligned closed history to exercise the real signal-scoring pipeline.
    data = {
        Timeframe.M1: candles(Timeframe.M1, 1800),
        Timeframe.M5: candles(Timeframe.M5, 360),
        Timeframe.M15: candles(Timeframe.M15, 120),
    }
    signals = generate_signals(data, symbol="EURUSD")
    report = run_backtest(signals, data[Timeframe.M1])

    assert signals
    assert len(signals) < 100, "Selective scoring should not emit a signal on most M1 candles"
    assert all(signal.confidence <= Decimal("90") for signal in signals)
    assert all(signal.score >= 12 for signal in signals)
    assert report.total <= len(signals)
    assert report.wins + report.losses + report.ties == report.total
    assert report.win_rate >= Decimal(0)
    assert report.win_rate <= Decimal(100)
