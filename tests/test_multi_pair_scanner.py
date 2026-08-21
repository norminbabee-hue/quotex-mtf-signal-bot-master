from decimal import Decimal
from datetime import datetime, timezone

from quotex_mtf_signal_bot.live.multi_pair_scanner import MultiPairScanner
from quotex_mtf_signal_bot.data.mt5_adapter import Tick


class FakeAdapter:
    def __init__(self, symbols):
        self._symbols = symbols

    def symbols(self):
        return self._symbols

    def bars(self, symbol, timeframe, count):
        return []

    def latest_tick(self, symbol):
        return Tick(symbol, datetime.now(timezone.utc), Decimal("1"), Decimal("1"))


def test_multi_pair_scanner_discovers_all_broker_fx_symbols():
    adapter = FakeAdapter([
        "EURUSD",
        "GBPUSDm",
        "USDJPY",
        "AUDNZD-OTC",
        "XAUUSD",
        "US30",
    ])

    scanner = MultiPairScanner(adapter, lambda signal: None)

    assert scanner.registry.symbols == (
        "AUDNZD-OTC",
        "EURUSD",
        "GBPUSDm",
        "USDJPY",
    )
    assert set(scanner.managers) == set(scanner.registry.symbols)
    assert set(scanner.services) == set(scanner.registry.symbols)


def test_multi_pair_scanner_refreshes_symbol_universe():
    adapter = FakeAdapter(["EURUSD", "USDJPY"])
    scanner = MultiPairScanner(adapter, lambda signal: None)

    adapter._symbols = ["EURUSD", "AUDNZD-OTC"]
    snapshot = scanner.refresh()

    assert snapshot.symbols == ("AUDNZD-OTC", "EURUSD")
    assert set(scanner.managers) == {"AUDNZD-OTC", "EURUSD"}
