from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SymbolRegistry:
    """Runtime symbol universe; broker suffixes are discovered from MT5."""

    symbols: tuple[str, ...]

    @classmethod
    def from_mt5(cls, adapter, candidates: tuple[str, ...] | None = None) -> "SymbolRegistry":
        """Resolve available major FX symbols without hard-coding a broker suffix.

        The adapter is expected to expose `symbols()` returning MT5 symbol names.
        Candidates are canonical FX names; e.g. EURUSD may resolve to EURUSDm.
        """
        available = {str(name) for name in adapter.symbols()}
        if candidates is None:
            candidates = (
                "EURUSD", "GBPUSD", "USDJPY", "USDCHF", "AUDUSD", "USDCAD", "NZDUSD",
                "EURGBP", "EURJPY", "EURCHF", "EURAUD", "EURCAD", "EURNZD",
                "GBPJPY", "GBPCHF", "GBPAUD", "GBPCAD", "GBPNZD",
                "AUDJPY", "AUDCHF", "AUDCAD", "AUDNZD", "CADJPY", "CADCHF",
                "CHFJPY", "NZDJPY", "NZDCHF", "NZDCAD",
            )
        resolved: list[str] = []
        for canonical in candidates:
            exact = canonical if canonical in available else None
            suffixed = next((name for name in available if name.startswith(canonical)), None)
            if exact or suffixed:
                resolved.append(exact or suffixed)
        return cls(tuple(sorted(set(resolved))))
