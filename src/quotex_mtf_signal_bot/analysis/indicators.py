from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from quotex_mtf_signal_bot.core.models import Candle


@dataclass(frozen=True, slots=True)
class IndicatorSnapshot:
    ema_fast: Decimal | None
    ema_slow: Decimal | None
    rsi: Decimal | None
    macd: Decimal | None
    macd_signal: Decimal | None
    macd_histogram: Decimal | None


def _closes(candles: list[Candle]) -> list[Decimal]:
    if not candles:
        raise ValueError("At least one candle is required")
    return [Decimal(c.close) for c in candles]


def ema(candles: list[Candle], period: int) -> Decimal | None:
    if period <= 0:
        raise ValueError("EMA period must be positive")
    values = _closes(candles)
    if len(values) < period:
        return None
    current = sum(values[:period], Decimal(0)) / Decimal(period)
    alpha = Decimal(2) / Decimal(period + 1)
    for price in values[period:]:
        current = (price * alpha) + (current * (Decimal(1) - alpha))
    return current


def rsi(candles: list[Candle], period: int = 14) -> Decimal | None:
    if period <= 0:
        raise ValueError("RSI period must be positive")
    values = _closes(candles)
    if len(values) <= period:
        return None

    gains: list[Decimal] = []
    losses: list[Decimal] = []
    for previous, current in zip(values, values[1:]):
        change = current - previous
        gains.append(max(change, Decimal(0)))
        losses.append(max(-change, Decimal(0)))

    avg_gain = sum(gains[:period], Decimal(0)) / Decimal(period)
    avg_loss = sum(losses[:period], Decimal(0)) / Decimal(period)
    for gain, loss in zip(gains[period:], losses[period:]):
        avg_gain = ((avg_gain * Decimal(period - 1)) + gain) / Decimal(period)
        avg_loss = ((avg_loss * Decimal(period - 1)) + loss) / Decimal(period)

    if avg_loss == 0:
        return Decimal(100) if avg_gain > 0 else Decimal(50)
    rs = avg_gain / avg_loss
    return Decimal(100) - (Decimal(100) / (Decimal(1) + rs))


def _ema_values(values: list[Decimal], period: int) -> list[Decimal]:
    if period <= 0:
        raise ValueError("EMA period must be positive")
    if len(values) < period:
        return []
    current = sum(values[:period], Decimal(0)) / Decimal(period)
    result = [current]
    alpha = Decimal(2) / Decimal(period + 1)
    for price in values[period:]:
        current = (price * alpha) + (current * (Decimal(1) - alpha))
        result.append(current)
    return result


def macd(
    candles: list[Candle],
    fast_period: int = 12,
    slow_period: int = 26,
    signal_period: int = 9,
) -> tuple[Decimal | None, Decimal | None, Decimal | None]:
    if not (0 < fast_period < slow_period):
        raise ValueError("MACD requires 0 < fast_period < slow_period")
    if signal_period <= 0:
        raise ValueError("MACD signal period must be positive")

    values = _closes(candles)
    if len(values) < slow_period:
        return None, None, None

    slow_series = _ema_values(values, slow_period)
    fast_series = _ema_values(values, fast_period)
    offset = slow_period - fast_period
    fast_aligned = fast_series[offset:]
    macd_series = [fast - slow for fast, slow in zip(fast_aligned, slow_series)]
    if len(macd_series) < signal_period:
        return macd_series[-1], None, None

    signal_series = _ema_values(macd_series, signal_period)
    signal_value = signal_series[-1]
    macd_value = macd_series[-1]
    histogram = macd_value - signal_value
    return macd_value, signal_value, histogram


def snapshot(candles: list[Candle]) -> IndicatorSnapshot:
    macd_value, signal_value, histogram = macd(candles)
    return IndicatorSnapshot(
        ema_fast=ema(candles, 9),
        ema_slow=ema(candles, 21),
        rsi=rsi(candles, 14),
        macd=macd_value,
        macd_signal=signal_value,
        macd_histogram=histogram,
    )
