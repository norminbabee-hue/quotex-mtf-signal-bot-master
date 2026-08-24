from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
import inspect

from quotex_mtf_signal_bot.analysis.mtf import MTFAnalysis
from quotex_mtf_signal_bot.core.models import Timeframe
from quotex_mtf_signal_bot.signals.scoring import SignalScore, score_mtf


@dataclass(frozen=True, slots=True)
class Signal:
    symbol: str
    direction: str
    expiry: str
    confidence: Decimal
    entry_time_utc: datetime
    score: int = 0
    reasons: tuple[str, ...] = ()
    # Explicit prediction target: the direction of the NEXT closed candle.
    next_candle_direction: str | None = None
    # Forecast strength is separate from the stricter actionable confidence.
    # It is a directional score, not a calibrated probability of winning.
    prediction_confidence: Decimal = Decimal("0")
    # The timeframe whose next candle is being predicted.
    target_timeframe: str = "M1"


def build_signal(
    symbol: str,
    entry_time_utc: datetime,
    analysis: MTFAnalysis,
    target_timeframe: Timeframe = Timeframe.M1,
) -> Signal | None:
    # Some existing unit tests monkeypatch score_mtf with the old one-argument
    # signature. Keep those stubs working while using the target timeframe in
    # the real scorer.
    if "target_timeframe" in inspect.signature(score_mtf).parameters:
        score: SignalScore = score_mtf(analysis, target_timeframe=target_timeframe)
    else:
        score = score_mtf(analysis)

    # A next-candle prediction is useful even when the stricter actionable
    # signal gate rejects the setup. Preserve that forecast in the Signal.
    direction = score.direction
    if direction == "NO_SIGNAL":
        direction = score.next_candle_direction or "NO_SIGNAL"
        if direction == "NO_SIGNAL":
            return None

    return Signal(
        symbol=symbol,
        direction=direction,
        expiry=f"{target_timeframe.minutes}m",
        confidence=score.confidence,
        entry_time_utc=entry_time_utc,
        score=score.score,
        reasons=score.reasons + (f"Target: next {target_timeframe.value} candle direction",),
        next_candle_direction=score.next_candle_direction or direction,
        prediction_confidence=score.prediction_confidence,
        target_timeframe=target_timeframe.value,
    )
