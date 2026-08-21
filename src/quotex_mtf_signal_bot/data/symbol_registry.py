from __future__ import annotations

import re
from dataclasses import dataclass


# Real-market FX pairs supported by the Quotex watch-list used by this bot.
# OTC instruments are intentionally excluded from the normal live scanner.
QUOTEX_WATCHLIST = (
    "AUDNZD", "USDIDR", "USDINR", "USDBRL", "CADCHF", "USDMXN", "USDZAR",
    "NZDJPY", "USDPHP", "USDEGP", "CADJPY", "USDPKR", "USDCOP", "USDBDT",
    "EURUSD", "AUDJPY", "USDJPY", "AUDUSD", "AUDCAD", "GBPNZD", "NZDCAD",
    "NZDCHF", "USDARS", "USDDZD", "USDNGN", "EURCAD", "AUDCHF", "GBPAUD",
    "GBPCAD", "GBPUSD", "EURAUD", "CHFJPY", "GBPCHF", "GBPJPY", "USDCHF",
    "NZDUSD", "EURCHF", "USDCAD", "EURNZD", "EURGBP", "EURJPY",
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

    @staticmethod
    def _is_otc(symbol: str) -> bool:
        """Recognize Quotex-style OTC broker symbols without blocking normal suffixes."""
        return "OTC" in symbol.upper()

    @classmethod
    def from_mt5(
        cls,
        adapter,
        candidates: tuple[str, ...] | None = None,
        *,
        include_otc: bool = False,
    ) -> "SymbolRegistry":
        """Discover real-market broker symbols belonging to the Quotex FX universe.

        Broker suffixes such as ``m`` are preserved. OTC instruments are excluded
        by default because the live scanner is intended only for real-market
        trading sessions. ``include_otc=True`` remains available for explicit
        research/testing.
        """
        available = tuple(dict.fromkeys(str(name) for name in adapter.symbols()))
        allowed = tuple(str(item).upper() for item in (candidates or QUOTEX_WATCHLIST))
        allowed_set = set(allowed)

        resolved: list[str] = []
        for name in available:
            if not include_otc and cls._is_otc(name):
                continue
            canonical = cls._currency_pair(name)
            if canonical in allowed_set:
                resolved.append(name)

        return cls(tuple(sorted(set(resolved))))
