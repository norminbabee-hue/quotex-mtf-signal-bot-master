from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from quotex_mtf_signal_bot.analysis.indicators import IndicatorSnapshot, snapshot as indicator_snapshot
from quotex_mtf_signal_bot.analysis.price_action import PriceActionSnapshot, snapshot as price_action_snapshot
from quotex_mtf_signal_bot.analysis.support_resistance import SupportResistanceSnapshot, find_levels
from quotex_mtf_signal_bot.core.models import Candle, Timeframe


@dataclass(frozen=True, slots=True)
class TimeframeAnalysis:
    timeframe: Timeframe
    trend: str
    score: int
    indicators: IndicatorSnapshot
    price_action: PriceActionSnapshot
    levels: SupportResistanceSnapshot


@dataclass(frozen=True, slots=True)
class MTFAnalysis:
    analyses: dict[Timeframe, TimeframeAnalysis]
    bullish_score: int
    bearish_score: int
    alignment: str


def _trend(indicators: IndicatorSnapshot, price_action: PriceActionSnapshot) -> tuple[str, int]:
    bullish = 0
    bearish = 0

    if indicators.ema_fast is not None and indicators.ema_slow is not None:
        if indicators.ema_fast > indicators.ema_slow:
            bullish += 2
        elif indicators.ema_fast < indicators.ema_slow:
            bearish += 2

    if indicators.macd_histogram is not None:
        if indicators.macd_histogram > 0:
            bullish += 1
        elif indicators.macd_histogram < 0:
            bearish += 1

    if indicators.rsi is not None:
        if indicators.rsi >= Decimal("55"):
            bullish += 1
        elif indicators.rsi <= Decimal("45"):
            bearish += 1

    if price_action.momentum_bullish or price_action.bullish_engulfing:
        bullish += 1
    if price_action.momentum_bearish or price_action.bearish_engulfing:
        bearish += 1

    if bullish > bearish:
        return "bullish", bullish
    if bearish > bullish:
        return "bearish", bearish
    return "neutral", 0


def analyze_timeframe(candles: list[Candle], timeframe: Timeframe) -> TimeframeAnalysis:
    if not candles:
        raise ValueError(f"No candles supplied for {timeframe}")
    indicators = indicator_snapshot(candles)
    action = price_action_snapshot(candles)
    levels = find_levels(candles)
    trend, score = _trend(indicators, action)
    return TimeframeAnalysis(timeframe, trend, score, indicators, action, levels)


def analyze_mtf(candles_by_timeframe: dict[Timeframe, list[Candle]]) -> MTFAnalysis:
    analyses = {
        timeframe: analyze_timeframe(candles, timeframe)
        for timeframe, candles in candles_by_timeframe.items()
    }
    bullish = sum(item.score for item in analyses.values() if item.trend == "bullish")
    bearish = sum(item.score for item in analyses.values() if item.trend == "bearish")

    if bullish > bearish and bullish >= 5:
        alignment = "bullish"
    elif bearish > bullish and bearish >= 5:
        alignment = "bearish"
    elif bullish == bearish:
        alignment = "conflict"
    else:
        alignment = "weak"

    return MTFAnalysis(analyses, bullish, bearish, alignment)
