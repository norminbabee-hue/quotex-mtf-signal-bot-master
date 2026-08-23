from __future__ import annotations

from decimal import Decimal
from typing import Callable

from quotex_mtf_signal_bot.data.mt5_adapter import MT5Adapter, Tick
from quotex_mtf_signal_bot.live.audit import SignalAuditLog
from quotex_mtf_signal_bot.live.multi_pair_scanner import MultiPairScanner
from quotex_mtf_signal_bot.signals.guard import SignalGuard
from quotex_mtf_signal_bot.signals.model import Signal


class MultiPairBot:
    """Apply guard, audit and publishing to signals from every monitored FX pair."""

    def __init__(
        self,
        adapter: MT5Adapter,
        publisher,
        guard: SignalGuard | None = None,
        spread_provider: Callable[[Tick], Decimal] | None = None,
        audit: SignalAuditLog | None = None,
        *,
        server_offset_seconds: int | float = 6 * 60 * 60,
    ) -> None:
        self.adapter = adapter
        self.publisher = publisher
        self.guard = guard or SignalGuard()
        self.spread_provider = spread_provider or (lambda tick: Decimal("0"))
        self.audit = audit or SignalAuditLog()
        self._last_tick: Tick | None = None
        self.scanner = MultiPairScanner(
            adapter,
            self._handle_signal,
            server_offset_seconds=server_offset_seconds,
        )

    @property
    def symbols(self) -> tuple[str, ...]:
        return tuple(self.scanner.registry.symbols)

    def refresh_symbols(self) -> tuple[str, ...]:
        snapshot = self.scanner.refresh()
        self.audit.record(
            "symbols_refreshed", "FX", count=len(snapshot.symbols), symbols=list(snapshot.symbols)
        )
        return snapshot.symbols

    def warm_up(self, history_count: int = 200) -> None:
        self.scanner.warm_up(history_count)
        self.audit.record(
            "multi_pair_warm_up_complete",
            "FX",
            history_count=history_count,
            pair_count=len(self.symbols),
        )

    def on_tick(self, tick: Tick) -> None:
        self._last_tick = tick
        self.scanner.on_tick(tick)

    def _handle_signal(self, signal: Signal) -> None:
        tick = self._last_tick
        spread = self.spread_provider(tick) if tick is not None else Decimal("0")
        result = self.guard.check(signal, spread_points=spread)
        self.audit.signal(signal, approved=result.allowed, reason=result.reason)
        if result.allowed:
            self.publisher.publish(signal)
        elif signal.next_candle_direction in {"CALL", "PUT"} and hasattr(self.publisher, "publish_prediction"):
            self.publisher.publish_prediction(signal, rejection_reason=result.reason)
