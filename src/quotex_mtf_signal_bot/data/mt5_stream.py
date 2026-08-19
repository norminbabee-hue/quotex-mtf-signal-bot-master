from __future__ import annotations

from collections.abc import Iterator, Sequence
from datetime import datetime, timezone
from decimal import Decimal

from quotex_mtf_signal_bot.core.models import Tick


class MT5Stream:
    """Thin, testable adapter around the MetaTrader5 tick API."""

    def __init__(self, mt5_module) -> None:
        self._mt5 = mt5_module

    def connect(self) -> None:
        if not self._mt5.initialize():
            raise RuntimeError(f"MT5 initialize failed: {self._mt5.last_error()}")

    def close(self) -> None:
        self._mt5.shutdown()

    def subscribe(self, symbols: Sequence[str]) -> None:
        for symbol in symbols:
            if not self._mt5.symbol_select(symbol, True):
                raise RuntimeError(f"Unable to select MT5 symbol: {symbol}")

    def poll(self, symbol: str) -> Tick | None:
        raw = self._mt5.symbol_info_tick(symbol)
        if raw is None:
            return None

        timestamp = getattr(raw, "time_msc", None)
        if timestamp is None:
            timestamp = int(raw.time) * 1000

        return Tick(
            symbol=symbol,
            timestamp_utc=datetime.fromtimestamp(
                timestamp / 1000, tz=timezone.utc
            ),
            bid=Decimal(str(raw.bid)),
            ask=Decimal(str(raw.ask)),
        )

    def stream(
        self, symbol: str, *, interval_seconds: float = 0.2
    ) -> Iterator[Tick]:
        """Yield ticks by polling MT5.

        The caller owns scheduling and can stop the iterator. Duplicate ticks
        are suppressed using timestamp and bid/ask values.
        """
        import time

        last_key = None
        while True:
            current = self.poll(symbol)
            if current is not None:
                key = (current.timestamp_utc, current.bid, current.ask)
                if key != last_key:
                    last_key = key
                    yield current
            time.sleep(interval_seconds)
