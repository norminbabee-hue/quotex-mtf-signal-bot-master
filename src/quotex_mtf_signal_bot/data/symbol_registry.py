from __future__ import annotations

import re
from dataclasses import dataclass


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
    """Canonical FX universe discovered from the connected MT5 feed.

    MT5/Exness broker names may contain suffixes such as ``m`` or ``-OTC``.
    Those suffixes are naming details only: the underlying six-letter FX pair
    is the identity used by the scanner and dashboard.
    """

    symbols: tuple[str, ...]
    _broker_pairs: tuple[tuple[str, str], ...]

    @staticmethod
    def canonical_symbol(symbol: str) -> str | None:
        """Return the underlying six-letter FX pair from a broker symbol."""
        letters = re.sub(r"[^A-Z]", "", str(symbol).upper())
        if len(letters) < 6:
            return None
        pair = letters[:6]
        base, quote = pair[:3], pair[3:]
        if base in CURRENCY_CODES and quote in CURRENCY_CODES and base != quote:
            return pair
        return None

    def broker_symbol(self, canonical: str) -> str:
        """Return the selected MT5 broker symbol for a canonical FX pair."""
        mapping = dict(self._broker_pairs)
        return mapping[canonical]

    @classmethod
    def from_mt5(
        cls,
        adapter,
        candidates: tuple[str, ...] | None = None,
        *,
        include_otc: bool | None = None,
    ) -> "SymbolRegistry":
        """Discover every available FX pair from MT5.

        ``include_otc`` is retained only for backwards compatibility with older
        callers/tests. It is intentionally ignored: ``-OTC`` is not a market
        classification for this project and never causes a pair to be dropped.

        When several MT5 symbols represent the same pair (for example
        ``EURUSD``, ``EURUSDm`` and ``EURUSD-OTC``), one broker symbol is chosen
        for the pair while the public identity remains simply ``EURUSD``.
        """
        del include_otc
        available = tuple(dict.fromkeys(str(name) for name in adapter.symbols()))
        candidate_set = None
        if candidates is not None:
            candidate_set = {
                canonical
                for item in candidates
                if (canonical := cls.canonical_symbol(item)) is not None
            }

        selected: dict[str, str] = {}

        def rank(name: str, canonical: str) -> tuple[int, int, str]:
            upper = name.upper()
            if upper == canonical:
                suffix_rank = 0
            elif "OTC" in upper:
                suffix_rank = 2
            else:
                suffix_rank = 1
            return suffix_rank, len(name), upper

        for name in available:
            canonical = cls.canonical_symbol(name)
            if canonical is None:
                continue
            if candidate_set is not None and canonical not in candidate_set:
                continue
            current = selected.get(canonical)
            if current is None or rank(name, canonical) < rank(current, canonical):
                selected[canonical] = name

        pairs = tuple(sorted(selected.items()))
        return cls(
            symbols=tuple(canonical for canonical, _ in pairs),
            _broker_pairs=pairs,
        )
