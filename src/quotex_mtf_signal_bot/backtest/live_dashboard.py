from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

from quotex_mtf_signal_bot.analysis.mtf import analyze_mtf
from quotex_mtf_signal_bot.core.models import Candle, Timeframe
from quotex_mtf_signal_bot.data.candle_timing import format_server_time, next_candle_window, timeframe_seconds
from quotex_mtf_signal_bot.data.mt5_adapter import MT5Adapter, MT5Bar
from quotex_mtf_signal_bot.data.symbol_registry import SymbolRegistry
from quotex_mtf_signal_bot.signals.scoring import score_mtf

TIMEFRAMES = {"M1": Timeframe.M1, "M5": Timeframe.M5, "M15": Timeframe.M15}
QUOTEX_SERVER_OFFSET_HOURS = float(os.getenv("QUOTEX_SERVER_UTC_OFFSET_HOURS", "6"))


def _to_candles(bars: list[MT5Bar], canonical_symbol: str) -> list[Candle]:
    return [
        Candle(
            symbol=canonical_symbol,
            timeframe=TIMEFRAMES[bar.timeframe],
            timestamp_utc=bar.timestamp_utc,
            open=bar.open,
            high=bar.high,
            low=bar.low,
            close=bar.close,
        )
        for bar in bars
    ]


def _next_m1_timing(now_utc: datetime | None = None) -> dict[str, Any]:
    now = (now_utc or datetime.now(timezone.utc)).astimezone(timezone.utc)
    window = next_candle_window(now, timeframe_seconds("M1"))
    return {
        "server_now": format_server_time(now, QUOTEX_SERVER_OFFSET_HOURS),
        "open": format_server_time(window.open_time_utc, QUOTEX_SERVER_OFFSET_HOURS),
        "close": format_server_time(window.close_time_utc, QUOTEX_SERVER_OFFSET_HOURS),
        "seconds_to_open": window.seconds_to_open,
    }


def scan_live_pairs(adapter: MT5Adapter, history_count: int = 120) -> list[dict[str, Any]]:
    """Analyze every available FX pair; broker suffixes never define pair identity."""
    registry = SymbolRegistry.from_mt5(adapter)
    rows: list[dict[str, Any]] = []

    for pair in registry.symbols:
        broker_symbol = registry.broker_symbol(pair)
        try:
            raw: dict[Timeframe, list[MT5Bar]] = {}
            for label, timeframe in TIMEFRAMES.items():
                bars = adapter.bars(broker_symbol, label, history_count)
                if len(bars) < 61:
                    raise RuntimeError(f"only {len(bars)} {label} bars available for {broker_symbol}")
                raw[timeframe] = bars[:-1]
            candles = {tf: _to_candles(bars, pair) for tf, bars in raw.items()}
            analysis = analyze_mtf(candles)
            score = score_mtf(analysis)
            latest = candles[Timeframe.M1][-1]
            if score.next_candle_direction == "CALL":
                next_candle = "UP ↑"
            elif score.next_candle_direction == "PUT":
                next_candle = "DOWN ↓"
            else:
                next_candle = "NO SIGNAL"
            rows.append({
                "pair": pair,
                "signal": score.direction,
                "next_candle": next_candle,
                "score": score.score,
                "confidence": f"{score.confidence:.0f}%" if score.confidence else "—",
                "expiry": "1m" if score.next_candle_direction else "—",
                "closed_at": latest.timestamp_utc.astimezone(timezone.utc).isoformat(),
                "reason": " | ".join(score.reasons),
            })
        except Exception as exc:
            rows.append({
                "pair": pair,
                "signal": "ERROR",
                "next_candle": "ERROR",
                "score": 0,
                "confidence": "—",
                "expiry": "—",
                "closed_at": "—",
                "reason": str(exc),
            })

    def sort_key(row: dict[str, Any]) -> tuple[int, int, str]:
        signal, next_candle = row["signal"], row["next_candle"]
        if signal == "CALL": bucket = 0
        elif signal == "PUT": bucket = 1
        elif next_candle == "UP ↑": bucket = 2
        elif next_candle == "DOWN ↓": bucket = 3
        elif signal == "ERROR": bucket = 5
        else: bucket = 4
        return bucket, -int(row["score"]), row["pair"]

    rows.sort(key=sort_key)
    return rows


