from __future__ import annotations

import re
from dataclasses import dataclass


# Canonical FX universe from the user's Quotex watch-list screenshots.
# It remains available as an explicit restriction for callers that want the
# screenshot-only universe, while the default runtime discovery is dynamic.
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
    """Runtime FX symbol universe discovered from the connected MT5 feed."""

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
        candidates: tuple[str, ...] | None = None,
    ) -> "SymbolRegistry":
        """Discover every broker-provided FX symbol by default.

        With no explicit ``candidates`` restriction, every MT5 symbol whose
        first two 3-letter blocks are recognised currency codes is included.
        Broker suffixes and OTC-style names are preserved exactly, so symbols
        such as ``GBPUSDm``, ``EURUSDm`` and ``AUDNZD-OTC`` are all retained.

        An explicit candidates tuple still restricts the result to the
        requested canonical pairs, which keeps the screenshot-only Quotex
        universe available via ``candidates=QUOTEX_WATCHLIST``.
        """
        available = tuple(dict.fromkeys(str(name) for name in adapter.symbols()))

        if candidates is None:
            resolved = [name for name in available if cls._currency_pair(name) is not None]
            return cls(tuple(sorted(set(resolved))))

        requested = tuple(str(item).upper() for item in candidates)
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
