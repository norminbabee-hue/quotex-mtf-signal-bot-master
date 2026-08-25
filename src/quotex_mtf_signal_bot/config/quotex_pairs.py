from __future__ import annotations

# Exact Quotex FX universe supplied by the user from the Quotex pair list.
# Canonical six-letter symbols; MT5 broker suffixes are resolved automatically.
QUOTEX_PAIRS: tuple[str, ...] = (
    "USDIDR", "NZDCAD", "USDARS", "USDNGN", "CADCHF", "EURUSD",
    "AUDJPY", "USDEGP", "USDCOP", "USDPHP", "GBPNZD", "USDINR",
    "EURGBP", "GBPUSD", "AUDUSD", "USDBRL", "CADJPY", "EURCAD",
    "GBPAUD", "GBPJPY", "USDCAD", "USDJPY", "EURAUD", "GBPCAD",
    "NZDJPY", "NZDUSD", "USDPKR", "USDCHF", "AUDCAD", "AUDNZD",
    "AUDCHF", "USDMXN", "CHFJPY", "NZDCHF", "USDBDT", "USDDZD",
    "EURCHF", "GBPCHF", "EURJPY", "USDZAR", "EURNZD",
)

QUOTEX_PAIRS_SET = frozenset(QUOTEX_PAIRS)
