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


MIN_ALIGNMENT_SCORE = 12
MIN_M15_TREND_SCORE = 3
MIN_M5_TREND_SCORE = 3
MIN_M1_TREND_SCORE = 2
MIN_ENTRY_BODY_RATIO = Decimal("0.50")
MIN_TRIGGER_BODY_RATIO = Decimal("0.55")
RSI_LONG_MAX = Decimal("72")
RSI_SHORT_MIN = Decimal("28")
RSI_LONG_CONFIRM = Decimal("55")
RSI_SHORT_CONFIRM = Decimal("45")
MIN_OPPOSING_LEVEL_DISTANCE = Decimal("0.0003")
MIN_PREDICTION_EDGE = 3


def _reject_near_opposing_level(entry, direction: str) -> bool:
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


def _prediction_weights(target: Timeframe) -> tuple[tuple[Timeframe, int], ...]:
    return tuple(
        (tf, 3 if tf == target else 2 if tf.minutes < target.minutes else 1)
        for tf in (Timeframe.M1, Timeframe.M5, Timeframe.M15)
    )


def _next_candle_prediction(analysis: MTFAnalysis, target: Timeframe) -> tuple[str, int, list[str]]:
    """Predict the next candle of the selected M1/M5/M15 timeframe."""
    target_analysis = analysis.analyses[target]
    up = down = 0
    reasons: list[str] = []

    for timeframe, weight in _prediction_weights(target):
        item = analysis.analyses[timeframe]
        if item.trend == "bullish":
            up += item.score * weight
        elif item.trend == "bearish":
            down += item.score * weight

    ind = target_analysis.indicators
    pa = target_analysis.price_action
    if ind.ema_fast is not None and ind.ema_slow is not None:
        if ind.ema_fast > ind.ema_slow:
            up += 2
            reasons.append(f"{target.value} EMA momentum points UP")
        elif ind.ema_fast < ind.ema_slow:
            down += 2
            reasons.append(f"{target.value} EMA momentum points DOWN")
    if ind.macd_histogram is not None:
        if ind.macd_histogram > 0:
            up += 1
            reasons.append(f"{target.value} MACD is positive")
        elif ind.macd_histogram < 0:
            down += 1
            reasons.append(f"{target.value} MACD is negative")
    if ind.rsi is not None:
        if ind.rsi >= RSI_LONG_CONFIRM and ind.rsi < RSI_LONG_MAX:
            up += 1
            reasons.append("RSI supports UP")
        elif ind.rsi <= RSI_SHORT_CONFIRM and ind.rsi > RSI_SHORT_MIN:
            down += 1
            reasons.append("RSI supports DOWN")
    if pa.bullish_engulfing or pa.bullish_rejection or pa.momentum_bullish:
        up += 4
        reasons.append(f"Fresh bullish {target.value} price action")
    if pa.bearish_engulfing or pa.bearish_rejection or pa.momentum_bearish:
        down += 4
        reasons.append(f"Fresh bearish {target.value} price action")

    if up == down or abs(up - down) < MIN_PREDICTION_EDGE:
        return "NO_SIGNAL", max(up, down), reasons + [f"Next {target.value} prediction edge is too small"]
    return ("CALL", up, reasons) if up > down else ("PUT", down, reasons)


def _no_signal(reason: str, next_direction: str | None = None, score: int = 0) -> SignalScore:
    return SignalScore("NO_SIGNAL", score, Decimal(0), (reason,), next_direction)


