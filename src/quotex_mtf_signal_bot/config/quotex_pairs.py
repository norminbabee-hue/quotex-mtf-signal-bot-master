from __future__ import annotations

import json
from pathlib import Path

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

# Built-in fallback. The editable JSON watchlist below normally supplies the
# active list; this tuple keeps the bot safe if that file is missing or invalid.
DEFAULT_QUOTEX_REAL_PAIRS: tuple[str, ...] = (
    "GBPCHF", "EURCHF", "USDCAD", "USDCHF", "CHFJPY",
    "GBPCAD", "EURCAD", "AUDCAD", "AUDCHF", "EURAUD",
    "GBPJPY", "USDJPY", "GBPUSD", "GBPAUD", "CADJPY",
    "EURUSD", "AUDUSD", "EURGBP", "AUDJPY", "EURJPY",
)

REAL_PAIRS_FILE = Path(__file__).with_name("quotex_real_pairs.json")


def normalize_pair(value: str) -> str:
    return "".join(str(value).upper().strip().replace("/", "").split())


def _validated_pairs(values) -> tuple[str, ...]:
    pairs: list[str] = []
    for value in values:
        pair = normalize_pair(value)
        if len(pair) != 6 or not pair.isalpha():
            continue
        if pair not in pairs:
            pairs.append(pair)
    return tuple(pairs)


def load_current_quotex_real_pairs(path: Path | None = None) -> tuple[str, ...]:
    """Load the current Quotex real-market watchlist.

    Edit quotex_real_pairs.json whenever Quotex changes the available pairs,
    then restart the live dashboard. If the file is missing or invalid, the
    built-in list remains active instead of silently broadening to OTC pairs.
    """
    watchlist = path or REAL_PAIRS_FILE
    try:
        payload = json.loads(watchlist.read_text(encoding="utf-8"))
        values = payload.get("pairs", []) if isinstance(payload, dict) else payload
        pairs = _validated_pairs(values)
        return pairs or DEFAULT_QUOTEX_REAL_PAIRS
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        return DEFAULT_QUOTEX_REAL_PAIRS


# Current list loaded from the editable watchlist file.
QUOTEX_PAIRS = load_current_quotex_real_pairs()
CURRENT_QUOTEX_REAL_PAIRS = QUOTEX_PAIRS
CURRENT_QUOTEX_REAL_PAIRS_SET = frozenset(CURRENT_QUOTEX_REAL_PAIRS)
BACKUP_QUOTEX_PAIRS_SET = frozenset(BACKUP_QUOTEX_PAIRS)

# Backwards-compatible name used by the existing scanner/dashboard code.
QUOTEX_PAIRS_SET = CURRENT_QUOTEX_REAL_PAIRS_SET
