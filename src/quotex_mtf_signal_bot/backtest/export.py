from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from quotex_mtf_signal_bot.backtest.dashboard import build_metrics
from quotex_mtf_signal_bot.backtest.engine import BacktestReport


def write_dashboard_json(report: BacktestReport, path: str | Path) -> Path:
    """Export backtest metrics and trades for the local dashboard."""
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    metrics = build_metrics(report)
    payload = {
        "metrics": {
            "total": metrics.total_signals,
            "wins": metrics.wins,
            "losses": metrics.losses,
            "ties": metrics.ties,
            "winRate": str(metrics.win_rate),
            "lossRate": str(metrics.loss_rate),
            "winStreak": metrics.max_win_streak,
            "lossStreak": metrics.max_loss_streak,
        },
        "trades": [
            {
                "time": trade.signal.entry_time_utc.isoformat(),
                "pair": trade.signal.symbol,
                "direction": trade.signal.direction,
                "expiry": trade.signal.expiry,
                "confidence": str(trade.signal.confidence),
                "outcome": trade.outcome,
            }
            for trade in report.trades
        ],
    }
    destination.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return destination
