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


def build_signal(symbol: str, entry_time_utc: datetime, analysis: MTFAnalysis) -> Signal | None:
    score: SignalScore = score_mtf(analysis)
    if score.direction == "NO_SIGNAL":
        return None

    # The live Quotex-style research signal is specifically a next-M1-candle
    # prediction. Keep the legacy direction field compatible, but make the
    # horizon explicit instead of silently using a 5m/15m research expiry.
    return Signal(
        symbol=symbol,
        direction=score.direction,
        expiry="1m",
        confidence=score.confidence,
        entry_time_utc=entry_time_utc,
        score=score.score,
        reasons=score.reasons + ("Target: next M1 candle direction",),
        next_candle_direction=score.next_candle_direction,
    )
