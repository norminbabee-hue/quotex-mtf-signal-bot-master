from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class Timeframe(StrEnum):
    M1 = "M1"
    M5 = "M5"
    M15 = "M15"

    @property
    def minutes(self) -> int:
        """Return the duration of this timeframe in minutes."""
        return {Timeframe.M1: 1, Timeframe.M5: 5, Timeframe.M15: 15}[self]


class SignalDirection(StrEnum):
    CALL = "CALL"
    PUT = "PUT"
    NONE = "NONE"


@dataclass(frozen=True, slots=True)
class Tick:
    symbol: str
    timestamp_utc: datetime
    bid: float
    ask: float


@dataclass(frozen=True, slots=True)
class Candle:
    symbol: str
    timeframe: Timeframe
    timestamp_utc: datetime
    open: float
    high: float
    low: float
    close: float
    tick_volume: int = 0

    @property
    def is_bullish(self) -> bool:
        return self.close > self.open

    @property
    def is_bearish(self) -> bool:
        return self.close < self.open


@dataclass(frozen=True, slots=True)
class ClockSnapshot:
    local_utc: datetime
    broker_utc: datetime
    offset_seconds: float


@dataclass(frozen=True, slots=True)
class Signal:
    symbol: str
    direction: SignalDirection
    expiry_minutes: int
    confidence: float
    generated_at_utc: datetime
    source_candle_time_utc: datetime
