from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Iterable

from quotex_mtf_signal_bot.data.live_candles import LiveCandleManager
from quotex_mtf_signal_bot.data.mt5_adapter import MarketDataAdapter, Tick
from quotex_mtf_signal_bot.data.symbol_registry import SymbolRegistry
from quotex_mtf_signal_bot.signals.model import Signal
from quotex_mtf_signal_bot.live.mtf_signal_service import LiveMTFSignalService
from quotex_mtf_signal_bot.core.models import Timeframe


@dataclass(frozen=True, slots=True)
class ScannerSnapshot:
    symbols: tuple[str, ...]


class MultiPairScanner:
    """Run the closed-candle M1/M5/M15 pipeline for every selected FX pair."""

    _TIMEFRAME_PRIORITY = {900: 0, 300: 1, 60: 2}

    def __init__(
        self,
        adapter: MarketDataAdapter,
        on_signal: Callable[[Signal], None],
        *,
        server_offset_seconds: int | float = 6 * 60 * 60,
        candidates: Iterable[str] | None = None,
    ) -> None:
        self.adapter = adapter
        self.on_signal = on_signal
        self.server_offset_seconds = server_offset_seconds
        self.candidates = tuple(candidates) if candidates is not None else None
        self.registry = SymbolRegistry.from_mt5(adapter, candidates=self.candidates)
        self.managers: dict[str, LiveCandleManager] = {}
        self.services: dict[str, LiveMTFSignalService] = {}
        self._broker_symbols: dict[str, str] = {}
        self.refresh()

    def refresh(self) -> ScannerSnapshot:
        self.registry = SymbolRegistry.from_mt5(self.adapter, candidates=self.candidates)
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

    def broker_symbol(self, canonical: str) -> str:
        return self._broker_symbols[canonical]

    def broker_symbols(self) -> dict[str, str]:
        return dict(self._broker_symbols)

    def warm_up(self, history_count: int = 200) -> None:
        """Seed every matched pair; disable only pairs whose MT5 history is unusable."""
        valid: list[str] = []
        failed: list[tuple[str, str]] = []
        for symbol, manager in list(self.managers.items()):
            try:
                history = manager.seed_history(history_count)
                self.services[symbol].seed_history(history)
                valid.append(symbol)
            except Exception as exc:
                failed.append((symbol, str(exc)))

        if failed:
            for symbol, reason in failed:
                print(f"Skipping {symbol}: {reason}")

        if not valid:
            raise RuntimeError("No configured Quotex pair has enough MT5 M1/M5/M15 history")

        if len(valid) != len(self.registry.symbols):
            broker_pairs = tuple((symbol, self._broker_symbols[symbol]) for symbol in valid)
            self.registry = SymbolRegistry(tuple(valid), broker_pairs)
            self._broker_symbols = dict(broker_pairs)
            self.managers = {symbol: self.managers[symbol] for symbol in valid}
            self.services = {symbol: self.services[symbol] for symbol in valid}

    def preview_candidates(self, now_utc: datetime, lead_seconds: int = 45) -> list[Signal]:
        """Return actionable candidates whose next candle opens in the lead window.

        Every pair is evaluated internally, but only actionable candidates are
        returned. The caller ranks them and publishes at most one signal per
        target window.
        """
        now_utc = now_utc.astimezone(timezone.utc)
        candidates: list[Signal] = []
        for symbol, service in self.services.items():
            for timeframe in (Timeframe.M1, Timeframe.M5, Timeframe.M15):
                seconds = timeframe.seconds
                epoch = int(now_utc.timestamp())
                next_epoch = ((epoch // seconds) + 1) * seconds
                entry = datetime.fromtimestamp(next_epoch, tz=timezone.utc)
                seconds_to_entry = (entry - now_utc).total_seconds()
                if lead_seconds - 10 <= seconds_to_entry <= lead_seconds + 10:
                    signal = service.preview_next_signal(timeframe, entry)
                    if signal is not None and float(signal.confidence) > 0:
                        candidates.append(signal)
        return candidates

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

        events = manager.on_tick(tick)
        events.sort(key=lambda event: self._TIMEFRAME_PRIORITY[event.candle.timeframe_seconds])
        for event in events:
            signals = service.on_closed_candle(event.candle)
            for signal in signals:
                self.on_signal(signal)
