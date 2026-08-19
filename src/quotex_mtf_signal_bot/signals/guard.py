from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from quotex_mtf_signal_bot.signals.model import Signal


@dataclass(frozen=True, slots=True)
class GuardConfig:
    min_confidence: Decimal = Decimal("70")
    max_spread_points: Decimal = Decimal("30")


@dataclass(frozen=True, slots=True)
class GuardResult:
    allowed: bool
    reason: str


class SignalGuard:
    """Final safety/quality gate before a signal is published."""

    def __init__(self, config: GuardConfig | None = None) -> None:
        self.config = config or GuardConfig()

    def check(self, signal: Signal, *, spread_points: Decimal) -> GuardResult:
        if signal.direction not in {"CALL", "PUT"}:
            return GuardResult(False, "invalid_direction")
        if signal.confidence < self.config.min_confidence:
            return GuardResult(False, "confidence_below_threshold")
        if spread_points > self.config.max_spread_points:
            return GuardResult(False, "spread_too_wide")
        if signal.expiry not in {"1m", "2m", "3m", "5m", "10m", "15m"}:
            return GuardResult(False, "unsupported_expiry")
        return GuardResult(True, "approved")
