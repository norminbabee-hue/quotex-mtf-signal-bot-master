from __future__ import annotations

import re
from dataclasses import dataclass


# Currencies seen in common FX feeds, including the non-major pairs shown in
# the user's Quotex watch-list. The registry still returns only symbols that
# actually exist in the connected MT5 terminal.
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
    """Runtime FX symbol universe discovered from the connected broker feed."""

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
    def from_mt5(cls, adapter, candidates: tuple[str, ...] | None = None) -> "SymbolRegistry":
        """Discover every available currency pair instead of only 28 majors.

        When a broker exposes suffixes or OTC-style names, the original broker
        symbol is preserved so the adapter can request its real market data.
        An explicit ``candidates`` list remains supported for tests or a
        deliberately restricted deployment.
        """
        available = tuple(dict.fromkeys(str(name) for name in adapter.symbols()))

        if candidates is not None:
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

        resolved = [name for name in available if cls._currency_pair(name) is not None]
        return cls(tuple(sorted(set(resolved))))
