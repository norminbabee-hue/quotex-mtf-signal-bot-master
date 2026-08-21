from quotex_mtf_signal_bot.data.symbol_registry import SymbolRegistry


class FakeAdapter:
    def __init__(self, symbols):
        self._symbols = symbols

    def symbols(self):
        return self._symbols


def test_registry_discovers_all_currency_pairs_and_broker_suffixes():
    adapter = FakeAdapter(
        [
            "EURUSD",
            "GBPUSDm",
            "USDJPY",
            "AUDNZD-OTC",
            "USDINR",
            "XAUUSD",
            "US30",
            "EURUSDm",
        ]
    )

    registry = SymbolRegistry.from_mt5(adapter)

    assert registry.symbols == (
        "AUDNZD-OTC",
        "EURUSD",
        "EURUSDm",
        "GBPUSDm",
        "USDINR",
        "USDJPY",
    )


def test_registry_can_still_use_explicit_canonical_candidates():
    adapter = FakeAdapter(["EURUSDm", "USDJPY", "AUDNZD-OTC", "XAUUSD"])

    registry = SymbolRegistry.from_mt5(adapter, candidates=("EURUSD", "AUDNZD", "GBPUSD"))

    assert registry.symbols == ("AUDNZD-OTC", "EURUSDm")
