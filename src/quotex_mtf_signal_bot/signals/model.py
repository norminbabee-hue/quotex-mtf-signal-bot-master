from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from quotex_mtf_signal_bot.analysis.mtf import MTFAnalysis
from quotex_mtf_signal_bot.signals.expiry import ExpiryDecision, choose_expiry
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


def build_signal(symbol: str, entry_time_utc: datetime, analysis: MTFAnalysis) -> Signal | None:
    score: SignalScore = score_mtf(analysis)
    if score.direction == "NO_SIGNAL":
        return None
    expiry: ExpiryDecision = choose_expiry(analysis)
    return Signal(
        symbol=symbol,
        direction=score.direction,
        expiry=expiry.expiry.value,
        confidence=score.confidence,
        entry_time_utc=entry_time_utc,
        score=score.score,
        reasons=score.reasons + (expiry.rationale,),
    )
