from __future__ import annotations

import re
from dataclasses import dataclass


# Currency pairs visible in the Quotex watch-list used by this bot. The
# canonical names are deliberately separated from broker symbols so names
# such as GBPUSDm and AUDNZD-OTC can be matched without losing their suffix.
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

CURRENCY_CODES = frozenset(
    {
        "AED", "ARS", "AUD", "BDT", "BGN", "BRL", "CAD", "CHF", "CLP",
        "CNH", "CNY", "COP", "CZK", "DKK", "DZD", "EGP", "EUR", "GBP",
        "HKD", "HUF", "IDR", "ILS", "INR", "ISK", "JPY", "KES", "KRW",
        "MXN", "MYR", "NGN", "NOK", "NZD", "PHP", "PKR", "PLN", "QAR",
        "RON", "SAR", "SEK", "SGD", "THB", "TRY", "TWD", "USD", "ZAR",
    }
)


@dataclass(frozen=True, slots=True)
class SymbolRegistry:
    """Runtime Quotex FX universe discovered from the connected MT5 feed."""

    symbols: tuple[str, ...]

    @staticmethod
    def _currency_pair(symbol: str) -> str | None:
        """Return the canonical six-letter FX pair represented by a broker name."""
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
        """Discover broker symbols that belong to the Quotex FX universe.

        The connected MT5 feed can contain instruments that Quotex does not
        expose (for example USDTRY, EURTRY, XAUUSD or indices). Those are
        intentionally excluded by default. The Quotex watch-list is the
        source of truth, while broker suffixes/OTC markers are preserved.

        ``candidates`` is an optional canonical-pair restriction for callers
        that need a smaller subset; it is not required for normal scanning.
        """
        available = tuple(dict.fromkeys(str(name) for name in adapter.symbols()))
        allowed = tuple(str(item).upper() for item in (candidates or QUOTEX_WATCHLIST))
        allowed_set = set(allowed)

        resolved: list[str] = []
        for name in available:
            canonical = cls._currency_pair(name)
            if canonical in allowed_set:
                resolved.append(name)

        return cls(tuple(sorted(set(resolved))))
