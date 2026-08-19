from __future__ import annotations

from decimal import Decimal
from typing import Callable

from quotex_mtf_signal_bot.data.live_candles import LiveCandleManager
from quotex_mtf_signal_bot.data.mt5_adapter import MT5Adapter, Tick
from quotex_mtf_signal_bot.live.audit import SignalAuditLog
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
        audit: SignalAuditLog | None = None,
    ) -> None:
        self.manager = LiveCandleManager(adapter, symbol)
        self.analysis = LiveMTFSignalService(symbol)
        self.publisher = publisher
        self.guard = guard or SignalGuard()
        self.spread_provider = spread_provider or (lambda tick: Decimal("0"))
        self.audit = audit or SignalAuditLog()

    def on_tick(self, tick: Tick) -> None:
        for event in self.manager.on_tick(tick):
            self.audit.record(
                "candle_closed",
                event.candle.symbol,
                timeframe_seconds=event.candle.timeframe_seconds,
                open_time_utc=event.candle.open_time_utc.isoformat(),
                close_time_utc=event.candle.close_time_utc.isoformat(),
                tick_count=event.candle.tick_count,
            )
            signal = self.analysis.on_closed_candle(event.candle)
            if signal is None:
                continue
            spread = self.spread_provider(tick)
            result = self.guard.check(signal, spread_points=spread)
            self.audit.signal(signal, approved=result.allowed, reason=result.reason)
            if result.allowed:
                self.publisher.publish(signal)

    def warm_up(self, history_count: int = 200) -> None:
        self.manager.seed_history(history_count)
        self.audit.record("warm_up_complete", self.manager.symbol, history_count=history_count)
