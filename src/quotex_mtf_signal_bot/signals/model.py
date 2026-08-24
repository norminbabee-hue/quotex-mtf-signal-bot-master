from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from quotex_mtf_signal_bot.analysis.mtf import MTFAnalysis
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
    # Explicit prediction target: the direction of the NEXT closed M1 candle.
    # CALL = UP, PUT = DOWN. Kept optional for backward-compatible test stubs.
    next_candle_direction: str | None = None
    # Forecast strength is separate from the stricter actionable confidence.
    # It is a directional score, not a calibrated probability of winning.
    prediction_confidence: Decimal = Decimal("0")


def build_signal(symbol: str, entry_time_utc: datetime, analysis: MTFAnalysis) -> Signal | None:
    score: SignalScore = score_mtf(analysis)

    # A next-candle prediction is useful even when the stricter actionable
    # signal gates reject the setup. The live UI/Telegram layer can therefore
    # distinguish "prediction" from "actionable signal" without losing the
    # requested UP/DOWN forecast.
    direction = score.direction
    if direction == "NO_SIGNAL":
        direction = score.next_candle_direction or "NO_SIGNAL"
        if direction == "NO_SIGNAL":
            return None

    return Signal(
        symbol=symbol,
        direction=direction,
        expiry="1m",
        confidence=score.confidence,
        entry_time_utc=entry_time_utc,
        score=score.score,
        reasons=score.reasons + ("Target: next M1 candle direction",),
        next_candle_direction=score.next_candle_direction or direction,
        prediction_confidence=score.prediction_confidence,
    )