def run_live_dashboard() -> None:
    import streamlit as st

    st.set_page_config(page_title="Quotex MTF — Live Scanner", page_icon="📡", layout="wide")
    st.title("📡 Live MTF Currency Scanner")
    st.caption(
        "Live FX research analysis from the connected MT5 feed. Broker suffixes such as -OTC are ignored. "
        "The scanner predicts the next closed M1 candle using M1 + M5 + M15 context."
    )

    refresh = st.button("🔄 Refresh all FX pairs", type="primary", use_container_width=True)
    timing = _next_m1_timing()
    timing_cols = st.columns(4)
    timing_cols[0].metric("Quotex server time", timing["server_now"])
    timing_cols[1].metric("NEXT M1 opens", timing["open"])
    timing_cols[2].metric("NEXT M1 closes", timing["close"])
    timing_cols[3].metric("Entry countdown", f"{timing['seconds_to_open']}s")
    st.caption(f"Server display offset: UTC{QUOTEX_SERVER_OFFSET_HOURS:+g}.")

    if "live_rows" not in st.session_state or refresh:
        try:
            adapter = MT5Adapter()
            try:
                with st.spinner("Analyzing every available FX currency pair…"):
                    st.session_state.live_rows = scan_live_pairs(adapter)
            finally:
                adapter.close()
            st.session_state.live_error = None
        except Exception as exc:
            st.session_state.live_error = str(exc)

    if st.session_state.get("live_error"):
        st.error(st.session_state.live_error)
        st.info("Make sure the MT5 terminal is running and the required FX symbols are visible in Market Watch.")
        return

    rows = st.session_state.get("live_rows", [])
    if not rows:
        st.info("No FX currency pairs were discovered from the connected MT5 terminal yet.")
        return

    calls = sum(row["next_candle"] == "UP ↑" for row in rows)
    puts = sum(row["next_candle"] == "DOWN ↓" for row in rows)
    actionable_calls = sum(row["signal"] == "CALL" for row in rows)
    actionable_puts = sum(row["signal"] == "PUT" for row in rows)
    errors = sum(row["signal"] == "ERROR" for row in rows)
    metrics = st.columns(6)
    metrics[0].metric("FX pairs scanned", len(rows))
    metrics[1].metric("NEXT UP", calls)
    metrics[2].metric("NEXT DOWN", puts)
    metrics[3].metric("Actionable UP", actionable_calls)
    metrics[4].metric("Actionable DOWN", actionable_puts)
    metrics[5].metric("Errors", errors)

    st.divider()
    st.subheader("Next candle prediction")
    st.caption(
        f"Target candle: M1 opening at {timing['open']} and closing at {timing['close']} server time. "
        "UP ↑ = CALL, DOWN ↓ = PUT."
    )
    st.dataframe(
        rows,
        use_container_width=True,
        hide_index=True,
        column_config={
            "pair": "Pair",
            "signal": "Action status",
            "next_candle": "NEXT M1",
            "score": st.column_config.NumberColumn("Score", format="%d"),
            "confidence": "Confidence",
            "expiry": "Horizon",
            "closed_at": "Latest closed M1",
            "reason": "Why",
        },
    )
    st.caption(
        "MT5 is the analysis feed. Broker-specific suffixes do not change the underlying FX pair identity. "
        "Candle timing uses UTC boundaries and converts them to the configured Quotex server display time."
    )


if __name__ == "__main__":
    run_live_dashboard()
