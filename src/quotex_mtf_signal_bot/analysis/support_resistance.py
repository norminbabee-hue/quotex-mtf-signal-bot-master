from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from quotex_mtf_signal_bot.core.models import Candle


@dataclass(frozen=True, slots=True)
class Level:
    price: Decimal
    kind: str
    touches: int
    distance: Decimal


@dataclass(frozen=True, slots=True)
class SupportResistanceSnapshot:
    supports: tuple[Level, ...]
    resistances: tuple[Level, ...]


def _is_swing_low(candles: list[Candle], index: int, strength: int) -> bool:
    center = candles[index].low
    left = candles[index - strength : index]
    right = candles[index + 1 : index + strength + 1]
    return all(center <= c.low for c in (*left, *right))


def _is_swing_high(candles: list[Candle], index: int, strength: int) -> bool:
    center = candles[index].high
    left = candles[index - strength : index]
    right = candles[index + 1 : index + strength + 1]
    return all(center >= c.high for c in (*left, *right))


def _cluster(values: list[Decimal], tolerance: Decimal) -> list[tuple[Decimal, int]]:
    clusters: list[list[Decimal]] = []
    for value in sorted(values):
        for cluster in clusters:
            center = sum(cluster, Decimal(0)) / Decimal(len(cluster))
            if abs(value - center) <= tolerance:
                cluster.append(value)
                break
        else:
            clusters.append([value])
    return [
        (sum(cluster, Decimal(0)) / Decimal(len(cluster)), len(cluster))
        for cluster in clusters
    ]


def find_levels(
    candles: list[Candle],
    *,
    swing_strength: int = 2,
    tolerance: Decimal = Decimal("0.00030"),
    max_levels: int = 5,
) -> SupportResistanceSnapshot:
    if swing_strength < 1:
        raise ValueError("Swing strength must be positive")
    if len(candles) < (swing_strength * 2 + 1):
        return SupportResistanceSnapshot((), ())

    lows: list[Decimal] = []
    highs: list[Decimal] = []
    for index in range(swing_strength, len(candles) - swing_strength):
        if _is_swing_low(candles, index, swing_strength):
            lows.append(candles[index].low)
        if _is_swing_high(candles, index, swing_strength):
            highs.append(candles[index].high)

    current = candles[-1].close
    supports = [
        (price, touches)
        for price, touches in _cluster(lows, tolerance)
        if price <= current
    ]
    resistances = [
        (price, touches)
        for price, touches in _cluster(highs, tolerance)
        if price >= current
    ]

    supports.sort(key=lambda item: (item[1], -abs(current - item[0])), reverse=True)
    resistances.sort(key=lambda item: (item[1], -abs(current - item[0])), reverse=True)

    return SupportResistanceSnapshot(
        supports=tuple(
            Level(price, "support", touches, abs(current - price))
            for price, touches in supports[:max_levels]
        ),
        resistances=tuple(
            Level(price, "resistance", touches, abs(current - price))
            for price, touches in resistances[:max_levels]
        ),
    )
