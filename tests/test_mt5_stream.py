from datetime import datetime, timezone
from types import SimpleNamespace
from decimal import Decimal

from quotex_mtf_signal_bot.data.mt5_stream import MT5Stream


class FakeMT5:
    def __init__(self):
        self.initialized = False
        self.selected = []
        self.shutdown_called = False

    def initialize(self):
        self.initialized = True
        return True

    def shutdown(self):
        self.shutdown_called = True

    def last_error(self):
        return (0, "")

    def symbol_select(self, symbol, enabled):
        if enabled:
            self.selected.append(symbol)
        return True

    def symbol_info_tick(self, symbol):
        return SimpleNamespace(
            time_msc=1767268800123,
            bid=1.10000,
            ask=1.10002,
        )


def test_mt5_stream_maps_millisecond_tick():
    fake = FakeMT5()
    stream = MT5Stream(fake)
    stream.connect()
    stream.subscribe(["EURUSD"])

    result = stream.poll("EURUSD")

    assert result is not None
    assert result.symbol == "EURUSD"
    assert result.bid == Decimal("1.1")
    assert result.ask == Decimal("1.10002")
    assert result.timestamp_utc.tzinfo == timezone.utc
    assert result.timestamp_utc.microsecond == 123000

    stream.close()
    assert fake.shutdown_called


def test_mt5_stream_uses_second_timestamp_when_millisecond_field_missing():
    class FallbackMT5(FakeMT5):
        def symbol_info_tick(self, symbol):
            return SimpleNamespace(time=1767268800, bid=1.2, ask=1.20002)

    result = MT5Stream(FallbackMT5()).poll("EURUSD")
    assert result is not None
    assert result.timestamp_utc == datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
