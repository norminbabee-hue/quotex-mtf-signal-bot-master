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


# Quality-first threshold. Confidence is deliberately a model-strength score,
# not a claim that a trade has this probability of winning.
MIN_ALIGNMENT_SCORE = 12
MIN_M15_TREND_SCORE = 3
MIN_M5_TREND_SCORE = 3
MIN_M1_TREND_SCORE = 2
MIN_ENTRY_BODY_RATIO = Decimal("0.55")
MIN_TRIGGER_BODY_RATIO = Decimal("0.60")
RSI_LONG_MAX = Decimal("70")
RSI_SHORT_MIN = Decimal("30")
RSI_LONG_CONFIRM = Decimal("55")
RSI_SHORT_CONFIRM = Decimal("45")
MIN_OPPOSING_LEVEL_DISTANCE = Decimal("0.0005")


def _reject_near_opposing_level(entry, direction: str) -> bool:
    """Avoid entries with little room before the nearest opposing level."""
    levels = entry.levels.resistances if direction == "CALL" else entry.levels.supports
    if not levels:
        return False
    nearest = min(levels, key=lambda level: level.distance)
    if nearest.distance <= 0:
        return True
    current_price = nearest.price + nearest.distance
    if current_price == 0:
        return False
    return (nearest.distance / current_price) < MIN_OPPOSING_LEVEL_DISTANCE


def score_mtf(analysis: MTFAnalysis) -> SignalScore:
    """Score a live M1 entry using closed M1/M5/M15 confirmation.

    The scorer is intentionally selective. It does not lower its threshold just
    to increase the number of alerts, and it never treats confidence as a
    guaranteed win probability. This is especially important when scanning many
    pairs, because weak pairs should be filtered rather than forced into a trade.
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
    if any(item.trend != expected_trend for item in (context, confirmation, entry)):
        return SignalScore("NO_SIGNAL", 0, Decimal(0), ("M15/M5/M1 trend confirmation is incomplete",))
    if context.score < MIN_M15_TREND_SCORE:
        return SignalScore("NO_SIGNAL", 0, Decimal(0), ("M15 context is not strong enough",))
    if confirmation.score < MIN_M5_TREND_SCORE:
        return SignalScore("NO_SIGNAL", 0, Decimal(0), ("M5 confirmation is not strong enough",))
    if entry.score < MIN_M1_TREND_SCORE:
        return SignalScore("NO_SIGNAL", 0, Decimal(0), ("M1 trend evidence is too weak",))

    points = context.score + confirmation.score + entry.score
    reasons: list[str] = [f"MTF alignment: {analysis.alignment}", "M15 context confirms", "M5 confirms", "M1 entry trend confirms"]

    indicators = entry.indicators
    action = entry.price_action

    if indicators.rsi is not None:
        if direction == "CALL" and indicators.rsi >= RSI_LONG_MAX:
            return SignalScore("NO_SIGNAL", 0, Decimal(0), ("RSI is too extended for CALL",))
        if direction == "PUT" and indicators.rsi <= RSI_SHORT_MIN:
            return SignalScore("NO_SIGNAL", 0, Decimal(0), ("RSI is too extended for PUT",))
        if (direction == "CALL" and indicators.rsi >= RSI_LONG_CONFIRM) or (
            direction == "PUT" and indicators.rsi <= RSI_SHORT_CONFIRM
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

    current = action.current
    previous = action.previous
    candle_agrees = (
        direction == "CALL" and current.bullish and current.body_ratio >= MIN_ENTRY_BODY_RATIO
    ) or (
        direction == "PUT" and current.bearish and current.body_ratio >= MIN_ENTRY_BODY_RATIO
    )
    pattern_agrees = (
        direction == "CALL" and (action.bullish_engulfing or action.bullish_rejection)
    ) or (
        direction == "PUT" and (action.bearish_engulfing or action.bearish_rejection)
    )
    fresh_momentum = (
        previous is not None
        and current.body_ratio >= MIN_TRIGGER_BODY_RATIO
        and (
            (direction == "CALL" and current.bullish and not previous.bullish)
            or (direction == "PUT" and current.bearish and not previous.bearish)
        )
    )

    if not pattern_agrees and not fresh_momentum:
        return SignalScore("NO_SIGNAL", 0, Decimal(0), ("M1 has no fresh entry trigger",))
    if not candle_agrees and not pattern_agrees:
        return SignalScore("NO_SIGNAL", 0, Decimal(0), ("M1 entry candle has insufficient directional intent",))

    points += 2
    reasons.append("Fresh M1 price-action trigger")

    if _reject_near_opposing_level(entry, direction):
        return SignalScore("NO_SIGNAL", 0, Decimal(0), ("Too close to opposing support/resistance",))

    points += 1
    reasons.append("Adequate room from opposing level")

    if points < MIN_ALIGNMENT_SCORE:
        return SignalScore("NO_SIGNAL", 0, Decimal(0), ("Signal score below live threshold",))

    confidence = min(Decimal(90), Decimal(75) + Decimal(max(0, points - MIN_ALIGNMENT_SCORE) * 2))
    return SignalScore(direction, points, confidence, tuple(reasons))
