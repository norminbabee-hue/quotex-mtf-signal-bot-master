from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from quotex_mtf_signal_bot.core.models import Candle


@dataclass(frozen=True, slots=True)
class CandleFeatures:
    bullish: bool
    bearish: bool
    body: Decimal
    upper_wick: Decimal
    lower_wick: Decimal
    range: Decimal
    body_ratio: Decimal
    upper_wick_ratio: Decimal
    lower_wick_ratio: Decimal


@dataclass(frozen=True, slots=True)
class PriceActionSnapshot:
    current: CandleFeatures
    previous: CandleFeatures | None
    bullish_engulfing: bool
    bearish_engulfing: bool
    bullish_rejection: bool
    bearish_rejection: bool
    momentum_bullish: bool
    momentum_bearish: bool


def features(candle: Candle) -> CandleFeatures:
    if candle.high < candle.low:
        raise ValueError("Candle high cannot be below low")
    candle_range = candle.high - candle.low
    body = abs(candle.close - candle.open)
    upper = candle.high - max(candle.open, candle.close)
    lower = min(candle.open, candle.close) - candle.low

    if candle_range == 0:
        return CandleFeatures(
            bullish=candle.close > candle.open,
            bearish=candle.close < candle.open,
            body=body,
            upper_wick=upper,
            lower_wick=lower,
            range=candle_range,
            body_ratio=Decimal(0),
            upper_wick_ratio=Decimal(0),
            lower_wick_ratio=Decimal(0),
        )

    return CandleFeatures(
        bullish=candle.close > candle.open,
        bearish=candle.close < candle.open,
        body=body,
        upper_wick=upper,
        lower_wick=lower,
        range=candle_range,
        body_ratio=body / candle_range,
        upper_wick_ratio=upper / candle_range,
        lower_wick_ratio=lower / candle_range,
    )


def _engulfing(previous: Candle, current: Candle) -> tuple[bool, bool]:
    prev = features(previous)
    cur = features(current)
    bullish = (
        prev.bearish
        and cur.bullish
        and current.open <= previous.close
        and current.close >= previous.open
    )
    bearish = (
        prev.bullish
        and cur.bearish
        and current.open >= previous.close
        and current.close <= previous.open
    )
    return bullish, bearish


def snapshot(candles: list[Candle]) -> PriceActionSnapshot:
    if not candles:
        raise ValueError("At least one candle is required")

    current = features(candles[-1])
    previous = features(candles[-2]) if len(candles) >= 2 else None
    bullish_engulfing = bearish_engulfing = False
    if len(candles) >= 2:
        bullish_engulfing, bearish_engulfing = _engulfing(candles[-2], candles[-1])

    bullish_rejection = (
        current.lower_wick_ratio >= Decimal("0.45")
        and current.body_ratio >= Decimal("0.20")
        and current.upper_wick_ratio <= Decimal("0.25")
    )
    bearish_rejection = (
        current.upper_wick_ratio >= Decimal("0.45")
        and current.body_ratio >= Decimal("0.20")
        and current.lower_wick_ratio <= Decimal("0.25")
    )

    momentum_bullish = current.bullish and current.body_ratio >= Decimal("0.60")
    momentum_bearish = current.bearish and current.body_ratio >= Decimal("0.60")

    return PriceActionSnapshot(
        current=current,
        previous=previous,
        bullish_engulfing=bullish_engulfing,
        bearish_engulfing=bearish_engulfing,
        bullish_rejection=bullish_rejection,
        bearish_rejection=bearish_rejection,
        momentum_bullish=momentum_bullish,
        momentum_bearish=momentum_bearish,
    )
