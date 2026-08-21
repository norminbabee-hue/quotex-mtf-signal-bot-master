from quotex_mtf_signal_bot.data.symbol_registry import SymbolRegistry


class FakeAdapter:
    def __init__(self, symbols):
        self._symbols = symbols

    def symbols(self):
        return self._symbols


def test_registry_normalizes_all_fx_pairs_and_ignores_broker_suffixes():
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
        "AUDNZD",
        "EURUSD",
        "GBPUSD",
        "USDINR",
        "USDJPY",
    )
    assert registry.broker_symbol("AUDNZD") == "AUDNZD-OTC"
    assert registry.broker_symbol("GBPUSD") == "GBPUSDm"


def test_otc_flag_is_ignored_and_otc_suffix_does_not_remove_pair():
    adapter = FakeAdapter(["EURUSDm", "USDJPY", "AUDNZD-OTC", "XAUUSD"])

    without_flag = SymbolRegistry.from_mt5(adapter)
    with_flag = SymbolRegistry.from_mt5(adapter, include_otc=True)

    assert without_flag.symbols == ("AUDNZD", "EURUSD", "USDJPY")
    assert with_flag.symbols == without_flag.symbols


def test_registry_uses_canonical_candidates():
    adapter = FakeAdapter(["EURUSDm", "USDJPY", "AUDNZD-OTC", "XAUUSD"])

    registry = SymbolRegistry.from_mt5(
        adapter,
        candidates=("EURUSD", "AUDNZD", "GBPUSD"),
    )

    assert registry.symbols == ("AUDNZD", "EURUSD")
    assert registry.broker_symbol("AUDNZD") == "AUDNZD-OTC"
    assert registry.broker_symbol("EURUSD") == "EURUSDm"
