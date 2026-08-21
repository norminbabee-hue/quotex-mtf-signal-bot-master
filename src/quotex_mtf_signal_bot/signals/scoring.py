from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from quotex_mtf_signal_bot.analysis.mtf import MTFAnalysis
from quotex_mtf_signal_bot.core.models import Timeframe


@dataclass(frozen=True, slots=True)
class SignalScore:
    direction: str
    score: int
    confidence: Decimal
    reasons: tuple[str, ...]


MIN_ALIGNMENT_SCORE = 12
MIN_ENTRY_BODY_RATIO = Decimal("0.45")
RSI_LONG_MAX = Decimal("70")
RSI_SHORT_MIN = Decimal("30")
MIN_OPPOSING_LEVEL_DISTANCE = Decimal("0.0005")  # 0.05% of price


def _reject_near_opposing_level(entry, direction: str) -> bool:
    """Avoid entries with little room before the nearest opposing level."""
    price = entry.levels.supports if direction == "CALL" else entry.levels.resistances
    if not price:
        return False

    nearest = min(price, key=lambda level: level.distance)
    if nearest.distance <= 0:
        return True

    current_price = nearest.price + nearest.distance
    if current_price == 0:
        return False
    relative_distance = nearest.distance / current_price
    return relative_distance < MIN_OPPOSING_LEVEL_DISTANCE


def score_mtf(analysis: MTFAnalysis) -> SignalScore:
    """Return a deliberately selective live-signal score.

    Confidence is a model-strength value, not a statistical win probability.
    A signal is emitted only when M15 context, M5 confirmation and M1 entry
    direction agree and the M1 candle/RSI/level filters do not contradict it.
    """
    required = (Timeframe.M1, Timeframe.M5, Timeframe.M15)
    if any(timeframe not in analysis.analyses for timeframe in required):
        return SignalScore("NO_SIGNAL", 0, Decimal(0), ("Missing M1/M5/M15 analysis",))

    entry = analysis.analyses[Timeframe.M1]
    confirmation = analysis.analyses[Timeframe.M5]
    context = analysis.analyses[Timeframe.M15]

    if analysis.alignment not in {"bullish", "bearish"}:
        return SignalScore("NO_SIGNAL", 0, Decimal(0), ("MTF alignment is insufficient",))

    direction = "CALL" if analysis.alignment == "bullish" else "PUT"
    expected_trend = analysis.alignment

    # Hard gate: all three timeframes must point in the same direction.
    if any(item.trend != expected_trend for item in (context, confirmation, entry)):
        return SignalScore("NO_SIGNAL", 0, Decimal(0), ("M15/M5/M1 trend confirmation is incomplete",))

    points = max(analysis.bullish_score, analysis.bearish_score)
    reasons: list[str] = [f"MTF alignment: {analysis.alignment}"]
    reasons.extend(("M15 context confirms", "M5 confirms", "M1 entry trend confirms"))
    points += 6

    indicators = entry.indicators
    action = entry.price_action

    # Avoid chasing an already extreme RSI reading.
    if indicators.rsi is not None:
        if direction == "CALL" and indicators.rsi >= RSI_LONG_MAX:
            return SignalScore("NO_SIGNAL", 0, Decimal(0), ("RSI is too extended for CALL",))
        if direction == "PUT" and indicators.rsi <= RSI_SHORT_MIN:
            return SignalScore("NO_SIGNAL", 0, Decimal(0), ("RSI is too extended for PUT",))
        if (direction == "CALL" and indicators.rsi >= Decimal("55")) or (
            direction == "PUT" and indicators.rsi <= Decimal("45")
        ):
            points += 1
            reasons.append("RSI supports direction")

    if indicators.macd_histogram is not None:
        macd_agrees = (
            direction == "CALL" and indicators.macd_histogram > 0
        ) or (
            direction == "PUT" and indicators.macd_histogram < 0
        )
        if not macd_agrees:
            return SignalScore("NO_SIGNAL", 0, Decimal(0), ("MACD does not confirm direction",))
        points += 1
        reasons.append("MACD confirms direction")

    # M1 entry candle must show actual directional intent. A flat/doji candle
    # is not good enough for a short-expiry signal.
    current = action.current
    candle_agrees = (
        direction == "CALL"
        and current.bullish
        and current.body_ratio >= MIN_ENTRY_BODY_RATIO
    ) or (
        direction == "PUT"
        and current.bearish
        and current.body_ratio >= MIN_ENTRY_BODY_RATIO
    )
    pattern_agrees = (
        direction == "CALL"
        and (action.bullish_engulfing or action.bullish_rejection)
    ) or (
        direction == "PUT"
        and (action.bearish_engulfing or action.bearish_rejection)
    )

    if not (candle_agrees or pattern_agrees):
        return SignalScore("NO_SIGNAL", 0, Decimal(0), ("M1 entry candle has no strong confirmation",))

    points += 2
    reasons.append("M1 price action confirms entry")

    if _reject_near_opposing_level(entry, direction):
        return SignalScore("NO_SIGNAL", 0, Decimal(0), ("Too close to opposing support/resistance",))

    points += 1
    reasons.append("Adequate room from opposing level")

    if points < MIN_ALIGNMENT_SCORE:
        return SignalScore("NO_SIGNAL", 0, Decimal(0), ("Signal score below live threshold",))

    # Deliberately conservative model-strength scale. This must not be
    # presented as a 95% probability of winning.
    confidence = min(Decimal(92), Decimal(70) + Decimal(max(0, points - MIN_ALIGNMENT_SCORE) * 3))
    return SignalScore(direction, points, confidence, tuple(reasons))
