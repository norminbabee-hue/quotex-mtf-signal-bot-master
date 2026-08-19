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


def score_mtf(analysis: MTFAnalysis) -> SignalScore:
    """Combine already-computed evidence without placing or executing trades.

    The score is an internal model score, not a statistical win probability.
    """
    if analysis.alignment in {"conflict", "weak"}:
        return SignalScore("NO_SIGNAL", 0, Decimal(0), ("MTF alignment is insufficient",))

    points = analysis.bullish_score if analysis.alignment == "bullish" else analysis.bearish_score
    direction = "CALL" if analysis.alignment == "bullish" else "PUT"
    reasons: list[str] = [f"MTF alignment: {analysis.alignment}"]

    entry = analysis.analyses.get(Timeframe.M1)
    confirmation = analysis.analyses.get(Timeframe.M5)
    context = analysis.analyses.get(Timeframe.M15)

    if entry is not None and entry.trend == analysis.alignment:
        points += 2
        reasons.append("M1 agrees with direction")
    if confirmation is not None and confirmation.trend == analysis.alignment:
        points += 2
        reasons.append("M5 confirms direction")
    if context is not None and context.trend == analysis.alignment:
        points += 2
        reasons.append("M15 confirms direction")

    # Keep confidence bounded and explicitly label it as a model score.
    confidence = min(Decimal(95), Decimal(50) + Decimal(points * 5))
    return SignalScore(direction, points, confidence, tuple(reasons))
