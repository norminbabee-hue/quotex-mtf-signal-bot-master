from __future__ import annotations

import re
from dataclasses import dataclass


# Broad ISO-4217-style currency-code set used only to distinguish FX symbols
# from metals, indices, crypto, and other MT5 instruments. Broker suffixes such
# as ``m`` and ``-OTC`` are deliberately ignored when identifying a pair.
CURRENCY_CODES = frozenset(
    {
        "AED", "AFN", "ALL", "AMD", "ANG", "AOA", "ARS", "AUD", "AWG", "AZN",
        "BAM", "BBD", "BDT", "BGN", "BHD", "BIF", "BMD", "BND", "BOB", "BRL",
        "BSD", "BTN", "BWP", "BYN", "BZD", "CAD", "CDF", "CHF", "CLP", "CNH",
        "CNY", "COP", "CRC", "CUP", "CVE", "CZK", "DJF", "DKK", "DOP", "DZD",
        "EGP", "ERN", "ETB", "EUR", "FJD", "FKP", "GBP", "GEL", "GHS", "GIP",
        "GMD", "GNF", "GTQ", "GYD", "HKD", "HNL", "HTG", "HUF", "IDR", "ILS",
        "INR", "IQD", "IRR", "ISK", "JMD", "JOD", "JPY", "KES", "KGS", "KHR",
        "KMF", "KPW", "KRW", "KWD", "KYD", "KZT", "LAK", "LBP", "LKR", "LRD",
        "LSL", "LYD", "MAD", "MDL", "MGA", "MKD", "MMK", "MNT", "MOP", "MRU",
        "MUR", "MVR", "MWK", "MXN", "MYR", "MZN", "NAD", "NGN", "NIO", "NOK",
        "NPR", "NZD", "OMR", "PAB", "PEN", "PGK", "PHP", "PKR", "PLN", "PYG",
        "QAR", "RON", "RSD", "RUB", "RWF", "SAR", "SBD", "SCR", "SDG", "SEK",
        "SGD", "SHP", "SLE", "SOS", "SRD", "SSP", "STN", "SVC", "SYP", "SZL",
        "THB", "TJS", "TMT", "TND", "TOP", "TRY", "TTD", "TWD", "TZS", "UAH",
        "UGX", "USD", "UYU", "UZS", "VES", "VND", "VUV", "WST", "XAF", "XCD",
        "XOF", "XPF", "YER", "ZAR", "ZMW", "ZWL",
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
