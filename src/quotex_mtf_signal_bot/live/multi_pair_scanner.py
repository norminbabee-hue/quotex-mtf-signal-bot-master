from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from quotex_mtf_signal_bot.data.live_candles import LiveCandleManager
from quotex_mtf_signal_bot.data.mt5_adapter import MarketDataAdapter, Tick
from quotex_mtf_signal_bot.data.symbol_registry import SymbolRegistry
from quotex_mtf_signal_bot.signals.model import Signal
from quotex_mtf_signal_bot.live.mtf_signal_service import LiveMTFSignalService


@dataclass(frozen=True, slots=True)
class ScannerSnapshot:
    symbols: tuple[str, ...]


class MultiPairScanner:
    """Run the closed-candle M1/M5/M15 pipeline for every canonical FX pair."""

    def __init__(
        self,
        adapter: MarketDataAdapter,
        on_signal: Callable[[Signal], None],
        *,
        server_offset_seconds: int | float = 6 * 60 * 60,
    ) -> None:
        self.adapter = adapter
        self.on_signal = on_signal
        self.server_offset_seconds = server_offset_seconds
        self.registry = SymbolRegistry.from_mt5(adapter)
        self.managers: dict[str, LiveCandleManager] = {}
        self.services: dict[str, LiveMTFSignalService] = {}
        self._broker_symbols: dict[str, str] = {}
        self.refresh()

    def refresh(self) -> ScannerSnapshot:
        self.registry = SymbolRegistry.from_mt5(self.adapter)
        symbols = self.registry.symbols
        self._broker_symbols = {symbol: self.registry.broker_symbol(symbol) for symbol in symbols}
        self.managers = {
            symbol: LiveCandleManager(
                self.adapter,
                self._broker_symbols[symbol],
                server_offset_seconds=self.server_offset_seconds,
            )
            for symbol in symbols
        }
        self.services = {symbol: LiveMTFSignalService(symbol) for symbol in symbols}
        return ScannerSnapshot(symbols)

    def warm_up(self, history_count: int = 200) -> None:
        for symbol, manager in self.managers.items():
            history = manager.seed_history(history_count)
            self.services[symbol].seed_history(history)

    def on_tick(self, tick: Tick) -> None:
        canonical = SymbolRegistry.canonical_symbol(tick.symbol)
        if canonical is None:
            return
        broker_symbol = self._broker_symbols.get(canonical)
        service = self.services.get(canonical)
        manager = self.managers.get(canonical)
        if broker_symbol is None or service is None or manager is None:
            return
        if tick.symbol != broker_symbol:
            return
        for event in manager.on_tick(tick):
            signal = service.on_closed_candle(event.candle)
            if signal is not None:
                self.on_signal(signal)
