from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from quotex_mtf_signal_bot.analysis.mtf import MTFAnalysis


class Expiry(Enum):
    M1 = "1m"
    M3 = "3m"
    M5 = "5m"
    M15 = "15m"


@dataclass(frozen=True, slots=True)
class ExpiryDecision:
    expiry: Expiry
    rationale: str


def choose_expiry(analysis: MTFAnalysis) -> ExpiryDecision:
    """Choose a research candidate expiry from alignment strength.

    This is a model suggestion only; it is not an execution instruction.
    """
    if analysis.alignment in {"conflict", "weak"}:
        return ExpiryDecision(Expiry.M1, "No strong MTF alignment; shortest research horizon")

    strength = max(analysis.bullish_score, analysis.bearish_score)
    if strength >= 10:
        return ExpiryDecision(Expiry.M15, "Strong multi-timeframe alignment")
    if strength >= 7:
        return ExpiryDecision(Expiry.M5, "Moderate-to-strong multi-timeframe alignment")
    return ExpiryDecision(Expiry.M3, "Moderate alignment")
