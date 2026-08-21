from quotex_mtf_signal_bot.data.symbol_registry import SymbolRegistry


class FakeAdapter:
    def __init__(self, symbols):
        self._symbols = symbols

    def symbols(self):
        return self._symbols


def test_default_registry_excludes_mt5_pairs_not_in_quotex_watchlist():
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
        "GBPUSDm",
        "USDINR",
        "USDJPY",
    )

    assert "USDTRY" not in registry.symbols
    assert "EURTRY" not in registry.symbols
    assert "XAUUSD" not in registry.symbols
    assert "US30" not in registry.symbols


def test_configured_quotex_pairs_keep_broker_suffixes():
    adapter = FakeAdapter(["EURUSDm", "AUDNZD-OTC", "USDJPY", "GBPUSDm"])

    registry = SymbolRegistry.from_mt5(adapter)

    assert "EURUSDm" in registry.symbols
    assert "AUDNZD-OTC" in registry.symbols
    assert "USDJPY" in registry.symbols
    assert "GBPUSDm" in registry.symbols