def score_mtf(analysis: MTFAnalysis, target_timeframe: Timeframe = Timeframe.M1) -> SignalScore:
    """Score a selected M1/M5/M15 entry as the NEXT candle prediction."""
    required = (Timeframe.M1, Timeframe.M5, Timeframe.M15)
    if any(timeframe not in analysis.analyses for timeframe in required):
        return _no_signal("Missing M1/M5/M15 analysis")

    target = target_timeframe
    predicted_direction, prediction_score, prediction_reasons = _next_candle_prediction(analysis, target)
    visible_prediction = None if predicted_direction == "NO_SIGNAL" else predicted_direction

    context = analysis.analyses[Timeframe.M15]
    if target == Timeframe.M1:
        confirmation = analysis.analyses[Timeframe.M5]
    elif target == Timeframe.M5:
        confirmation = analysis.analyses[Timeframe.M1]
    else:
        confirmation = analysis.analyses[Timeframe.M5]
    entry = analysis.analyses[target]

    if target != Timeframe.M15 and (context.trend not in {"bullish", "bearish"} or confirmation.trend not in {"bullish", "bearish"}):
        return _no_signal(f"MTF confirmation is incomplete for {target.value}", visible_prediction, prediction_score)
    if target != Timeframe.M15 and context.trend != confirmation.trend:
        return _no_signal(f"M15/{confirmation.timeframe.value} trend confirmation conflicts", visible_prediction, prediction_score)
    if context.score < MIN_M15_TREND_SCORE:
        return _no_signal("M15 context is not strong enough", visible_prediction, prediction_score)
    if target != Timeframe.M15:
        minimum_confirmation = MIN_M5_TREND_SCORE if confirmation.timeframe == Timeframe.M5 else MIN_M1_TREND_SCORE
        if confirmation.score < minimum_confirmation:
            return _no_signal(f"{confirmation.timeframe.value} confirmation is not strong enough", visible_prediction, prediction_score)

    if predicted_direction == "NO_SIGNAL":
        return _no_signal(" | ".join(prediction_reasons), None, 0)
    direction = predicted_direction

    points = prediction_score + context.score
    reasons: list[str] = [
        f"MTF context: {context.trend}",
        f"Target: next {target.value} candle direction",
        f"Next {target.value}: {'UP' if direction == 'CALL' else 'DOWN'}",
    ]
    if target != Timeframe.M15:
        points += confirmation.score
        reasons.append(f"{confirmation.timeframe.value} confirms")
    reasons.extend(prediction_reasons)

    minimum_entry_score = MIN_M1_TREND_SCORE if target == Timeframe.M1 else MIN_M5_TREND_SCORE
    if entry.trend == context.trend:
        if entry.score < minimum_entry_score:
            return _no_signal(f"{target.value} trend evidence is too weak", direction, prediction_score)
        points += 2
        reasons.append(f"{target.value} trend agrees with context")
    elif entry.trend == "neutral":
        points += 1
        reasons.append(f"{target.value} neutral; fresh trigger decides next candle")
    else:
        points += 1
        reasons.append(f"{target.value} counter-trend reversal trigger")

    indicators = entry.indicators
    action = entry.price_action

    if indicators.rsi is not None:
        if direction == "CALL" and indicators.rsi >= RSI_LONG_MAX:
            return _no_signal(f"RSI is too extended for UP on {target.value}", direction, prediction_score)
        if direction == "PUT" and indicators.rsi <= RSI_SHORT_MIN:
            return _no_signal(f"RSI is too extended for DOWN on {target.value}", direction, prediction_score)
        if (direction == "CALL" and indicators.rsi >= RSI_LONG_CONFIRM) or (direction == "PUT" and indicators.rsi <= RSI_SHORT_CONFIRM):
            points += 1
            reasons.append("RSI supports direction")

    if indicators.macd_histogram is not None:
        macd_agrees = (direction == "CALL" and indicators.macd_histogram > 0) or (direction == "PUT" and indicators.macd_histogram < 0)
        if macd_agrees:
            points += 1
            reasons.append("MACD confirms direction")
        else:
            reasons.append("MACD lags the fresh trigger")

    current = action.current
    previous = action.previous
    candle_agrees = (direction == "CALL" and current.bullish and current.body_ratio >= MIN_ENTRY_BODY_RATIO) or (direction == "PUT" and current.bearish and current.body_ratio >= MIN_ENTRY_BODY_RATIO)
    pattern_agrees = (direction == "CALL" and (action.bullish_engulfing or action.bullish_rejection)) or (direction == "PUT" and (action.bearish_engulfing or action.bearish_rejection))
    fresh_momentum = previous is not None and current.body_ratio >= MIN_TRIGGER_BODY_RATIO and ((direction == "CALL" and current.bullish and not previous.bullish) or (direction == "PUT" and current.bearish and previous.bullish))

    if not pattern_agrees and not fresh_momentum and not candle_agrees:
        return _no_signal(f"{target.value} has no fresh directional trigger", direction, prediction_score)

    points += 2 if pattern_agrees else 1
    reasons.append(f"Fresh {target.value} price-action trigger")

    if _reject_near_opposing_level(entry, direction):
        return _no_signal("Too close to opposing support/resistance", direction, prediction_score)

    points += 1
    reasons.append("Adequate room from opposing level")

    if points < MIN_ALIGNMENT_SCORE:
        return _no_signal("Signal score below live threshold", direction, points)

    confidence = min(Decimal(90), Decimal(75) + Decimal(max(0, points - MIN_ALIGNMENT_SCORE) * 2))
    return SignalScore(direction, points, confidence, tuple(reasons), direction)
