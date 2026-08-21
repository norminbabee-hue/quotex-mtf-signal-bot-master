from __future__ import annotations

import re
from dataclasses import dataclass


# Canonical FX universe from the user's Quotex watch-list screenshots.
# The live scanner intersects this list with the connected MT5 symbols, so
# broker-only pairs that are not in the Quotex watch-list are never analyzed.
QUOTEX_WATCHLIST = (
    "AUDNZD",
    "USDIDR",
    "USDINR",
    "USDBRL",
    "CADCHF",
    "USDMXN",
    "USDZAR",
    "NZDJPY",
    "USDPHP",
    "USDEGP",
    "CADJPY",
    "USDPKR",
    "USDCOP",
    "USDBDT",
    "EURUSD",
    "AUDJPY",
    "USDJPY",
    "AUDUSD",
    "AUDCAD",
    "GBPNZD",
    "NZDCAD",
    "NZDCHF",
    "USDARS",
    "USDDZD",
    "USDNGN",
    "EURCAD",
    "AUDCHF",
    "GBPAUD",
    "GBPCAD",
    "GBPUSD",
    "EURAUD",
    "CHFJPY",
    "GBPCHF",
    "GBPJPY",
    "USDCHF",
    "NZDUSD",
    "EURCHF",
    "USDCAD",
    "EURNZD",
    "EURGBP",
    "EURJPY",
)


# Currencies seen in common FX feeds, including the non-major pairs shown in
# the user's Quotex watch-list.
CURRENCY_CODES = frozenset(
    {
        "AED",
        "ARS",
        "AUD",
        "BDT",
        "BGN",
        "BRL",
        "CAD",
        "CHF",
        "CLP",
        "CNH",
        "CNY",
        "COP",
        "CZK",
        "DKK",
        "DZD",
        "EGP",
        "EUR",
        "GBP",
        "HKD",
        "HUF",
        "IDR",
        "ILS",
        "INR",
        "ISK",
        "JPY",
        "KES",
        "KRW",
        "MXN",
        "MYR",
        "NGN",
        "NOK",
        "NZD",
        "PHP",
        "PKR",
        "PLN",
        "QAR",
        "RON",
        "SAR",
        "SEK",
        "SGD",
        "THB",
        "TRY",
        "TWD",
        "USD",
        "ZAR",
    }
)


@dataclass(frozen=True, slots=True)
class SymbolRegistry:
    """Runtime symbol universe constrained to the configured Quotex watch-list."""

    symbols: tuple[str, ...]

    @staticmethod
    def _currency_pair(symbol: str) -> str | None:
        # Strip broker separators/suffixes while preserving the first six
        # currency letters. This accepts names such as EURUSDm, EUR/USD and
        # AUDNZD-OTC when the connected data source exposes them.
        letters = re.sub(r"[^A-Z]", "", symbol.upper())
        if len(letters) < 6:
            return None
        pair = letters[:6]
        base, quote = pair[:3], pair[3:]
        if base in CURRENCY_CODES and quote in CURRENCY_CODES and base != quote:
            return pair
        return None

    @classmethod
    def from_mt5(
        cls,
        adapter,
        candidates: tuple[str, ...] | None = QUOTEX_WATCHLIST,
    ) -> "SymbolRegistry":
        """Resolve only configured Quotex pairs against the connected MT5 feed.

        If ``candidates`` is omitted, the scanner uses the Quotex watch-list
        captured from the user's screenshots. An explicit candidates tuple is
        still supported for tests or another deliberately restricted universe.
        Broker suffixes and OTC-style names are preserved exactly as supplied
        by MT5 when a configured canonical pair is found.
        """
        available = tuple(dict.fromkeys(str(name) for name in adapter.symbols()))
        requested = tuple(str(item).upper() for item in candidates or ())

        resolved: list[str] = []
        for canonical in requested:
            exact = next((name for name in available if name.upper() == canonical), None)
            suffixed = next(
                (name for name in available if cls._currency_pair(name) == canonical),
                None,
            )
            if exact or suffixed:
                resolved.append(exact or suffixed)
        return cls(tuple(sorted(set(resolved))))
