from __future__ import annotations

# Stable backup of the original 41-pair Quotex whitelist.
# Keep this unchanged so we can recover the broader universe later if needed.
BACKUP_QUOTEX_PAIRS: tuple[str, ...] = (
    "USDIDR", "NZDCAD", "USDARS", "USDNGN", "CADCHF", "EURUSD",
    "AUDJPY", "USDEGP", "USDCOP", "USDPHP", "GBPNZD", "USDINR",
    "EURGBP", "GBPUSD", "AUDUSD", "USDBRL", "CADJPY", "EURCAD",
    "GBPAUD", "GBPJPY", "USDCAD", "USDJPY", "EURAUD", "GBPCAD",
    "NZDJPY", "NZDUSD", "USDPKR", "USDCHF", "AUDCAD", "AUDNZD",
    "AUDCHF", "USDMXN", "CHFJPY", "NZDCHF", "USDBDT", "USDDZD",
    "EURCHF", "GBPCHF", "EURJPY", "USDZAR", "EURNZD",
)

# Current Quotex REAL-market pairs supplied by the user for this session.
# The live scanner uses this list, so Telegram actionable signals are limited
# to pairs currently seen as real-market pairs on Quotex.
QUOTEX_PAIRS: tuple[str, ...] = (
    "GBPCHF", "EURCHF", "USDCAD", "USDCHF", "CHFJPY",
    "GBPCAD", "EURCAD", "AUDCAD", "AUDCHF", "EURAUD",
    "GBPJPY", "USDJPY", "GBPUSD", "GBPAUD", "CADJPY",
    "EURUSD", "AUDUSD", "EURGBP", "AUDJPY", "EURJPY",
)

# Explicit aliases make future list updates safe and easy to understand.
CURRENT_QUOTEX_REAL_PAIRS = QUOTEX_PAIRS
CURRENT_QUOTEX_REAL_PAIRS_SET = frozenset(CURRENT_QUOTEX_REAL_PAIRS)
BACKUP_QUOTEX_PAIRS_SET = frozenset(BACKUP_QUOTEX_PAIRS)

# Backwards-compatible name used by the existing scanner/dashboard code.
QUOTEX_PAIRS_SET = CURRENT_QUOTEX_REAL_PAIRS_SET
