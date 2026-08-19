from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from quotex_mtf_signal_bot.core.models import Candle, Timeframe
from quotex_mtf_signal_bot.signals.model import Signal


@dataclass(frozen=True, slots=True)
class BacktestTrade:
    signal: Signal
    outcome: str
    exit_time_utc: object
    entry_price: Decimal
    exit_price: Decimal


@dataclass(frozen=True, slots=True)
class BacktestReport:
    trades: tuple[BacktestTrade, ...]
    wins: int
    losses: int
    ties: int

    @property
    def total(self) -> int:
        return len(self.trades)

    @property
    def win_rate(self) -> Decimal:
        decisive = self.wins + self.losses
        if decisive == 0:
            return Decimal(0)
        return Decimal(self.wins * 100) / Decimal(decisive)


def _expiry_minutes(expiry: str) -> int:
    if not expiry.endswith("m"):
        raise ValueError(f"Unsupported expiry: {expiry}")
    minutes = int(expiry[:-1])
    if minutes <= 0:
        raise ValueError("Expiry must be positive")
    return minutes


def _find_exit(candles: list[Candle], entry_time, expiry: str) -> Candle | None:
    target = entry_time.timestamp() + (_expiry_minutes(expiry) * 60)
    candidates = [c for c in candles if c.timestamp_utc.timestamp() >= target]
    return candidates[0] if candidates else None


def evaluate_signal(signal: Signal, candles: list[Candle]) -> BacktestTrade | None:
    """Evaluate a signal only against candles after its entry time."""
    entry_candidates = [c for c in candles if c.timestamp_utc >= signal.entry_time_utc]
    if not entry_candidates:
        return None
    entry = entry_candidates[0]
    exit_candle = _find_exit(candles, signal.entry_time_utc, signal.expiry)
    if exit_candle is None:
        return None

    if signal.direction == "CALL":
        if exit_candle.close > entry.close:
            outcome = "WIN"
        elif exit_candle.close < entry.close:
            outcome = "LOSS"
        else:
            outcome = "TIE"
    elif signal.direction == "PUT":
        if exit_candle.close < entry.close:
            outcome = "WIN"
        elif exit_candle.close > entry.close:
            outcome = "LOSS"
        else:
            outcome = "TIE"
    else:
        raise ValueError(f"Cannot evaluate direction: {signal.direction}")

    return BacktestTrade(signal, outcome, exit_candle.timestamp_utc, entry.close, exit_candle.close)


def run_backtest(signals: list[Signal], candles: list[Candle]) -> BacktestReport:
    trades: list[BacktestTrade] = []
    for signal in signals:
        trade = evaluate_signal(signal, candles)
        if trade is not None:
            trades.append(trade)

    return BacktestReport(
        trades=tuple(trades),
        wins=sum(t.outcome == "WIN" for t in trades),
        losses=sum(t.outcome == "LOSS" for t in trades),
        ties=sum(t.outcome == "TIE" for t in trades),
    )
