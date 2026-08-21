from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

from quotex_mtf_signal_bot.backtest.engine import BacktestReport
from quotex_mtf_signal_bot.core.models import Timeframe


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


def _project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _load_dashboard_data(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"metrics": {}, "trades": []}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"metrics": {}, "trades": []}
    if not isinstance(payload, dict):
        return {"metrics": {}, "trades": []}
    return payload


def run_dashboard() -> None:
    """Run the local Streamlit research dashboard."""
    import streamlit as st

    st.set_page_config(
        page_title="Quotex MTF Signal Bot — Research",
        page_icon="📊",
        layout="wide",
    )

    st.title("📊 MTF Signal Research")
    st.caption("Live analysis uses the connected MT5 feed. Backtest is optional research validation; it does not execute trades.")

    data_path = _project_root() / "data" / "backtest.json"
    default_pairs = [
        "EURUSD", "GBPUSD", "USDJPY", "USDCHF", "AUDUSD", "USDCAD", "NZDUSD",
        "EURGBP", "EURJPY", "EURCHF", "EURAUD", "EURCAD", "EURNZD",
        "GBPJPY", "GBPCHF", "GBPAUD", "GBPCAD", "GBPNZD",
        "AUDJPY", "AUDCHF", "AUDCAD", "AUDNZD", "CADJPY", "CADCHF",
        "CHFJPY", "NZDJPY", "NZDCHF", "NZDCAD",
    ]

    controls = st.columns([1, 1, 1, 1])
    with controls[0]:
        symbol = st.selectbox("Pair", default_pairs, index=2)
    with controls[1]:
        timeframe_label = st.selectbox("Timeframe", ["M1", "M5", "M15"], index=0)
        evaluation_timeframe = Timeframe(timeframe_label)
    with controls[2]:
        run_backtest_clicked = st.button("Optional MT5 backtest", use_container_width=True)
    with controls[3]:
        st.metric("Signal mode", "Closed M1 + M5 + M15")

    if run_backtest_clicked:
        with st.spinner(f"Running research backtest for {symbol} {timeframe_label}..."):
            try:
                from quotex_mtf_signal_bot.backtest.mt5_backtest import run_mt5_backtest
                output = run_mt5_backtest(
                    symbol,
                    evaluation_timeframe=evaluation_timeframe,
                    output_path=data_path,
                )
                st.success(f"Backtest complete. Results saved to {output}")
                st.rerun()
            except Exception as exc:
                st.error(f"Backtest could not run: {exc}")
                st.info("The live signal engine does not depend on this button. Ensure the MT5 terminal/feed is available if you want historical validation.")

    data = _load_dashboard_data(data_path)
    metrics = data.get("metrics") or {}
    trades = data.get("trades") or []

    st.divider()

    def metric_value(name: str, default: Any = 0) -> Any:
        return metrics.get(name, default)

    row1 = st.columns(4)
    row1[0].metric("Total signals", metric_value("total"))
    row1[1].metric("Wins", metric_value("wins"))
    row1[2].metric("Losses", metric_value("losses"))
    row1[3].metric("Ties", metric_value("ties"))

    row2 = st.columns(4)
    row2[0].metric("Win rate", f"{float(metric_value('winRate', 0)):.2f}%")
    row2[1].metric("Loss rate", f"{float(metric_value('lossRate', 0)):.2f}%")
    row2[2].metric("Max win streak", metric_value("winStreak"))
    row2[3].metric("Max loss streak", metric_value("lossStreak"))

    st.subheader("Recent research results")
    if trades:
        recent = list(reversed(trades[-50:]))
        st.dataframe(recent, use_container_width=True, hide_index=True)
    else:
        st.info("No historical research data loaded. Live signal analysis does not require running a backtest first.")


if __name__ == "__main__":
    run_dashboard()
