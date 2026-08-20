from datetime import datetime, timedelta, timezone
from decimal import Decimal

from quotex_mtf_signal_bot.data.live_candles import LiveCandleManager
from quotex_mtf_signal_bot.data.mt5_adapter import Tick


class FakeAdapter:
    def bars(self, symbol: str, timeframe: str, count: int):
        return [object()] * count

    def latest_tick(self, symbol: str):
        raise NotImplementedError


def tick(second: int) -> Tick:
    return Tick(
        symbol="EURUSD",
        timestamp_utc=datetime(2026, 1, 1, 0, 0, second, tzinfo=timezone.utc),
        bid=Decimal("1.10000"),
        ask=Decimal("1.10002"),
    )


def test_warmup_checks_all_timeframes():
    manager = LiveCandleManager(FakeAdapter(), "EURUSD")
    manager.seed_history(60)


def test_one_tick_stream_closes_m1_m5_and_m15_at_boundaries():
    manager = LiveCandleManager(FakeAdapter(), "EURUSD")
    base = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
    closed = []
    for seconds in range(0, 15 * 60 + 1, 30):
        ts = base + timedelta(seconds=seconds)
        closed.extend(manager.on_tick(Tick("EURUSD", ts, Decimal("1.10000"), Decimal("1.10002"))))

    by_tf = {}
    for event in closed:
        by_tf.setdefault(event.candle.timeframe_seconds, []).append(event.candle)

    assert len(by_tf[60]) == 15
    assert len(by_tf[300]) == 3
    assert len(by_tf[900]) == 1
    assert all(c.close_time_utc > c.open_time_utc for c in by_tf[60])
