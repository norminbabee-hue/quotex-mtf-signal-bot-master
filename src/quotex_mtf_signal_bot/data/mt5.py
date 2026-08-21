from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import pandas as pd

from quotex_mtf_signal_bot.core.models import Candle, Tick, Timeframe


_MT5_TIMEFRAME_NAMES = {
    Timeframe.M1: "TIMEFRAME_M1",
    Timeframe.M5: "TIMEFRAME_M5",
    Timeframe.M15: "TIMEFRAME_M15",
}


class MT5DataSource:
    """Thin MT5 adapter; strategy code stays independent of MetaTrader5."""

    def __init__(self, mt5_module: Any) -> None:
        self._mt5 = mt5_module

    def connect(self, **kwargs: Any) -> bool:
        return bool(self._mt5.initialize(**kwargs))

    def shutdown(self) -> None:
        self._mt5.shutdown()

    def _resolve_symbol(self, symbol: str) -> str:
        """Resolve a dashboard symbol to the broker's actual MT5 symbol.

        Brokers such as Exness commonly expose symbols with suffixes, e.g.
        EURUSD -> EURUSDm and USDJPY -> USDJPYm. The dashboard keeps the
        broker-neutral names while this adapter resolves the real terminal name.
        """
        requested = symbol.strip()
        if not requested:
            raise ValueError("MT5 symbol cannot be empty")

        info = self._mt5.symbol_info(requested)
        if info is not None:
            self._mt5.symbol_select(requested, True)
            return requested

        symbols = self._mt5.symbols_get()
        if symbols:
            wanted = requested.upper()
            candidates = [
                item.name
                for item in symbols
                if str(item.name).upper().startswith(wanted)
            ]
            if candidates:
                resolved = min(candidates, key=lambda name: (len(name), name))
                self._mt5.symbol_select(resolved, True)
                return resolved

        raise RuntimeError(
            f"MT5 symbol not found: {requested}. "
            "Open the broker's Market Watch and make sure the symbol is available."
        )

    def tick(self, symbol: str) -> Tick:
        resolved_symbol = self._resolve_symbol(symbol)
        raw = self._mt5.symbol_info_tick(resolved_symbol)
        if raw is None:
            raise RuntimeError(f"No tick available for {symbol} (MT5 symbol: {resolved_symbol})")

        if hasattr(raw, "time_msc"):
            timestamp = datetime.fromtimestamp(int(raw.time_msc) / 1000, tz=timezone.utc)
        else:
            timestamp = datetime.fromtimestamp(int(raw.time), tz=timezone.utc)

        return Tick(
            symbol=symbol,
            timestamp_utc=timestamp,
            bid=Decimal(str(raw.bid)),
            ask=Decimal(str(raw.ask)),
        )

    def server_tick_time(self, symbol: str) -> datetime:
        return self.tick(symbol).timestamp_utc

    def candles(self, symbol: str, timeframe: Timeframe, count: int = 500) -> list[Candle]:
        resolved_symbol = self._resolve_symbol(symbol)
        mt5_tf = getattr(self._mt5, _MT5_TIMEFRAME_NAMES[timeframe])
        rows = self._mt5.copy_rates_from_pos(resolved_symbol, mt5_tf, 0, count)
        if rows is None or len(rows) == 0:
            raise RuntimeError(
                f"MT5 returned no rates for {symbol} {timeframe} "
                f"(MT5 symbol: {resolved_symbol})"
            )

        frame = pd.DataFrame(rows)
        required = {"time", "open", "high", "low", "close", "tick_volume"}
        missing = required.difference(frame.columns)
        if missing:
            raise RuntimeError(f"MT5 rates missing columns: {sorted(missing)}")

        return [
            Candle(
                symbol=symbol,
                timeframe=timeframe,
                timestamp_utc=datetime.fromtimestamp(int(row.time), tz=timezone.utc),
                open=Decimal(str(row.open)),
                high=Decimal(str(row.high)),
                low=Decimal(str(row.low)),
                close=Decimal(str(row.close)),
                tick_volume=int(row.tick_volume),
            )
            for row in frame.itertuples(index=False)
        ]
