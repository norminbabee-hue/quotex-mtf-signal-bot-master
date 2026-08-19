from __future__ import annotations

from decimal import Decimal
from typing import Callable

from quotex_mtf_signal_bot.data.live_candles import LiveCandleManager
from quotex_mtf_signal_bot.data.mt5_adapter import MT5Adapter, Tick
from quotex_mtf_signal_bot.live.mtf_signal_service import LiveMTFSignalService
from quotex_mtf_signal_bot.signals.guard import SignalGuard
from quotex_mtf_signal_bot.telegram.publisher import TelegramPublisher


class LiveBot:
    """Orchestrate MT5 -> MTF analysis -> guard -> Telegram delivery."""

    def __init__(
        self,
        adapter: MT5Adapter,
        symbol: str,
        publisher: TelegramPublisher,
        guard: SignalGuard | None = None,
        spread_provider: Callable[[Tick], Decimal] | None = None,
    ) -> None:
        self.manager = LiveCandleManager(adapter, symbol)
        self.analysis = LiveMTFSignalService(symbol)
        self.publisher = publisher
        self.guard = guard or SignalGuard()
        self.spread_provider = spread_provider or (lambda tick: Decimal("0"))

    def on_tick(self, tick: Tick) -> None:
        for event in self.manager.on_tick(tick):
            signal = self.analysis.on_closed_candle(event.candle)
            if signal is None:
                continue
            result = self.guard.check(signal, spread_points=self.spread_provider(tick))
            if result.allowed:
                self.publisher.publish(signal)

    def warm_up(self, history_count: int = 200) -> None:
        self.manager.seed_history(history_count)
