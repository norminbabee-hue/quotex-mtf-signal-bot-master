from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Protocol


@dataclass(frozen=True, slots=True)
class Tick:
    symbol: str
    timestamp_utc: datetime
    bid: Decimal
    ask: Decimal


@dataclass(frozen=True, slots=True)
class MT5Bar:
    symbol: str
    timeframe: str
    timestamp_utc: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    tick_volume: int


class MarketDataAdapter(Protocol):
    def latest_tick(self, symbol: str) -> Tick: ...
    def bars(self, symbol: str, timeframe: str, count: int) -> list[MT5Bar]: ...


class MT5Adapter:
    """Thin MT5 integration boundary."""

    def __init__(self, *, login: int | None = None, password: str | None = None,
                 server: str | None = None, path: str | None = None) -> None:
        try:
            import MetaTrader5 as mt5
        except ImportError as exc:
            raise RuntimeError("Install the MetaTrader5 Python package before using live MT5 data") from exc
        self._mt5 = mt5
        kwargs = {"path": path} if path else {}
        if not mt5.initialize(**kwargs):
            raise RuntimeError(f"MT5 initialize failed: {mt5.last_error()}")
        if login is not None:
            if not password or not server:
                raise ValueError("login requires password and server")
            if not mt5.login(login, password=password, server=server):
                raise RuntimeError(f"MT5 login failed: {mt5.last_error()}")

    def close(self) -> None:
        self._mt5.shutdown()

    def symbols(self) -> list[str]:
        raw = self._mt5.symbols_get()
        if raw is None:
            raise RuntimeError(f"MT5 symbols_get failed: {self._mt5.last_error()}")
        return [item.name for item in raw]

    @staticmethod
    def _utc(timestamp_seconds: int | float) -> datetime:
        return datetime.fromtimestamp(timestamp_seconds, tz=timezone.utc)

    def latest_tick(self, symbol: str) -> Tick:
        raw = self._mt5.symbol_info_tick(symbol)
        if raw is None:
            raise RuntimeError(f"No MT5 tick available for {symbol}")
        return Tick(symbol, self._utc(raw.time), Decimal(str(raw.bid)), Decimal(str(raw.ask)))

    def bars(self, symbol: str, timeframe: str, count: int) -> list[MT5Bar]:
        tf = getattr(self._mt5, f"TIMEFRAME_{timeframe}", None)
        if tf is None:
            raise ValueError(f"Unsupported MT5 timeframe: {timeframe}")
        raw = self._mt5.copy_rates_from_pos(symbol, tf, 0, count)
        if raw is None:
            raise RuntimeError(f"No MT5 bars available for {symbol}/{timeframe}: {self._mt5.last_error()}")
        return [
            MT5Bar(
                symbol=symbol, timeframe=timeframe,
                timestamp_utc=self._utc(row["time"]),
                open=Decimal(str(row["open"])), high=Decimal(str(row["high"])),
                low=Decimal(str(row["low"])), close=Decimal(str(row["close"])),
                tick_volume=int(row["tick_volume"]),
            ) for row in raw
        ]
