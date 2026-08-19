from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from quotex_mtf_signal_bot.backtest.engine import BacktestReport


@dataclass(frozen=True, slots=True)
class DashboardMetrics:
    total_signals: int
    wins: int
    losses: int
    ties: int
    win_rate: Decimal
    loss_rate: Decimal
    max_win_streak: int
    max_loss_streak: int


def build_metrics(report: BacktestReport) -> DashboardMetrics:
    outcomes = [trade.outcome for trade in report.trades]
    max_win = max_loss = current_win = current_loss = 0
    for outcome in outcomes:
        if outcome == "WIN":
            current_win += 1
            current_loss = 0
            max_win = max(max_win, current_win)
        elif outcome == "LOSS":
            current_loss += 1
            current_win = 0
            max_loss = max(max_loss, current_loss)
        else:
            current_win = current_loss = 0

    decisive = report.wins + report.losses
    win_rate = Decimal(report.wins * 100) / Decimal(decisive) if decisive else Decimal(0)
    loss_rate = Decimal(report.losses * 100) / Decimal(decisive) if decisive else Decimal(0)
    return DashboardMetrics(
        total_signals=report.total,
        wins=report.wins,
        losses=report.losses,
        ties=report.ties,
        win_rate=win_rate,
        loss_rate=loss_rate,
        max_win_streak=max_win,
        max_loss_streak=max_loss,
    )
