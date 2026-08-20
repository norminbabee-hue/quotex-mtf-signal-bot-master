from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from quotex_mtf_signal_bot.data.live_candles import LiveCandleManager
from quotex_mtf_signal_bot.data.mt5_adapter import MarketDataAdapter, Tick
from quotex_mtf_signal_bot.data.symbol_monitor import MajorFXMonitor
from quotex_mtf_signal_bot.signals.model import Signal
from quotex_mtf_signal_bot.live.mtf_signal_service import LiveMTFSignalService


@dataclass(frozen=True, slots=True)
class ScannerSnapshot:
    symbols: tuple[str, ...]


class MultiPairScanner:
    """Run the same M1/M5/M15 signal pipeline independently for each FX pair."""

    def __init__(
        self,
        adapter: MarketDataAdapter,
        on_signal: Callable[[Signal], None],
    ) -> None:
        self.adapter = adapter
        self.on_signal = on_signal
        self.monitor = MajorFXMonitor(adapter)
        self.managers: dict[str, LiveCandleManager] = {}
        self.services: dict[str, LiveMTFSignalService] = {}
        self.refresh()

    def refresh(self) -> ScannerSnapshot:
        symbols = tuple(self.monitor.refresh().symbols)
        self.managers = {symbol: LiveCandleManager(self.adapter, symbol) for symbol in symbols}
        self.services = {symbol: LiveMTFSignalService(symbol) for symbol in symbols}
        return ScannerSnapshot(symbols)

    def warm_up(self, history_count: int = 200) -> None:
        for manager in self.managers.values():
            manager.seed_history(history_count)

    def on_tick(self, tick: Tick) -> None:
        manager = self.managers.get(tick.symbol)
        service = self.services.get(tick.symbol)
        if manager is None or service is None:
            return
        for event in manager.on_tick(tick):
            signal = service.on_closed_candle(event.candle)
            if signal is not None:
                self.on_signal(signal)
