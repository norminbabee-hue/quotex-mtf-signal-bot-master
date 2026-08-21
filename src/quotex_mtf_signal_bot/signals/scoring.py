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
    next_candle_direction: str | None = None


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


def _next_candle_prediction(analysis: MTFAnalysis) -> tuple[str, int, list[str]]:
    """Predict the next M1 candle from only information closed at entry time.

    This is intentionally separate from the higher-timeframe trend. The
    prediction combines M1 momentum/price action with M5/M15 context, so a
    bearish market can still produce an UP prediction when a strong bullish
    M1 reversal trigger is present, and vice versa.
    """
    m1 = analysis.analyses[Timeframe.M1]
    m5 = analysis.analyses[Timeframe.M5]
    m15 = analysis.analyses[Timeframe.M15]
    up = down = 0
    reasons: list[str] = []

    for item, weight in ((m15, 2), (m5, 2), (m1, 1)):
        if item.trend == "bullish":
            up += item.score * weight
        elif item.trend == "bearish":
            down += item.score * weight

    ind = m1.indicators
    pa = m1.price_action
    if ind.ema_fast is not None and ind.ema_slow is not None:
        if ind.ema_fast > ind.ema_slow:
            up += 2
            reasons.append("M1 EMA momentum points UP")
        elif ind.ema_fast < ind.ema_slow:
            down += 2
            reasons.append("M1 EMA momentum points DOWN")
    if ind.macd_histogram is not None:
        if ind.macd_histogram > 0:
            up += 2
            reasons.append("M1 MACD points UP")
        elif ind.macd_histogram < 0:
            down += 2
            reasons.append("M1 MACD points DOWN")
    if ind.rsi is not None:
        if ind.rsi >= RSI_LONG_CONFIRM and ind.rsi < RSI_LONG_MAX:
            up += 1
            reasons.append("RSI supports UP")
        elif ind.rsi <= RSI_SHORT_CONFIRM and ind.rsi > RSI_SHORT_MIN:
            down += 1
            reasons.append("RSI supports DOWN")
    if pa.bullish_engulfing or pa.bullish_rejection or pa.momentum_bullish:
        up += 3
        reasons.append("Fresh bullish M1 price action")
    if pa.bearish_engulfing or pa.bearish_rejection or pa.momentum_bearish:
        down += 3
        reasons.append("Fresh bearish M1 price action")

    return ("CALL", up, reasons) if up > down else ("PUT", down, reasons)


def score_mtf(analysis: MTFAnalysis) -> SignalScore:
    """Score a live M1 entry using closed M1/M5/M15 confirmation."""
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

    if context.trend != expected_trend or confirmation.trend != expected_trend:
        return SignalScore("NO_SIGNAL", 0, Decimal(0), ("M15/M5 trend confirmation is incomplete",))
    if entry.trend not in {expected_trend, "neutral"}:
        return SignalScore("NO_SIGNAL", 0, Decimal(0), ("M1 trend conflicts with M15/M5",))
    if context.score < MIN_M15_TREND_SCORE:
        return SignalScore("NO_SIGNAL", 0, Decimal(0), ("M15 context is not strong enough",))
    if confirmation.score < MIN_M5_TREND_SCORE:
        return SignalScore("NO_SIGNAL", 0, Decimal(0), ("M5 confirmation is not strong enough",))
    if entry.trend == expected_trend and entry.score < MIN_M1_TREND_SCORE:
        return SignalScore("NO_SIGNAL", 0, Decimal(0), ("M1 trend evidence is too weak",))

    predicted_direction, prediction_score, prediction_reasons = _next_candle_prediction(analysis)
    # The actual signal must agree with the next-candle model. This prevents
    # simply echoing M15/M5 direction when M1 predicts a reversal.
    if predicted_direction != direction:
        return SignalScore("NO_SIGNAL", 0, Decimal(0), ("Next M1 candle prediction conflicts with MTF context",))

    effective_entry_score = entry.score if entry.trend == expected_trend else 2
    points = context.score + confirmation.score + effective_entry_score
    reasons: list[str] = [
        f"MTF alignment: {analysis.alignment}",
        "M15 context confirms",
        "M5 confirms",
        f"Next M1 candle: {'UP' if predicted_direction == 'CALL' else 'DOWN'}",
    ]
    reasons.extend(prediction_reasons)
    if entry.trend == expected_trend:
        reasons.append("M1 entry trend confirms")
    else:
        reasons.append("M1 pullback with higher-timeframe trend intact")

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
    return SignalScore(direction, points, confidence, tuple(reasons), predicted_direction)
