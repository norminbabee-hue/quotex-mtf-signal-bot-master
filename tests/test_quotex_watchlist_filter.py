from quotex_mtf_signal_bot.data.symbol_registry import SymbolRegistry


class FakeAdapter:
    def __init__(self, symbols):
        self._symbols = symbols

    def symbols(self):
        return self._symbols


def test_default_registry_discovers_all_available_fx_pairs():
    adapter = FakeAdapter(
        [
            "AUDNZD",
            "USDINR",
            "USDJPY",
            "GBPUSDm",
            "EURUSD",
            "USDTRY",
            "EURTRY",
            "XAUUSD",
            "US30",
        ]
    )

    registry = SymbolRegistry.from_mt5(adapter)

    assert registry.symbols == (
        "AUDNZD",
        "EURUSD",
        "EURTRY",
        "GBPUSD",
        "USDINR",
        "USDJPY",
        "USDTRY",
    )
    assert "XAUUSD" not in registry.symbols
    assert "US30" not in registry.symbols


def test_quotex_suffix_does_not_change_pair_identity():
    adapter = FakeAdapter(["EURUSDm", "AUDNZD-OTC", "USDJPY", "GBPUSDm"])

    registry = SymbolRegistry.from_mt5(adapter)

    assert registry.symbols == ("AUDNZD", "EURUSD", "GBPUSD", "USDJPY")
    assert registry.broker_symbol("AUDNZD") == "AUDNZD-OTC"
    assert registry.broker_symbol("EURUSD") == "EURUSDm"
    assert registry.broker_symbol("GBPUSD") == "GBPUSDm"
    assert registry.broker_symbol("USDJPY") == "USDJPY"
