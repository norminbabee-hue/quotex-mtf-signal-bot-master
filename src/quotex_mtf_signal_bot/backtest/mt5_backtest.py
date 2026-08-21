from __future__ import annotations

from pathlib import Path
from typing import Any

from quotex_mtf_signal_bot.backtest.engine import run_backtest
from quotex_mtf_signal_bot.backtest.export import write_dashboard_json
from quotex_mtf_signal_bot.backtest.replay import generate_signals
from quotex_mtf_signal_bot.core.models import Timeframe
from quotex_mtf_signal_bot.data.mt5 import MT5DataSource


def run_mt5_backtest(
    symbol: str,
    *,
    bars: int = 1000,
    output_path: str | Path = "data/backtest.json",
    evaluation_timeframe: Timeframe = Timeframe.M1,
    mt5_module: Any | None = None,
) -> Path:
    """Run a closed-candle M1/M5/M15 backtest directly from the local MT5 terminal."""
    if bars < 100:
        raise ValueError("At least 100 bars are required for a meaningful MTF backtest")

    if mt5_module is None:
        import MetaTrader5 as mt5_module

    source = MT5DataSource(mt5_module)
    if not source.connect():
        error = getattr(mt5_module, "last_error", lambda: "unknown MT5 error")()
        raise RuntimeError(f"MT5 initialization failed: {error}")

    try:
        candles = {}
        for timeframe in (Timeframe.M1, Timeframe.M5, Timeframe.M15):
            values = source.candles(symbol, timeframe, count=bars)
            # copy_rates_from_pos(..., 0, ...) includes the currently forming bar.
            # Never let that bar enter historical signal generation or expiry evaluation.
            candles[timeframe] = values[:-1] if len(values) > 1 else []

        signals = generate_signals(candles, symbol=symbol)
        report = run_backtest(signals, candles[evaluation_timeframe])
        return write_dashboard_json(report, output_path)
    finally:
        source.shutdown()
