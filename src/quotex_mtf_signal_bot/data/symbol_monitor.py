from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from quotex_mtf_signal_bot.data.mt5_adapter import MT5Adapter
from quotex_mtf_signal_bot.data.symbol_registry import SymbolRegistry


@dataclass(frozen=True, slots=True)
class SymbolSnapshot:
    symbols: tuple[str, ...]


class MajorFXMonitor:
    """Resolve and maintain broker-specific names of major FX pairs."""

    def __init__(self, adapter: MT5Adapter) -> None:
        self.adapter = adapter
        self.registry = SymbolRegistry.from_mt5(adapter)

    def refresh(self) -> SymbolSnapshot:
        self.registry = SymbolRegistry.from_mt5(self.adapter)
        return SymbolSnapshot(self.registry.symbols)

    def symbols(self) -> Iterable[str]:
        return self.registry.symbols
